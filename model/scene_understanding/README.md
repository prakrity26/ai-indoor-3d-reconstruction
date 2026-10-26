# scene_understanding

**Phase:** 8  
**Status:** implemented

Labels indoor objects on Phase 2 keyframes and writes `scene.json` in the job folder. When `poses.json` and `depth.json` exist, each box is placed at one relative 3D point using the stored depth. Same-label points closer than `SCENE_MERGE_DISTANCE` become one object. Positions are not measured metres.

The default detector is YOLOv8n, limited to COCO classes that belong in a room. Tests pass their own detector and do not download weights.

```bash
pip install -e ".[detect]"
python -m model.scene_understanding data/frames/<job_id>
```

The first run may download the small `yolov8n.pt` weights. Without pose or depth, labels stay on the image.
