# pointcloud

**Phase:** 6  
**Status:** implemented

This package denoise-crops and voxel-fuses the Phase 5 concatenated cloud.

It does **not** build a mesh (Phase 7). Scale is still relative. Voxel downsampling is the fusion step: nearby points from overlapping views collapse into one.

## Public API

```python
from model.pointcloud import filter_point_cloud

result = filter_point_cloud("data/frames/<job_id>")
```

CLI:

```bash
pip install -e ".[cloud]"
python -m model.pointcloud data/frames/<job_id>
```

## Strategy

`open3d_stat_voxel`:

1. Load `cloud.ply`.
2. Crop to the central `CLOUD_CROP_PERCENTILE` box (drop far flyers).
3. Statistical outlier removal (`CLOUD_FILTER_NB_NEIGHBORS`, `CLOUD_FILTER_STD_RATIO`).
4. Voxel downsample (`CLOUD_VOXEL_SIZE`) to fuse overlapping samples.
5. Write `cloud_filtered.ply`.

## Outputs

| Artifact | Location |
|----------|----------|
| Filtered cloud | `data/frames/<job_id>/cloud_filtered.ply` |
| Copy | `data/outputs/<job_id>/cloud_filtered.ply` |
| Manifest | `data/frames/<job_id>/cloud_filtered.json` |
