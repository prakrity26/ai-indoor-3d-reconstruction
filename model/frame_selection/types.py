"""Dataclasses for Phase 2 keyframe selection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STRATEGY_NAME = "adaptive_histogram_mad"


@dataclass(frozen=True)
class KeyframeRecord:
    index: int
    source_index: int
    timestamp_sec: float
    path: str
    source_path: str
    sharpness: float
    change_from_previous: float
    reason: str


@dataclass(frozen=True)
class SelectionIssue:
    severity: str
    code: str
    message: str


@dataclass
class SelectionResult:
    job_id: str
    strategy: str = STRATEGY_NAME
    input_count: int = 0
    selected: list[KeyframeRecord] = field(default_factory=list)
    warnings: list[SelectionIssue] = field(default_factory=list)
    selected_dir: str = ""
    selection_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["selected_count"] = len(self.selected)
        payload["skipped_count"] = max(0, self.input_count - len(self.selected))
        return payload


def dump_selection(result: SelectionResult, path: Path) -> None:
    import json

    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
