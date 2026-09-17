"""Load a Phase 6 filtered cloud for meshing."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from model.mesh.exceptions import MeshError
from model.reconstruction.ply import read_ply_xyzrgb


def load_filtered_cloud(source: str | Path) -> tuple[np.ndarray, np.ndarray, Path, str]:
    path = Path(source)
    if not path.exists():
        raise MeshError("source_not_found", f"Source not found: {path}")

    if path.is_file() and path.suffix.lower() == ".ply":
        job_dir = path.parent
        ply_path = path
    elif path.is_dir():
        job_dir = path
        ply_path = job_dir / "cloud_filtered.ply"
    else:
        raise MeshError(
            "unsupported_source",
            "Expected a job directory or a filtered cloud.ply file.",
            {"path": str(path)},
        )

    if not ply_path.is_file():
        raise MeshError(
            "filtered_cloud_missing",
            "Phase 7 needs cloud_filtered.ply from Phase 6.",
            {"path": str(ply_path)},
        )

    points, colors = read_ply_xyzrgb(ply_path)
    if len(points) == 0:
        raise MeshError("cloud_empty", "The filtered point cloud has no vertices.")

    job_id = job_dir.name
    for name in ("cloud_filtered.json", "cloud.json"):
        manifest = job_dir / name
        if not manifest.is_file():
            continue
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            job_id = str(payload.get("job_id") or job_id)
            break
        except json.JSONDecodeError:
            continue
    return points, colors, job_dir.resolve(), job_id
