"""Load keyframes for depth; prefer successfully posed cameras when available."""

from __future__ import annotations

import json
from pathlib import Path

from model.camera.exceptions import CameraPoseError
from model.camera.io import load_pose_frames
from model.depth.exceptions import DepthEstimationError
from model.preprocessing.types import FrameRecord


def load_depth_frames(
    source: str | Path,
    job_id: str | None = None,
) -> tuple[list[FrameRecord], Path, str, list[str]]:
    warnings: list[str] = []
    try:
        frames, job_dir, resolved_id = load_pose_frames(source, job_id=job_id)
    except CameraPoseError as exc:
        raise DepthEstimationError(exc.code, exc.message, exc.details) from exc

    poses_path = job_dir / "poses.json"
    if not poses_path.is_file():
        warnings.append("poses_missing")
        return frames, job_dir, resolved_id, warnings

    try:
        payload = json.loads(poses_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        warnings.append("poses_unreadable")
        return frames, job_dir, resolved_id, warnings

    posed = {
        str(Path(item["path"]).resolve())
        for item in payload.get("cameras", [])
        if isinstance(item, dict) and item.get("status") != "failed" and item.get("path")
    }
    if not posed:
        warnings.append("no_posed_cameras")
        return frames, job_dir, resolved_id, warnings

    filtered = [frame for frame in frames if str(Path(frame.path).resolve()) in posed]
    if not filtered:
        warnings.append("pose_paths_mismatch")
        return frames, job_dir, resolved_id, warnings
    return filtered, job_dir, resolved_id, warnings
