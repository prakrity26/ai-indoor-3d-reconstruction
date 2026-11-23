# queue

The worker process. The API only saves the video and marks the job queued.

**Phase:** 12 · **Status:** implemented

The queue of record is the `jobs` table. A worker claims the oldest queued row (`FOR UPDATE SKIP
LOCKED` on Postgres, so several workers can run) and reports the stage and percentage as it goes.
When `REDIS_URL` is set the API also pushes the job id to Redis so an idle worker wakes at once.

```bash
python -m queue.workers --pipeline mesh          # Phases 1–9 (CPU / Apple MPS)
python -m queue.workers --pipeline splat         # Gaussian splat (CUDA + COLMAP)
python -m queue.workers --once --pipeline mesh   # drain the queue, then exit
```

Reliability:

- A failing stage marks the job `failed` with the error message; users can retry it from the UI.
- `SIGTERM` (e.g. `docker stop`) or Ctrl-C mid-job marks the job failed instead of leaving it `running`.
- Every 5 minutes the worker fails jobs whose progress has not changed for `WORKER_STALE_MINUTES` (default 180), which covers a worker that was killed outright.

## Splat workers (GPU)

Splat training is tracked separately from the mesh (`splat_status` on each project), so a mesh
worker on the laptop and a GPU worker elsewhere never compete for the same job.

```bash
python -m queue.workers --pipeline splat                                   # CUDA host sharing the database
python -m queue.workers --pipeline splat --gateway https://… --token …     # anywhere, through api.worker_gateway
```

The remote worker downloads the video, runs the trainer (`--backend splatfacto` by default, or
`gsplat`), posts progress every few seconds plus a heartbeat every minute, and uploads the PLY. If
the server stops treating the job as running (stale, retried, deleted), the worker cancels the
training process group and moves on. Network calls through the tunnel are retried.

Redis support needs `pip install -e ".[queue]"`.
