"""Load keyframes for pose estimation from a Phase 2 job folder."""

from __future__ import annotations

import json
from pathlib import Path

from model.camera.exceptions import CameraPoseError
from model.frame_selection.exceptions import FrameSelectionError
from model.frame_selection.io import load_source
from model.preprocessing.types import FrameRecord

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def load_pose_frames(
    source: str | Path,
    job_id: str | None = None,
) -> tuple[list[FrameRecord], Path, str]:
    path = Path(source)
    if not path.exists():
        raise CameraPoseError("source_not_found", f"Source not found: {path}")

    if path.is_file():
        if path.name == "selection.json":
            return _from_selection(path, job_id)
        if path.name == "manifest.json":
            return _from_phase1(path, job_id)
        raise CameraPoseError(
            "unsupported_source",
            "Expected a job directory, selection.json, or a folder of frames.",
            {"path": str(path)},
        )

    selection = path / "selection.json"
    if selection.is_file():
        return _from_selection(selection, job_id)

    selected_dir = path / "selected"
    if selected_dir.is_dir() and _image_paths(selected_dir):
        frames = _from_image_dir(selected_dir)
        return frames, path.resolve(), job_id or path.name

    return _from_phase1(path, job_id)


def _from_selection(
    selection_path: Path,
    job_id: str | None,
) -> tuple[list[FrameRecord], Path, str]:
    try:
        payload = json.loads(selection_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CameraPoseError(
            "invalid_selection",
            f"Could not parse selection.json: {selection_path}",
            {"error": str(exc)},
        ) from exc

    raw = payload.get("selected")
    if not isinstance(raw, list) or not raw:
        raise CameraPoseError(
            "empty_frames",
            "selection.json does not list any keyframes.",
            {"path": str(selection_path)},
        )

    frames: list[FrameRecord] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        frames.append(
            FrameRecord(
                index=int(item.get("index", len(frames))),
                timestamp_sec=float(item.get("timestamp_sec", 0.0)),
                path=str(item["path"]),
            )
        )
    if not frames:
        raise CameraPoseError(
            "empty_frames",
            "selection.json keyframes were present but unreadable.",
            {"path": str(selection_path)},
        )
    job_dir = selection_path.parent.resolve()
    resolved_id = job_id or str(payload.get("job_id") or job_dir.name)
    return frames, job_dir, resolved_id


def _from_phase1(
    source: Path,
    job_id: str | None,
) -> tuple[list[FrameRecord], Path, str]:
    try:
        return load_source(source, job_id=job_id)
    except FrameSelectionError as exc:
        raise CameraPoseError(exc.code, exc.message, exc.details) from exc


def _image_paths(directory: Path) -> list[Path]:
    return sorted(
        p
        for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES
    )


def _from_image_dir(image_dir: Path) -> list[FrameRecord]:
    paths = _image_paths(image_dir)
    return [
        FrameRecord(index=i, timestamp_sec=0.0, path=str(p.resolve()))
        for i, p in enumerate(paths)
    ]
