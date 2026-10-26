"""Phase 8: label keyframes and, when depth and pose exist, place boxes in the room."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from model.camera.exceptions import CameraPoseError
from model.camera.io import load_pose_frames
from model.scene_understanding.associate import backproject_box
from model.scene_understanding.exceptions import SceneError
from model.scene_understanding.types import (
    STRATEGY_NAME,
    Detection,
    FrameDetections,
    PlacedDetection,
    SceneIssue,
    SceneObject,
    SceneResult,
    dump_scene,
)
from shared.config.settings import SceneSettings, load_scene_settings


def understand_scene(
    source: str | Path,
    detector=None,
    *,
    job_id: str | None = None,
    settings: SceneSettings | None = None,
) -> SceneResult:
    """Write ``scene.json`` for a Phase 2 job folder.

    ``detector`` is optional and must provide ``detect(image_bgr)``.
    The default detector is YOLOv8n and needs ``pip install -e ".[detect]"``.
    A placed point uses the stored relative depth. It is not a measured metre.
    """
    settings = settings or load_scene_settings()
    try:
        settings.validate()
    except ValueError as exc:
        raise SceneError("invalid_settings", str(exc)) from exc

    try:
        frames, job_dir, resolved_id = load_pose_frames(source, job_id=job_id)
    except CameraPoseError as exc:
        raise SceneError(exc.code, exc.message, exc.details) from exc
    if not frames:
        raise SceneError("empty_frames", "No keyframes found for scene understanding.")

    chosen = _limit_frames(frames, settings.max_frames)
    warnings: list[SceneIssue] = []
    if len(chosen) < len(frames):
        warnings.append(
            SceneIssue(
                "info",
                "frame_cap",
                f"Labeled {len(chosen)} of {len(frames)} frames (SCENE_MAX_FRAMES).",
            )
        )

    backend = detector if detector is not None else _load_detector(settings)
    geometry = _load_geometry(job_dir, warnings)
    if geometry is None:
        warnings.append(
            SceneIssue(
                "info",
                "geometry_missing",
                "No usable poses and depth. Labels stay on the image.",
            )
        )

    frame_records: list[FrameDetections] = []
    placed: list[PlacedDetection] = []
    for frame in chosen:
        image = cv2.imread(frame.path, cv2.IMREAD_COLOR)
        if image is None:
            warnings.append(
                SceneIssue("warning", "unreadable_frame", f"Could not read {frame.path}")
            )
            continue
        try:
            raw = list(backend.detect(image))
        except SceneError:
            raise
        except Exception as exc:
            raise SceneError("detection_failed", str(exc)) from exc
        kept = [_clip_box(item, image.shape[1], image.shape[0]) for item in raw]
        kept = [
            item
            for item in kept
            if item.confidence >= settings.confidence and item.x2 > item.x1 and item.y2 > item.y1
        ]
        camera = geometry.cameras.get(str(Path(frame.path).resolve())) if geometry else None
        depth = _depth_for(geometry, frame.path) if geometry else None
        detections: list[PlacedDetection] = []
        for item in kept:
            position = None
            if geometry is not None and camera is not None and depth is not None:
                position = backproject_box(
                    depth,
                    item,
                    image_width=image.shape[1],
                    image_height=image.shape[0],
                    fx=geometry.fx,
                    fy=geometry.fy,
                    cx=geometry.cx,
                    cy=geometry.cy,
                    matrix_c2w=np.asarray(camera, dtype=np.float64),
                )
                if position is not None:
                    position = [round(float(value), 6) for value in position]
            placed_item = PlacedDetection(
                label=item.label,
                confidence=round(float(item.confidence), 4),
                bbox=[round(item.x1, 1), round(item.y1, 1), round(item.x2, 1), round(item.y2, 1)],
                position=position,
            )
            detections.append(placed_item)
            placed.append(placed_item)
        frame_records.append(
            FrameDetections(
                index=frame.index,
                source_path=str(Path(frame.path).resolve()),
                detections=detections,
            )
        )

    if not frame_records:
        raise SceneError("detection_failed", "No frames could be labeled.")

    objects = _merge_objects(placed, settings.merge_distance)
    has_point = any(item.position is not None for item in placed)
    manifest_path = job_dir / "scene.json"
    result = SceneResult(
        job_id=resolved_id,
        strategy=str(getattr(backend, "name", STRATEGY_NAME)),
        scale_meaning="arbitrary_monocular" if has_point else "image_only",
        frame_count=len(frame_records),
        detection_count=len(placed),
        frames=frame_records,
        objects=objects,
        warnings=warnings,
        manifest_path=str(manifest_path.resolve()),
    )
    dump_scene(result, manifest_path)
    return result


class _Geometry:
    def __init__(
        self,
        fx: float,
        fy: float,
        cx: float,
        cy: float,
        cameras: dict[str, list],
        depth_by_path: dict[str, Path],
    ) -> None:
        self.fx = fx
        self.fy = fy
        self.cx = cx
        self.cy = cy
        self.cameras = cameras
        self.depth_by_path = depth_by_path


def _load_detector(settings: SceneSettings):
    from model.scene_understanding.detect import YoloDetector

    return YoloDetector(settings.model_name, settings.confidence, settings.device)


def _limit_frames(frames: list, max_frames: int) -> list:
    if len(frames) <= max_frames:
        return list(frames)
    if max_frames == 1:
        return [frames[len(frames) // 2]]
    picks: list[int] = []
    for slot in range(max_frames):
        index = round(slot * (len(frames) - 1) / (max_frames - 1))
        if not picks or picks[-1] != index:
            picks.append(index)
    return [frames[index] for index in picks]


def _load_geometry(job_dir: Path, warnings: list[SceneIssue]) -> _Geometry | None:
    poses_path = job_dir / "poses.json"
    depth_manifest = job_dir / "depth.json"
    if not poses_path.is_file() or not depth_manifest.is_file():
        return None
    try:
        poses = json.loads(poses_path.read_text(encoding="utf-8"))
        depth_payload = json.loads(depth_manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        warnings.append(
            SceneIssue("warning", "geometry_unreadable", "poses.json or depth.json is not valid JSON.")
        )
        return None
    intrinsics = poses.get("intrinsics")
    if not isinstance(intrinsics, dict):
        warnings.append(SceneIssue("warning", "intrinsics_missing", "poses.json has no camera intrinsics."))
        return None
    try:
        fx = float(intrinsics["fx"])
        fy = float(intrinsics["fy"])
        cx = float(intrinsics["cx"])
        cy = float(intrinsics["cy"])
    except (KeyError, TypeError, ValueError):
        warnings.append(SceneIssue("warning", "intrinsics_missing", "poses.json intrinsics are incomplete."))
        return None
    cameras: dict[str, list] = {}
    for item in poses.get("cameras", []):
        if not isinstance(item, dict) or item.get("status") == "failed" or not item.get("path"):
            continue
        matrix = item.get("matrix_c2w")
        if not isinstance(matrix, list):
            continue
        cameras[str(Path(item["path"]).resolve())] = matrix
    depth_by_path: dict[str, Path] = {}
    for item in depth_payload.get("maps", []):
        if not isinstance(item, dict) or not item.get("source_path") or not item.get("depth_path"):
            continue
        depth_by_path[str(Path(item["source_path"]).resolve())] = Path(item["depth_path"])
    if not cameras or not depth_by_path:
        return None
    return _Geometry(fx, fy, cx, cy, cameras, depth_by_path)


def _depth_for(geometry: _Geometry, frame_path: str) -> np.ndarray | None:
    depth_path = geometry.depth_by_path.get(str(Path(frame_path).resolve()))
    if depth_path is None or not depth_path.is_file():
        return None
    depth = np.load(depth_path)
    if depth.ndim != 2:
        return None
    return depth


def _clip_box(item: Detection, width: int, height: int) -> Detection:
    return Detection(
        label=str(item.label),
        confidence=float(item.confidence),
        x1=float(np.clip(item.x1, 0, width - 1)),
        y1=float(np.clip(item.y1, 0, height - 1)),
        x2=float(np.clip(item.x2, 0, width)),
        y2=float(np.clip(item.y2, 0, height)),
    )


def _merge_objects(detections: list[PlacedDetection], merge_distance: float) -> list[SceneObject]:
    clusters: list[dict] = []
    image_only: dict[str, int] = {}
    for item in detections:
        if item.position is None:
            image_only[item.label] = image_only.get(item.label, 0) + 1
            continue
        point = np.asarray(item.position, dtype=np.float64)
        matched = False
        for cluster in clusters:
            if cluster["label"] != item.label:
                continue
            centroid = np.mean(cluster["points"], axis=0)
            if float(np.linalg.norm(centroid - point)) <= merge_distance:
                cluster["points"].append(point)
                matched = True
                break
        if not matched:
            clusters.append({"label": item.label, "points": [point]})

    objects: list[SceneObject] = []
    for cluster in clusters:
        centroid = np.mean(cluster["points"], axis=0)
        objects.append(
            SceneObject(
                label=cluster["label"],
                count=len(cluster["points"]),
                position=[round(float(value), 6) for value in centroid],
            )
        )
    for label in sorted(image_only):
        objects.append(SceneObject(label=label, count=image_only[label], position=None))
    objects.sort(key=lambda item: (item.position is None, item.label, -item.count))
    return objects
