"""Dataclasses for the Gaussian-splat reconstruction path."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STRATEGY_NAME = "colmap_gsplat"


@dataclass(frozen=True)
class SplatIssue:
    severity: str
    code: str
    message: str


@dataclass
class SplatResult:
    job_id: str
    strategy: str = STRATEGY_NAME
    image_count: int = 0
    registered_images: int = 0
    ply_path: str = ""
    colmap_dir: str = ""
    manifest_path: str = ""
    warnings: list[SplatIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def dump_splat_manifest(result: SplatResult, path: Path) -> None:
    import json

    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
