"""Tests for Phase 2 adaptive keyframe selection."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from model.frame_selection.exceptions import FrameSelectionError
from model.frame_selection.metrics import change_score, thumbnail, to_gray
from model.frame_selection.pipeline import select_keyframes
from model.frame_selection.selection import select_indices
from model.preprocessing.pipeline import ingest_video
from shared.config.settings import FrameSelectionSettings, PreprocessSettings


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


def _selection_settings(**overrides) -> FrameSelectionSettings:
    values = dict(
        min_count=3,
        max_count=20,
        min_gap=1,
        max_gap=4,
        diff_threshold=0.08,
        thumbnail_size=32,
        sharpness_width=64,
    )
    values.update(overrides)
    settings = FrameSelectionSettings(**values)
    settings.validate()
    return settings


def _preprocess_settings(tmp_path: Path) -> PreprocessSettings:
    base = PreprocessSettings.from_env()
    values = base.__dict__.copy()
    values["frames_dir"] = tmp_path / "frames"
    return PreprocessSettings(**values)


def write_jpeg(path: Path, color: tuple[int, int, int], *, edges: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = np.full((120, 160, 3), color, dtype=np.uint8)
    if edges:
        cv2.rectangle(frame, (20, 20), (80, 80), (255, 255, 255), 2)
        cv2.line(frame, (10, 10), (150, 110), (0, 0, 0), 2)
    cv2.imwrite(str(path), frame)
    return path


def test_identical_frames_drop_redundancy(tmp_path: Path) -> None:
    job = tmp_path / "static"
    frames_dir = job / "frames"
    for i in range(12):
        write_jpeg(frames_dir / f"frame_{i:06d}.jpg", (40, 180, 40))

    result = select_keyframes(job, settings=_selection_settings(min_count=3, max_gap=4))
    assert result.input_count == 12
    assert len(result.selected) < 12
    assert result.selected[0].index == 0
    assert result.selected[-1].index == 11
    assert Path(result.selection_path).is_file()
    assert Path(result.selected[0].path).is_file()


def test_changing_frames_keep_content_shifts(tmp_path: Path) -> None:
    job = tmp_path / "pan"
    frames_dir = job / "frames"
    colors = [
        (0, 0, 255),
        (0, 255, 0),
        (255, 0, 0),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
        (30, 30, 30),
        (220, 220, 220),
    ]
    for i, color in enumerate(colors):
        write_jpeg(frames_dir / f"frame_{i:06d}.jpg", color)

    result = select_keyframes(job, settings=_selection_settings(min_count=3, max_count=20))
    assert len(result.selected) == len(colors)
    assert {item.reason for item in result.selected} >= {"first", "content_change"}


def test_max_count_caps_selection(tmp_path: Path) -> None:
    job = tmp_path / "budget"
    frames_dir = job / "frames"
    for i in range(10):
        color = (int(i * 24), 40, 200 - i * 12)
        write_jpeg(frames_dir / f"frame_{i:06d}.jpg", color)

    result = select_keyframes(
        job,
        settings=_selection_settings(min_count=3, max_count=4, diff_threshold=0.01),
    )
    assert len(result.selected) == 4
    assert result.selected[0].index == 0
    assert result.selected[-1].index == 9


def test_min_count_fills_coverage(tmp_path: Path) -> None:
    job = tmp_path / "fill"
    frames_dir = job / "frames"
    for i in range(10):
        write_jpeg(frames_dir / f"frame_{i:06d}.jpg", (80, 80, 80))

    result = select_keyframes(
        job,
        settings=_selection_settings(min_count=6, max_gap=20, max_count=10),
    )
    assert len(result.selected) == 6
    assert any(item.reason == "coverage_fill" for item in result.selected)


def test_max_gap_prefers_sharper_frame() -> None:
    blurry = np.full((32, 32), 40, dtype=np.uint8)
    sharp = blurry.copy()
    cv2.rectangle(sharp, (4, 4), (28, 28), 220, 2)
    thumbs = [thumbnail(blurry, 32) for _ in range(5)]
    sharpness_values = [1.0, 1.0, 1.0, 50.0, 1.0]
    thumbs[3] = thumbnail(sharp, 32)

    chosen = select_indices(
        thumbs,
        sharpness_values,
        _selection_settings(min_count=2, max_count=10, max_gap=4, diff_threshold=0.9),
    )
    indices = [item[0] for item in chosen]
    assert 0 in indices
    assert 4 in indices
    assert 3 in indices
    reasons = {item[0]: item[1] for item in chosen}
    assert reasons[3] == "max_gap"


def test_change_score_identical_is_zero() -> None:
    image = np.full((48, 48, 3), 90, dtype=np.uint8)
    thumb = thumbnail(to_gray(image), 32)
    assert change_score(thumb, thumb) == 0.0


def test_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(FrameSelectionError) as err:
        select_keyframes(tmp_path / "missing")
    assert err.value.code == "source_not_found"


def test_empty_directory_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FrameSelectionError) as err:
        select_keyframes(empty)
    assert err.value.code == "empty_frames"


def test_selects_after_phase1_ingest(tmp_path: Path) -> None:
    video = write_video(
        tmp_path / "still.avi",
        n_frames=24,
        fps=8,
        moving=False,
    )
    preprocess = ingest_video(
        video,
        job_id="phase2job",
        settings=_preprocess_settings(tmp_path),
        target_fps=8,
        max_frames=50,
    )
    result = select_keyframes(
        Path(preprocess.manifest_path).parent,
        settings=_selection_settings(min_count=3, max_gap=5),
    )
    assert result.job_id == "phase2job"
    assert result.input_count == len(preprocess.frames)
    assert 3 <= len(result.selected) < len(preprocess.frames)
