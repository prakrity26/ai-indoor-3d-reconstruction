"""Dataclasses for Phase 7 meshes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STRATEGY_NAME = "open3d_poisson"


@dataclass(frozen=True)
class MeshIssue:
    severity: str
    code: str
    message: str


@dataclass
class MeshResult:
    job_id: str
    strategy: str = STRATEGY_NAME
    input_count: int = 0
    vertex_count: int = 0
    triangle_count: int = 0
    ply_path: str = ""
    glb_path: str = ""
    manifest_path: str = ""
    warnings: list[MeshIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def dump_mesh_manifest(result: MeshResult, path: Path) -> None:
    import json

    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
