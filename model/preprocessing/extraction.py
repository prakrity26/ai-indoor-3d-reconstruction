"""Uniform frame extraction. Adaptive selection belongs to Phase 2."""

from __future__ import annotations

import math
from pathlib import Path

import cv2

from model.preprocessing.exceptions import VideoValidationError
from model.preprocessing.types import FrameRecord, VideoInfo
from model.preprocessing.validation import open_capture
from shared.config.settings import PreprocessSettings


def compute_stride(
    frame_count: int,
    source_fps: float,
    target_fps: float,
    max_frames: int,
) -> int:
    """Uniform stride so extraction stays near target_fps and within max_frames."""
    if target_fps <= 0 or source_fps <= 0:
        stride = 1
    else:
        stride = max(1, int(round(source_fps / target_fps)))
    if frame_count > 0:
        estimated = max(1, math.ceil(frame_count / stride))
        if estimated > max_frames:
            stride = max(1, math.ceil(frame_count / max_frames))
    return stride


def extract_frames(
    path: Path,
    video: VideoInfo,
    output_dir: Path,
    settings: PreprocessSettings,
    target_fps: float | None = None,
    max_frames: int | None = None,
) -> tuple[list[FrameRecord], int, float]:
    target = settings.target_extract_fps if target_fps is None else target_fps
    budget = settings.max_extracted_frames if max_frames is None else max_frames
    stride = compute_stride(video.frame_count, video.fps, target, budget)
    output_dir.mkdir(parents=True, exist_ok=True)

    records: list[FrameRecord] = []
    with open_capture(path) as capture:
        index = 0
        extracted = 0
        while extracted < budget:
            ok, frame = capture.read()
            if not ok or frame is None:
                break
            if index % stride == 0:
                filename = f"frame_{index:06d}.jpg"
                frame_path = output_dir / filename
                written = cv2.imwrite(
                    str(frame_path),
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), settings.jpeg_quality],
                )
                if not written:
                    raise VideoValidationError(
                        "write_failed",
                        f"Could not write frame image: {frame_path}",
                    )
                timestamp = index / video.fps if video.fps > 0 else 0.0
                records.append(
                    FrameRecord(
                        index=index,
                        timestamp_sec=round(timestamp, 4),
                        path=str(frame_path.resolve()),
                    )
                )
                extracted += 1
            index += 1

    if not records:
        raise VideoValidationError(
            "no_frames",
            "Frame extraction produced no images.",
            {"path": str(path)},
        )
    return records, stride, target
