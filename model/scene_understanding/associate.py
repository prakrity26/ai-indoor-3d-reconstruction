"""Place one detection in the reconstructed scene using depth and the camera pose."""

from __future__ import annotations

import numpy as np

from model.scene_understanding.types import DetectionBox


def backproject_box(
    depth: np.ndarray,
    box: DetectionBox,
    *,
    image_width: int,
    image_height: int,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
    matrix_c2w: np.ndarray,
) -> list[float] | None:
    """Median depth inside the box, then one world point. Scale stays relative."""
    height, width = depth.shape[:2]
    if image_width < 1 or image_height < 1 or width < 1 or height < 1:
        return None
    sx = width / float(image_width)
    sy = height / float(image_height)
    x1 = int(np.clip(box.x1 * sx, 0, width - 1))
    x2 = int(np.clip(box.x2 * sx, 0, width - 1))
    y1 = int(np.clip(box.y1 * sy, 0, height - 1))
    y2 = int(np.clip(box.y2 * sy, 0, height - 1))
    if x2 <= x1 or y2 <= y1:
        return None
    patch = np.asarray(depth[y1:y2, x1:x2], dtype=np.float32)
    finite = patch[np.isfinite(patch)]
    if finite.size == 0:
        return None
    z = float(np.median(finite))
    if z <= 1e-4:
        return None
    u = (x1 + x2) * 0.5
    v = (y1 + y2) * 0.5
    # Intrinsics are for the original frame. Scale them with the depth map.
    cam = np.array(
        [(u - cx * sx) / (fx * sx) * z, (v - cy * sy) / (fy * sy) * z, z],
        dtype=np.float64,
    )
    rotation = np.asarray(matrix_c2w, dtype=np.float64)[:3, :3]
    translation = np.asarray(matrix_c2w, dtype=np.float64)[:3, 3]
    world = rotation @ cam + translation
    if not np.isfinite(world).all():
        return None
    return [float(world[0]), float(world[1]), float(world[2])]
