"""Monocular depth estimation (Phase 4)."""

from model.depth.exceptions import DepthEstimationError
from model.depth.pipeline import estimate_depth

__all__ = ["DepthEstimationError", "estimate_depth"]
