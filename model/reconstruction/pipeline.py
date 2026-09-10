"""Phase 5: back-project posed depth maps into an initial colored cloud."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from model.reconstruction.backproject import subsample_points, unproject_frame
from model.reconstruction.exceptions import ReconstructionError
from model.reconstruction.io import load_job_artifacts
from model.reconstruction.ply import write_ply_xyzrgb
from model.reconstruction.types import (
    STRATEGY_NAME,
    CloudIssue,
    CloudResult,
    FrameCloudStats,
    dump_cloud_manifest,
)
from shared.config.settings import ReconstructionSettings, load_reconstruction_settings


def build_point_cloud(
    source: str | Path,
    *,
    output_ply: str | Path | None = None,
    settings: ReconstructionSettings | None = None,
) -> CloudResult:
    """Fuse Phase 3 poses and Phase 4 depth into a concatenated point cloud.

    Filtering and true multi-view fusion belong to Phase 6. Scale is still
    relative: each depth map is median-normalized, then posed.
    """
    settings = settings or load_reconstruction_settings()
    try:
        settings.validate()
    except ValueError as exc:
        raise ReconstructionError("invalid_settings", str(exc)) from exc

    poses, depth, job_dir, job_id = load_job_artifacts(source)
    cameras = [
        item
        for item in poses.get("cameras", [])
        if isinstance(item, dict) and item.get("status") != "failed"
    ]
    maps = [item for item in depth.get("maps", []) if isinstance(item, dict)]
    if not cameras:
        raise ReconstructionError("no_posed_cameras", "No successfully posed cameras in poses.json.")
    if not maps:
        raise ReconstructionError("no_depth_maps", "No depth maps listed in depth.json.")

    intrinsics = poses.get("intrinsics") or {}
    depth_by_stem = {
        Path(item["source_path"]).stem: item
        for item in maps
        if item.get("source_path")
    }

    all_points: list[np.ndarray] = []
    all_colors: list[np.ndarray] = []
    frame_stats: list[FrameCloudStats] = []
    warnings: list[CloudIssue] = [
        CloudIssue(
            "info",
            "relative_scale",
            "Depth and pose scales are not metric. Each view is median-normalized before unprojection.",
        )
    ]

    for camera in cameras:
        source_path = str(camera.get("path") or "")
        stem = Path(source_path).stem
        record = depth_by_stem.get(stem)
        if record is None:
            continue
        depth_path = Path(record["depth_path"])
        if not depth_path.is_file():
            warnings.append(
                CloudIssue("warning", "depth_file_missing", f"Missing depth file: {depth_path}")
            )
            continue
        depth_map = np.load(depth_path)
        fx, fy, cx, cy = _scaled_intrinsics(intrinsics, depth_map.shape)
        matrix = np.array(camera["matrix_c2w"], dtype=np.float64)
        color = cv2.imread(source_path, cv2.IMREAD_COLOR)
        points, colors = unproject_frame(
            depth_map,
            color,
            fx,
            fy,
            cx,
            cy,
            matrix,
            settings,
        )
        if len(points) == 0:
            warnings.append(
                CloudIssue("warning", "empty_frame", f"No valid depth pixels for {stem}")
            )
            continue
        all_points.append(points)
        all_colors.append(colors)
        frame_stats.append(
            FrameCloudStats(index=int(camera.get("index", 0)), source_path=source_path, point_count=len(points))
        )

    if not all_points:
        raise ReconstructionError("cloud_empty", "No points could be unprojected from the posed depth maps.")

    points = np.concatenate(all_points, axis=0)
    colors = np.concatenate(all_colors, axis=0)
    points, colors = subsample_points(points, colors, settings.max_points)

    ply_path = Path(output_ply) if output_ply is not None else job_dir / "cloud.ply"
    write_ply_xyzrgb(ply_path, points, colors)
    extra = settings.output_dir / job_id / "cloud.ply"
    extra.parent.mkdir(parents=True, exist_ok=True)
    if extra.resolve() != ply_path.resolve():
        extra.write_bytes(ply_path.read_bytes())

    result = CloudResult(
        job_id=job_id,
        strategy=STRATEGY_NAME,
        scale_meaning="relative_per_view_then_posed",
        frame_count=len(frame_stats),
        point_count=int(len(points)),
        ply_path=str(ply_path.resolve()),
        manifest_path=str((job_dir / "cloud.json").resolve()),
        frames=frame_stats,
        warnings=warnings,
    )
    dump_cloud_manifest(result, job_dir / "cloud.json")
    return result


def _scaled_intrinsics(intrinsics: dict, depth_shape: tuple[int, ...]) -> tuple[float, float, float, float]:
    height, width = int(depth_shape[0]), int(depth_shape[1])
    fx = float(intrinsics.get("fx") or max(width, height))
    fy = float(intrinsics.get("fy") or fx)
    cx = float(intrinsics.get("cx") if intrinsics.get("cx") is not None else width / 2.0)
    cy = float(intrinsics.get("cy") if intrinsics.get("cy") is not None else height / 2.0)
    calib_w = float(intrinsics.get("width") or width)
    calib_h = float(intrinsics.get("height") or height)
    if calib_w > 0 and abs(calib_w - width) > 1:
        scale_x = width / calib_w
        fx *= scale_x
        cx *= scale_x
    if calib_h > 0 and abs(calib_h - height) > 1:
        scale_y = height / calib_h
        fy *= scale_y
        cy *= scale_y
    return fx, fy, cx, cy
