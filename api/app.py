"""HTTP boundary for a later UI: upload a video, poll the job, download the splat."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from shared.config.settings import load_settings
from shared.jobs import JobStore
from shared.stdlib_queue import ensure_stdlib_queue

ensure_stdlib_queue()

_ROOT = Path(__file__).resolve().parents[1]
_STUDIO = _ROOT / "ui" / "studio.html"
_VIEWER = _ROOT / "ui" / "splat_viewer.html"
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def create_app(store: JobStore | None = None) -> FastAPI:
    jobs = store or JobStore(Path(os.environ.get("JOBS_DIR", "data/jobs")))
    app = FastAPI(title="Indoor 3D reconstruction")
    app.state.jobs = jobs

    @app.get("/", response_class=HTMLResponse)
    def studio() -> HTMLResponse:
        return HTMLResponse(_STUDIO.read_text(encoding="utf-8"))

    @app.get("/viewer", response_class=HTMLResponse)
    def viewer() -> HTMLResponse:
        return HTMLResponse(_VIEWER.read_text(encoding="utf-8"))

    @app.get("/jobs")
    def list_jobs() -> dict:
        return {"jobs": [_public(record) for record in jobs.list_jobs()]}

    @app.post("/jobs")
    async def create_job(file: UploadFile) -> dict:
        name = file.filename or "upload.mp4"
        suffix = Path(name).suffix.lower()
        if suffix not in _VIDEO_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Upload an indoor video ({', '.join(sorted(_VIDEO_EXTENSIONS))}).")
        payload = await file.read()
        limit = load_settings().max_upload_mb * 1024 * 1024
        if len(payload) > limit:
            raise HTTPException(status_code=400, detail=f"Video is larger than {load_settings().max_upload_mb} MB.")
        try:
            record = jobs.create(name, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _public(record)

    @app.get("/jobs/{job_id}")
    def read_job(job_id: str) -> dict:
        record = jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Unknown job.")
        return _public(record)

    @app.get("/jobs/{job_id}/point_cloud.ply")
    def download_splat(job_id: str) -> FileResponse:
        record = jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Unknown job.")
        ply = Path(record.get("ply_path") or "")
        if record["status"] != "succeeded" or not ply.is_file():
            raise HTTPException(status_code=409, detail="The 3D file is not ready.")
        return FileResponse(ply, media_type="application/octet-stream", filename="point_cloud.ply")

    return app


def _public(record: dict) -> dict:
    ready = record["status"] == "succeeded" and bool(record.get("ply_path"))
    return {
        "job_id": record["job_id"],
        "status": record["status"],
        "filename": record["filename"],
        "error": record["error"],
        "splat_url": f"/jobs/{record['job_id']}/point_cloud.ply" if ready else "",
    }


app = create_app()
