"""2D boxes. Tests pass a detector; the CLI loads YOLOv8n when ultralytics is installed."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from model.scene_understanding.exceptions import SceneError
from model.scene_understanding.types import DetectionBox


class Detector(Protocol):
    def detect(self, image_bgr: np.ndarray) -> list[DetectionBox]:
        """Return boxes in pixel coordinates of image_bgr."""


# COCO names that belong in a room. Cars, animals, and sports gear are dropped.
INDOOR_LABELS = frozenset(
    {
        "person",
        "backpack",
        "handbag",
        "suitcase",
        "bottle",
        "wine glass",
        "cup",
        "fork",
        "knife",
        "spoon",
        "bowl",
        "banana",
        "apple",
        "sandwich",
        "orange",
        "broccoli",
        "carrot",
        "chair",
        "couch",
        "potted plant",
        "bed",
        "dining table",
        "toilet",
        "tv",
        "laptop",
        "mouse",
        "remote",
        "keyboard",
        "cell phone",
        "microwave",
        "oven",
        "toaster",
        "sink",
        "refrigerator",
        "book",
        "clock",
        "vase",
    }
)


class YoloDetector:
    """Indoor COCO labels from YOLOv8n. The first call can download the small weights."""

    name = "yolov8n"

    def __init__(self, model_name: str, confidence: float, device: str = "cpu") -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise SceneError(
                "detector_unavailable",
                'Install the detect extra first: pip install -e ".[detect]"',
            ) from exc
        self._model = YOLO(model_name)
        self._confidence = confidence
        self._device = device

    def detect(self, image_bgr: np.ndarray) -> list[DetectionBox]:
        result = self._model.predict(
            image_bgr,
            conf=self._confidence,
            verbose=False,
            device=self._device,
        )[0]
        names = result.names or {}
        boxes: list[DetectionBox] = []
        if result.boxes is None:
            return boxes
        for box in result.boxes:
            label = str(names.get(int(box.cls[0]), ""))
            if label not in INDOOR_LABELS:
                continue
            x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
            boxes.append(DetectionBox(label, float(box.conf[0]), x1, y1, x2, y2))
        return boxes
