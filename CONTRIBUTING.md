# Contributing

## Setup

```bash
git lfs install && git clone git@github.com:prakrity26/ai-indoor-3d-reconstruction.git
cd ai-indoor-3d-reconstruction
python3.10 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api,db,queue,cloud]"     # add ,depth for Phase 4 (PyTorch)
cp .env.example .env
```

`git lfs pull --include "samples/img1299/*"` fetches the 139 MB splat sample only when you need it.

Run the platform with `python -m api` (http://127.0.0.1:8000) and a worker with
`python -m queue.workers --pipeline mesh`, or everything with `docker compose up -d --build`.

## Before you push

```bash
python -m ruff check .          # lint (config in pyproject.toml)
python -m pytest -q             # tests; no GPU, PyTorch or network needed
```

CI runs both, syntax-checks the frontend modules, and builds and smoke-tests the `api` image.

## Where things go

| Change | Place |
|---|---|
| A reconstruction step | `model/<phase>/`, reachable as `python -m model.<phase>` |
| An API route | `api/app.py`; file lookup in `api/artifacts.py` |
| A job field | New numbered file in `database/migrations/` (never edit an applied one), then `database/repositories/jobs.py` and `shared/jobs.py` |
| Worker behaviour | `shared/worker.py` (mesh), `shared/splat_worker.py` and `model/splat/splatfacto.py` (splats) |
| A web page | `ui/web/assets/js/pages/`; build DOM with `h()` and `textContent`, never `innerHTML` |
| A setting | `.env.example` with a comment, read through `shared/config/settings.py` or `os.environ` |

## Conventions

- **The `queue/` package shadows Python's stdlib `queue`.** Entry points call
  `shared.stdlib_queue.ensure_stdlib_queue()` first; do not run PyTorch or gsplat code with the
  repository root as the working directory.
- The API never runs reconstruction. It stores uploads, queues jobs and serves files; workers do the work.
- Frontend: plain ES modules, no build step. Never pass a value that may be `null` to `append()`.
- Commit messages: an imperative summary line, then a short paragraph on *why*.
- Tests use stand-ins for COLMAP, Nerfstudio and ffmpeg (`tests/test_splat_worker.py`); add one
  for each bug you fix, named after the behaviour it protects.
