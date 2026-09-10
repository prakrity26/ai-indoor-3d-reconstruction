# camera

**Phase:** 3  
**Status:** implemented

This package estimates a monocular camera trajectory for Phase 2 keyframes using OpenCV ORB features and the essential matrix.

It does **not** estimate depth or build a point cloud (Phases 4–5). Scale is arbitrary, not metric.

## Public API

```python
from model.camera import estimate_poses

result = estimate_poses("data/frames/<job_id>")
```

CLI:

```bash
python -m model.camera data/frames/<job_id>
```

`source` may be a job directory with `selection.json`, a `selected/` folder, or a directory of JPEG/PNG frames.

## Strategy

`opencv_orb_essential` (OpenCV, CPU):

1. Prefer Phase 2 keyframes (`selection.json` / `selected/`).
2. Build a pinhole `K` from image size (`POSE_FOCAL_SCALE`) unless `POSE_FX` / `POSE_FY` are set.
3. Detect ORB features and match consecutive keyframes with a Lowe ratio test.
4. Estimate `E` with RANSAC and recover relative `R`, `t`.
5. Chain poses from the first camera (identity at the origin). If a consecutive pair fails, retry against a recent posed frame.
6. When tracks exist, rescale the new translation using triangulated points so step lengths are not all 1.

COLMAP and learned pose models were not adopted in this phase (see local `docs/architecture/model-selection.md`).

## Outputs

| Artifact | Location |
|----------|----------|
| Pose record | `data/frames/<job_id>/poses.json` |

Each camera stores world-to-camera `R`/`t`, the camera center, and a 4×4 camera-to-world matrix. Failed frames are listed with `status: failed`.
