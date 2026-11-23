# tests

Each phase adds tests for the behavior it introduces.

Phase 1: `test_preprocessing.py` covers validation failures and uniform frame extraction using synthetic OpenCV videos.

Phase 2: `test_frame_selection.py` covers redundant-frame dropping, content-change keeps, min/max count, sharpness preference in a forced gap, and selection after Phase 1 ingest.

Phase 3: `test_camera_pose.py` recovers a known synthetic two-plane motion up to scale, and rejects missing, single-frame, and degenerate identical views.

Phase 4: `test_depth.py` writes local `.npy` maps with a fake estimator, prefers posed cameras, and does not download Hugging Face videos or weights.

Phase 5: `test_reconstruction.py` unprojects a known plane, writes PLY, and builds a cloud from a synthetic job folder.

Phase 6: `test_pointcloud.py` crops flyers and, with Open3D installed, statistical-filters and voxel-fuses a noisy cluster.

Phase 7: `test_mesh.py` rejects a missing filtered cloud and, with Open3D installed, Poisson-meshes a synthetic sphere to PLY and GLB.

Phase 8: `test_scene.py` places one box through depth and pose. `test_scene_understanding.py` also drops low confidence, merges nearby objects, and caps the frame count. The YOLO weights are not downloaded.

Phase 9: `test_evaluation.py` scores pose coverage, cloud and mesh counts, timings, and keeps a small splat marked sparse.

API and UI: `test_api_ui.py` lists the sample mesh, downloads the GLB, and reads the evaluation counts. `test_jobs.py` still checks that an upload is trained by the worker, not by the request.

Phase 11: `test_database.py` stores job status in SQLite, claims the next queued job, and refuses a Postgres URL until the database extra is installed.

Phase 12: `test_queue.py` keeps the database as the queue, reports a missing Redis server, and lets a mesh job finish without a splat.

Splat path: `test_splat.py` prepares overlapping JPEGs in this repo and checks COLMAP TXT parsing. Training is CUDA-only (Colab) and is not run in pytest.

```bash
source .venv/bin/activate
pip install -e ".[dev,cloud]"
pytest
```

Collection disables the Dash pytest plugin (`-p no:dash` in `pyproject.toml`) because this repo's `queue/` package shadows the stdlib module Dash imports.
