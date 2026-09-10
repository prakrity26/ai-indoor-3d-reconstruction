"""OpenCV essential-matrix pose and monocular scale chaining."""

from __future__ import annotations

import cv2
import numpy as np

from model.camera.types import Intrinsics
from shared.config.settings import CameraPoseSettings


def rotation_y(degrees: float) -> np.ndarray:
    angle = np.radians(degrees)
    cosine, sine = np.cos(angle), np.sin(angle)
    return np.array(
        [[cosine, 0.0, sine], [0.0, 1.0, 0.0], [-sine, 0.0, cosine]],
        dtype=np.float64,
    )


def make_intrinsics(
    width: int,
    height: int,
    settings: CameraPoseSettings,
) -> Intrinsics:
    fx = settings.fx if settings.fx is not None else settings.focal_scale * max(width, height)
    fy = settings.fy if settings.fy is not None else fx
    cx = settings.cx if settings.cx is not None else width / 2.0
    cy = settings.cy if settings.cy is not None else height / 2.0
    return Intrinsics(fx=float(fx), fy=float(fy), cx=float(cx), cy=float(cy), width=width, height=height)


def k_matrix(intrinsics: Intrinsics) -> np.ndarray:
    return np.array(intrinsics.matrix(), dtype=np.float64)


def camera_center(rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    return -rotation.T @ translation.reshape(3)


def matrix_c2w(rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    transform = np.eye(4, dtype=np.float64)
    transform[:3, :3] = rotation.T
    transform[:3, 3] = camera_center(rotation, translation)
    return transform


def compose_w2c(
    rotation_prev: np.ndarray,
    translation_prev: np.ndarray,
    rotation_rel: np.ndarray,
    translation_rel: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    rotation = rotation_rel @ rotation_prev
    translation = rotation_rel @ translation_prev.reshape(3) + translation_rel.reshape(3)
    return rotation, translation


def rotation_angle_deg(rotation_a: np.ndarray, rotation_b: np.ndarray) -> float:
    delta = rotation_a @ rotation_b.T
    cosine = float(np.clip((np.trace(delta) - 1.0) / 2.0, -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def direction_cosine(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    a = vector_a.reshape(3)
    b = vector_b.reshape(3)
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def estimate_relative_pose(
    points_a: np.ndarray,
    points_b: np.ndarray,
    intrinsics: Intrinsics,
    settings: CameraPoseSettings,
) -> tuple[np.ndarray, np.ndarray, int, np.ndarray] | None:
    if len(points_a) < settings.min_matches:
        return None
    camera = k_matrix(intrinsics)
    essential, mask = cv2.findEssentialMat(
        points_a,
        points_b,
        camera,
        method=cv2.RANSAC,
        prob=0.999,
        threshold=settings.ransac_thresh,
    )
    if essential is None or mask is None:
        return None
    inlier_mask = mask.ravel().astype(np.uint8)
    _, rotation, translation, pose_mask = cv2.recoverPose(
        essential,
        points_a,
        points_b,
        camera,
        mask=inlier_mask,
    )
    inliers = int(np.count_nonzero(pose_mask))
    if inliers < settings.min_inliers:
        return None
    kept = pose_mask.ravel().astype(bool)
    return rotation, translation.reshape(3), inliers, kept


def triangulate_points(
    intrinsics: Intrinsics,
    rotation_a: np.ndarray,
    translation_a: np.ndarray,
    rotation_b: np.ndarray,
    translation_b: np.ndarray,
    points_a: np.ndarray,
    points_b: np.ndarray,
) -> np.ndarray:
    camera = k_matrix(intrinsics)
    proj_a = camera @ np.hstack([rotation_a, translation_a.reshape(3, 1)])
    proj_b = camera @ np.hstack([rotation_b, translation_b.reshape(3, 1)])
    homogeneous = cv2.triangulatePoints(proj_a, proj_b, points_a.T, points_b.T)
    weight = homogeneous[3]
    points = np.full((homogeneous.shape[1], 3), np.nan, dtype=np.float64)
    valid = np.abs(weight) > 1e-8
    if np.any(valid):
        with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
            candidate = (homogeneous[:3, valid] / weight[valid]).T
        finite = np.isfinite(candidate).all(axis=1)
        bounded = np.linalg.norm(np.nan_to_num(candidate, nan=0.0, posinf=0.0, neginf=0.0), axis=1) < 1e4
        keep = finite & bounded
        valid_idx = np.flatnonzero(valid)
        points[valid_idx[keep]] = candidate[keep]
    return points


def positive_depth_mask(
    rotation: np.ndarray,
    translation: np.ndarray,
    points_world: np.ndarray,
) -> np.ndarray:
    points = np.asarray(points_world, dtype=np.float64)
    result = np.zeros(len(points), dtype=bool)
    finite = np.isfinite(points).all(axis=1)
    magnitudes = np.linalg.norm(
        np.nan_to_num(points, nan=0.0, posinf=0.0, neginf=0.0),
        axis=1,
    )
    finite &= magnitudes < 1e4
    if not np.any(finite):
        return result
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        camera_points = (rotation @ points[finite].T).T + translation.reshape(3)
    depth = camera_points[:, 2]
    result[finite] = np.isfinite(depth) & (depth > 0)
    return result


def scale_from_prior_points(
    prior_world: np.ndarray,
    unit_world: np.ndarray,
    center: np.ndarray,
) -> float | None:
    if len(prior_world) < 4 or len(unit_world) < 4:
        return None
    count = min(len(prior_world), len(unit_world))
    prior_dist = np.linalg.norm(prior_world[:count] - center.reshape(3), axis=1)
    unit_dist = np.linalg.norm(unit_world[:count] - center.reshape(3), axis=1)
    valid = (
        np.isfinite(prior_world).all(axis=1)
        & np.isfinite(unit_world).all(axis=1)
        & (prior_dist > 1e-8)
        & (unit_dist > 1e-8)
    )
    if int(np.count_nonzero(valid)) < 4:
        return None
    ratios = prior_dist[valid] / unit_dist[valid]
    scale = float(np.median(ratios))
    if not np.isfinite(scale) or scale <= 1e-6:
        return None
    return scale
