"""Filesystem and OpenCV checks that decide whether a video can be ingested."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import cv2

from model.preprocessing.exceptions import VideoValidationError
from model.preprocessing.types import ValidationIssue, VideoInfo
from shared.config.settings import PreprocessSettings


def fourcc_to_str(value: float) -> str:
    code = int(value)
    chars = "".join(chr((code >> (8 * i)) & 0xFF) for i in range(4))
    cleaned = "".join(ch if ch.isprintable() else "" for ch in chars).strip()
    return cleaned or "unknown"


@contextmanager
def open_capture(path: Path) -> Iterator[cv2.VideoCapture]:
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise VideoValidationError(
                "unreadable",
                "OpenCV could not open the file as a video.",
                {"path": str(path)},
            )
        yield capture
    finally:
        capture.release()


def probe_video(path: Path) -> VideoInfo:
    size_bytes = path.stat().st_size
    with open_capture(path) as capture:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        codec = fourcc_to_str(capture.get(cv2.CAP_PROP_FOURCC) or 0)
        ok, _frame = capture.read()
        if not ok or width <= 0 or height <= 0:
            raise VideoValidationError(
                "no_frames",
                "The file opened but no decodable video frame was found.",
                {"path": str(path), "width": width, "height": height},
            )
        if fps <= 0:
            fps = 0.0
        if frame_count < 1:
            frame_count = 1
        duration_sec = frame_count / fps if fps > 0 else 0.0
        return VideoInfo(
            path=str(path.resolve()),
            size_bytes=size_bytes,
            width=width,
            height=height,
            fps=round(fps, 4),
            frame_count=frame_count,
            duration_sec=round(duration_sec, 4),
            codec=codec,
        )


def validate_video(path: Path, settings: PreprocessSettings) -> tuple[VideoInfo, list[ValidationIssue]]:
    """Return probe metadata or raise VideoValidationError."""
    warnings: list[ValidationIssue] = []
    if not path.exists():
        raise VideoValidationError("file_not_found", f"Video not found: {path}")
    if not path.is_file():
        raise VideoValidationError("not_a_file", f"Path is not a file: {path}")

    size_bytes = path.stat().st_size
    if size_bytes <= 0:
        raise VideoValidationError("empty_file", "The video file is empty.")

    max_bytes = settings.max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise VideoValidationError(
            "file_too_large",
            f"File is {size_bytes} bytes; limit is {settings.max_upload_mb} MB.",
            {"size_bytes": size_bytes, "max_upload_mb": settings.max_upload_mb},
        )

    suffix = path.suffix.lower()
    if suffix not in settings.allowed_extensions:
        raise VideoValidationError(
            "unsupported_extension",
            f"Extension {suffix or '(none)'} is not allowed.",
            {"allowed": list(settings.allowed_extensions)},
        )

    info = probe_video(path)

    if info.width < settings.min_width or info.height < settings.min_height:
        raise VideoValidationError(
            "resolution_too_low",
            (
                f"Resolution {info.width}x{info.height} is below "
                f"{settings.min_width}x{settings.min_height}."
            ),
            {"width": info.width, "height": info.height},
        )

    if info.fps < settings.min_fps:
        raise VideoValidationError(
            "invalid_fps",
            f"Frame rate {info.fps} fps is below the minimum {settings.min_fps}.",
            {"fps": info.fps, "min_fps": settings.min_fps},
        )

    if info.duration_sec < settings.min_duration_sec:
        raise VideoValidationError(
            "duration_too_short",
            (
                f"Duration {info.duration_sec:.2f}s is shorter than "
                f"{settings.min_duration_sec:.2f}s."
            ),
            {"duration_sec": info.duration_sec},
        )

    if info.duration_sec > settings.max_duration_sec:
        raise VideoValidationError(
            "duration_too_long",
            (
                f"Duration {info.duration_sec:.2f}s exceeds "
                f"{settings.max_duration_sec:.2f}s."
            ),
            {"duration_sec": info.duration_sec},
        )

    return info, warnings
