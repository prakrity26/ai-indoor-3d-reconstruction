"""Depth estimator protocol and a local synthetic backend for tests."""

from __future__ import annotations

from typing import Protocol

import numpy as np


class DepthEstimator(Protocol):
    name: str

    def infer(self, image_bgr: np.ndarray) -> np.ndarray:
        """Return an HxW float32 depth map. Larger values are farther."""
        ...


class GradientDepthEstimator:
    """Deterministic stand-in. Does not download weights or videos."""

    name = "synthetic_gradient"

    def infer(self, image_bgr: np.ndarray) -> np.ndarray:
        height, width = image_bgr.shape[:2]
        columns = np.linspace(0.2, 1.0, num=width, dtype=np.float32)
        rows = np.linspace(0.9, 0.4, num=height, dtype=np.float32)
        grid = rows[:, None] * 0.35 + columns[None, :]
        gray = image_bgr.mean(axis=2).astype(np.float32) / 255.0
        return (grid + 0.15 * (1.0 - gray)).astype(np.float32)
