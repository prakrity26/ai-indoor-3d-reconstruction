# model

Reconstruction engine library.

**Phases:** 1–9  
**Status:** Phases 1–9 (`preprocessing` through `evaluation`) implemented; `splat` is the GPU appearance path in this repo

The worker (Phase 12) will call this library. Stages are separate packages so they can be implemented, tested, and replaced independently.

| Package | Stage |
|---------|--------|
| `preprocessing` | Validation and frame extraction |
| `frame_selection` | Adaptive keyframe selection |
| `camera` | Pose / SfM |
| `depth` | Monocular depth |
| `reconstruction` | Back-projection / initial cloud |
| `pointcloud` | Filter and fuse |
| `mesh` | Mesh + GLB/PLY (laptop fallback) |
| `splat` | COLMAP + Gaussian splat (Captures-like; train on Colab) |
| `scene_understanding` | Detection and 3D association |
| `evaluation` | Metrics for an existing job |

Optional extras: `pip install -e ".[depth]"`, `pip install -e ".[cloud]"`, `pip install -e ".[detect]"`. The splat extra (`pip install -e ".[splat]"`) is for **CUDA/Colab**, not the Mac venv.
