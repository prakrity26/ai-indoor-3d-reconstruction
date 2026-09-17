# mesh

**Phase:** 7  
**Status:** implemented

This package builds a triangle mesh from the Phase 6 filtered cloud and writes PLY plus GLB.

It does **not** detect objects (Phase 8). Scale is still relative. Poisson reconstruction can fill holes and slightly balloon; vertices outside a scaled axis-aligned box of the input cloud are cropped.

## Public API

```python
from model.mesh import reconstruct_mesh

result = reconstruct_mesh("data/frames/<job_id>")
```

CLI:

```bash
pip install -e ".[cloud]"
python -m model.mesh data/frames/<job_id>
```

## Strategy

`open3d_poisson`:

1. Load `cloud_filtered.ply`.
2. Estimate and orient normals.
3. Screened Poisson reconstruction (`MESH_POISSON_DEPTH`).
4. Drop low-density vertices, crop to the cloud bounding box, optionally simplify.
5. Copy nearby point colors onto vertices.
6. Write `mesh.ply` and `mesh.glb`.

## Outputs

| Artifact | Location |
|----------|----------|
| Triangle mesh | `data/frames/<job_id>/mesh.ply` |
| glTF binary | `data/frames/<job_id>/mesh.glb` |
| Copies | `data/outputs/<job_id>/mesh.ply`, `mesh.glb` |
| Manifest | `data/frames/<job_id>/mesh.json` |
