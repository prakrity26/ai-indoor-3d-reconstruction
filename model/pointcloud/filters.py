"""Crop, statistical outlier removal, and voxel fusion."""

from __future__ import annotations

import numpy as np

from model.pointcloud.exceptions import PointCloudError
from shared.config.settings import PointCloudFilterSettings


def crop_percentile(
    points: np.ndarray,
    colors: np.ndarray,
    percentile: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Drop far flyers by keeping the central percentile box on each axis."""
    if percentile <= 0:
        return points, colors
    lo = np.percentile(points, percentile, axis=0)
    hi = np.percentile(points, 100.0 - percentile, axis=0)
    keep = np.all((points >= lo) & (points <= hi), axis=1)
    if not np.any(keep):
        raise PointCloudError("crop_empty", "Percentile crop removed every point.")
    return points[keep], colors[keep]


def _require_open3d():
    from shared.stdlib_queue import ensure_stdlib_queue

    ensure_stdlib_queue()
    try:
        import open3d as o3d
    except ImportError as exc:
        raise PointCloudError(
            "missing_dependency",
            "Point-cloud filtering needs the optional cloud extra: pip install -e '.[cloud]'",
            {"import_error": str(exc)},
        ) from exc
    return o3d


def to_open3d(points: np.ndarray, colors: np.ndarray):
    o3d = _require_open3d()
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(np.asarray(points, dtype=np.float64))
    cloud.colors = o3d.utility.Vector3dVector(np.asarray(colors, dtype=np.float64) / 255.0)
    return cloud


def from_open3d(cloud) -> tuple[np.ndarray, np.ndarray]:
    points = np.asarray(cloud.points, dtype=np.float32)
    if cloud.has_colors():
        colors = np.clip(np.asarray(cloud.colors) * 255.0, 0, 255).astype(np.uint8)
    else:
        colors = np.full((len(points), 3), 180, dtype=np.uint8)
    return points, colors


def remove_statistical_outliers(
    points: np.ndarray,
    colors: np.ndarray,
    settings: PointCloudFilterSettings,
) -> tuple[np.ndarray, np.ndarray, int]:
    cloud = to_open3d(points, colors)
    filtered, _index = cloud.remove_statistical_outlier(
        nb_neighbors=settings.nb_neighbors,
        std_ratio=settings.std_ratio,
    )
    out_points, out_colors = from_open3d(filtered)
    return out_points, out_colors, int(len(out_points))


def voxel_downsample(
    points: np.ndarray,
    colors: np.ndarray,
    voxel_size: float,
) -> tuple[np.ndarray, np.ndarray]:
    cloud = to_open3d(points, colors)
    fused = cloud.voxel_down_sample(voxel_size=voxel_size)
    return from_open3d(fused)
