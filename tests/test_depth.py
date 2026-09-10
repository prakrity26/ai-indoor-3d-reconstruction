"""Tests for Phase 4 depth. Uses a local fake estimator — no Hugging Face video or weights."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from model.depth.device import resolve_torch_device
from model.depth.estimator import GradientDepthEstimator
from model.depth.exceptions import DepthEstimationError
from model.depth.pipeline import estimate_depth
from shared.config.settings import DepthSettings


def _settings(**overrides) -> DepthSettings:
    values = dict(
        model_id="local-fake",
        local_files_only=True,
        max_size=256,
        write_preview=True,
        compute_device="cpu",
    )
    values.update(overrides)
    settings = DepthSettings(**values)
    settings.validate()
    return settings


def _write_jpeg(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((48, 64, 3), color, dtype=np.uint8)
    cv2.circle(image, (20, 24), 8, (255, 255, 255), -1)
    cv2.imwrite(str(path), image)


def test_resolve_device_auto_prefers_cuda_then_mps() -> None:
    assert resolve_torch_device("auto", cuda=True, mps=True) == "cuda"
    assert resolve_torch_device("auto", cuda=False, mps=True) == "mps"
    assert resolve_torch_device("auto", cuda=False, mps=False) == "cpu"
    assert resolve_torch_device("mps", cuda=True, mps=False) == "cpu"


def test_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(DepthEstimationError) as err:
        estimate_depth(tmp_path / "missing", settings=_settings(), estimator=GradientDepthEstimator())
    assert err.value.code == "source_not_found"


def test_empty_directory_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(DepthEstimationError) as err:
        estimate_depth(empty, settings=_settings(), estimator=GradientDepthEstimator())
    assert err.value.code == "empty_frames"


def test_writes_depth_maps_from_local_frames(tmp_path: Path) -> None:
    job = tmp_path / "room"
    frames = job / "selected"
    _write_jpeg(frames / "frame_000000.jpg", (30, 80, 30))
    _write_jpeg(frames / "frame_000001.jpg", (30, 80, 180))

    result = estimate_depth(
        job,
        settings=_settings(),
        estimator=GradientDepthEstimator(),
    )
    assert result.strategy == "synthetic_gradient"
    assert len(result.maps) == 2
    depth = np.load(result.maps[0].depth_path)
    assert depth.shape == (48, 64)
    assert Path(result.manifest_path).is_file()
    assert result.maps[0].preview_path is not None
    assert Path(result.maps[0].preview_path).is_file()
    assert result.maps[0].max_value > result.maps[0].min_value


def test_prefers_posed_cameras_when_poses_exist(tmp_path: Path) -> None:
    job = tmp_path / "posed"
    selected = job / "selected"
    first = selected / "frame_000000.jpg"
    second = selected / "frame_000001.jpg"
    third = selected / "frame_000002.jpg"
    _write_jpeg(first, (10, 10, 10))
    _write_jpeg(second, (20, 20, 20))
    _write_jpeg(third, (30, 30, 30))
    job.joinpath("poses.json").write_text(
        (
            '{"cameras":['
            f'{{"path":"{first.resolve()}","status":"reference"}},'
            f'{{"path":"{second.resolve()}","status":"estimated"}},'
            f'{{"path":"{third.resolve()}","status":"failed"}}'
            "]}\n"
        ),
        encoding="utf-8",
    )
    result = estimate_depth(job, settings=_settings(), estimator=GradientDepthEstimator())
    assert len(result.maps) == 2
    assert all("frame_000002" not in item.source_path for item in result.maps)
