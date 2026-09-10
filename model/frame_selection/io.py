"""Load Phase 1 frames from a job folder, manifest, or image directory."""

from __future__ import annotations

import json
from pathlib import Path

from model.frame_selection.exceptions import FrameSelectionError
from model.preprocessing.types import FrameRecord

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def load_source(
    source: str | Path,
    job_id: str | None = None,
) -> tuple[list[FrameRecord], Path, str]:
    path = Path(source)
    if not path.exists():
        raise FrameSelectionError("source_not_found", f"Source not found: {path}")

    if path.is_file():
        if path.suffix.lower() != ".json":
            raise FrameSelectionError(
                "unsupported_source",
                "Expected a job directory, frames directory, or manifest.json.",
                {"path": str(path)},
            )
        return _from_manifest(path, job_id)

    manifest = path / "manifest.json"
    if manifest.is_file():
        return _from_manifest(manifest, job_id)

    image_dir = path / "frames" if (path / "frames").is_dir() else path
    frames = _from_image_dir(image_dir)
    resolved_id = job_id or path.name
    return frames, path.resolve(), resolved_id


def _from_manifest(
    manifest_path: Path,
    job_id: str | None,
) -> tuple[list[FrameRecord], Path, str]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FrameSelectionError(
            "invalid_manifest",
            f"Could not parse manifest: {manifest_path}",
            {"error": str(exc)},
        ) from exc

    raw_frames = payload.get("frames")
    if not isinstance(raw_frames, list) or not raw_frames:
        raise FrameSelectionError(
            "empty_frames",
            "Manifest does not list any extracted frames.",
            {"path": str(manifest_path)},
        )

    frames: list[FrameRecord] = []
    for item in raw_frames:
        if not isinstance(item, dict):
            continue
        frames.append(
            FrameRecord(
                index=int(item["index"]),
                timestamp_sec=float(item.get("timestamp_sec", 0.0)),
                path=str(item["path"]),
            )
        )
    if not frames:
        raise FrameSelectionError(
            "empty_frames",
            "Manifest frames were present but unreadable.",
            {"path": str(manifest_path)},
        )

    job_dir = manifest_path.parent.resolve()
    resolved_id = job_id or str(payload.get("job_id") or job_dir.name)
    return frames, job_dir, resolved_id


def _from_image_dir(image_dir: Path) -> list[FrameRecord]:
    paths = sorted(
        p
        for p in image_dir.iterdir()
        if p.is_file() and p.suffix.lower() in _IMAGE_SUFFIXES
    )
    if not paths:
        raise FrameSelectionError(
            "empty_frames",
            f"No JPEG/PNG frames found in {image_dir}",
        )
    return [
        FrameRecord(index=i, timestamp_sec=0.0, path=str(p.resolve()))
        for i, p in enumerate(paths)
    ]
