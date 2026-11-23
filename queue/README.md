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

Redis support needs `pip install -e ".[queue]"`.
