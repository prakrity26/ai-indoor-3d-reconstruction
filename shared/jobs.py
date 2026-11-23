"""One reconstruction project per uploaded video. The API writes jobs; a worker runs them."""

from __future__ import annotations

import inspect
import os
import re
import secrets
import shutil
import time
from pathlib import Path
from typing import Any, BinaryIO, Callable

from database.repositories.jobs import JobRepository
from database.session import sqlite_url

STATUSES = ("queued", "running", "succeeded", "failed")
VISIBILITIES = ("private", "public")
_CHUNK = 1024 * 1024


class UploadTooLarge(ValueError):
    """The streamed upload went past the configured limit."""


def job_id_from_filename(filename: str) -> str:
    stem = Path(filename or "upload").stem
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_").lower()
    return cleaned or "upload"


def _clean_line(value: str | None, limit: int = 120) -> str:
    """Single-line text such as a project name: collapse whitespace."""
    return " ".join((value or "").split())[:limit]


def _clean_block(value: str | None, limit: int = 2000) -> str:
    """Multi-line text such as a description: keep line breaks, trim the ends."""
    return (value or "").strip()[:limit]


class JobStore:
    """Uploads on disk, project metadata in the database. The API and the worker share both."""

    def __init__(self, root: Path, database_url: str | None = None) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.repo = JobRepository(database_url or sqlite_url(self.root))

    # ---- create -------------------------------------------------------------------------
    def create(
        self,
        filename: str,
        payload: bytes | BinaryIO,
        *,
        name: str = "",
        description: str = "",
        max_bytes: int | None = None,
    ) -> dict[str, Any]:
        """Save the video (streamed in chunks when given a file object) and queue it."""
        job_id = self._unique_id(job_id_from_filename(name or filename))
        folder = self.root / job_id
        folder.mkdir(parents=True, exist_ok=False)
        suffix = Path(filename).suffix.lower() or ".mp4"
        source = folder / f"source{suffix}"
        try:
            written = _write(source, payload, max_bytes)
            if written == 0:
                raise ValueError("empty_file")
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return self.repo.insert(
            {
                "job_id": job_id,
                "status": "queued",
                "filename": Path(filename).name or f"{job_id}{suffix}",
                "source_path": str(source.resolve()),
                "name": _clean_line(name) or Path(filename).stem or job_id,
                "description": _clean_block(description),
                "stage": "queued",
            }
        )

    def register_sample(self, job_id: str, filename: str, *, name: str = "", mesh_path: str = "") -> dict[str, Any]:
        """Checked-in samples become read-only projects so they can be annotated and shared."""
        existing = self.repo.get(job_id)
        if existing is not None:
            return existing
        return self.repo.insert(
            {
                "job_id": job_id,
                "status": "succeeded",
                "filename": filename,
                "source_path": "",
                "name": name or filename,
                "mesh_path": mesh_path,
                "origin": "sample",
                "stage": "done",
                "progress": 100,
                "created_at": "2026-09-28T00:00:00+00:00",
            }
        )

    # ---- read ---------------------------------------------------------------------------
    def list_jobs(self) -> list[dict[str, Any]]:
        return self.repo.list_jobs()

    def get(self, job_id: str) -> dict[str, Any] | None:
        return self.repo.get(job_id)

    def get_shared(self, token: str) -> dict[str, Any] | None:
        record = self.repo.get_by_share_token(token)
        if record is None or record["visibility"] != "public":
            return None
        return record

    # ---- edit ---------------------------------------------------------------------------
    def update(self, job_id: str, *, name: str | None = None, description: str | None = None) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        if name is not None:
            cleaned = _clean_line(name)
            if not cleaned:
                raise ValueError("name_required")
            fields["name"] = cleaned
        if description is not None:
            fields["description"] = _clean_block(description)
        return self.repo.update_fields(job_id, **fields) if fields else self._require(job_id)

    def set_visibility(self, job_id: str, visibility: str) -> dict[str, Any]:
        if visibility not in VISIBILITIES:
            raise ValueError("visibility must be private or public")
        record = self._require(job_id)
        token = record["share_token"]
        if visibility == "public" and not token:
            token = secrets.token_urlsafe(9)
        return self.repo.update_fields(job_id, visibility=visibility, share_token=token)

    def rotate_share_token(self, job_id: str) -> dict[str, Any]:
        self._require(job_id)
        return self.repo.update_fields(job_id, share_token=secrets.token_urlsafe(9))

    def retry(self, job_id: str) -> dict[str, Any]:
        record = self._require(job_id)
        if record["status"] != "failed":
            raise ValueError("Only failed jobs can be retried.")
        return self.repo.save_status(job_id, "queued", error="", stage="queued", progress=0)

    def delete(self, job_id: str, extra_dirs: list[Path] | None = None) -> None:
        """Remove the row and every folder this job wrote. Samples are never deleted."""
        record = self._require(job_id)
        if record["origin"] == "sample":
            raise PermissionError("Sample scenes cannot be deleted.")
        if record["status"] == "running":
            raise ValueError("Wait for the job to finish before deleting it.")
        for folder in [self.root / job_id, *(Path(d) / job_id for d in (extra_dirs or []))]:
            if folder.is_dir() and folder.name == job_id:
                shutil.rmtree(folder, ignore_errors=True)
        self.repo.delete(job_id)

    # ---- worker -------------------------------------------------------------------------
    def claim_next(self) -> dict[str, Any] | None:
        return self.repo.claim_next()

    def report(self, job_id: str, stage: str, progress: int) -> None:
        self.repo.save_progress(job_id, stage, progress)

    def complete(self, job_id: str, ply_path: str, mesh_path: str = "") -> dict[str, Any]:
        stored = str(Path(ply_path).resolve()) if ply_path else ""
        mesh = str(Path(mesh_path).resolve()) if mesh_path else ""
        return self.repo.save_status(
            job_id, "succeeded", ply_path=stored, mesh_path=mesh, error="", stage="done", progress=100
        )

    def fail(self, job_id: str, message: str) -> dict[str, Any]:
        return self.repo.save_status(job_id, "failed", error=message)

    def _require(self, job_id: str) -> dict[str, Any]:
        record = self.repo.get(job_id)
        if record is None:
            raise KeyError(job_id)
        return record

    def _unique_id(self, base: str) -> str:
        candidate = base
        number = 2
        while (self.root / candidate).exists() or self.repo.get(candidate) is not None:
            candidate = f"{base}_{number}"
            number += 1
        return candidate


def _write(target: Path, payload: bytes | BinaryIO, max_bytes: int | None) -> int:
    if isinstance(payload, (bytes, bytearray)):
        if max_bytes is not None and len(payload) > max_bytes:
            raise UploadTooLarge("upload_too_large")
        target.write_bytes(payload)
        return len(payload)
    written = 0
    with target.open("wb") as out:
        while True:
            chunk = payload.read(_CHUNK)
            if not chunk:
                break
            written += len(chunk)
            if max_bytes is not None and written > max_bytes:
                raise UploadTooLarge("upload_too_large")
            out.write(chunk)
    return written


def _accepts_report(train: Callable) -> bool:
    try:
        params = inspect.signature(train).parameters
    except (TypeError, ValueError):
        return False
    return "report" in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def process_next(store: JobStore, train: Callable) -> bool:
    """Run the oldest queued upload. Returns False when the queue is empty."""
    job = store.claim_next()
    if job is None:
        return False
    job_id = job["job_id"]
    try:
        kwargs: dict[str, Any] = {"job_id": job_id}
        if _accepts_report(train):

            def report(stage: str, progress: int) -> None:
                try:
                    store.report(job_id, stage, progress)
                except Exception:  # progress is best effort; never fail a job over it
                    pass

            kwargs["report"] = report
        result = train(job["source_path"], **kwargs)
        ply = getattr(result, "ply_path", "") or ""
        mesh = getattr(result, "mesh_path", "") or ""
        ply_ok = bool(ply) and Path(ply).is_file()
        mesh_ok = bool(mesh) and Path(mesh).is_file()
        if not ply_ok and not mesh_ok:
            raise RuntimeError("The worker finished without a splat or a mesh.")
        store.complete(job_id, ply if ply_ok else "", mesh if mesh_ok else "")
    except Exception as exc:
        message = getattr(exc, "message", None) or str(exc) or exc.__class__.__name__
        store.fail(job_id, message)
    return True


def serve(
    store: JobStore,
    train: Callable,
    *,
    once: bool = False,
    poll_seconds: float = 2.0,
    wait: Callable[[float], None] | None = None,
) -> None:
    pause = wait or _sleep

    while True:
        if process_next(store, train):
            continue
        if once:
            return
        pause(poll_seconds)


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


def default_store() -> JobStore:
    root = Path(os.environ.get("JOBS_DIR", "data/jobs"))
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres"):
        return JobStore(root, database_url=url)
    return JobStore(root)
