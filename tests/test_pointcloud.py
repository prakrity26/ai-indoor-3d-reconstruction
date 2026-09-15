"""Tests for Phase 6 crop and Open3D statistical/voxel filtering."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from model.pointcloud.exceptions import PointCloudError
from model.pointcloud.filters import crop_percentile
from model.pointcloud.pipeline import filter_point_cloud
from model.reconstruction.ply import write_ply_xyzrgb
from shared.config.settings import PointCloudFilterSettings


def _settings(tmp_path: Path, **overrides) -> PointCloudFilterSettings:
    values = dict(
        nb_neighbors=8,
        std_ratio=1.5,
        voxel_size=0.02,
        crop_percentile=2.0,
        min_points=10,
        output_dir=tmp_path / "outputs",
    )
    values.update(overrides)
    settings = PointCloudFilterSettings(**values)
    settings.validate()
    return settings


def test_crop_percentile_drops_far_flyers() -> None:
    rng = np.random.default_rng(0)
    core = rng.normal(0.0, 0.05, size=(200, 3)).astype(np.float32)
    flyers = np.array([[50.0, 0.0, 0.0], [-40.0, 20.0, 30.0]], dtype=np.float32)
    points = np.vstack([core, flyers])
    colors = np.full((len(points), 3), 120, dtype=np.uint8)
    cropped, _ = crop_percentile(points, colors, 2.0)
    assert len(cropped) < len(points)
    assert np.max(np.abs(cropped)) < 5.0


def test_missing_cloud_raises(tmp_path: Path) -> None:
    job = tmp_path / "empty"
    job.mkdir()
    with pytest.raises(PointCloudError) as err:
        filter_point_cloud(job, settings=_settings(tmp_path))
    assert err.value.code == "cloud_missing"


def test_filters_noisy_cluster(tmp_path: Path) -> None:
    pytest.importorskip("open3d")
    rng = np.random.default_rng(1)
    core = rng.normal(0.0, 0.03, size=(400, 3)).astype(np.float32)
    noise = rng.uniform(-3.0, 3.0, size=(40, 3)).astype(np.float32)
    points = np.vstack([core, noise])
    colors = np.full((len(points), 3), (20, 180, 40), dtype=np.uint8)
    job = tmp_path / "job"
    job.mkdir()
    write_ply_xyzrgb(job / "cloud.ply", points, colors)
    (job / "cloud.json").write_text('{"job_id":"job"}\n', encoding="utf-8")

    result = filter_point_cloud(job, settings=_settings(tmp_path, min_points=20))
    assert result.output_count < result.input_count
    assert result.output_count >= 20
    assert Path(result.ply_path).is_file()
    assert Path(result.manifest_path).is_file()
    assert (tmp_path / "outputs" / "job" / "cloud_filtered.ply").is_file()
    assert result.after_crop <= result.input_count
    assert result.output_count <= result.after_outlier
