"""One reconstruction job per uploaded video. The API writes jobs; the GPU worker runs them."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Callable

from database.repositories.jobs import JobRepository
from database.session import sqlite_url

STATUSES = ("queued", "running", "succeeded", "failed")


def job_id_from_filename(filename: str) -> str:
    stem = Path(filename or "upload").stem
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_").lower()
    return cleaned or "upload"


class JobStore:
    """Uploads on disk, job status in the database. The API and the worker share both."""

    def __init__(self, root: Path, database_url: str | None = None) -> None:
        self.root = Path(root)
        self.repo = JobRepository(database_url or sqlite_url(self.root))

    def create(self, filename: str, payload: bytes) -> dict[str, Any]:
        if not payload:
            raise ValueError("empty_file")
        job_id = self._unique_id(job_id_from_filename(filename))
        folder = self.root / job_id
        folder.mkdir(parents=True, exist_ok=False)
        suffix = Path(filename).suffix.lower() or ".mp4"
        source = folder / f"source{suffix}"
        source.write_bytes(payload)
        return self.repo.insert(
            {
                "job_id": job_id,
                "status": "queued",
                "filename": Path(filename).name or f"{job_id}{suffix}",
                "source_path": str(source.resolve()),
                "ply_path": "",
                "error": "",
            }
        )

    def list_jobs(self) -> list[dict[str, Any]]:
        return self.repo.list_jobs()

    def get(self, job_id: str) -> dict[str, Any] | None:
        return self.repo.get(job_id)

    def claim_next(self) -> dict[str, Any] | None:
        return self.repo.claim_next()

    def complete(self, job_id: str, ply_path: str) -> dict[str, Any]:
        stored = str(Path(ply_path).resolve()) if ply_path else ""
        return self.repo.save_status(job_id, "succeeded", ply_path=stored, error="")

    def fail(self, job_id: str, message: str) -> dict[str, Any]:
        return self.repo.save_status(job_id, "failed", error=message)

    def _unique_id(self, base: str) -> str:
        candidate = base
        number = 2
        while (self.root / candidate).exists() or self.repo.get(candidate) is not None:
            candidate = f"{base}_{number}"
            number += 1
        return candidate


def process_next(store: JobStore, train: Callable) -> bool:
    """Run the oldest queued upload. Returns False when the queue is empty."""
    job = store.claim_next()
    if job is None:
        return False
    job_id = job["job_id"]
    try:
        result = train(job["source_path"], job_id=job_id)
        ply = getattr(result, "ply_path", "") or ""
        mesh = getattr(result, "mesh_path", "") or ""
        if ply and Path(ply).is_file():
            store.complete(job_id, ply)
        elif mesh and Path(mesh).is_file():
            store.complete(job_id, "")
        else:
            raise RuntimeError("The worker finished without a splat or a mesh.")
    except Exception as exc:
        message = getattr(exc, "message", None) or str(exc)
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
