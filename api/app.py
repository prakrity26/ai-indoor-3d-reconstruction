"""HTTP boundary for the UI: upload a video, poll the job, open mesh or splat."""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response

from api.artifacts import (
    evaluation_document,
    library_record,
    library_records,
    mesh_path,
    scene_path,
    splat_path,
    summary_from,
    valid_job_id,
)
from shared.config.settings import load_settings
from shared.jobs import JobStore
from shared.stdlib_queue import ensure_stdlib_queue

ensure_stdlib_queue()

_ROOT = Path(__file__).resolve().parents[1]
_STUDIO = _ROOT / "ui" / "studio.html"
_ORBIT = _ROOT / "ui" / "orbit.html"
_VIEWER = _ROOT / "ui" / "splat_viewer.html"
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def _default_job_store() -> JobStore:
    root = Path(os.environ.get("JOBS_DIR", "data/jobs"))
    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres"):
        return JobStore(root, database_url=url)
    return JobStore(root)


def create_app(store: JobStore | None = None, *, include_library: bool = False) -> FastAPI:
    jobs = store or _default_job_store()
    app = FastAPI(title="Indoor 3D reconstruction")
    app.state.jobs = jobs
    app.state.include_library = include_library

    @app.get("/", response_class=HTMLResponse)
    def studio() -> HTMLResponse:
        return HTMLResponse(_STUDIO.read_text(encoding="utf-8"))

    @app.get("/orbit", response_class=HTMLResponse)
    def orbit() -> HTMLResponse:
        return HTMLResponse(_ORBIT.read_text(encoding="utf-8"))

    @app.get("/viewer", response_class=HTMLResponse)
    def viewer() -> HTMLResponse:
        return HTMLResponse(_VIEWER.read_text(encoding="utf-8"))

    @app.get("/jobs")
    def list_jobs() -> dict:
        return {"jobs": [_public(record) for record in _all_records()]}

    @app.post("/jobs")
    async def create_job(file: UploadFile) -> dict:
        name = file.filename or "upload.mp4"
        suffix = Path(name).suffix.lower()
        if suffix not in _VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Upload an indoor video ({', '.join(sorted(_VIDEO_EXTENSIONS))}).",
            )
        payload = await file.read()
        limit = load_settings().max_upload_mb * 1024 * 1024
        if len(payload) > limit:
            raise HTTPException(status_code=400, detail=f"Video is larger than {load_settings().max_upload_mb} MB.")
        try:
            record = jobs.create(name, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        try:
            from shared.broker import QueueError, publish

            publish(record["job_id"])
        except QueueError:
            pass
        return _public(record)

    @app.get("/jobs/{job_id}")
    def read_job(job_id: str) -> dict:
        record = _require(job_id)
        return _public(record)

    @app.get("/jobs/{job_id}/point_cloud.ply")
    def download_splat(job_id: str) -> FileResponse:
        record = _require(job_id)
        ply = splat_path(record)
        if record["status"] != "succeeded" or ply is None:
            raise HTTPException(status_code=409, detail="The 3D file is not ready.")
        return FileResponse(ply, media_type="application/octet-stream", filename="point_cloud.ply")

    @app.get("/jobs/{job_id}/mesh.glb")
    def download_mesh(job_id: str) -> FileResponse:
        record = _require(job_id)
        mesh = mesh_path(record)
        if mesh is None:
            raise HTTPException(status_code=404, detail="This job has no mesh.")
        return FileResponse(mesh, media_type="model/gltf-binary", filename="mesh.glb")

    @app.get("/jobs/{job_id}/scene.json")
    def read_scene(job_id: str) -> Response:
        record = _require(job_id)
        path = scene_path(record)
        if path is None:
            raise HTTPException(status_code=404, detail="This job has no object labels.")
        return Response(path.read_text(encoding="utf-8"), media_type="application/json")

    @app.get("/jobs/{job_id}/evaluation.json")
    def read_evaluation(job_id: str) -> Response:
        record = _require(job_id)
        document = evaluation_document(record)
        if document is None:
            raise HTTPException(status_code=404, detail="This job has no evaluation.")
        return Response(json.dumps(document, indent=2) + "\n", media_type="application/json")

    def _all_records() -> list[dict]:
        stored = jobs.list_jobs()
        if not include_library:
            return stored
        taken = {record["job_id"] for record in stored}
        merged = [*stored, *library_records(taken)]
        merged.sort(key=lambda item: item["job_id"])
        return merged

    def _require(job_id: str) -> dict:
        if not valid_job_id(job_id):
            raise HTTPException(status_code=404, detail="Unknown job.")
        record = jobs.get(job_id)
        if record is None and include_library:
            record = library_record(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Unknown job.")
        return record

    def _public(record: dict) -> dict:
        job_id = record["job_id"]
        ply = splat_path(record)
        mesh = mesh_path(record)
        scene = scene_path(record)
        evaluation = evaluation_document(record)
        ready = record["status"] == "succeeded" and ply is not None
        return {
            "job_id": job_id,
            "status": record["status"],
            "filename": record["filename"],
            "error": record["error"],
            "splat_url": f"/jobs/{job_id}/point_cloud.ply" if ready else "",
            "mesh_url": f"/jobs/{job_id}/mesh.glb" if mesh is not None else "",
            "scene_url": f"/jobs/{job_id}/scene.json" if scene is not None else "",
            "evaluation_url": f"/jobs/{job_id}/evaluation.json" if evaluation is not None else "",
            "summary": summary_from(evaluation),
        }

    return app


app = create_app(include_library=True)
