"""Run Phases 1–9 on this machine. The GPU splat path stays separate."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


class LocalResult:
    def __init__(self, mesh_path: str) -> None:
        self.mesh_path = mesh_path
        self.ply_path = ""


def run_mesh_job(
    source: str,
    job_id: str,
    stages: list[Callable[[dict[str, Any]], None]] | None = None,
) -> LocalResult:
    """Each stage reads and updates one state dict. Tests pass their own stages."""
    state: dict[str, Any] = {"source": source, "job_id": job_id, "mesh_path": ""}
    for stage in stages or default_stages():
        stage(state)
    return LocalResult(str(state.get("mesh_path") or ""))


def default_stages() -> list[Callable[[dict[str, Any]], None]]:
    return [_ingest, _select, _poses, _depth, _cloud, _filter, _mesh, _scene, _evaluate]


def _ingest(state: dict[str, Any]) -> None:
    from model.preprocessing.pipeline import ingest_video

    result = ingest_video(state["source"], job_id=state["job_id"])
    state["job_dir"] = str(Path(result.manifest_path).parent)


def _select(state: dict[str, Any]) -> None:
    from model.frame_selection.pipeline import select_keyframes

    select_keyframes(state["job_dir"], job_id=state["job_id"])


def _poses(state: dict[str, Any]) -> None:
    from model.camera.pipeline import estimate_poses

    estimate_poses(state["job_dir"], job_id=state["job_id"])


def _depth(state: dict[str, Any]) -> None:
    from model.depth.pipeline import estimate_depth

    estimate_depth(state["job_dir"], job_id=state["job_id"])


def _cloud(state: dict[str, Any]) -> None:
    from model.reconstruction.pipeline import build_point_cloud

    build_point_cloud(state["job_dir"])


def _filter(state: dict[str, Any]) -> None:
    from model.pointcloud.pipeline import filter_point_cloud

    filter_point_cloud(state["job_dir"])


def _mesh(state: dict[str, Any]) -> None:
    from model.mesh.pipeline import reconstruct_mesh

    result = reconstruct_mesh(state["job_dir"])
    state["mesh_path"] = result.glb_path or result.ply_path


def _scene(state: dict[str, Any]) -> None:
    from model.scene_understanding.exceptions import SceneError
    from model.scene_understanding.pipeline import understand_scene

    try:
        understand_scene(state["job_dir"], job_id=state["job_id"])
    except SceneError as exc:
        if exc.code != "detector_unavailable":
            raise


def _evaluate(state: dict[str, Any]) -> None:
    from model.evaluation.pipeline import evaluate_job

    evaluate_job(state["job_dir"], job_id=state["job_id"])
