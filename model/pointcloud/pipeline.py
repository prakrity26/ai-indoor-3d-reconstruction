"""Phase 6: denoise, crop, and voxel-fuse a Phase 5 concatenated cloud."""

from __future__ import annotations

from pathlib import Path

from model.pointcloud.exceptions import PointCloudError
from model.pointcloud.filters import (
    crop_percentile,
    remove_statistical_outliers,
    voxel_downsample,
)
from model.pointcloud.io import load_input_cloud
from model.pointcloud.types import (
    STRATEGY_NAME,
    FilterIssue,
    FilterResult,
    dump_filter_manifest,
)
from model.reconstruction.ply import write_ply_xyzrgb
from shared.config.settings import PointCloudFilterSettings, load_pointcloud_filter_settings


def filter_point_cloud(
    source: str | Path,
    *,
    output_ply: str | Path | None = None,
    settings: PointCloudFilterSettings | None = None,
) -> FilterResult:
    """Clean and voxel-fuse `cloud.ply`. Mesh reconstruction is Phase 7."""
    settings = settings or load_pointcloud_filter_settings()
    try:
        settings.validate()
    except ValueError as exc:
        raise PointCloudError("invalid_settings", str(exc)) from exc

    points, colors, job_dir, job_id = load_input_cloud(source)
    input_count = int(len(points))
    warnings: list[FilterIssue] = [
        FilterIssue(
            "info",
            "voxel_fusion",
            "Overlapping views are fused by voxel downsampling, not TSDF. Scale remains relative.",
        )
    ]

    points, colors = crop_percentile(points, colors, settings.crop_percentile)
    after_crop = int(len(points))
    points, colors, after_outlier = remove_statistical_outliers(points, colors, settings)
    points, colors = voxel_downsample(points, colors, settings.voxel_size)
    if len(points) < settings.min_points:
        raise PointCloudError(
            "too_few_points",
            "Filtering left too few points for a usable cloud.",
            {"count": int(len(points)), "min_points": settings.min_points},
        )

    ply_path = Path(output_ply) if output_ply is not None else job_dir / "cloud_filtered.ply"
    write_ply_xyzrgb(ply_path, points, colors)
    extra = settings.output_dir / job_id / "cloud_filtered.ply"
    extra.parent.mkdir(parents=True, exist_ok=True)
    if extra.resolve() != ply_path.resolve():
        extra.write_bytes(ply_path.read_bytes())

    result = FilterResult(
        job_id=job_id,
        strategy=STRATEGY_NAME,
        input_count=input_count,
        after_crop=after_crop,
        after_outlier=after_outlier,
        output_count=int(len(points)),
        ply_path=str(ply_path.resolve()),
        manifest_path=str((job_dir / "cloud_filtered.json").resolve()),
        warnings=warnings,
    )
    dump_filter_manifest(result, job_dir / "cloud_filtered.json")
    return result
