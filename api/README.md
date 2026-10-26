# api

FastAPI service. A later UI calls only this package. It does not import `model/` and it does not train.

**Status:** upload and job status

- `POST /jobs` saves one indoor video and returns a queued job. The job name is the file name.
- `GET /jobs/{job_id}` returns `queued`, `running`, `succeeded`, or `failed`.
- `GET /jobs/{job_id}/point_cloud.ply` returns the walkable splat after the GPU worker finishes.

```bash
pip install -e ".[api]"
python -m api
```

The NVIDIA worker is separate: `python -m queue.workers`.
