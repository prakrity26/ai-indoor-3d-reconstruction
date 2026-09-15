"""Load a Phase 5 cloud.ply from a job folder."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from model.pointcloud.exceptions import PointCloudError
from model.reconstruction.ply import read_ply_xyzrgb


def load_input_cloud(source: str | Path) -> tuple[np.ndarray, np.ndarray, Path, str]:
    path = Path(source)
    if not path.exists():
        raise PointCloudError("source_not_found", f"Source not found: {path}")

    if path.is_file() and path.suffix.lower() == ".ply":
        job_dir = path.parent
        ply_path = path
    elif path.is_dir():
        job_dir = path
        ply_path = job_dir / "cloud.ply"
    else:
        raise PointCloudError(
            "unsupported_source",
            "Expected a job directory or a cloud.ply file.",
            {"path": str(path)},
        )

    if not ply_path.is_file():
        raise PointCloudError(
            "cloud_missing",
            "Phase 6 needs cloud.ply from Phase 5.",
            {"path": str(ply_path)},
        )

    points, colors = read_ply_xyzrgb(ply_path)
    if len(points) == 0:
        raise PointCloudError("cloud_empty", "The input point cloud has no vertices.")

    job_id = job_dir.name
    manifest = job_dir / "cloud.json"
    if manifest.is_file():
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            job_id = str(payload.get("job_id") or job_id)
        except json.JSONDecodeError:
            pass
    return points, colors, job_dir.resolve(), job_id
