"""Phase 3: estimate camera poses from selected keyframes."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from model.camera.exceptions import CameraPoseError
from model.camera.features import detect_orb, match_descriptors, matched_points
from model.camera.geometry import (
    camera_center,
    compose_w2c,
    estimate_relative_pose,
    make_intrinsics,
    matrix_c2w,
    positive_depth_mask,
    scale_from_prior_points,
    triangulate_points,
)
from model.camera.io import load_pose_frames
from model.camera.types import (
    STRATEGY_NAME,
    CameraPose,
    Intrinsics,
    PoseIssue,
    PoseResult,
    dump_poses,
)
from model.preprocessing.types import FrameRecord
from shared.config.settings import CameraPoseSettings, load_camera_pose_settings


def estimate_poses(
    source: str | Path,
    *,
    job_id: str | None = None,
    output_path: str | Path | None = None,
    settings: CameraPoseSettings | None = None,
) -> PoseResult:
    """Estimate a monocular camera trajectory for Phase 2 keyframes.

    Depth and point-cloud fusion are intentionally not performed here (Phases 4–5).
    """
    settings = settings or load_camera_pose_settings()
    try:
        settings.validate()
    except ValueError as exc:
        raise CameraPoseError("invalid_settings", str(exc)) from exc

    frames, job_dir, resolved_id = load_pose_frames(source, job_id=job_id)
    loaded = _load_images(frames)
    if len(loaded) < 2:
        raise CameraPoseError(
            "too_few_frames",
            "Pose estimation needs at least two readable keyframes.",
            {"count": len(loaded)},
        )

    width = loaded[0][1].shape[1]
    height = loaded[0][1].shape[0]
    intrinsics = make_intrinsics(width, height, settings)
    cameras, warnings = _increment_poses(loaded, intrinsics, settings)
    posed = [item for item in cameras if item.status != "failed"]
    if len(posed) < 2:
        raise CameraPoseError(
            "pose_failed",
            "Could not recover a relative pose for any keyframe pair.",
            {"frames": len(loaded)},
        )

    poses_path = Path(output_path) if output_path is not None else job_dir / "poses.json"
    result = PoseResult(
        job_id=resolved_id,
        strategy=STRATEGY_NAME,
        scale_meaning="arbitrary_monocular",
        input_count=len(loaded),
        posed_count=len(posed),
        failed_count=len(cameras) - len(posed),
        intrinsics=intrinsics,
        cameras=cameras,
        warnings=warnings,
        poses_path=str(poses_path.resolve()),
    )
    dump_poses(result, poses_path)
    return result


def _load_images(
    frames: list[FrameRecord],
) -> list[tuple[FrameRecord, np.ndarray, list, np.ndarray | None]]:
    loaded = []
    for frame in frames:
        image = cv2.imread(frame.path, cv2.IMREAD_COLOR)
        if image is None:
            continue
        loaded.append((frame, image, None, None))
    return loaded


def _increment_poses(
    loaded: list[tuple[FrameRecord, np.ndarray, list, np.ndarray | None]],
    intrinsics: Intrinsics,
    settings: CameraPoseSettings,
) -> tuple[list[CameraPose], list[PoseIssue]]:
    features: list[tuple[list, np.ndarray | None]] = []
    for _record, image, _kp, _desc in loaded:
        features.append(detect_orb(image, settings.orb_features))

    cameras: list[CameraPose] = [
        _pose_record(
            loaded[0][0],
            0,
            np.eye(3),
            np.zeros(3),
            status="reference",
        )
    ]
    warnings: list[PoseIssue] = [
        PoseIssue(
            "info",
            "arbitrary_scale",
            "Monocular pose has arbitrary scale; it is not a metric reconstruction.",
        )
    ]

    last_posed = 0
    point_map: dict[int, np.ndarray] = {}

    for index in range(1, len(loaded)):
        recovered = None
        used_ref = last_posed
        for skip in range(1, settings.max_pair_skip + 1):
            ref = last_posed - skip + 1
            if ref < 0:
                continue
            if cameras[ref].status == "failed":
                continue
            recovered = _recover_pair(
                features[ref][0],
                features[ref][1],
                features[index][0],
                features[index][1],
                cameras[ref],
                point_map if ref == last_posed else {},
                intrinsics,
                settings,
            )
            if recovered is not None:
                used_ref = ref
                break

        if recovered is None:
            cameras.append(
                _pose_record(
                    loaded[index][0],
                    index,
                    np.eye(3),
                    np.zeros(3),
                    status="failed",
                    reference_index=last_posed,
                )
            )
            warnings.append(
                PoseIssue(
                    "warning",
                    "pair_failed",
                    f"Could not pose keyframe {index}; not enough geometric inliers.",
                )
            )
            continue

        rotation, translation, inliers, matches, new_map, scale = recovered
        cameras.append(
            _pose_record(
                loaded[index][0],
                index,
                rotation,
                translation,
                status="estimated",
                reference_index=used_ref,
                inliers=inliers,
                match_count=matches,
                scale=scale,
            )
        )
        last_posed = index
        point_map = new_map

    posed = sum(1 for item in cameras if item.status != "failed")
    failed = len(cameras) - posed
    if failed:
        warnings.append(
            PoseIssue(
                "warning",
                "partial_trajectory",
                f"{failed} of {len(cameras)} keyframes could not be posed.",
            )
        )
    return cameras, warnings


def _recover_pair(
    keypoints_a,
    descriptors_a,
    keypoints_b,
    descriptors_b,
    pose_a: CameraPose,
    point_map: dict[int, np.ndarray],
    intrinsics: Intrinsics,
    settings: CameraPoseSettings,
) -> tuple[np.ndarray, np.ndarray, int, int, dict[int, np.ndarray], float] | None:
    matches = match_descriptors(descriptors_a, descriptors_b, settings.ratio_test)
    if len(matches) < settings.min_matches:
        return None
    points_a, points_b = matched_points(keypoints_a, keypoints_b, matches)
    estimated = estimate_relative_pose(points_a, points_b, intrinsics, settings)
    if estimated is None:
        return None
    rotation_rel, translation_rel, inliers, kept = estimated
    inlier_matches = [match for match, flag in zip(matches, kept) if flag]
    inlier_a = points_a[kept]
    inlier_b = points_b[kept]
    if len(inlier_matches) < settings.min_inliers:
        return None

    rotation_a = np.array(pose_a.rotation_w2c, dtype=np.float64)
    translation_a = np.array(pose_a.translation_w2c, dtype=np.float64)
    rotation_unit, translation_unit = compose_w2c(
        rotation_a, translation_a, rotation_rel, translation_rel
    )
    unit_world = triangulate_points(
        intrinsics,
        rotation_a,
        translation_a,
        rotation_unit,
        translation_unit,
        inlier_a,
        inlier_b,
    )
    scale = 1.0
    if point_map:
        prior = []
        unit = []
        for match, point in zip(inlier_matches, unit_world):
            mapped = point_map.get(match.queryIdx)
            if mapped is not None:
                prior.append(mapped)
                unit.append(point)
        center = camera_center(rotation_a, translation_a)
        guessed = scale_from_prior_points(np.array(prior), np.array(unit), center) if prior else None
        if guessed is not None:
            scale = guessed

    translation_rel = translation_rel * scale
    rotation, translation = compose_w2c(
        rotation_a, translation_a, rotation_rel, translation_rel
    )
    world = triangulate_points(
        intrinsics,
        rotation_a,
        translation_a,
        rotation,
        translation,
        inlier_a,
        inlier_b,
    )
    depth_ok = positive_depth_mask(rotation_a, translation_a, world) & positive_depth_mask(
        rotation, translation, world
    )
    new_map: dict[int, np.ndarray] = {}
    for match, point, ok in zip(inlier_matches, world, depth_ok):
        if ok:
            new_map[match.trainIdx] = point
    return rotation, translation, inliers, len(matches), new_map, float(scale)


def _pose_record(
    frame: FrameRecord,
    index: int,
    rotation: np.ndarray,
    translation: np.ndarray,
    *,
    status: str,
    reference_index: int | None = None,
    inliers: int = 0,
    match_count: int = 0,
    scale: float = 1.0,
) -> CameraPose:
    rotation = np.asarray(rotation, dtype=np.float64)
    translation = np.asarray(translation, dtype=np.float64).reshape(3)
    center = camera_center(rotation, translation)
    return CameraPose(
        index=index,
        path=frame.path,
        status=status,
        rotation_w2c=_tolist2(rotation),
        translation_w2c=_tolist1(translation),
        center_world=_tolist1(center),
        matrix_c2w=_tolist2(matrix_c2w(rotation, translation)),
        reference_index=reference_index,
        inliers=inliers,
        match_count=match_count,
        scale=round(float(scale), 6),
    )


def _tolist1(vector: np.ndarray) -> list[float]:
    return [round(float(v), 6) for v in np.asarray(vector).ravel()]


def _tolist2(matrix: np.ndarray) -> list[list[float]]:
    return [[round(float(v), 6) for v in row] for row in np.asarray(matrix)]
