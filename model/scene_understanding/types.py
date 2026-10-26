"""Dataclasses for Phase 8 object labels."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

STRATEGY_NAME = "indoor_objects"


@dataclass(frozen=True)
class Detection:
    """One box in image pixels. ``position`` is filled later, in the room frame."""

    label: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float

    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


DetectionBox = Detection


@dataclass(frozen=True)
class PlacedDetection:
    label: str
    confidence: float
    bbox: list[float]
    position: list[float] | None


@dataclass(frozen=True)
class FrameDetections:
    index: int
    source_path: str
    detections: list[PlacedDetection]


@dataclass(frozen=True)
class SceneObject:
    label: str
    count: int
    position: list[float] | None


@dataclass(frozen=True)
class SceneIssue:
    severity: str
    code: str
    message: str


@dataclass
class SceneResult:
    job_id: str
    strategy: str = STRATEGY_NAME
    scale_meaning: str = "image_only"
    frame_count: int = 0
    detection_count: int = 0
    frames: list[FrameDetections] = field(default_factory=list)
    objects: list[SceneObject] = field(default_factory=list)
    warnings: list[SceneIssue] = field(default_factory=list)
    manifest_path: str = ""

    @property
    def object_count(self) -> int:
        return len(self.objects)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["object_count"] = self.object_count
        return payload


def dump_scene(result: SceneResult, path: Path) -> None:
    import json

    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
