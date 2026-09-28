# AI-Based Indoor 3D Reconstruction System

A modular system for 3D scene reconstruction and spatial understanding from monocular indoor video.

This repository is an internship engineering project. The reconstruction engine is designed as a reusable module that a company application can call through a REST API, without depending on the Streamlit UI or on internal pipeline details.

**Current status:** Phases 1–7 are implemented (video → frames → pose → depth → cloud → mesh). Sample mesh outputs are in [`samples/img7916/`](samples/README.md) from clip `IMG_7916`. A walkable Gaussian splat for the same clip is trained on Colab and is not stored in git until the PLY is saved. No object detection, API, or Streamlit product UI yet.

## Review

GitHub account: **[prakrity26](https://github.com/prakrity26)**  
Repository: **https://github.com/prakrity26/ai-indoor-3d-reconstruction**  
Progress log: **[PROGRESS.md](PROGRESS.md)** (work through Phases 1–7). Sample 3D files use **Git LFS**.

| What to look at | Where |
|-----------------|--------|
| Code through week 05 / Phases 1–7 | `model/` (preprocessing → mesh) |
| Mesh output (orbit) | `samples/img7916/mesh.glb` |
| Filtered point cloud | `samples/img7916/cloud_filtered.ply` |
| How to open the mesh | `python -m ui.demo --job-id img7916` |
| Optional splat training | `notebooks/colab_gaussian_splat.ipynb` then `python -m ui.splat_demo` |

After clone:

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m ui.demo --job-id img7916
```

That serves **http://127.0.0.1:8765/** from the checked-in sample GLB. Internet is needed once for the viewer library.

## Mesh preview (local)

The indoor clip is already reconstructed. Do **not** re-train splat on stage.

```bash
# from the project root, with the venv active
python -m ui.demo --job-id img7916
```

Show: selected frames on the left, orbitable GLB on the right. Say: relative scale, estimated mesh, API still remaining.

To rebuild only the mesh from the existing filtered cloud (optional, needs `.[cloud]`):

```bash
python -m model.mesh data/frames/img7916
```


## Problem

An ordinary indoor phone video is a sequential 2D recording. It is not an explorable spatial model. This project asks:

> How effectively can a monocular indoor video be converted into an interactive 3D representation using modern AI and computer-vision techniques while maintaining an acceptable balance between reconstruction quality, processing time and computational cost?

The intended output is reconstructed geometry (point cloud / mesh) plus metadata, not a video with a 3D effect.

## Target user flow

```text
Upload indoor video
        ↓
Validate and enqueue a reconstruction job
        ↓
Worker: frames → poses → depth → fusion → mesh → scene analysis
        ↓
Store GLB/PLY + metadata
        ↓
Interactive 3D exploration  (or API consumption by another app)
```

## What this project is not

- A copy or wrapper of LingBot-Map (LingBot-Map is a concept reference only)
- A standalone YOLO, depth, Streamlit, or 3D-viewer demo
- A claim of a new fundamental reconstruction algorithm unless one is later implemented and evaluated
- A promise of ground-truth geometry

## Architecture

Five services, one Compose file. The UI talks only to the API. The API does not run reconstruction inline. The worker will own the reconstruction engine. Phases 1–7 are the local mesh library. Gaussian splat training is the same repository (`model/splat` + `notebooks/`); Colab only provides a GPU.

```text
                 Streamlit UI
                      │
                      ▼
                 FastAPI API
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
      PostgreSQL    Redis      ML Worker
                                  │
                                  ▼
                         Reconstruction Engine
                    (OpenCV, pose, depth, 3D)
```

## Repository layout

Python packages use lowercase names. They map to the conceptual modules UI, API, MODEL, DATABASE, QUEUE, and SHARED.

```text
ai-indoor-3d-reconstruction/
├── ui/                 # Streamlit (Phase 13)
├── api/                # FastAPI (Phase 10)
├── model/              # Reconstruction engine (Phases 1–9 + splat path)
├── notebooks/          # Colab GPU notebooks (clone this repo; not a second project)
├── database/           # Persistence (Phase 11)
├── queue/              # Async workers (Phase 12)
├── shared/             # Schemas, config, utilities
├── data/               # Runtime artifacts (gitignored content)
├── tests/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Development phases

Work proceeds **one phase at a time**. Do not start the next phase until the current one is reviewed.

| Phase | Focus |
|------:|-------|
| 0 | Planning and architecture | done |
| 1 | Video ingestion and preprocessing | done |
| 2 | Adaptive frame selection | done |
| 3 | Camera pose estimation | done |
| 4 | Depth estimation | done |
| 5 | 3D point-cloud generation | done |
| 6 | Point-cloud filtering and fusion | done |
| 7 | Mesh reconstruction and GLB/PLY export | implemented |
| 8 | Object detection and scene understanding |
| 9 | Evaluation and benchmarking |
| 10 | FastAPI service |
| 11 | Database |
| 12 | Queue and asynchronous workers |
| 13 | Streamlit UI |
| 14 | Docker and Compose hardening |
| 15 | Testing, optimization, production hardening |
| 16 | Final documentation and internship deliverables |

## Hardware

Development is on Apple Silicon. The design assumes:

- No NVIDIA CUDA on the development machine
- PyTorch MPS when a model phase needs it, with CPU fallback
- **Gaussian splat training uses NVIDIA CUDA.** Development GPU is Google Colab running **this** repo. A later worker can use the same `python -m model.splat` command.
- A later production host may enable CUDA through a device abstraction

## Local setup (Phases 1–7)

Requires Python 3.10 or newer (Homebrew `python3.10` on this Apple Silicon machine).

Put **your own** indoor phone video in `data/uploads/` (or pass any local path). Do not use Hugging Face demo videos.

```bash
cp .env.example .env
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,depth,cloud]"
pytest
python -m model.preprocessing data/uploads/your_room.mp4
python -m model.frame_selection data/frames/<job_id>
python -m model.camera data/frames/<job_id>
python -m model.depth data/frames/<job_id>
python -m model.reconstruction data/frames/<job_id>
python -m model.pointcloud data/frames/<job_id>
python -m model.mesh data/frames/<job_id>
```

Phase 4 needs `.[depth]`. Phases 6–7 need `.[cloud]` (Open3D). `mesh.glb` is the laptop fallback. For a Captures-like walkable splat, use **this repo** on Colab:

```bash
# Mac: extract overlapping frames only
python -m model.splat data/uploads/your_room.mp4 --job-id room_splat --prepare-only

# Colab GPU: open notebooks/colab_gaussian_splat.ipynb (clones this GitHub repo)
# then save point_cloud.ply and run: python -m ui.splat_demo --job-id img7916
```

Artifacts land under `data/frames/<job_id>/` (and copies under `data/outputs/<job_id>/`) and are gitignored.

`docker compose config` still validates the Compose skeleton. Application services are not built yet.

## Documentation

Architecture notes, the proposal outline, daily logs, weekly reports, and experiment records live in the local `docs/` folder. That folder is gitignored and is **not** published to GitHub.

## License

MIT. See [LICENSE](LICENSE).
