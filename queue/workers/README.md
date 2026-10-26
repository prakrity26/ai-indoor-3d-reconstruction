# Worker

One process on the NVIDIA GPU. It claims queued uploads and calls `model.splat`. Each video is its own scene.

```bash
python -m queue.workers
```

`--once` trains whatever is already queued, then exits. The API must stay a different process so an upload request never runs training.
