"""Dataclasses for Phase 5 back-projected point clouds."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STRATEGY_NAME = "depth_unproject_concat"


@dataclass(frozen=True)
class CloudIssue:
    severity: str
    code: str
    message: str


@dataclass(frozen=True)
class FrameCloudStats:
    index: int
    source_path: str
    point_count: int


@dataclass
class CloudResult:
    job_id: str
    strategy: str = STRATEGY_NAME
    scale_meaning: str = "relative_per_view_then_posed"
    frame_count: int = 0
    point_count: int = 0
    ply_path: str = ""
    manifest_path: str = ""
    frames: list[FrameCloudStats] = field(default_factory=list)
    warnings: list[CloudIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def dump_cloud_manifest(result: CloudResult, path: Path) -> None:
    import json

    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
