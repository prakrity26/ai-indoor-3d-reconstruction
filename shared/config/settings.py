"""Environment-backed settings used by preprocessing (Phase 1)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v")


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


@dataclass(frozen=True)
class PreprocessSettings:
    frames_dir: Path
    max_upload_mb: int
    min_width: int
    min_height: int
    min_duration_sec: float
    max_duration_sec: float
    min_fps: float
    target_extract_fps: float
    max_extracted_frames: int
    jpeg_quality: int
    allowed_extensions: tuple[str, ...]
    quality_sample_count: int
    dark_mean_threshold: float
    bright_mean_threshold: float
    blur_laplacian_threshold: float

    @classmethod
    def from_env(cls) -> PreprocessSettings:
        extensions = os.environ.get("ALLOWED_VIDEO_EXTENSIONS", "")
        allowed = tuple(
            item.strip().lower()
            for item in extensions.split(",")
            if item.strip()
        ) or _DEFAULT_EXTENSIONS
        allowed = tuple(
            ext if ext.startswith(".") else f".{ext}" for ext in allowed
        )
        return cls(
            frames_dir=Path(os.environ.get("FRAMES_DIR", "./data/frames")),
            max_upload_mb=_int("MAX_UPLOAD_MB", 500),
            min_width=_int("MIN_VIDEO_WIDTH", 320),
            min_height=_int("MIN_VIDEO_HEIGHT", 240),
            min_duration_sec=_float("MIN_DURATION_SEC", 1.0),
            max_duration_sec=_float("MAX_DURATION_SEC", 600.0),
            min_fps=_float("MIN_FPS", 5.0),
            target_extract_fps=_float("TARGET_EXTRACT_FPS", 5.0),
            max_extracted_frames=_int("MAX_EXTRACTED_FRAMES", 400),
            jpeg_quality=_int("FRAME_JPEG_QUALITY", 95),
            allowed_extensions=allowed,
            quality_sample_count=_int("QUALITY_SAMPLE_COUNT", 12),
            dark_mean_threshold=_float("DARK_MEAN_THRESHOLD", 12.0),
            bright_mean_threshold=_float("BRIGHT_MEAN_THRESHOLD", 245.0),
            blur_laplacian_threshold=_float("BLUR_LAPLACIAN_THRESHOLD", 20.0),
        )


def load_settings() -> PreprocessSettings:
    return PreprocessSettings.from_env()
