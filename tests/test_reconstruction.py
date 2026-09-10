"""Tests for Phase 5 depth unprojection. No Open3D and no real videos."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from model.reconstruction.backproject import prepare_depth, unproject_frame
from model.reconstruction.exceptions import ReconstructionError
from model.reconstruction.pipeline import build_point_cloud
from model.reconstruction.ply import write_ply_xyzrgb
from shared.config.settings import ReconstructionSettings


def _settings(**overrides) -> ReconstructionSettings:
    values = dict(
        stride=1,
        min_depth=0.05,
        max_depth=20.0,
        median_target=0.0,
        max_points=10000,
        output_dir=Path("./data/outputs"),
    )
    values.update(overrides)
    settings = ReconstructionSettings(**values)
    settings.validate()
    return settings


def test_unproject_identity_plane() -> None:
    depth = np.full((10, 12), 2.0, dtype=np.float32)
    color = np.zeros((10, 12, 3), dtype=np.uint8)
    color[:, :] = (0, 0, 255)
    matrix = np.eye(4)
    points, colors = unproject_frame(
        depth,
        color,
        fx=100.0,
        fy=100.0,
        cx=6.0,
        cy=5.0,
        matrix_c2w=matrix,
        settings=_settings(median_target=0.0, stride=1),
    )
    assert len(points) == 120
    np.testing.assert_allclose(points[:, 2], 2.0, atol=1e-5)
    assert (colors[:, 0] == 255).all()
    center = points.reshape(10, 12, 3)[5, 6]
    np.testing.assert_allclose(center, [0.0, 0.0, 2.0], atol=1e-5)


def test_unproject_applies_camera_translation() -> None:
    depth = np.array([[1.0]], dtype=np.float32)
    matrix = np.eye(4)
    matrix[:3, 3] = [1.0, 2.0, 3.0]
    points, _colors = unproject_frame(
        depth,
        None,
        fx=1.0,
        fy=1.0,
        cx=0.0,
        cy=0.0,
        matrix_c2w=matrix,
        settings=_settings(min_depth=0.05, median_target=0.0, stride=1),
    )
    np.testing.assert_allclose(points[0], [1.0, 2.0, 4.0], atol=1e-5)


def test_prepare_depth_shifts_negatives() -> None:
    depth = np.array([[-1.0, 1.0]], dtype=np.float32)
    prepared = prepare_depth(depth, _settings(min_depth=0.05, max_depth=20.0, median_target=0.0))
    assert np.isnan(prepared[0, 0])
    assert prepared[0, 1] == pytest.approx(2.0)


def test_write_and_build_cloud_from_job(tmp_path: Path) -> None:
    job = tmp_path / "job"
    selected = job / "selected"
    depth_dir = job / "depth"
    selected.mkdir(parents=True)
    depth_dir.mkdir()
    image = np.full((8, 10, 3), (10, 200, 30), dtype=np.uint8)
    cv2.imwrite(str(selected / "frame_000000.jpg"), image)
    np.save(depth_dir / "frame_000000.npy", np.full((8, 10), 1.5, dtype=np.float32))
    poses = {
        "job_id": "job",
        "intrinsics": {"fx": 20.0, "fy": 20.0, "cx": 5.0, "cy": 4.0, "width": 10, "height": 8},
        "cameras": [
            {
                "index": 0,
                "path": str((selected / "frame_000000.jpg").resolve()),
                "status": "reference",
                "matrix_c2w": np.eye(4).tolist(),
            }
        ],
    }
    depth = {
        "job_id": "job",
        "maps": [
            {
                "index": 0,
                "source_path": str((selected / "frame_000000.jpg").resolve()),
                "depth_path": str((depth_dir / "frame_000000.npy").resolve()),
            }
        ],
    }
    (job / "poses.json").write_text(json.dumps(poses), encoding="utf-8")
    (job / "depth.json").write_text(json.dumps(depth), encoding="utf-8")

    result = build_point_cloud(
        job,
        settings=_settings(stride=2, median_target=0.0, max_points=1000, output_dir=tmp_path / "out"),
    )
    assert result.point_count > 0
    assert Path(result.ply_path).is_file()
    assert Path(result.manifest_path).is_file()
    assert (tmp_path / "out" / "job" / "cloud.ply").is_file()


def test_missing_poses_raises(tmp_path: Path) -> None:
    job = tmp_path / "empty"
    job.mkdir()
    (job / "depth.json").write_text('{"maps":[]}\n', encoding="utf-8")
    with pytest.raises(ReconstructionError) as err:
        build_point_cloud(job, settings=_settings(output_dir=tmp_path))
    assert err.value.code == "poses_missing"


def test_ply_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "tiny.ply"
    points = np.array([[0.0, 1.0, 2.0]], dtype=np.float32)
    colors = np.array([[9, 8, 7]], dtype=np.uint8)
    write_ply_xyzrgb(path, points, colors)
    raw = path.read_bytes()
    assert raw.startswith(b"ply")
    assert b"element vertex 1" in raw
