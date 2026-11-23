# Work so far

Internship project: indoor 3D reconstruction from a monocular phone video.  
GitHub: https://github.com/prakrity26/ai-indoor-3d-reconstruction  
Intern: Prakriti Khanal.

This file is the public progress note. Detailed daily/weekly notes stay in the local `docs/` folder and are not on GitHub.

## Status

| Item | Status |
|------|--------|
| Phases 0–7 (video → frames → pose → depth → cloud → mesh) | Done |
| Phase 8 object labels (`scene.json`) | Done; YOLO weights are an optional extra |
| Phase 9 evaluation (`evaluation.json`) | Done |
| Phase 10 API | Done; projects, uploads, progress, studio document, sharing, files |
| Phase 11 job database | Done; SQLite by default, Postgres via `DATABASE_URL`, versioned migrations |
| Phase 12 worker | Done; per-stage progress, retry, crash/stop recovery |
| Phase 13 web platform | Done; Dashboard, My projects, Create project, Processing jobs, 3D Studio, Shared scenes, Settings |
| Phase 14 Docker | Done; `api` and `worker` images, Compose with Postgres and Redis |
| Phase 15 hardening and CI | Done; streamed uploads with limits, security headers, stale-job recovery, GitHub Actions |
| Phase 16 documentation | Done; README, module READMEs, this log |
| Sample mesh + filtered cloud | `samples/img7916/` (Git LFS), from clip `IMG_7916` |
| Remote GPU splat worker | Done; worker gateway + `colab_gpu_worker.ipynb` (splatfacto), progress in the UI, Walk mode in Studio and share page |
| Walkable Gaussian splat (`IMG_7916`) | Next: run the Colab worker on the IMG_7916 upload |

## What the sample output is

`samples/img7916/mesh.glb` is a **coarse triangle mesh** from Poisson reconstruction of `IMG_7916`. It is 3D geometry you **orbit**, not a photoreal room you walk through. GitHub’s file page will not look like a 3D app; download it or run the local viewer.

```bash
git lfs install
git clone git@github.com:prakrity26/ai-indoor-3d-reconstruction.git
cd ai-indoor-3d-reconstruction
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m api
```

Opens the web platform at http://127.0.0.1:8000/. The sample room is on the dashboard; open it in the 3D Studio and drag to orbit. To process your own video, upload it on Create project and run `python -m queue.workers --pipeline mesh` in a second terminal.

## Timeline

| When | Work |
|------|------|
| 2026-08-21 | Phase 0 layout; Phase 1 video ingest (validate, extract JPEGs) |
| 2026-09-07 | Phase 2 keyframes; Phase 3 camera poses |
| 2026-09-09–10 | Phase 4 depth; Phase 5 concatenated colored cloud (`room20260814`) |
| 2026-09-15 | Phase 6 statistical filter + voxel fusion |
| 2026-09-17 | Phase 7 Poisson mesh (GLB/PLY); splat training path in this same repo |
| 2026-09-28 | Sample mesh on GitHub from `IMG_7916`; local mesh/splat viewers; Colab splat PLY still pending |
| 2026-10-26 | Phase 8 indoor object labels (`scene.json`); Phase 9 evaluation JSON for an existing job |
| 2026-11-23 | Phases 10–13 committed; web platform (7 sections, 3D Studio editor, sharing); Docker (14); hardening and CI (15); docs (16). First real video processed end to end through upload → worker → studio |

## Pipeline (Phases 1–9)

Indoor video → extracted frames → selected keyframes → relative camera poses → monocular depth → back-projected point cloud → filtered/fused cloud → Poisson mesh (`mesh.glb` / `mesh.ply`) → object labels (`scene.json`) → evaluation (`evaluation.json`).

Scale is **relative** (not metric). The mesh can look incomplete or ballooned. That is expected for this stage.

## Optional splat path

Same repository, `model/splat` + `notebooks/colab_gaussian_splat.ipynb`. Mac prepares frames; Colab (CUDA + COLMAP + gsplat) trains. Walk viewer: `python -m ui.splat_demo` after `point_cloud.ply` exists.

## How to review the delivery

1. Clone with Git LFS and install as above (`pip install -e ".[dev,api,depth,cloud]"`).
2. `python -m api`, open http://127.0.0.1:8000/, and open the sample room in the 3D Studio.
3. In the Studio: turn on Edit, click the model to add a hotspot, save a view, then Share → "Anyone with the link" and open the link.
4. Upload a short room video on Create project and run `python -m queue.workers --pipeline mesh`; watch Processing jobs.
5. Or run everything with `docker compose up --build`.
6. `pytest` runs the test suite.
7. Treat the splat as in progress until the Colab PLY is copied into `samples/` and pushed.
