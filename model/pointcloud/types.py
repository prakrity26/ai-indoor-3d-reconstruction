"""Dataclasses for Phase 6 filtered clouds."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STRATEGY_NAME = "open3d_stat_voxel"


@dataclass(frozen=True)
class FilterIssue:
    severity: str
    code: str
    message: str


@dataclass
class FilterResult:
    job_id: str
    strategy: str = STRATEGY_NAME
    input_count: int = 0
    after_crop: int = 0
    after_outlier: int = 0
    output_count: int = 0
    ply_path: str = ""
    manifest_path: str = ""
    warnings: list[FilterIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def dump_filter_manifest(result: FilterResult, path: Path) -> None:
    import json

    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
