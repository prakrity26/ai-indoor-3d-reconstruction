"""Dense JPEG frames for COLMAP / Gaussian splat training."""

from __future__ import annotations

import uuid
from pathlib import Path

import cv2

from model.preprocessing.exceptions import VideoValidationError
from model.preprocessing.extraction import extract_frames
from model.preprocessing.validation import validate_video
from model.splat.exceptions import SplatError
from shared.config.settings import PreprocessSettings, SplatSettings, load_settings


def prepare_splat_images(
    video_path: str | Path,
    *,
    job_id: str | None = None,
    frames_dir: str | Path | None = None,
    settings: SplatSettings | None = None,
    preprocess: PreprocessSettings | None = None,
) -> tuple[str, Path, int]:
    """Extract overlapping JPEGs into ``<job>/splat/images``.

    This reuses Phase 1 decode, but at a higher frame rate than the mesh path.
    """
    from shared.config.settings import load_splat_settings

    settings = settings or load_splat_settings()
    preprocess = preprocess or load_settings()
    path = Path(video_path)
    try:
        info, _warnings = validate_video(path, preprocess)
    except VideoValidationError as exc:
        raise SplatError(exc.code, exc.message, exc.details) from exc

    job = job_id or uuid.uuid4().hex[:12]
    root = Path(frames_dir) if frames_dir is not None else preprocess.frames_dir
    image_dir = root / job / "splat" / "images"
    records, _stride, _fps = extract_frames(
        path,
        info,
        image_dir,
        preprocess,
        target_fps=settings.extract_fps,
        max_frames=settings.max_frames,
    )
    _maybe_downscale_images(image_dir, settings.image_max_size)
    return job, image_dir.resolve(), len(records)


def _maybe_downscale_images(image_dir: Path, max_size: int) -> None:
    for jpeg in sorted(image_dir.glob("*.jpg")):
        image = cv2.imread(str(jpeg))
        if image is None:
            continue
        height, width = image.shape[:2]
        long_edge = max(height, width)
        if long_edge <= max_size:
            continue
        scale = max_size / float(long_edge)
        resized = cv2.resize(
            image,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
        cv2.imwrite(str(jpeg), resized)
