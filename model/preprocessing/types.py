"""Dataclasses for Phase 1 video probe, quality, and extraction results."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VideoInfo:
    path: str
    size_bytes: int
    width: int
    height: int
    fps: float
    frame_count: int
    duration_sec: float
    codec: str


@dataclass(frozen=True)
class QualityMetrics:
    sample_count: int
    mean_brightness: float
    mean_laplacian_variance: float
    likely_dark: bool
    likely_bright: bool
    likely_blurry: bool


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class FrameRecord:
    index: int
    timestamp_sec: float
    path: str


@dataclass
class PreprocessResult:
    job_id: str
    video: VideoInfo
    quality: QualityMetrics
    warnings: list[ValidationIssue] = field(default_factory=list)
    frames: list[FrameRecord] = field(default_factory=list)
    stride: int = 1
    target_fps: float = 0.0
    frames_dir: str = ""
    manifest_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["frame_count_extracted"] = len(self.frames)
        return payload


def dump_manifest(result: PreprocessResult, path: Path) -> None:
    import json

    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
