# api

FastAPI service. The UI calls only this package. It does not import `model/` and it does not train.

**Status:** upload, job status, mesh, splat, scene labels, evaluation

- `POST /jobs` saves one indoor video and returns a queued job.
- `GET /jobs` lists uploads and the checked-in sample mesh.
- `GET /jobs/{job_id}` returns `queued`, `running`, `succeeded`, or `failed`.
- `GET /jobs/{job_id}/mesh.glb` returns the orbitable mesh when that file exists.
- `GET /jobs/{job_id}/point_cloud.ply` returns the splat after the GPU worker finishes.
- `GET /jobs/{job_id}/scene.json` and `GET /jobs/{job_id}/evaluation.json` return the Phase 8 and Phase 9 files when they exist. A sample manifest fills the evaluation counts.

```bash
pip install -e ".[api]"
python -m api
```

Open http://127.0.0.1:8000/. The video file stays on disk. Job status is stored in SQLite (`data/jobs/index.sqlite`) unless `DATABASE_URL` points at Postgres. The GPU worker is separate: `python -m queue.workers`.
