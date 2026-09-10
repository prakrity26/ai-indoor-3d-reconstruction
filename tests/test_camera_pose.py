"""Tests for Phase 3 OpenCV ORB + essential-matrix pose."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from model.camera.exceptions import CameraPoseError
from model.camera.geometry import (
    compose_w2c,
    direction_cosine,
    make_intrinsics,
    rotation_angle_deg,
    rotation_y,
)
from model.camera.pipeline import estimate_poses
from shared.config.settings import CameraPoseSettings


WIDTH = 640
HEIGHT = 480
FX = 700.0
FY = 700.0
CX = 320.0
CY = 240.0


def _settings(**overrides) -> CameraPoseSettings:
    values = dict(
        focal_scale=1.2,
        fx=FX,
        fy=FY,
        cx=CX,
        cy=CY,
        orb_features=2500,
        ratio_test=0.8,
        ransac_thresh=1.5,
        min_matches=20,
        min_inliers=12,
        max_pair_skip=2,
    )
    values.update(overrides)
    settings = CameraPoseSettings(**values)
    settings.validate()
    return settings


def _k() -> np.ndarray:
    return np.array([[FX, 0.0, CX], [0.0, FY, CY], [0.0, 0.0, 1.0]], dtype=np.float64)


def _w2c(center: np.ndarray, yaw_deg: float) -> tuple[np.ndarray, np.ndarray]:
    rotation = rotation_y(yaw_deg)
    translation = -rotation @ np.asarray(center, dtype=np.float64).reshape(3)
    return rotation, translation


def _unique_texture(seed: int, width: int = 900, height: int = 700) -> np.ndarray:
    rng = np.random.default_rng(seed)
    texture = rng.integers(40, 220, (height, width, 3), dtype=np.uint8)
    for index in range(60):
        x = int(rng.integers(10, width - 40))
        y = int(rng.integers(10, height - 40))
        color = tuple(int(c) for c in rng.integers(0, 255, size=3))
        cv2.rectangle(texture, (x, y), (x + int(rng.integers(18, 70)), y + int(rng.integers(18, 70))), color, -1)
        cv2.putText(
            texture,
            f"{seed}-{index}",
            (x, y + 16),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return texture


def _project_corners(
    rotation: np.ndarray,
    translation: np.ndarray,
    corners: np.ndarray,
) -> np.ndarray | None:
    camera = _k()
    camera_pts = (rotation @ corners.T).T + translation.reshape(3)
    if np.any(camera_pts[:, 2] <= 0.2):
        return None
    projected = (camera @ camera_pts.T).T
    return (projected[:, :2] / projected[:, 2:3]).astype(np.float32)


def _paste_plane(
    image: np.ndarray,
    rotation: np.ndarray,
    translation: np.ndarray,
    texture: np.ndarray,
    origin: np.ndarray,
    axis_u: np.ndarray,
    axis_v: np.ndarray,
) -> None:
    height, width = texture.shape[:2]
    corners = np.array(
        [origin, origin + axis_u, origin + axis_u + axis_v, origin + axis_v],
        dtype=np.float64,
    )
    destination = _project_corners(rotation, translation, corners)
    if destination is None:
        return
    source = np.array(
        [[0.0, 0.0], [width - 1.0, 0.0], [width - 1.0, height - 1.0], [0.0, height - 1.0]],
        dtype=np.float32,
    )
    homography = cv2.getPerspectiveTransform(source, destination)
    warped = cv2.warpPerspective(texture, homography, (WIDTH, HEIGHT))
    mask = cv2.warpPerspective(
        np.full((height, width), 255, dtype=np.uint8),
        homography,
        (WIDTH, HEIGHT),
    )
    image[mask > 0] = warped[mask > 0]


def render_view(rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    image = np.full((HEIGHT, WIDTH, 3), 28, dtype=np.uint8)
    far = _unique_texture(1)
    near = _unique_texture(2)
    _paste_plane(
        image,
        rotation,
        translation,
        far,
        origin=np.array([-1.2, -0.9, 2.6]),
        axis_u=np.array([2.4, 0.0, 0.0]),
        axis_v=np.array([0.0, 1.8, 0.0]),
    )
    _paste_plane(
        image,
        rotation,
        translation,
        near,
        origin=np.array([0.05, -0.5, 1.55]),
        axis_u=np.array([1.0, 0.0, 0.12]),
        axis_v=np.array([0.0, 1.0, 0.0]),
    )
    return image


def write_views(directory: Path, poses: list[tuple[np.ndarray, np.ndarray]]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for index, (rotation, translation) in enumerate(poses):
        image = render_view(rotation, translation)
        cv2.imwrite(str(directory / f"frame_{index:06d}.jpg"), image)
    return directory


def test_compose_chains_relative_pose() -> None:
    rotation_rel = rotation_y(10)
    translation_rel = np.array([0.2, 0.0, 0.05])
    rotation, translation = compose_w2c(
        np.eye(3),
        np.zeros(3),
        rotation_rel,
        translation_rel,
    )
    np.testing.assert_allclose(rotation, rotation_rel)
    np.testing.assert_allclose(translation, translation_rel)


def test_make_intrinsics_uses_image_center() -> None:
    settings = _settings(fx=None, fy=None, cx=None, cy=None, focal_scale=1.2)
    intrinsics = make_intrinsics(640, 480, settings)
    assert intrinsics.cx == 320.0
    assert intrinsics.cy == 240.0
    assert intrinsics.fx == pytest.approx(1.2 * 640)


def test_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(CameraPoseError) as err:
        estimate_poses(tmp_path / "missing")
    assert err.value.code == "source_not_found"


def test_too_few_frames_raises(tmp_path: Path) -> None:
    job = tmp_path / "one"
    job.mkdir()
    cv2.imwrite(str(job / "frame_000000.jpg"), np.full((48, 64, 3), 80, dtype=np.uint8))
    with pytest.raises(CameraPoseError) as err:
        estimate_poses(job, settings=_settings())
    assert err.value.code == "too_few_frames"


def test_recovers_relative_motion_up_to_scale(tmp_path: Path) -> None:
    true = [
        _w2c(np.array([0.0, 0.0, 0.0]), 0.0),
        _w2c(np.array([0.22, 0.0, 0.04]), -8.0),
        _w2c(np.array([0.44, 0.02, 0.08]), -16.0),
    ]
    job = write_views(tmp_path / "sfm", true)
    result = estimate_poses(job, settings=_settings())
    posed = [item for item in result.cameras if item.status != "failed"]
    assert result.posed_count >= 2
    assert posed[0].status == "reference"
    assert Path(result.poses_path).is_file()

    rotation_true_1 = true[1][0]
    rotation_est_1 = np.array(posed[1].rotation_w2c)
    assert rotation_angle_deg(rotation_est_1, rotation_true_1) < 12.0

    center_true = -true[1][0].T @ true[1][1]
    center_est = np.array(posed[1].center_world)
    assert direction_cosine(center_est, center_true) > 0.85


def test_identical_views_are_degenerate(tmp_path: Path) -> None:
    rotation, translation = _w2c(np.array([0.0, 0.0, 0.0]), 0.0)
    image = render_view(rotation, translation)
    job = tmp_path / "still"
    job.mkdir()
    cv2.imwrite(str(job / "frame_000000.jpg"), image)
    cv2.imwrite(str(job / "frame_000001.jpg"), image)
    with pytest.raises(CameraPoseError) as err:
        estimate_poses(job, settings=_settings(min_inliers=25))
    assert err.value.code in {"pose_failed", "too_few_frames"}
