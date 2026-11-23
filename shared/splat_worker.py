"""GPU splat worker. Claims splat jobs, trains, and hands back a PLY.

Two ways to reach the job queue, one training loop:

* ``LocalSplatQueue``: the worker shares the database and disk with the API (a CUDA host on
  the same network, or the same machine).
* ``GatewaySplatQueue``: the worker is somewhere else (Colab, a rented GPU) and talks to
  ``api.worker_gateway`` over HTTPS with a bearer token. The video is downloaded and the PLY
  uploaded through the gateway.

    python -m queue.workers --pipeline splat --gateway https://<tunnel> --token $WORKER_TOKEN
"""

from __future__ import annotations

import logging
import os
import shutil
import socket
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger("reconstruction.splat_worker")

Trainer = Callable[..., Path]  # trainer(video, work_dir, report=..., cancel=...) -> ply path


class JobGone(Exception):
    """The server no longer considers this job running (stale, retried, or deleted)."""


class SplatQueue(Protocol):
    def claim(self) -> dict[str, Any] | None: ...
    def fetch_source(self, job: dict[str, Any], target_dir: Path, on_progress: Callable[[float], None] | None = None) -> Path: ...
    def progress(self, job_id: str, stage: str, percent: int) -> None: ...
    def deliver(self, job_id: str, ply: Path) -> None: ...
    def fail(self, job_id: str, message: str) -> None: ...


# ---- local queue ------------------------------------------------------------------------------
class LocalSplatQueue:
    def __init__(self, store, frames_dir: Path | None = None, worker: str = "") -> None:
        self.store = store
        self.frames_dir = Path(frames_dir or os.environ.get("FRAMES_DIR", "data/frames"))
        self.worker = worker or socket.gethostname()

    def claim(self) -> dict[str, Any] | None:
        return self.store.claim_next_splat(self.worker)

    def fetch_source(self, job: dict[str, Any], target_dir: Path, on_progress: Callable[[float], None] | None = None) -> Path:
        return Path(job["source_path"])

    def progress(self, job_id: str, stage: str, percent: int) -> None:
        record = self.store.get(job_id)
        if record is None or record.get("splat_status") != "running":
            raise JobGone(job_id)
        self.store.splat_report(job_id, stage, percent)

    def deliver(self, job_id: str, ply: Path) -> None:
        final = self.frames_dir / job_id / "splat" / "point_cloud.ply"
        final.parent.mkdir(parents=True, exist_ok=True)
        if Path(ply).resolve() != final.resolve():
            shutil.copy2(ply, final)
        self.store.complete_splat(job_id, str(final))

    def fail(self, job_id: str, message: str) -> None:
        self.store.fail_splat(job_id, message)


# ---- gateway queue (remote GPU) -----------------------------------------------------------------
class GatewaySplatQueue:
    def __init__(self, base_url: str, token: str, worker: str = "", client=None) -> None:
        import httpx

        self.base = base_url.rstrip("/")
        self.worker = worker or socket.gethostname()
        self.http = client or httpx.Client(
            headers={"Authorization": f"Bearer {token}"},
            timeout=httpx.Timeout(60.0, write=None, read=600.0),
            follow_redirects=True,
        )

    def ping(self) -> None:
        response = self.http.get(f"{self.base}/worker/ping")
        if response.status_code == 401:
            raise SystemExit("The gateway rejected the worker token. Check WORKER_TOKEN on both machines.")
        response.raise_for_status()

    def claim(self) -> dict[str, Any] | None:
        response = self._retry(lambda: self.http.post(f"{self.base}/worker/claim", json={"worker": self.worker}))
        if response.status_code == 204:
            return None
        response.raise_for_status()
        return response.json()

    def fetch_source(self, job: dict[str, Any], target_dir: Path, on_progress: Callable[[float], None] | None = None) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"source{job.get('source_suffix') or '.mp4'}"
        total = int(job.get("source_bytes") or 0)
        for attempt in range(4):
            try:
                with self.http.stream("GET", f"{self.base}/worker/jobs/{job['job_id']}/source") as response:
                    if response.status_code == 409:
                        raise JobGone(job["job_id"])
                    response.raise_for_status()
                    done = 0
                    with target.open("wb") as out:
                        for chunk in response.iter_bytes(1024 * 1024):
                            out.write(chunk)
                            done += len(chunk)
                            if on_progress is not None and total:
                                on_progress(min(1.0, done / total))
                return target
            except JobGone:
                raise
            except Exception as exc:  # network hiccup through the tunnel
                if attempt == 3:
                    raise
                log.warning("download failed (%s); retrying", exc)
                time.sleep(5 * (attempt + 1))
        return target

    def progress(self, job_id: str, stage: str, percent: int) -> None:
        response = self._retry(
            lambda: self.http.post(f"{self.base}/worker/jobs/{job_id}/progress", json={"stage": stage, "progress": percent})
        )
        if response.status_code in (404, 409):
            raise JobGone(job_id)
        response.raise_for_status()

    def deliver(self, job_id: str, ply: Path) -> None:
        size = Path(ply).stat().st_size
        for attempt in range(4):
            try:
                with Path(ply).open("rb") as handle:
                    response = self.http.put(
                        f"{self.base}/worker/jobs/{job_id}/result",
                        content=_chunks(handle),
                        headers={"Content-Type": "application/octet-stream", "Content-Length": str(size)},
                    )
                if response.status_code in (404, 409):
                    raise JobGone(job_id)
                response.raise_for_status()
                return
            except JobGone:
                raise
            except Exception as exc:
                if attempt == 3:
                    raise
                log.warning("upload failed (%s); retrying", exc)
                time.sleep(10 * (attempt + 1))

    def fail(self, job_id: str, message: str) -> None:
        try:
            self.http.post(f"{self.base}/worker/jobs/{job_id}/fail", json={"message": message[:2000]})
        except Exception as exc:  # the server will mark it stale anyway
            log.warning("could not report failure: %s", exc)

    def _retry(self, call, attempts: int = 4):
        for attempt in range(attempts):
            try:
                return call()
            except Exception as exc:
                if attempt == attempts - 1:
                    raise
                log.warning("gateway request failed (%s); retrying", exc)
                time.sleep(3 * (attempt + 1))
        raise RuntimeError("unreachable")


def _chunks(handle, size: int = 1024 * 1024):
    while True:
        block = handle.read(size)
        if not block:
            return
        yield block


# ---- training loop -------------------------------------------------------------------------------
class _Reporter:
    """Throttles progress posts and re-sends the last one as a heartbeat during silent steps."""

    def __init__(self, queue: SplatQueue, job_id: str, cancel: threading.Event, every: float = 10.0, heartbeat: float = 60.0):
        self.queue, self.job_id, self.cancel = queue, job_id, cancel
        self.every, self.heartbeat = every, heartbeat
        self.stage, self.percent = "Starting", 0
        self.sent_at = 0.0
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._beat, daemon=True)

    def __call__(self, stage: str, percent: int) -> None:
        with self.lock:
            changed_stage = stage.split("·")[0] != self.stage.split("·")[0]
            self.stage, self.percent = stage, percent
            due = changed_stage or time.monotonic() - self.sent_at >= self.every
        if due:
            self._send()

    def _send(self) -> None:
        with self.lock:
            stage, percent = self.stage, self.percent
            self.sent_at = time.monotonic()
        try:
            self.queue.progress(self.job_id, stage, percent)
        except JobGone:
            log.warning("job %s was cancelled on the server; stopping", self.job_id)
            self.cancel.set()
        except Exception as exc:
            log.warning("progress update failed: %s", exc)

    def _beat(self) -> None:
        while not self.stop.wait(self.heartbeat):
            if time.monotonic() - self.sent_at >= self.heartbeat:
                self._send()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()


def process_one(queue: SplatQueue, trainer: Trainer, work_root: Path) -> bool:
    """Claim and train one splat job. Returns False when nothing is queued."""
    job = queue.claim()
    if job is None:
        return False
    job_id = job["job_id"]
    work = Path(work_root) / job_id
    cancel = threading.Event()
    started = time.monotonic()
    log.info("splat %s: claimed (%s)", job_id, job.get("name") or job.get("filename"))
    try:
        with _Reporter(queue, job_id, cancel) as report:
            report("Downloading video", 1)
            video = queue.fetch_source(
                job, work, on_progress=lambda fraction: report(f"Downloading video · {int(fraction * 100)}%", 1)
            )
            ply = trainer(video, work, report=report, cancel=cancel)
            if cancel.is_set():
                raise JobGone(job_id)
            report("Uploading splat", 99)
            _keep_copy(job_id, Path(ply))
            queue.deliver(job_id, Path(ply))
        _clear_resume(job_id)
        log.info("splat %s: delivered in %.0f min", job_id, (time.monotonic() - started) / 60)
    except JobGone:
        log.warning("splat %s: abandoned (no longer running on the server)", job_id)
    except Exception as exc:
        message = getattr(exc, "message", None) or str(exc) or exc.__class__.__name__
        log.error("splat %s: failed: %s", job_id, message)
        queue.fail(job_id, message)
    except BaseException:
        queue.fail(job_id, "The GPU worker was stopped during training. Train again to retry.")
        raise
    finally:
        if os.environ.get("SPLAT_KEEP_WORK", "") != "1":
            shutil.rmtree(work, ignore_errors=True)
    return True


def _keep_copy(job_id: str, ply: Path) -> None:
    """Optionally copy the PLY somewhere durable first (e.g. Google Drive on Colab)."""
    root = os.environ.get("SPLAT_KEEP_ROOT", "").strip()
    if not root:
        return
    try:
        dest = Path(root) / job_id / "point_cloud.ply"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ply, dest)
        log.info("kept a copy at %s", dest)
    except OSError as exc:
        log.warning("could not keep a copy: %s", exc)


def resume_dir(job_id: str) -> Path | None:
    """Where poses and checkpoints survive a Colab disconnect (inside SPLAT_KEEP_ROOT)."""
    root = os.environ.get("SPLAT_KEEP_ROOT", "").strip()
    return Path(root) / job_id / "resume" if root else None


def _clear_resume(job_id: str) -> None:
    folder = resume_dir(job_id)
    if folder is not None and folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)
        log.info("cleared resume data in %s", folder)


def run(queue: SplatQueue, trainer: Trainer, work_root: Path, *, once: bool = False, poll_seconds: float = 15.0) -> None:
    """Train queued splats forever. Survives the gateway being unreachable (laptop asleep,
    tunnel restarting) by backing off and retrying instead of exiting."""
    outages = 0
    while True:
        try:
            worked = process_one(queue, trainer, work_root)
            if outages:
                log.info("gateway reachable again")
            outages = 0
        except Exception as exc:
            outages += 1
            wait = min(300.0, poll_seconds * outages)
            log.warning(
                "cannot reach the gateway (%s). Is the laptop awake and the tunnel running? "
                "If the tunnel restarted, its URL changed: stop this cell and rerun cells 3 and 4. "
                "Retrying in %.0f s.",
                exc, wait,
            )
            time.sleep(wait)
            continue
        if worked:
            continue
        if once:
            return
        time.sleep(poll_seconds)


# ---- backends ------------------------------------------------------------------------------------
def splatfacto_trainer(video: Path, work: Path, *, report, cancel) -> Path:
    from model.splat.splatfacto import train_splatfacto

    # work is <work_root>/<job_id>; keep poses and checkpoints on Drive when configured.
    return train_splatfacto(video, work, report=report, cancel=cancel, persist_dir=resume_dir(work.name))


def gsplat_trainer(video: Path, work: Path, *, report, cancel) -> Path:
    """The in-repo COLMAP + gsplat trainer (model.splat)."""
    from model.splat.pipeline import reconstruct_gaussian_splat

    report("Training Gaussians (in-repo gsplat)", 10)
    result = reconstruct_gaussian_splat(video, job_id="splat", frames_dir=work / "frames")
    if not result.ply_path:
        raise RuntimeError("The gsplat trainer finished without a PLY.")
    return Path(result.ply_path)


TRAINERS: dict[str, Trainer] = {"splatfacto": splatfacto_trainer, "gsplat": gsplat_trainer}
