"""Cheap visual-change and sharpness scores for keyframe selection."""

from __future__ import annotations

import cv2
import numpy as np


def to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def thumbnail(gray: np.ndarray, size: int) -> np.ndarray:
    return cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)


def downscale_width(gray: np.ndarray, max_width: int) -> np.ndarray:
    height, width = gray.shape[:2]
    if width <= max_width:
        return gray
    scale = max_width / float(width)
    new_size = (max_width, max(1, int(round(height * scale))))
    return cv2.resize(gray, new_size, interpolation=cv2.INTER_AREA)


def mean_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    delta = np.abs(a.astype(np.float32) - b.astype(np.float32))
    return float(np.mean(delta) / 255.0)


def histogram_distance(a: np.ndarray, b: np.ndarray) -> float:
    hist_a = cv2.calcHist([a], [0], None, [32], [0, 256])
    hist_b = cv2.calcHist([b], [0], None, [32], [0, 256])
    cv2.normalize(hist_a, hist_a)
    cv2.normalize(hist_b, hist_b)
    correlation = float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))
    return float(1.0 - max(correlation, 0.0))


def change_score(thumb_a: np.ndarray, thumb_b: np.ndarray) -> float:
    """0 is identical; 1 is a large appearance change.

    Uses the stronger of mean absolute difference and histogram distance so
    both a camera pan (pixel shift) and a lighting/scene change are noticed.
    """
    return max(mean_abs_diff(thumb_a, thumb_b), histogram_distance(thumb_a, thumb_b))


def sharpness(gray: np.ndarray, max_width: int) -> float:
    sample = downscale_width(gray, max_width)
    return float(cv2.Laplacian(sample, cv2.CV_64F).var())
