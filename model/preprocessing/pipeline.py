"""Phase 1 ingestion: validate a video, estimate quality, extract frames."""

from __future__ import annotations

import uuid
from pathlib import Path

from model.preprocessing.extraction import extract_frames
from model.preprocessing.quality import assess_quality
from model.preprocessing.types import PreprocessResult, dump_manifest
from model.preprocessing.validation import validate_video
from shared.config.settings import PreprocessSettings, load_settings


def ingest_video(
    video_path: str | Path,
    *,
    job_id: str | None = None,
    frames_dir: str | Path | None = None,
    target_fps: float | None = None,
    max_frames: int | None = None,
    settings: PreprocessSettings | None = None,
) -> PreprocessResult:
    """Validate `video_path` and write uniformly sampled JPEG frames.

    Adaptive keyframe selection is intentionally not performed here (Phase 2).
    """
    settings = settings or load_settings()
    path = Path(video_path)
    info, warnings = validate_video(path, settings)
    quality, quality_warnings = assess_quality(str(path), info, settings)
    warnings.extend(quality_warnings)

    job = job_id or uuid.uuid4().hex[:12]
    root = Path(frames_dir) if frames_dir is not None else settings.frames_dir
    job_dir = root / job / "frames"
    records, stride, used_target = extract_frames(
        path,
        info,
        job_dir,
        settings,
        target_fps=target_fps,
        max_frames=max_frames,
    )

    manifest_path = job_dir.parent / "manifest.json"
    result = PreprocessResult(
        job_id=job,
        video=info,
        quality=quality,
        warnings=warnings,
        frames=records,
        stride=stride,
        target_fps=used_target,
        frames_dir=str(job_dir.resolve()),
        manifest_path=str(manifest_path.resolve()),
    )
    dump_manifest(result, manifest_path)
    return result
