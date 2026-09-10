# reconstruction

**Phase:** 5  
**Status:** implemented

This package back-projects Phase 4 depth through Phase 3 camera poses into an **initial colored point cloud**.

It does **not** denoise, downsample statistically, or fuse overlapping views (Phase 6). Scale is still relative: each depth map is median-normalized, then placed with the estimated pose.

## Public API

```python
from model.reconstruction import build_point_cloud

result = build_point_cloud("data/frames/<job_id>")
```

CLI:

```bash
python -m model.reconstruction data/frames/<job_id>
```

## Strategy

`depth_unproject_concat` (NumPy + OpenCV, no Open3D):

1. Load `poses.json` and `depth.json`.
2. For each successfully posed camera that has a depth map, treat depth as Z in the camera frame.
3. Unproject pixels on a `CLOUD_STRIDE` grid, color from the keyframe JPEG.
4. Concatenate views and cap `CLOUD_MAX_POINTS`.
5. Write a binary RGB PLY.

Open3D is deferred to Phase 6 (filtering / fusion).

## Outputs

| Artifact | Location |
|----------|----------|
| Point cloud | `data/frames/<job_id>/cloud.ply` |
| Copy | `data/outputs/<job_id>/cloud.ply` |
| Manifest | `data/frames/<job_id>/cloud.json` |

Open `cloud.ply` in MeshLab, CloudCompare, or Preview-capable 3D tools. This is not a mesh.
