"""Tests for Phase 1 video validation and uniform frame extraction."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from model.preprocessing.exceptions import VideoValidationError
from model.preprocessing.extraction import compute_stride
from model.preprocessing.pipeline import ingest_video
from shared.config.settings import PreprocessSettings


def _settings(**overrides) -> PreprocessSettings:
    base = PreprocessSettings.from_env()
    values = base.__dict__.copy()
    values.update(overrides)
    return PreprocessSettings(**values)


def write_video(
    path: Path,
    *,
    n_frames: int = 20,
    size: tuple[int, int] = (640, 480),
    fps: int = 10,
    color: tuple[int, int, int] = (40, 180, 40),
    moving: bool = True,
) -> Path:
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    writer = cv2.VideoWriter(str(path), fourcc, float(fps), size)
    assert writer.isOpened(), "OpenCV could not create a test video"
    width, height = size
    for i in range(n_frames):
        frame = np.full((height, width, 3), color, dtype=np.uint8)
        if moving:
            x = (i * 12) % max(1, width - 50)
            cv2.rectangle(frame, (x, 40), (x + 40, 90), (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    return path


@pytest.fixture
def settings(tmp_path: Path) -> PreprocessSettings:
    return _settings(frames_dir=tmp_path / "frames")


def test_valid_video_extracts_frames_and_manifest(tmp_path: Path, settings: PreprocessSettings) -> None:
    video = write_video(tmp_path / "room.avi")
    result = ingest_video(
        video,
        job_id="testjob",
        settings=settings,
        target_fps=5,
        max_frames=50,
    )
    assert result.job_id == "testjob"
    assert result.video.width == 640
    assert result.video.height == 480
    assert len(result.frames) >= 2
    assert Path(result.frames[0].path).is_file()
    assert Path(result.manifest_path).is_file()
    assert result.stride >= 1


def test_missing_file_raises(settings: PreprocessSettings) -> None:
    with pytest.raises(VideoValidationError) as err:
        ingest_video("does-not-exist.mp4", settings=settings)
    assert err.value.code == "file_not_found"


def test_unsupported_extension_raises(tmp_path: Path, settings: PreprocessSettings) -> None:
    fake = tmp_path / "notes.txt"
    fake.write_text("not a video")
    with pytest.raises(VideoValidationError) as err:
        ingest_video(fake, settings=settings)
    assert err.value.code == "unsupported_extension"


def test_empty_file_raises(tmp_path: Path, settings: PreprocessSettings) -> None:
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    with pytest.raises(VideoValidationError) as err:
        ingest_video(empty, settings=settings)
    assert err.value.code == "empty_file"


def test_low_resolution_raises(tmp_path: Path, settings: PreprocessSettings) -> None:
    video = write_video(tmp_path / "tiny.avi", size=(80, 60))
    with pytest.raises(VideoValidationError) as err:
        ingest_video(video, settings=settings)
    assert err.value.code == "resolution_too_low"


def test_too_dark_raises(tmp_path: Path, settings: PreprocessSettings) -> None:
    video = write_video(
        tmp_path / "dark.avi",
        color=(0, 0, 0),
        moving=False,
    )
    with pytest.raises(VideoValidationError) as err:
        ingest_video(video, settings=settings)
    assert err.value.code == "too_dark"


def test_compute_stride_respects_max_frames() -> None:
    stride = compute_stride(frame_count=1000, source_fps=30, target_fps=5, max_frames=50)
    assert stride >= 20
    assert 1000 / stride <= 50 + 1e-6
