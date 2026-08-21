# preprocessing

**Phase:** 1  
**Status:** implemented

This package validates a monocular indoor video and extracts uniformly sampled JPEG frames.

It does **not** perform adaptive keyframe selection (Phase 2).

## Public API

```python
from model.preprocessing import ingest_video

result = ingest_video("path/to/video.mp4")
```

CLI:

```bash
python -m model.preprocessing path/to/video.mp4
```

## Pipeline

1. Confirm the file exists, is non-empty, and has an allowed extension.
2. Open it with OpenCV and read resolution, fps, duration, and codec.
3. Reject videos that are too small, too short/long, or have an unusable frame rate.
4. Sample frames for brightness and blur (Laplacian variance). Near-black video is rejected; blur/dark/bright otherwise become warnings.
5. Extract frames at a uniform stride near `TARGET_EXTRACT_FPS`, capped by `MAX_EXTRACTED_FRAMES`.
6. Write `data/frames/<job_id>/frames/frame_XXXXXX.jpg` and `manifest.json`.

## Outputs

| Artifact | Location |
|----------|----------|
| JPEG frames | `data/frames/<job_id>/frames/` |
| Manifest | `data/frames/<job_id>/manifest.json` |

Generated media is gitignored.
