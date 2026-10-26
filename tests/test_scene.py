"""Phase 8 places a detected box in the scene when pose and depth exist."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from model.scene_understanding.pipeline import understand_scene
from model.scene_understanding.types import DetectionBox
from shared.config.settings import SceneSettings


class _Chair:
    def detect(self, image_bgr: np.ndarray) -> list[DetectionBox]:
        height, width = image_bgr.shape[:2]
        return [DetectionBox("chair", 0.9, width * 0.25, height * 0.25, width * 0.75, height * 0.75)]


def test_detection_is_backprojected(tmp_path: Path) -> None:
    job = tmp_path / "room"
    selected = job / "selected"
    depth_dir = job / "depth"
    selected.mkdir(parents=True)
    depth_dir.mkdir()
    image = np.full((40, 30, 3), 180, dtype=np.uint8)
    cv2.imwrite(str(selected / "frame_000000.jpg"), image)
    np.save(depth_dir / "frame_000000.npy", np.full((40, 30), 2.0, dtype=np.float32))
    (job / "poses.json").write_text(
        json.dumps(
            {
                "intrinsics": {"fx": 20.0, "fy": 20.0, "cx": 15.0, "cy": 20.0},
                "cameras": [
                    {
                        "path": str(selected / "frame_000000.jpg"),
                        "status": "reference",
                        "matrix_c2w": [
                            [1, 0, 0, 0],
                            [0, 1, 0, 0],
                            [0, 0, 1, 0],
                            [0, 0, 0, 1],
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (job / "depth.json").write_text(
        json.dumps(
            {
                "maps": [
                    {
                        "source_path": str(selected / "frame_000000.jpg"),
                        "depth_path": str(depth_dir / "frame_000000.npy"),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    settings = SceneSettings(confidence=0.35, max_frames=5, model_name="unused", merge_distance=0.6)
    result = understand_scene(job, _Chair(), settings=settings)
    assert result.object_count == 1
    assert result.objects[0].label == "chair"
    assert result.objects[0].position is not None
    assert abs(result.objects[0].position[2] - 2.0) < 1e-3
    saved = json.loads((job / "scene.json").read_text(encoding="utf-8"))
    assert saved["detection_count"] == 1
