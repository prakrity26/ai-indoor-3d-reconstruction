"""Cheap video quality estimates from evenly spaced decoded frames."""

from __future__ import annotations

import cv2
import numpy as np

from model.preprocessing.exceptions import VideoValidationError
from model.preprocessing.types import QualityMetrics, ValidationIssue, VideoInfo
from model.preprocessing.validation import open_capture
from shared.config.settings import PreprocessSettings


def _sample_indices(frame_count: int, sample_count: int) -> list[int]:
    if frame_count <= 0:
        return [0]
    count = min(sample_count, frame_count)
    if count == 1:
        return [0]
    return [
        int(round(i * (frame_count - 1) / (count - 1)))
        for i in range(count)
    ]


def assess_quality(
    path: str,
    video: VideoInfo,
    settings: PreprocessSettings,
) -> tuple[QualityMetrics, list[ValidationIssue]]:
    warnings: list[ValidationIssue] = []
    indices = _sample_indices(video.frame_count, settings.quality_sample_count)
    brightness_values: list[float] = []
    laplacian_values: list[float] = []

    with open_capture(path) as capture:
        for index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, float(index))
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness_values.append(float(np.mean(gray)))
            laplacian_values.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))

    if not brightness_values:
        raise VideoValidationError(
            "no_frames",
            "Quality assessment could not decode any sample frames.",
            {"path": path},
        )

    mean_brightness = float(np.mean(brightness_values))
    mean_laplacian = float(np.mean(laplacian_values))
    likely_dark = mean_brightness < settings.dark_mean_threshold
    likely_bright = mean_brightness > settings.bright_mean_threshold
    likely_blurry = mean_laplacian < settings.blur_laplacian_threshold

    if likely_dark:
        if mean_brightness < settings.dark_mean_threshold / 2:
            raise VideoValidationError(
                "too_dark",
                "Sampled frames are too dark to reconstruct reliably.",
                {"mean_brightness": round(mean_brightness, 3)},
            )
        warnings.append(
            ValidationIssue(
                "warning",
                "likely_dark",
                "Sampled frames are dark; reconstruction quality may drop.",
            )
        )
    if likely_bright:
        warnings.append(
            ValidationIssue(
                "warning",
                "likely_bright",
                "Sampled frames are very bright; detail may be clipped.",
            )
        )
    if likely_blurry:
        warnings.append(
            ValidationIssue(
                "warning",
                "likely_blurry",
                "Sampled frames look blurry; camera motion or focus may be poor.",
            )
        )

    metrics = QualityMetrics(
        sample_count=len(brightness_values),
        mean_brightness=round(mean_brightness, 3),
        mean_laplacian_variance=round(mean_laplacian, 3),
        likely_dark=likely_dark,
        likely_bright=likely_bright,
        likely_blurry=likely_blurry,
    )
    return metrics, warnings
