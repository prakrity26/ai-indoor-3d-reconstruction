# AI-Based Indoor 3D Reconstruction & Spatial Experience Platform

Record a room with an ordinary smartphone, upload the video, and explore the reconstructed space as an interactive 3D scene in the browser. Add hotspots and saved viewpoints, then share a read-only link or embed the scene on a website.

```text
Capture → Upload → Process → Reconstruct → Explore → Edit → Save → Share
```

This is an internship engineering project. The reconstruction engine is a reusable module behind a REST API, so other company products can call it without the web platform.

**Status:** all 16 phases are implemented. The reconstruction pipeline (Phases 1–9), the API, job database, worker, web platform, Docker stack, CI, and documentation are in this repository. A walkable Gaussian splat is trained on a CUDA GPU (Colab); the trained PLY for the sample clip is not in git yet. See [PROGRESS.md](PROGRESS.md).

| | |
|---|---|
| GitHub | https://github.com/prakrity26/ai-indoor-3d-reconstruction |
| Progress log | [PROGRESS.md](PROGRESS.md) |
| Sample reconstruction | [`samples/img7916/`](samples/README.md) (Git LFS) |

## Quick start

### Option A: laptop (SQLite, no Docker)

Requires Python 3.10+.

```bash
git lfs install && git clone git@github.com:prakrity26/ai-indoor-3d-reconstruction.git
cd ai-indoor-3d-reconstruction
python3.10 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api,depth,cloud]"
python -m api                                   # http://127.0.0.1:8000
```

In a second terminal, start a worker so uploads get processed:

```bash
source .venv/bin/activate
python -m queue.workers --pipeline mesh         # Phases 1–9 on CPU / Apple MPS
```

The sample room is listed on the dashboard straight away. Uploads are processed by the worker; the Processing jobs page shows each stage live.

### Option B: Docker Compose (PostgreSQL + Redis)

```bash
cp .env.example .env            # change POSTGRES_PASSWORD
docker compose up --build       # first build downloads CPU PyTorch and Open3D
open http://localhost:8000
```

Compose runs `api` (web platform + REST API), `worker` (mesh pipeline), `postgres`, and `redis`. Uploads and outputs live in `./data` on the host.

## The web platform

Served by FastAPI at `/` (plain ES modules in [`ui/web/`](ui/web), no build step).

| Section | What it does |
|---|---|
| **Dashboard** | Project counts, recent projects, live processing jobs, capture tips |
| **My projects** | Search, filter by status, grid/list view; project page with video preview, input-quality warnings, reconstruction metrics, downloads, rename, retry, delete |
| **Create project** | Drag-and-drop upload with recording guidelines, in-browser checks (format, size, duration, resolution, orientation), name and description, upload progress |
| **Processing jobs** | Status, current stage and progress for every upload; retry failed jobs |
| **3D Studio** | Orbit / zoom / pan / reset / fullscreen / auto-rotate on the mesh; Walk mode (W A S D) on a Gaussian splat; edit mode to place info markers, text labels, and image/video markers; saved camera viewpoints and a start view; background, exposure, and shadow settings; `Cmd/Ctrl+S` to save |
| **Shared scenes** | Public links, embed code, make private, reset link |
| **Settings** | Theme, default viewer mode, platform info (database, queue, upload limit) |

A shared scene opens at `/s/<token>` (read-only viewer with hotspots and views). `/embed/<token>` is the same viewer without chrome, for an `<iframe>`.

### Mesh vs. Gaussian splat

| Representation | Viewer | Use |
|---|---|---|
| Mesh (`mesh.glb`) | `<model-viewer>` (Orbit) | Explicit geometry, hotspots, compatibility with 3D tools |
| Gaussian splat (`point_cloud.ply`) | GaussianSplats3D (Walk) | Photoreal exploration; needs CUDA training |

They are different formats with different viewers. A splat is not rendered as a GLB mesh.

## Architecture

```text
 Browser ── web platform (ui/web) ─┐
                                   ▼
                         FastAPI (api/)  ──  files on disk (data/)
                          │        │              ▲
                 PostgreSQL /    Redis (wake-up)  │
                 SQLite (jobs)     │              │
                          └────────┴──► Worker (queue/, shared/worker.py)
                                              │
                                   Reconstruction engine (model/)
              frames → keyframes → poses → depth → cloud → filter/fuse → mesh → labels → evaluation
```

- The API never runs reconstruction. It saves the upload (streamed to disk), creates a `queued` row, and serves files a worker wrote.
- The **database is the queue**. Workers claim the oldest queued row (`SKIP LOCKED` on Postgres). Redis, when configured, only wakes workers early.
- Workers report the current stage and percentage; the UI polls it. Jobs stuck in `running` after a crash or `docker stop` are marked failed and can be retried.
- Studio documents (hotspots, viewpoints, settings) are validated JSON in `data/jobs/_studio/<job_id>.json`.

## REST API

| Method & path | Purpose |
|---|---|
| `GET /health` · `GET /api/config` | Liveness; upload limit, formats, database and queue type |
| `GET /jobs` · `POST /jobs` | List projects · upload a video (`file`, `name`, `description`) |
| `GET /jobs/{id}` · `PATCH /jobs/{id}` · `DELETE /jobs/{id}` | Read (with stage, progress, input warnings, artifacts) · rename/describe · delete everything the job wrote |
| `POST /jobs/{id}/retry` | Re-queue a failed job |
| `GET\|PUT /jobs/{id}/studio.json` | Hotspots, viewpoints, scene settings |
| `PUT /jobs/{id}/visibility` · `POST /jobs/{id}/share/rotate` | `private` / `public`; issue a new share token |
| `GET /shared/{token}` | Public, read-only project + studio document |
| `GET /jobs/{id}/mesh.glb` · `point_cloud.ply` · `scene.json` · `evaluation.json` · `thumbnail.jpg` · `source` | Files |

Interactive docs: http://127.0.0.1:8000/docs.

## Reconstruction pipeline (CLI)

Each phase also runs on its own. Put **your own** indoor video in `data/uploads/`.

```bash
python -m model.preprocessing data/uploads/your_room.mp4   # 1 validate, extract frames
python -m model.frame_selection data/frames/<job_id>       # 2 keyframes
python -m model.camera data/frames/<job_id>                # 3 relative poses
python -m model.depth data/frames/<job_id>                 # 4 Depth Anything (needs .[depth])
python -m model.reconstruction data/frames/<job_id>        # 5 back-projected cloud
python -m model.pointcloud data/frames/<job_id>            # 6 filter + voxel fusion (needs .[cloud])
python -m model.mesh data/frames/<job_id>                  # 7 Poisson mesh → GLB/PLY
python -m model.scene_understanding data/frames/<job_id>   # 8 object labels (.[detect] optional)
python -m model.evaluation data/frames/<job_id>            # 9 evaluation.json
```

Gaussian splat (CUDA): prepare frames on the Mac with `python -m model.splat <video> --job-id <id> --prepare-only`, train with [`notebooks/colab_gaussian_splat.ipynb`](notebooks/README.md), or run `python -m queue.workers --pipeline splat` on a CUDA host.

**Scale is relative**, not metres: monocular video has no metric scale.

## Testing

```bash
pip install -e ".[dev,api,db,queue,cloud]"
pytest
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs the test suite, syntax-checks the frontend modules, and builds and smoke-tests the API image.

## Repository layout

```text
api/          FastAPI app, artifact lookup, studio document validation
ui/web/       Web platform (index.html, share.html, assets/)
ui/           Standalone mesh/splat viewers and a Streamlit client
model/        Reconstruction engine (Phases 1–9) and the splat trainer
database/     SQLAlchemy model, repository, versioned SQL migrations
queue/        Worker entry point (python -m queue.workers)
shared/       Job store, worker loop, broker, settings
samples/      Checked-in sample reconstruction (Git LFS)
notebooks/    Colab GPU notebooks for splat training
tests/        pytest suite
Dockerfile    api and worker targets
```

## Configuration

Copy `.env.example` to `.env`. Key settings: `DATABASE_URL` (empty → SQLite in `data/jobs/`), `REDIS_URL` (optional), `MAX_UPLOAD_MB`, `COMPUTE_DEVICE` (`auto` / `mps` / `cuda` / `cpu`), `MESH_POISSON_THREADS`, `WORKER_STALE_MINUTES`.

## Known limitations

- **No authentication.** Single-user mode. "Private" means "no share link"; file URLs are not access-controlled. Put the app behind a trusted network or add auth before exposing it publicly.
- Mesh quality is coarse and can look incomplete; scale is relative.
- Walkable splats need a CUDA GPU and COLMAP; the Docker worker runs only the mesh pipeline.
- Hotspots are placed on the mesh (Orbit mode), not inside the splat viewer.
- Media markers link to images/videos by URL; files are not uploaded to the platform.
- 360° video is out of scope for this version.

## Future work

Authentication and teams · uploading media for hotspots · hotspots in Walk mode · QR-code sharing · 360° capture · metric scale from known objects · collaboration.

## License

MIT. See [LICENSE](LICENSE).
