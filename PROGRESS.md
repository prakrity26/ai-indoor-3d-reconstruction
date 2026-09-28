# Work so far

Internship project: indoor 3D reconstruction from a monocular phone video.  
GitHub: https://github.com/prakrity26/ai-indoor-3d-reconstruction  
Intern: Prakriti Khanal.

This file is the public progress note. Detailed daily/weekly notes stay in the local `docs/` folder and are not on GitHub.

## Status

| Item | Status |
|------|--------|
| Phases 0–7 (video → frames → pose → depth → cloud → mesh) | Done and on GitHub |
| Sample mesh + filtered cloud | `samples/room20260814/` (Git LFS) |
| Walkable Gaussian splat (`IMG_7916`) | Training on Colab GPU; PLY not in the repo yet |
| Phases 8–16 (detection, API, database, queue, Streamlit) | Not started |

## What the sample output is

`samples/room20260814/mesh.glb` is a **coarse triangle mesh** from Poisson reconstruction. It is 3D geometry you **orbit**, not a photoreal room you walk through. GitHub’s file page will not look like a 3D app; download it or run the local viewer.

```bash
git lfs install
git clone git@github.com:prakrity26/ai-indoor-3d-reconstruction.git
cd ai-indoor-3d-reconstruction
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m ui.demo --job-id room20260814
```

Opens http://127.0.0.1:8765/ — drag to orbit.

## Timeline

| When | Work |
|------|------|
| 2026-08-21 | Phase 0 layout; Phase 1 video ingest (validate, extract JPEGs) |
| 2026-09-07 | Phase 2 keyframes; Phase 3 camera poses |
| 2026-09-09–10 | Phase 4 depth; Phase 5 concatenated colored cloud (`room20260814`) |
| 2026-09-15 | Phase 6 statistical filter + voxel fusion |
| 2026-09-17 | Phase 7 Poisson mesh (GLB/PLY); splat training path in this same repo |
| 2026-09-28 | Sample outputs on GitHub via Git LFS; local mesh/splat viewers; Colab saves splat PLY to Drive |

## Pipeline (Phases 1–7)

Indoor video → extracted frames → selected keyframes → relative camera poses → monocular depth → back-projected point cloud → filtered/fused cloud → Poisson mesh (`mesh.glb` / `mesh.ply`).

Scale is **relative** (not metric). The mesh can look incomplete or ballooned. That is expected for this stage.

## Optional splat path

Same repository, `model/splat` + `notebooks/colab_gaussian_splat.ipynb`. Mac prepares frames; Colab (CUDA + COLMAP + gsplat) trains. Walk viewer: `python -m ui.splat_demo` after `point_cloud.ply` exists.

## How to judge this week’s delivery

1. Clone with Git LFS.
2. Open `samples/room20260814/` for mesh and cloud files.
3. Run `python -m ui.demo --job-id room20260814`.
4. Treat the splat as in progress until the Colab PLY is copied into `samples/` and pushed.
