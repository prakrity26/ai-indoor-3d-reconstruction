# Sample reconstruction outputs

These files are the **checked-in demo artifacts** for mentor review. Runtime jobs under `data/` stay gitignored (videos, full frame dumps, Colab splats).

## Job `room20260814`

Indoor phone clip reconstructed through Phases 1–7 (mesh path).

| File | What it is |
|------|------------|
| `room20260814/mesh.glb` | Poisson mesh for orbit preview (~12k vertices, ~24k triangles) |
| `room20260814/mesh.ply` | Same mesh as PLY |
| `room20260814/cloud_filtered.ply` | Filtered / voxel-fused point cloud (~161k points) |
| `room20260814/preview/` | A few source frames from the clip |

Relative monocular scale. Not a walkable photoreal splat.

### View on a laptop

```bash
python -m ui.demo --job-id room20260814
```

Opens http://127.0.0.1:8765/ (mesh orbit). Works from this `samples/` copy after a GitHub clone.

## Job `img7916` (Gaussian splat)

Walk-through splat is trained on Colab GPU (`notebooks/colab_gaussian_splat.ipynb`). The PLY is **not** in this folder until training finishes and is copied here.

When you have `point_cloud.ply`:

```bash
python -m ui.splat_demo --job-id img7916
```

Then walk with WASD at http://127.0.0.1:8766/
