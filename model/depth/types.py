"""Dataclasses for Phase 4 monocular depth."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STRATEGY_NAME = "depth_anything_v2_small"


@dataclass(frozen=True)
class DepthMapRecord:
    index: int
    source_path: str
    depth_path: str
    preview_path: str | None
    height: int
    width: int
    min_value: float
    max_value: float


@dataclass(frozen=True)
class DepthIssue:
    severity: str
    code: str
    message: str


@dataclass
class DepthResult:
    job_id: str
    strategy: str = STRATEGY_NAME
    scale_meaning: str = "relative_affine_invariant"
    device: str = "cpu"
    model_id: str = ""
    input_count: int = 0
    maps: list[DepthMapRecord] = field(default_factory=list)
    warnings: list[DepthIssue] = field(default_factory=list)
    depth_dir: str = ""
    manifest_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def dump_depth_manifest(result: DepthResult, path: Path) -> None:
    import json

    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
