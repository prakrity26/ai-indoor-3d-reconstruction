# model

Reconstruction engine library.

**Phases:** 1–9  
**Status:** Phases 1–7 (`preprocessing` through `mesh`) implemented; `splat` is the GPU appearance path in this repo; detection is still a placeholder

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

Do not install detector libraries until Phase 8. Optional extras: `pip install -e ".[depth]"`, `pip install -e ".[cloud]"`. The splat extra (`pip install -e ".[splat]"`) is for **CUDA/Colab**, not the Mac venv.
