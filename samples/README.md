# Sample reconstruction outputs

These files are stored with **Git LFS**. After clone, run `git lfs install` (or `git lfs pull`) if the GLB/PLY files are tiny pointer text instead of 3D binaries.

## Job `img7916`

Indoor clip `IMG_7916` reconstructed through Phases 1–7 (mesh path). OpenCV posed 17 of 70 keyframes, so the surface is incomplete.

| File | What it is |
|------|------------|
| `img7916/mesh.glb` | Poisson mesh for orbit preview (~17k vertices, ~34k triangles) |
| `img7916/mesh.ply` | Same mesh as PLY |
| `img7916/cloud_filtered.ply` | Filtered / voxel-fused point cloud (~80k points) |
| `img7916/preview/` | A few source frames from the clip |

Relative monocular scale. Not a walkable photoreal splat.

### View on a laptop

```bash
python -m ui.demo --job-id img7916
```

Opens http://127.0.0.1:8765/ (mesh orbit). Works from this `samples/` copy after a GitHub clone.

## Gaussian splat (same clip)

Walk-through splat is trained on Colab GPU (`notebooks/colab_gaussian_splat.ipynb`). The splat PLY is **not** in this folder until training finishes and is copied here.

```bash
python -m ui.splat_demo --job-id img7916
```
