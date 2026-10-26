"""One reconstruction job per uploaded video. The API writes jobs; the GPU worker runs them."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable

STATUSES = ("queued", "running", "succeeded", "failed")


def job_id_from_filename(filename: str) -> str:
    stem = Path(filename or "upload").stem
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_").lower()
    return cleaned or "upload"


class JobStore:
    """Filesystem queue shared by the API and the splat worker."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def create(self, filename: str, payload: bytes) -> dict[str, Any]:
        if not payload:
            raise ValueError("empty_file")
        job_id = self._unique_id(job_id_from_filename(filename))
        folder = self.root / job_id
        folder.mkdir(parents=True, exist_ok=False)
        suffix = Path(filename).suffix.lower() or ".mp4"
        source = folder / f"source{suffix}"
        source.write_bytes(payload)
        record = {
            "job_id": job_id,
            "status": "queued",
            "filename": Path(filename).name or f"{job_id}{suffix}",
            "source_path": str(source.resolve()),
            "ply_path": "",
            "error": "",
        }
        self._write(record)
        return record

    def list_jobs(self) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        records = []
        for folder in self.root.iterdir():
            if not folder.is_dir():
                continue
            record = self.get(folder.name)
            if record is not None:
                records.append(record)
        records.sort(key=lambda item: item["job_id"])
        return records

    def get(self, job_id: str) -> dict[str, Any] | None:
        path = self._record_path(job_id)
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def claim_next(self) -> dict[str, Any] | None:
        if not self.root.is_dir():
            return None
        for folder in sorted(path for path in self.root.iterdir() if path.is_dir()):
            record = self.get(folder.name)
            if record is None or record["status"] != "queued":
                continue
            record["status"] = "running"
            record["error"] = ""
            self._write(record)
            return record
        return None

    def complete(self, job_id: str, ply_path: str) -> dict[str, Any]:
        record = self._require(job_id)
        record["status"] = "succeeded"
        record["ply_path"] = str(Path(ply_path).resolve())
        record["error"] = ""
        self._write(record)
        return record

    def fail(self, job_id: str, message: str) -> dict[str, Any]:
        record = self._require(job_id)
        record["status"] = "failed"
        record["error"] = message
        self._write(record)
        return record

    def _unique_id(self, base: str) -> str:
        candidate = base
        number = 2
        while (self.root / candidate).exists():
            candidate = f"{base}_{number}"
            number += 1
        return candidate

    def _require(self, job_id: str) -> dict[str, Any]:
        record = self.get(job_id)
        if record is None:
            raise KeyError(job_id)
        return record

    def _record_path(self, job_id: str) -> Path:
        return self.root / job_id / "job.json"

    def _write(self, record: dict[str, Any]) -> None:
        path = self._record_path(record["job_id"])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)


def process_next(store: JobStore, train: Callable) -> bool:
    """Train the oldest queued upload. Returns False when the queue is empty."""
    job = store.claim_next()
    if job is None:
        return False
    job_id = job["job_id"]
    try:
        result = train(job["source_path"], job_id=job_id)
        ply = getattr(result, "ply_path", "") or ""
        if not ply or not Path(ply).is_file():
            raise RuntimeError("Training finished without a point_cloud.ply.")
        store.complete(job_id, ply)
    except Exception as exc:
        message = getattr(exc, "message", None) or str(exc)
        store.fail(job_id, message)
    return True


def serve(store: JobStore, train: Callable, *, once: bool = False, poll_seconds: float = 2.0) -> None:
    while True:
        if process_next(store, train):
            continue
        if once:
            return
        time.sleep(poll_seconds)


def default_store() -> JobStore:
    return JobStore(Path(os.environ.get("JOBS_DIR", "data/jobs")))
