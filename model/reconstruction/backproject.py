"""Unproject a depth map into camera, then world, coordinates."""

from __future__ import annotations

import numpy as np

from shared.config.settings import ReconstructionSettings


def prepare_depth(depth: np.ndarray, settings: ReconstructionSettings) -> np.ndarray:
    """Shift/clip relative depth so Z is positive and roughly scaled per view."""
    z = np.asarray(depth, dtype=np.float32)
    finite = np.isfinite(z)
    if not np.any(finite):
        return np.full(z.shape, np.nan, dtype=np.float32)
    if float(np.nanmin(z)) < 0:
        z = z - float(np.nanmin(z))
    z = np.where(finite, z, np.nan)
    if settings.median_target > 0:
        valid = z[np.isfinite(z) & (z > 0)]
        if valid.size:
            median = float(np.median(valid))
            if median > 1e-6:
                z = z * (settings.median_target / median)
    z = np.where((z >= settings.min_depth) & (z <= settings.max_depth), z, np.nan)
    return z.astype(np.float32)


def unproject_frame(
    depth: np.ndarray,
    color_bgr: np.ndarray | None,
    fx: float,
    fy: float,
    cx: float,
    cy: float,
    matrix_c2w: np.ndarray,
    settings: ReconstructionSettings,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (N,3) world points and (N,3) uint8 RGB."""
    z = prepare_depth(depth, settings)
    height, width = z.shape[:2]
    stride = settings.stride
    vs = np.arange(0, height, stride, dtype=np.int32)
    us = np.arange(0, width, stride, dtype=np.int32)
    uu, vv = np.meshgrid(us, vs)
    zz = z[vv, uu]
    keep = np.isfinite(zz)
    if not np.any(keep):
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.uint8)

    u = uu[keep].astype(np.float32)
    v = vv[keep].astype(np.float32)
    depth_z = zz[keep]
    x = (u - cx) / fx * depth_z
    y = (v - cy) / fy * depth_z
    cam = np.stack([x, y, depth_z], axis=1)
    finite_cam = np.isfinite(cam).all(axis=1) & (np.abs(cam).max(axis=1) < 1e4)
    cam = cam[finite_cam]
    if color_bgr is None or color_bgr.shape[:2] != (height, width):
        rgb = np.full((len(cam), 3), 180, dtype=np.uint8)
    else:
        bgr = color_bgr[vv, uu][keep][finite_cam]
        rgb = bgr[:, ::-1].copy()
    if len(cam) == 0:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.uint8)
    rotation = matrix_c2w[:3, :3]
    translation = matrix_c2w[:3, 3]
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        world = (rotation @ cam.T).T + translation
    finite_world = np.isfinite(world).all(axis=1) & (np.abs(world).max(axis=1) < 1e4)
    return world[finite_world].astype(np.float32), rgb[finite_world].astype(np.uint8)


def subsample_points(
    points: np.ndarray,
    colors: np.ndarray,
    max_points: int,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    if len(points) <= max_points:
        return points, colors
    generator = rng or np.random.default_rng(0)
    choice = generator.choice(len(points), size=max_points, replace=False)
    choice.sort()
    return points[choice], colors[choice]
