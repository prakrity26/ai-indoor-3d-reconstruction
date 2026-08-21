# AI-Based Indoor 3D Reconstruction System

A modular system for 3D scene reconstruction and spatial understanding from monocular indoor video.

This repository is an internship engineering project. The reconstruction engine is designed as a reusable module that a company application can call through a REST API, without depending on the Streamlit UI or on internal pipeline details.

**Current status:** Phase 0 — project planning and architecture. No reconstruction, API, database, or UI implementation yet.

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

## Architecture (Phase 0)

Five services, one Compose file. The UI talks only to the API. The API does not run reconstruction inline. The worker owns the reconstruction engine.

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
├── model/              # Reconstruction engine (Phases 1–9)
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
| 0 | Planning and architecture (this commit) |
| 1 | Video ingestion and preprocessing |
| 2 | Adaptive frame selection |
| 3 | Camera pose estimation |
| 4 | Depth estimation |
| 5 | 3D point-cloud generation |
| 6 | Point-cloud filtering and fusion |
| 7 | Mesh reconstruction and GLB/PLY export |
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
- A later production host may enable CUDA through a device abstraction

## Local setup (Phase 0)

Phase 0 does not install ML libraries.

```bash
cp .env.example .env
docker compose config
```

`docker compose config` validates the Compose skeleton. PostgreSQL and Redis images are declared but are not required to be started in Phase 0. Application services (`ui`, `api`, `worker`) are commented until their phases.

## Documentation

Architecture notes, the proposal outline, daily logs, weekly reports, and experiment records live in the local `docs/` folder. That folder is gitignored and is **not** published to GitHub.

## License

MIT. See [LICENSE](LICENSE).
