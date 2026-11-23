"""HTTP boundary: projects, uploads, job status, 3D files, the studio document, and sharing.

The API never runs reconstruction. It saves the upload, queues a job, and serves files that a
worker wrote. The web platform (``ui/web``) is served from ``/``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from api import studio
from api.artifacts import (
    evaluation_document,
    frames_root,
    input_report,
    library_records,
    mesh_path,
    scene_path,
    splat_path,
    summary_from,
    thumbnail_path,
    valid_job_id,
)
from shared.config.settings import load_settings
from shared.jobs import JobStore, UploadTooLarge, default_store
from shared.stdlib_queue import ensure_stdlib_queue

ensure_stdlib_queue()

API_VERSION = "1.0.0"
_ROOT = Path(__file__).resolve().parents[1]
_WEB = _ROOT / "ui" / "web"
_ORBIT = _ROOT / "ui" / "orbit.html"
_VIEWER = _ROOT / "ui" / "splat_viewer.html"
VIDEO_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v")
_VIDEO_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".avi": "video/x-msvideo",
}


def _output_dir() -> Path:
    return Path(os.environ.get("OUTPUT_DIR", "./data/outputs"))


def create_app(store: JobStore | None = None, *, include_library: bool = False) -> FastAPI:
    jobs = store or default_store()
    app = FastAPI(title="Indoor 3D reconstruction", version=API_VERSION)
    app.state.jobs = jobs

    if include_library:
        for record in library_records(set()):
            jobs.register_sample(record["job_id"], record["filename"], name=_sample_name(record))

    if (_WEB / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_WEB / "assets"), name="assets")

    @app.middleware("http")
    async def response_headers(request, call_next):
        # The frontend has no build step or hashed filenames, so browsers must revalidate
        # (ETag) instead of running stale modules after an update.
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/assets/"):
            response.headers["Cache-Control"] = "no-cache"
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # Only the public embed page (and the splat viewer it frames) may be framed elsewhere.
        if not (path.startswith("/embed/") or path == "/viewer"):
            response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response

    # ---- pages ----------------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def platform() -> HTMLResponse:
        return _page("index.html")

    @app.get("/s/{token}", response_class=HTMLResponse)
    def shared_page(token: str) -> HTMLResponse:
        return _page("share.html")

    @app.get("/embed/{token}", response_class=HTMLResponse)
    def embed_page(token: str) -> HTMLResponse:
        return _page("share.html")

    @app.get("/orbit", response_class=HTMLResponse)
    def orbit() -> HTMLResponse:
        return HTMLResponse(_ORBIT.read_text(encoding="utf-8"))

    @app.get("/viewer", response_class=HTMLResponse)
    def viewer() -> HTMLResponse:
        return HTMLResponse(_VIEWER.read_text(encoding="utf-8"))

    # ---- platform -------------------------------------------------------------------------
    @app.get("/health")
    def health() -> dict:
        try:
            jobs.list_jobs()
            database = "ok"
        except Exception as exc:  # pragma: no cover - only when the database is down
            return JSONResponse({"status": "degraded", "database": str(exc)}, status_code=503)
        return {"status": "ok", "database": database, "version": API_VERSION}

    @app.get("/api/config")
    def config() -> dict:
        settings = load_settings()
        url = os.environ.get("DATABASE_URL", "").strip()
        return {
            "version": API_VERSION,
            "max_upload_mb": settings.max_upload_mb,
            "video_extensions": list(VIDEO_EXTENSIONS),
            "database": "postgresql" if url.startswith("postgres") else "sqlite",
            "queue": "redis" if os.environ.get("REDIS_URL", "").strip() else "database",
            "scale": "relative (monocular video has no metric scale)",
        }

    # ---- projects -------------------------------------------------------------------------
    @app.get("/jobs")
    def list_jobs() -> dict:
        # A Colab worker can vanish without a word; do not show "training" forever.
        jobs.recover_stale_splats(float(os.environ.get("SPLAT_STALE_MINUTES", "20")))
        return {"jobs": [_public(record) for record in jobs.list_jobs()]}

    @app.post("/jobs")
    async def create_job(
        file: UploadFile = File(...),
        name: str = Form(""),
        description: str = Form(""),
        splat: bool = Form(False),
    ) -> dict:
        filename = file.filename or "upload.mp4"
        suffix = Path(filename).suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Upload an indoor video ({', '.join(VIDEO_EXTENSIONS)}).",
            )
        limit_mb = load_settings().max_upload_mb
        try:
            record = jobs.create(
                filename,
                file.file,
                name=name,
                description=description,
                max_bytes=limit_mb * 1024 * 1024,
                splat=splat,
            )
        except UploadTooLarge as exc:
            raise HTTPException(status_code=413, detail=f"Video is larger than {limit_mb} MB.") from exc
        except ValueError as exc:
            detail = "The uploaded file is empty." if str(exc) == "empty_file" else str(exc)
            raise HTTPException(status_code=400, detail=detail) from exc
        finally:
            await file.close()
        try:
            from shared.broker import QueueError, publish

            publish(record["job_id"])
        except QueueError:
            pass  # the database row is still queued; a polling worker will find it
        return _public(record, detail=True)

    @app.get("/jobs/{job_id}")
    def read_job(job_id: str) -> dict:
        return _public(_require(job_id), detail=True)

    @app.patch("/jobs/{job_id}")
    def update_job(job_id: str, payload: dict = Body(...)) -> dict:
        _require(job_id)
        try:
            record = jobs.update(job_id, name=payload.get("name"), description=payload.get("description"))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="A project needs a name.") from exc
        return _public(record, detail=True)

    @app.delete("/jobs/{job_id}", status_code=204)
    def delete_job(job_id: str) -> Response:
        _require(job_id)
        try:
            jobs.delete(job_id, extra_dirs=[frames_root(), _output_dir()])
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        studio.remove(jobs.root, job_id)
        return Response(status_code=204)

    @app.post("/jobs/{job_id}/retry")
    def retry_job(job_id: str) -> dict:
        _require(job_id)
        try:
            record = jobs.retry(job_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        try:
            from shared.broker import QueueError, publish

            publish(job_id)
        except QueueError:
            pass
        return _public(record, detail=True)

    @app.post("/jobs/{job_id}/splat")
    def request_splat(job_id: str) -> dict:
        """Queue (or re-queue) Gaussian splat training for a GPU worker."""
        _require(job_id)
        try:
            record = jobs.request_splat(job_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _public(record, detail=True)

    @app.put("/jobs/{job_id}/visibility")
    def set_visibility(job_id: str, payload: dict = Body(...)) -> dict:
        _require(job_id)
        try:
            record = jobs.set_visibility(job_id, str(payload.get("visibility") or ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _public(record, detail=True)

    @app.post("/jobs/{job_id}/share/rotate")
    def rotate_share(job_id: str) -> dict:
        _require(job_id)
        return _public(jobs.rotate_share_token(job_id), detail=True)

    # ---- studio document --------------------------------------------------------------------
    @app.get("/jobs/{job_id}/studio.json")
    def read_studio(job_id: str) -> dict:
        _require(job_id)
        return studio.load(jobs.root, job_id)

    @app.put("/jobs/{job_id}/studio.json")
    def write_studio(job_id: str, payload: Any = Body(...)) -> dict:
        _require(job_id)
        try:
            return studio.save(jobs.root, job_id, payload)
        except studio.StudioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ---- files ----------------------------------------------------------------------------
    @app.api_route("/jobs/{job_id}/point_cloud.ply", methods=["GET", "HEAD"])
    def download_splat(job_id: str) -> FileResponse:
        record = _require(job_id)
        ply = splat_path(record)
        if ply is None or (record["status"] != "succeeded" and record.get("splat_status") != "succeeded"):
            raise HTTPException(status_code=409, detail="The 3D file is not ready.")
        return FileResponse(ply, media_type="application/octet-stream", filename="point_cloud.ply")

    @app.api_route("/jobs/{job_id}/mesh.glb", methods=["GET", "HEAD"])
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

    @app.get("/jobs/{job_id}/thumbnail.jpg")
    def thumbnail(job_id: str) -> FileResponse:
        path = thumbnail_path(_require(job_id))
        if path is None:
            raise HTTPException(status_code=404, detail="No preview yet.")
        return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "max-age=300"})

    @app.get("/jobs/{job_id}/source")
    def source_video(job_id: str) -> FileResponse:
        record = _require(job_id)
        source = Path(record.get("source_path") or "")
        if not record.get("source_path") or not source.is_file():
            raise HTTPException(status_code=404, detail="The original video is not stored for this project.")
        return FileResponse(source, media_type=_VIDEO_TYPES.get(source.suffix.lower(), "application/octet-stream"))

    # ---- public sharing ---------------------------------------------------------------------
    @app.get("/shared/{token}")
    def shared_scene(token: str) -> dict:
        record = jobs.get_shared(token) if valid_job_id(token) else None
        if record is None:
            raise HTTPException(status_code=404, detail="This scene is private or the link has changed.")
        public = _public(record)
        keep = ("job_id", "name", "description", "mesh_url", "splat_url", "summary", "updated_at")
        return {
            "project": {key: public[key] for key in keep},
            "studio": studio.load(jobs.root, record["job_id"]),
        }

    # ---- helpers --------------------------------------------------------------------------
    def _require(job_id: str) -> dict:
        if not valid_job_id(job_id):
            raise HTTPException(status_code=404, detail="Unknown project.")
        record = jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Unknown project.")
        return record

    def _public(record: dict, *, detail: bool = False) -> dict:
        job_id = record["job_id"]
        ply = splat_path(record)
        mesh = mesh_path(record)
        scene = scene_path(record)
        evaluation = evaluation_document(record)
        ready = ply is not None and (record["status"] == "succeeded" or record.get("splat_status") == "succeeded")
        public = record.get("visibility") == "public" and bool(record.get("share_token"))
        body = {
            "job_id": job_id,
            "name": record.get("name") or record["filename"] or job_id,
            "description": record.get("description") or "",
            "status": record["status"],
            "stage": record.get("stage") or "",
            "progress": int(record.get("progress") or 0),
            "filename": record["filename"],
            "error": record["error"],
            "origin": record.get("origin") or "upload",
            "created_at": record.get("created_at") or "",
            "updated_at": record.get("updated_at") or "",
            "visibility": record.get("visibility") or "private",
            "share_url": f"/s/{record['share_token']}" if public else "",
            "embed_url": f"/embed/{record['share_token']}" if public else "",
            "thumbnail_url": f"/jobs/{job_id}/thumbnail.jpg" if thumbnail_path(record) else "",
            "splat_url": f"/jobs/{job_id}/point_cloud.ply" if ready else "",
            "splat_status": "succeeded" if ready and record.get("splat_status") in (None, "", "none") else record.get("splat_status") or "none",
            "splat_stage": record.get("splat_stage") or "",
            "splat_progress": int(record.get("splat_progress") or 0),
            "splat_error": record.get("splat_error") or "",
            "splat_updated_at": record.get("splat_updated_at") or "",
            "can_train_splat": bool(record.get("source_path")) and Path(record.get("source_path") or "").is_file(),
            "mesh_url": f"/jobs/{job_id}/mesh.glb" if mesh is not None else "",
            "scene_url": f"/jobs/{job_id}/scene.json" if scene is not None else "",
            "evaluation_url": f"/jobs/{job_id}/evaluation.json" if evaluation is not None else "",
            "summary": summary_from(evaluation),
        }
        if detail:
            source = record.get("source_path") or ""
            body["source_url"] = f"/jobs/{job_id}/source" if source and Path(source).is_file() else ""
            body["input"] = input_report(record)
            body["evaluation_warnings"] = (evaluation or {}).get("warnings") or []
            body["artifacts"] = [
                {"kind": kind, "url": url, "bytes": _size(path)}
                for kind, url, path in (
                    ("Mesh (GLB)", body["mesh_url"], mesh),
                    ("Gaussian splat (PLY)", body["splat_url"], ply if ready else None),
                    ("Object labels (JSON)", body["scene_url"], scene),
                    ("Evaluation (JSON)", body["evaluation_url"], None),
                )
                if url
            ]
        return body

    return app


def _page(name: str) -> HTMLResponse:
    return HTMLResponse((_WEB / name).read_text(encoding="utf-8"), headers={"Cache-Control": "no-cache"})


def _size(path: Path | None) -> int | None:
    try:
        return path.stat().st_size if path is not None else None
    except OSError:
        return None


def _sample_name(record: dict) -> str:
    raw = record.get("filename") or record["job_id"]
    return f"Sample room ({raw})"


app = create_app(include_library=True)
