"""Phase 8 labels. A fake detector stands in for YOLO so tests stay offline."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from model.scene_understanding.__main__ import main
from model.scene_understanding.exceptions import SceneError
from model.scene_understanding.pipeline import understand_scene
from model.scene_understanding.types import Detection
from shared.config.settings import SceneSettings


def _scene(**overrides) -> SceneSettings:
    values = dict(
        confidence=0.35,
        max_frames=40,
        model_name="test",
        merge_distance=0.6,
        device="cpu",
    )
    values.update(overrides)
    settings = SceneSettings(**values)
    settings.validate()
    return settings


def _write_jpeg(path: Path, color: tuple[int, int, int] = (40, 80, 40)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((8, 10, 3), color, dtype=np.uint8)
    cv2.imwrite(str(path), image)


class _Boxes:
    name = "test_boxes"

    def __init__(self, detections: list[Detection]) -> None:
        self.detections = detections
        self.calls = 0

    def detect(self, image: np.ndarray) -> list[Detection]:
        self.calls += 1
        return list(self.detections)


def _chair() -> Detection:
    return Detection("chair", 0.91, 4, 3, 6, 5)


def test_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(SceneError) as err:
        understand_scene(tmp_path / "missing", settings=_scene(), detector=_Boxes([_chair()]))
    assert err.value.code == "source_not_found"


def test_empty_directory_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SceneError) as err:
        understand_scene(empty, settings=_scene(), detector=_Boxes([_chair()]))
    assert err.value.code == "empty_frames"


def test_invalid_settings_raise(tmp_path: Path) -> None:
    job = tmp_path / "room"
    _write_jpeg(job / "selected" / "frame_000000.jpg")
    settings = SceneSettings(
        confidence=0.0,
        max_frames=40,
        model_name="test",
        merge_distance=0.6,
        device="cpu",
    )
    with pytest.raises(SceneError) as err:
        understand_scene(job, settings=settings, detector=_Boxes([_chair()]))
    assert err.value.code == "invalid_settings"


def test_image_only_when_geometry_is_missing(tmp_path: Path) -> None:
    job = tmp_path / "room"
    _write_jpeg(job / "selected" / "frame_000000.jpg")
    result = understand_scene(job, settings=_scene(), detector=_Boxes([_chair()]))
    assert result.strategy == "test_boxes"
    assert result.scale_meaning == "image_only"
    assert result.detection_count == 1
    assert result.objects[0].label == "chair"
    assert result.objects[0].position is None
    assert Path(result.manifest_path).is_file()
    payload = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert payload["frames"][0]["detections"][0]["bbox"] == [4.0, 3.0, 6.0, 5.0]


def test_low_confidence_is_dropped(tmp_path: Path) -> None:
    job = tmp_path / "room"
    _write_jpeg(job / "selected" / "frame_000000.jpg")
    faint = Detection("chair", 0.1, 1, 1, 3, 3)
    result = understand_scene(job, settings=_scene(), detector=_Boxes([faint]))
    assert result.detection_count == 0
    assert result.objects == []


def test_places_box_center_in_the_room(tmp_path: Path) -> None:
    job = tmp_path / "posed"
    frame = job / "selected" / "frame_000000.jpg"
    _write_jpeg(frame)
    depth_path = job / "depth" / "frame_000000.npy"
    depth_path.parent.mkdir(parents=True)
    np.save(depth_path, np.full((8, 10), 2.0, dtype=np.float32))
    frame_path = str(frame.resolve())
    (job / "poses.json").write_text(
        json.dumps(
            {
                "intrinsics": {"fx": 20.0, "fy": 20.0, "cx": 5.0, "cy": 4.0, "width": 10, "height": 8},
                "cameras": [
                    {
                        "path": frame_path,
                        "status": "reference",
                        "matrix_c2w": np.eye(4).tolist(),
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
                        "source_path": frame_path,
                        "depth_path": str(depth_path.resolve()),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = understand_scene(job, settings=_scene(), detector=_Boxes([_chair()]))
    assert result.scale_meaning == "arbitrary_monocular"
    assert result.frames[0].detections[0].position == [0.0, 0.0, 2.0]
    assert result.objects[0].position == [0.0, 0.0, 2.0]
    assert result.objects[0].count == 1


def test_nearby_labels_merge_and_distant_ones_stay_apart(tmp_path: Path) -> None:
    job = tmp_path / "two"
    first = job / "selected" / "frame_000000.jpg"
    second = job / "selected" / "frame_000001.jpg"
    _write_jpeg(first)
    _write_jpeg(second, (20, 20, 80))
    depth_dir = job / "depth"
    depth_dir.mkdir(parents=True)
    maps = []
    cameras = []
    for index, frame, shift in ((0, first, 0.0), (1, second, 3.0)):
        depth_path = depth_dir / f"{frame.stem}.npy"
        np.save(depth_path, np.full((8, 10), 2.0, dtype=np.float32))
        matrix = np.eye(4)
        matrix[0, 3] = shift
        cameras.append(
            {
                "path": str(frame.resolve()),
                "status": "estimated",
                "matrix_c2w": matrix.tolist(),
            }
        )
        maps.append(
            {
                "source_path": str(frame.resolve()),
                "depth_path": str(depth_path.resolve()),
            }
        )
    (job / "poses.json").write_text(
        json.dumps(
            {
                "intrinsics": {"fx": 20.0, "fy": 20.0, "cx": 5.0, "cy": 4.0},
                "cameras": cameras,
            }
        ),
        encoding="utf-8",
    )
    (job / "depth.json").write_text(json.dumps({"maps": maps}), encoding="utf-8")

    near = understand_scene(job, settings=_scene(merge_distance=0.6), detector=_Boxes([_chair()]))
    # Rewrite the second camera onto the first so both chairs land on one point.
    cameras[1]["matrix_c2w"] = np.eye(4).tolist()
    (job / "poses.json").write_text(
        json.dumps(
            {
                "intrinsics": {"fx": 20.0, "fy": 20.0, "cx": 5.0, "cy": 4.0},
                "cameras": cameras,
            }
        ),
        encoding="utf-8",
    )
    merged = understand_scene(job, settings=_scene(merge_distance=0.6), detector=_Boxes([_chair()]))
    assert len(near.objects) == 2
    assert near.objects[0].count == 1
    assert len(merged.objects) == 1
    assert merged.objects[0].count == 2
    assert merged.objects[0].position == [0.0, 0.0, 2.0]


def test_max_frames_samples_evenly(tmp_path: Path) -> None:
    job = tmp_path / "many"
    for index in range(5):
        _write_jpeg(job / "selected" / f"frame_{index:06d}.jpg")
    detector = _Boxes([_chair()])
    result = understand_scene(job, settings=_scene(max_frames=2), detector=detector)
    assert detector.calls == 2
    assert result.frame_count == 2
    assert any(issue.code == "frame_cap" for issue in result.warnings)


def test_cli_missing_source(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main([str(tmp_path / "missing")])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "source_not_found"
