# frame_selection

**Phase:** 2  
**Status:** implemented

This package reduces Phase 1’s uniformly sampled frames to a smaller keyframe set: drop near-duplicates, keep viewpoint coverage, and prefer a sharper frame when a gap must be filled.

It does **not** estimate camera pose (Phase 3).

## Public API

```python
from model.frame_selection import select_keyframes

result = select_keyframes("data/frames/<job_id>")
```

CLI:

```bash
python -m model.frame_selection data/frames/<job_id>
```

`source` may be a Phase 1 job directory, `manifest.json`, or a folder of JPEG/PNG frames.

## Strategy

`adaptive_histogram_mad` (OpenCV, CPU):

1. Build a small grayscale thumbnail and a Laplacian sharpness score for each extracted frame.
2. Always keep the first frame.
3. Keep the next frame when appearance change vs the last keyframe is at least `KEYFRAME_DIFF_THRESHOLD`, and the index gap is at least `KEYFRAME_MIN_GAP`.
4. If nothing has been kept for `KEYFRAME_MAX_GAP` frames, force a keyframe and choose the sharpest frame in that window.
5. Always keep the last frame.
6. If the set is larger than `KEYFRAME_MAX_COUNT`, subsample evenly (ends kept). If it is smaller than `KEYFRAME_MIN_COUNT`, insert evenly spaced frames.

Change is the maximum of mean absolute thumbnail difference and grayscale histogram distance. That notices both a pan (pixels shift) and a lighting/scene change without adding a learned model.

## Outputs

| Artifact | Location |
|----------|----------|
| Copied keyframes | `data/frames/<job_id>/selected/` |
| Selection record | `data/frames/<job_id>/selection.json` |

Phase 1 frames and `manifest.json` are left unchanged.
