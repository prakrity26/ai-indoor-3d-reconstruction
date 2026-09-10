# depth

**Phase:** 4  
**Status:** implemented

This package estimates a **relative** per-keyframe depth map for a local reconstruction job.

It does **not** back-project a point cloud (Phase 5). It does **not** download Hugging Face demo videos. You supply an indoor recording; Phases 1–3 produce the job folder this stage reads.

## Public API

```python
from model.depth import estimate_depth

result = estimate_depth("data/frames/<job_id>")
```

CLI:

```bash
pip install -e ".[depth]"
python -m model.depth data/frames/<job_id>
```

## Strategy

`depth_anything_v2_small` (PyTorch, MPS/CPU, optional CUDA):

1. Prefer Phase 2 keyframes that Phase 3 successfully posed.
2. Run Depth Anything V2 Small (`depth-anything/Depth-Anything-V2-Small-hf`).
3. Resize the long edge to `DEPTH_MAX_SIZE` for inference, then upsample to the original frame.
4. Write float32 `.npy` maps and optional color previews.

The first real run may download **model weights** once. That is not a sample video. `COMPUTE_DEVICE=auto` tries CUDA, then Apple MPS, then CPU.

Tests use `GradientDepthEstimator` so `pytest` never hits the Hub.

## Outputs

| Artifact | Location |
|----------|----------|
| Depth maps | `data/frames/<job_id>/depth/*.npy` |
| Color previews | `data/frames/<job_id>/depth/*.png` |
| Manifest | `data/frames/<job_id>/depth.json` |
