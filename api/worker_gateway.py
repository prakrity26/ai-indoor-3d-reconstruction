"""Worker gateway: lets a GPU worker on another machine (Colab, a cloud GPU) train splats.

It is a separate app on its own port so that only these routes are exposed through a tunnel;
the web platform and the rest of the API stay on the local network. Every request needs
``Authorization: Bearer $WORKER_TOKEN``.

    export WORKER_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
    python -m api.worker_gateway                     # http://0.0.0.0:8001
    cloudflared tunnel --url http://localhost:8001   # public https URL for Colab

Flow for one job: POST /worker/claim → GET source → POST progress (also the heartbeat) →
PUT result (the PLY, streamed) or POST fail.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse

from shared.stdlib_queue import ensure_stdlib_queue

# This repo's queue/ package shadows the stdlib module that anyio (FastAPI's thread pool) imports.
ensure_stdlib_queue()

from api.artifacts import frames_root, valid_job_id  # noqa: E402
from shared.jobs import JobStore  # noqa: E402

MIN_TOKEN_LENGTH = 24
_PLY_MAGIC = b"ply"


def _default_store() -> JobStore:
    root = Path(os.environ.get("JOBS_DIR", "data/jobs"))
    url = os.environ.get("DATABASE_URL", "").strip()
    return JobStore(root, database_url=url) if url.startswith("postgres") else JobStore(root)


def create_worker_app(store: JobStore | None = None, *, token: str | None = None) -> FastAPI:
    expected = (token if token is not None else os.environ.get("WORKER_TOKEN", "")).strip()
    if len(expected) < MIN_TOKEN_LENGTH:
        raise RuntimeError(
            f"WORKER_TOKEN must be set to a random value of at least {MIN_TOKEN_LENGTH} characters. "
            'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    jobs = store or _default_store()
    max_bytes = int(os.environ.get("SPLAT_MAX_UPLOAD_MB", "3000")) * 1024 * 1024
    stale_minutes = float(os.environ.get("SPLAT_STALE_MINUTES", "20"))
    app = FastAPI(title="Indoor 3D worker gateway", docs_url=None, redoc_url=None, openapi_url=None)

    def authorize(authorization: str = Header("")) -> None:
        scheme, _, supplied = authorization.partition(" ")
        if scheme.lower() != "bearer" or not secrets.compare_digest(supplied.strip(), expected):
            raise HTTPException(status_code=401, detail="Invalid worker token.")

    def running(job_id: str) -> dict:
        if not valid_job_id(job_id):
            raise HTTPException(status_code=404, detail="Unknown job.")
        record = jobs.get(job_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Unknown job.")
        if record.get("splat_status") != "running":
            # The job was failed as stale, retried, or deleted: tell the worker to stop.
            raise HTTPException(status_code=409, detail="This splat job is no longer running.")
        return record

    @app.get("/worker/ping", dependencies=[Depends(authorize)])
    def ping() -> dict:
        return {"ok": True}

    @app.post("/worker/claim", dependencies=[Depends(authorize)])
    def claim(payload: dict = Body(default={})) -> Response:
        jobs.recover_stale_splats(stale_minutes)
        record = jobs.claim_next_splat(str(payload.get("worker") or "remote"))
        if record is None:
            return Response(status_code=204)
        source = Path(record["source_path"])
        if not source.is_file():
            jobs.fail_splat(record["job_id"], "The source video is missing on the server.")
            return Response(status_code=204)
        import json

        body = {
            "job_id": record["job_id"],
            "name": record["name"],
            "filename": record["filename"],
            "source_suffix": source.suffix.lower(),
            "source_bytes": source.stat().st_size,
        }
        return Response(json.dumps(body), media_type="application/json")

    @app.get("/worker/jobs/{job_id}/source", dependencies=[Depends(authorize)])
    def source(job_id: str) -> FileResponse:
        record = running(job_id)
        return FileResponse(record["source_path"], media_type="application/octet-stream")

    @app.post("/worker/jobs/{job_id}/progress", dependencies=[Depends(authorize)])
    def progress(job_id: str, payload: dict = Body(...)) -> dict:
        running(job_id)
        try:
            percent = int(payload.get("progress") or 0)
        except (TypeError, ValueError):
            percent = 0
        jobs.splat_report(job_id, str(payload.get("stage") or "Training"), percent)
        return {"ok": True}

    @app.put("/worker/jobs/{job_id}/result", dependencies=[Depends(authorize)])
    async def result(job_id: str, request: Request) -> dict:
        running(job_id)
        folder = frames_root() / job_id / "splat"
        folder.mkdir(parents=True, exist_ok=True)
        final = folder / "point_cloud.ply"
        partial = folder / "point_cloud.ply.uploading"
        written = 0
        head = b""
        try:
            with partial.open("wb") as out:
                async for chunk in request.stream():
                    if len(head) < 3:
                        head += chunk[: 3 - len(head)]
                    written += len(chunk)
                    if written > max_bytes:
                        raise HTTPException(status_code=413, detail="The splat file is larger than SPLAT_MAX_UPLOAD_MB.")
                    out.write(chunk)
            if head != _PLY_MAGIC:
                raise HTTPException(status_code=400, detail="The uploaded file is not a PLY.")
            partial.replace(final)
        finally:
            partial.unlink(missing_ok=True)
        jobs.complete_splat(job_id, str(final))
        return {"ok": True, "bytes": written}

    @app.post("/worker/jobs/{job_id}/fail", dependencies=[Depends(authorize)])
    def fail(job_id: str, payload: dict = Body(default={})) -> dict:
        running(job_id)
        jobs.fail_splat(job_id, str(payload.get("message") or "Splat training failed on the GPU worker."))
        return {"ok": True}

    return app


def main() -> None:
    import uvicorn

    app = create_worker_app()
    uvicorn.run(
        app,
        host=os.environ.get("WORKER_GATEWAY_HOST", "0.0.0.0"),
        port=int(os.environ.get("WORKER_GATEWAY_PORT", "8001")),
        # Large PLY uploads take a while over a tunnel.
        timeout_keep_alive=120,
    )


if __name__ == "__main__":
    main()
