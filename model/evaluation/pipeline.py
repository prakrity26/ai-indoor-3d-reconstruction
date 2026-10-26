"""Phase 9: score an existing job folder and write evaluation.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from model.evaluation.exceptions import EvaluationError
from model.evaluation.metrics import int_or_none, load_json, ply_counts
from model.evaluation.types import (
    STRATEGY_NAME,
    EvaluationIssue,
    EvaluationResult,
    dump_evaluation,
)

# A finished indoor splat from this trainer is tens of megabytes.
WALKABLE_MIN_BYTES = 5_000_000
WALKABLE_MIN_GAUSSIANS = 100_000


def evaluate_job(
    source: str | Path,
    *,
    job_id: str | None = None,
) -> EvaluationResult:
    """Read manifests and PLY headers. Scale stays relative. A small splat stays sparse."""
    path = Path(source)
    if not path.exists():
        raise EvaluationError("source_not_found", f"Source not found: {path}")
    if not path.is_dir():
        raise EvaluationError("unsupported_source", "Expected a job directory.", {"path": str(path)})

    job_dir = path.resolve()
    summary = load_json(job_dir / "manifest.json") or {}
    selection = load_json(job_dir / "selection.json")
    poses = load_json(job_dir / "poses.json")
    depth = load_json(job_dir / "depth.json")
    cloud = load_json(job_dir / "cloud.json")
    filtered = load_json(job_dir / "cloud_filtered.json")
    mesh = load_json(job_dir / "mesh.json")
    scene = load_json(job_dir / "scene.json")
    splat = load_json(job_dir / "splat" / "splat.json")
    timings = load_json(job_dir / "timings.json") or {}

    warnings: list[EvaluationIssue] = [
        EvaluationIssue(
            "info",
            "relative_scale",
            "Counts describe the reconstruction. Distances are relative, not metres.",
        )
    ]

    selected = _selected_frames(selection, summary, job_dir)
    posed, failed = _pose_counts(poses, summary)
    posed_ratio = None
    if selected and posed is not None and selected > 0:
        posed_ratio = round(posed / selected, 4)

    depth_maps = _depth_maps(depth, job_dir)
    cloud_points = _cloud_points(cloud)
    filtered_points, filtered_warning = _filtered_points(filtered, summary, job_dir)
    if filtered_warning:
        warnings.append(filtered_warning)
    vertices, triangles, mesh_warning = _mesh_counts(mesh, summary, job_dir)
    if mesh_warning:
        warnings.append(mesh_warning)

    scene_objects = None
    detection_count = None
    if scene is not None:
        detection_count = int_or_none(scene.get("detection_count"))
        scene_objects = int_or_none(scene.get("object_count"))
        if scene_objects is None and isinstance(scene.get("objects"), list):
            scene_objects = len(scene["objects"])

    splat_bytes, splat_gaussians, walkable, splat_warnings = _splat(job_dir, splat)
    warnings.extend(splat_warnings)

    if not _has_signal(
        selected,
        posed,
        depth_maps,
        cloud_points,
        filtered_points,
        vertices,
        scene_objects,
        splat_bytes,
    ):
        raise EvaluationError(
            "nothing_to_score",
            "The job folder has no poses, depth, cloud, mesh, scene labels, or splat to score.",
            {"path": str(job_dir)},
        )

    resolved_id = job_id or str(summary.get("job_id") or (poses or {}).get("job_id") or job_dir.name)
    manifest_path = job_dir / "evaluation.json"
    result = EvaluationResult(
        job_id=resolved_id,
        strategy=STRATEGY_NAME,
        posed_ratio=posed_ratio,
        selected_frames=selected,
        posed_frames=posed,
        failed_frames=failed,
        depth_maps=depth_maps,
        cloud_points=cloud_points,
        filtered_points=filtered_points,
        mesh_vertices=vertices,
        mesh_triangles=triangles,
        scene_objects=scene_objects,
        detection_count=detection_count,
        splat_bytes=splat_bytes,
        splat_gaussians=splat_gaussians,
        splat_walkable=walkable,
        timings_sec=_timings(timings),
        settings=_settings(poses, depth, cloud, filtered, mesh, scene, splat),
        warnings=warnings,
        manifest_path=str(manifest_path.resolve()),
    )
    dump_evaluation(result, manifest_path)
    return result


def _has_signal(*values: int | None) -> bool:
    return any(value is not None for value in values)


def _selected_frames(selection: dict | None, summary: dict, job_dir: Path) -> int | None:
    if selection is not None:
        count = int_or_none(selection.get("selected_count"))
        if count is None and isinstance(selection.get("selected"), list):
            count = len(selection["selected"])
        if count is not None:
            return count
    count = int_or_none(summary.get("selected_keyframes"))
    if count is not None:
        return count
    selected_dir = job_dir / "selected"
    if selected_dir.is_dir():
        images = [
            path
            for path in selected_dir.iterdir()
            if path.suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        if images:
            return len(images)
    return None


def _pose_counts(poses: dict | None, summary: dict) -> tuple[int | None, int | None]:
    if poses is not None:
        posed = int_or_none(poses.get("posed_count"))
        failed = int_or_none(poses.get("failed_count"))
        cameras = poses.get("cameras")
        if isinstance(cameras, list):
            if posed is None:
                posed = sum(1 for item in cameras if isinstance(item, dict) and item.get("status") != "failed")
            if failed is None:
                failed = sum(1 for item in cameras if isinstance(item, dict) and item.get("status") == "failed")
        return posed, failed
    posed = int_or_none(summary.get("posed_keyframes"))
    return posed, None


def _depth_maps(depth: dict | None, job_dir: Path) -> int | None:
    if depth is not None and isinstance(depth.get("maps"), list):
        return len(depth["maps"])
    depth_dir = job_dir / "depth"
    if depth_dir.is_dir():
        maps = list(depth_dir.glob("*.npy"))
        if maps:
            return len(maps)
    return None


def _cloud_points(cloud: dict | None) -> int | None:
    if cloud is None:
        return None
    return int_or_none(cloud.get("point_count"))


def _filtered_points(
    filtered: dict | None,
    summary: dict,
    job_dir: Path,
) -> tuple[int | None, EvaluationIssue | None]:
    if filtered is not None:
        count = int_or_none(filtered.get("output_count"))
        if count is not None:
            return count, None
    count = int_or_none(summary.get("filtered_cloud_points"))
    if count is not None:
        return count, None
    ply = _first_file(job_dir / "cloud_filtered.ply", job_dir / "splat" / "cloud_filtered.ply")
    if ply is None:
        return None, None
    counts = ply_counts(ply)
    if counts is None:
        return None, EvaluationIssue(
            "warning",
            "ply_unread",
            f"Could not read a vertex count from {ply.name}.",
        )
    return counts.get("vertex"), None


def _mesh_counts(
    mesh: dict | None,
    summary: dict,
    job_dir: Path,
) -> tuple[int | None, int | None, EvaluationIssue | None]:
    if mesh is not None:
        vertices = int_or_none(mesh.get("vertex_count"))
        triangles = int_or_none(mesh.get("triangle_count"))
        if vertices is not None or triangles is not None:
            return vertices, triangles, None
    vertices = int_or_none(summary.get("vertex_count"))
    triangles = int_or_none(summary.get("triangle_count"))
    if vertices is not None or triangles is not None:
        return vertices, triangles, None
    ply = _first_file(job_dir / "mesh.ply")
    if ply is None:
        return None, None, None
    counts = ply_counts(ply)
    if counts is None:
        return None, None, EvaluationIssue(
            "warning",
            "ply_unread",
            "Could not read mesh.ply. If it is a Git LFS pointer, run git lfs pull.",
        )
    return counts.get("vertex"), counts.get("face"), None


def _splat(job_dir: Path, splat: dict | None) -> tuple[int | None, int | None, bool, list[EvaluationIssue]]:
    warnings: list[EvaluationIssue] = []
    ply = _first_file(
        job_dir / "splat" / "point_cloud.ply",
        job_dir / "point_cloud.ply",
    )
    registered = int_or_none((splat or {}).get("registered_images"))
    if ply is None:
        if registered == 0:
            warnings.append(
                EvaluationIssue(
                    "info",
                    "splat_untrained",
                    "splat.json records zero registered images. Training has not produced a room.",
                )
            )
        return None, None, False, warnings
    size = ply.stat().st_size
    counts = ply_counts(ply)
    gaussians = None if counts is None else counts.get("vertex")
    if counts is None:
        warnings.append(
            EvaluationIssue("warning", "ply_unread", "The splat file is present but its header could not be read.")
        )
        return size, None, False, warnings
    walkable = size >= WALKABLE_MIN_BYTES and (gaussians or 0) >= WALKABLE_MIN_GAUSSIANS
    if walkable:
        warnings.append(
            EvaluationIssue(
                "info",
                "splat_size",
                f"Splat file has {gaussians} Gaussians and {size} bytes.",
            )
        )
    else:
        warnings.append(
            EvaluationIssue(
                "info",
                "splat_sparse",
                (
                    f"Splat file has {gaussians} Gaussians and {size} bytes. "
                    "A walk-through from this trainer is tens of megabytes."
                ),
            )
        )
    return size, gaussians, walkable, warnings


def _timings(payload: dict[str, Any]) -> dict[str, float]:
    timings: dict[str, float] = {}
    for key, value in payload.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            timings[str(key)] = round(float(value), 4)
    return timings


def _settings(
    poses: dict | None,
    depth: dict | None,
    cloud: dict | None,
    filtered: dict | None,
    mesh: dict | None,
    scene: dict | None,
    splat: dict | None,
) -> dict[str, Any]:
    return {
        "pose_strategy": _text(poses, "strategy"),
        "depth_model": _text(depth, "model_id"),
        "depth_device": _text(depth, "device"),
        "cloud_strategy": _text(cloud, "strategy"),
        "filter_strategy": _text(filtered, "strategy"),
        "mesh_strategy": _text(mesh, "strategy"),
        "scene_strategy": _text(scene, "strategy"),
        "splat_strategy": _text(splat, "strategy"),
        "splat_registered_images": int_or_none((splat or {}).get("registered_images")),
        "splat_images": int_or_none((splat or {}).get("image_count")),
    }


def _text(payload: dict | None, key: str) -> str | None:
    if payload is None:
        return None
    value = payload.get(key)
    if value is None or value == "":
        return None
    return str(value)


def _first_file(*paths: Path) -> Path | None:
    for path in paths:
        if path.is_file():
            return path
    return None
