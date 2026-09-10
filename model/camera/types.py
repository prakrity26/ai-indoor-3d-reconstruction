"""Dataclasses for Phase 3 camera pose estimation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STRATEGY_NAME = "opencv_orb_essential"


@dataclass(frozen=True)
class Intrinsics:
    fx: float
    fy: float
    cx: float
    cy: float
    width: int
    height: int

    def matrix(self) -> list[list[float]]:
        return [
            [self.fx, 0.0, self.cx],
            [0.0, self.fy, self.cy],
            [0.0, 0.0, 1.0],
        ]


@dataclass(frozen=True)
class CameraPose:
    index: int
    path: str
    status: str
    rotation_w2c: list[list[float]]
    translation_w2c: list[float]
    center_world: list[float]
    matrix_c2w: list[list[float]]
    reference_index: int | None = None
    inliers: int = 0
    match_count: int = 0
    scale: float = 1.0


@dataclass(frozen=True)
class PoseIssue:
    severity: str
    code: str
    message: str


@dataclass
class PoseResult:
    job_id: str
    strategy: str = STRATEGY_NAME
    scale_meaning: str = "arbitrary_monocular"
    input_count: int = 0
    posed_count: int = 0
    failed_count: int = 0
    intrinsics: Intrinsics | None = None
    cameras: list[CameraPose] = field(default_factory=list)
    warnings: list[PoseIssue] = field(default_factory=list)
    poses_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def dump_poses(result: PoseResult, path: Path) -> None:
    import json

    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
