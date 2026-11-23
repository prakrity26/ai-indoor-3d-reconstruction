# api

FastAPI service for the web platform and for other applications. It does not import the
reconstruction engine and never trains: it saves uploads, queues jobs, and serves files that a
worker wrote.

**Phase:** 10 (extended for the platform) · **Status:** implemented

| Module | Role |
|---|---|
| `app.py` | Routes, page serving, response headers |
| `artifacts.py` | Finds mesh, splat, labels, evaluation, thumbnail, and input report files for a job |
| `studio.py` | Validates and stores the 3D Studio document (hotspots, viewpoints, settings) |
| `worker_gateway.py` | Separate app for remote GPU workers: claim, source download, progress, PLY upload, fail. Bearer `WORKER_TOKEN` (24+ chars) required; no platform routes |

See the REST table in the root [README](../README.md#rest-api) or http://127.0.0.1:8000/docs.

Behaviour worth knowing:

- Uploads stream to disk in 1 MB chunks; going over `MAX_UPLOAD_MB` returns 413 and removes the partial file.
- Checked-in samples (`samples/<id>/`) are registered as read-only projects at startup. They can be annotated and shared but not deleted.
- `DELETE /jobs/{id}` removes the job row, its upload folder, `FRAMES_DIR/<id>`, `OUTPUT_DIR/<id>`, and its studio document. Running jobs cannot be deleted.
- Share tokens are random (`secrets.token_urlsafe`). `/shared/{token}` answers only while the project is public; rotating the token kills the old link.
- Media links in hotspots must be `http(s)://` or same-site paths; `javascript:` and `data:` are rejected.
- Every response gets `X-Content-Type-Options: nosniff`, a referrer policy, and `X-Frame-Options: SAMEORIGIN`, except `/embed/*` and `/viewer`, which other sites may frame.

```bash
pip install -e ".[api]"
python -m api
```
