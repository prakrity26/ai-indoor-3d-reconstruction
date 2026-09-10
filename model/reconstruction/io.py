"""Load Phase 3 poses and Phase 4 depth maps for a local job."""

from __future__ import annotations

import json
from pathlib import Path

from model.reconstruction.exceptions import ReconstructionError


def load_job_artifacts(source: str | Path) -> tuple[dict, dict, Path, str]:
    path = Path(source)
    if not path.exists():
        raise ReconstructionError("source_not_found", f"Source not found: {path}")

    if path.is_file():
        job_dir = path.parent
    else:
        job_dir = path

    poses_path = job_dir / "poses.json"
    depth_path = job_dir / "depth.json"
    if not poses_path.is_file():
        raise ReconstructionError(
            "poses_missing",
            "Phase 5 needs poses.json from Phase 3.",
            {"path": str(poses_path)},
        )
    if not depth_path.is_file():
        raise ReconstructionError(
            "depth_missing",
            "Phase 5 needs depth.json from Phase 4.",
            {"path": str(depth_path)},
        )

    try:
        poses = json.loads(poses_path.read_text(encoding="utf-8"))
        depth = json.loads(depth_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReconstructionError("invalid_manifest", str(exc)) from exc

    job_id = str(poses.get("job_id") or depth.get("job_id") or job_dir.name)
    return poses, depth, job_dir.resolve(), job_id
