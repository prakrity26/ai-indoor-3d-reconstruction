"""Dataclasses for Phase 9 evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STRATEGY_NAME = "artifact_metrics"
SCALE_MEANING = "arbitrary_monocular"


@dataclass(frozen=True)
class EvaluationIssue:
    severity: str
    code: str
    message: str


@dataclass
class EvaluationResult:
    job_id: str
    strategy: str = STRATEGY_NAME
    scale_meaning: str = SCALE_MEANING
    posed_ratio: float | None = None
    selected_frames: int | None = None
    posed_frames: int | None = None
    failed_frames: int | None = None
    depth_maps: int | None = None
    cloud_points: int | None = None
    filtered_points: int | None = None
    mesh_vertices: int | None = None
    mesh_triangles: int | None = None
    scene_objects: int | None = None
    detection_count: int | None = None
    splat_bytes: int | None = None
    splat_gaussians: int | None = None
    splat_walkable: bool = False
    timings_sec: dict[str, float] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)
    warnings: list[EvaluationIssue] = field(default_factory=list)
    manifest_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def dump_evaluation(result: EvaluationResult, path: Path) -> None:
    import json

    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
