# Worker

One process, separate from the API.

```bash
python -m queue.workers --once --pipeline mesh
python -m queue.workers --pipeline splat
```

`mesh` reconstructs on this Mac. `splat` trains on an NVIDIA GPU. `--once` finishes the queued jobs and exits. An upload request never calls either pipeline.
