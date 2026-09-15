# tests

Each phase adds tests for the behavior it introduces.

Phase 1: `test_preprocessing.py` covers validation failures and uniform frame extraction using synthetic OpenCV videos.

Phase 2: `test_frame_selection.py` covers redundant-frame dropping, content-change keeps, min/max count, sharpness preference in a forced gap, and selection after Phase 1 ingest.

Phase 3: `test_camera_pose.py` recovers a known synthetic two-plane motion up to scale, and rejects missing, single-frame, and degenerate identical views.

Phase 4: `test_depth.py` writes local `.npy` maps with a fake estimator, prefers posed cameras, and does not download Hugging Face videos or weights.

Phase 5: `test_reconstruction.py` unprojects a known plane, writes PLY, and builds a cloud from a synthetic job folder.

Phase 6: `test_pointcloud.py` crops flyers and, with Open3D installed, statistical-filters and voxel-fuses a noisy cluster. No large real indoor videos are committed.

```bash
source .venv/bin/activate
pip install -e ".[dev,cloud]"
pytest
```

Collection disables the Dash pytest plugin (`-p no:dash` in `pyproject.toml`) because this repo's `queue/` package shadows the stdlib module Dash imports.
