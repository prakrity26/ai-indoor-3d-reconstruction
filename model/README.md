# model

Reconstruction engine library.

**Phases:** 1–9  
**Status:** package skeleton only

The worker (Phase 12) will call this library. Stages are separate packages so they can be implemented, tested, and replaced independently.

| Package | Stage |
|---------|--------|
| `preprocessing` | Validation and frame extraction |
| `frame_selection` | Adaptive keyframe selection |
| `camera` | Pose / SfM |
| `depth` | Monocular depth |
| `reconstruction` | Back-projection / initial cloud |
| `pointcloud` | Filter and fuse |
| `mesh` | Mesh + GLB/PLY |
| `scene_understanding` | Detection and 3D association |

Do not install depth, pose, or detector libraries until the matching phase.
