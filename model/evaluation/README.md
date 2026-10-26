# evaluation

**Phase:** 9  
**Status:** implemented

Scores a job that already has reconstruction files. It does not rerun pose, depth, meshing, or splat training.

```bash
python -m model.evaluation data/frames/<job_id>
python -m model.evaluation samples/img7916
```

`evaluation.json` records the posed-frame ratio, point and triangle counts, scene-label counts when `scene.json` exists, and any stage durations written with `note_duration`. Scale is relative.

A splat counts as a walk-through candidate only at 100,000 Gaussians and 5 MB. A smaller file is reported as a sparse cloud.
