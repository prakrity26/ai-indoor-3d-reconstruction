# queue

The worker process. The API only saves the video and marks the job queued.

**Phase:** 12  
**Status:** implemented

The queue of record is the `jobs` table from Phase 11. The worker claims the oldest queued row. On this laptop it polls that table, so Redis does not have to be running.

When `REDIS_URL` is set, the API also pushes the job id to Redis and the worker waits on that list. That needs:

```bash
pip install -e ".[queue]"
```

```bash
python -m queue.workers --once --pipeline mesh
python -m queue.workers --pipeline splat
```

`mesh` runs Phases 1–9 on this machine. `splat` is the CUDA trainer and stays a different process from the API.
