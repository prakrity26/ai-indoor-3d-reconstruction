"""Locate mesh, splat, scene, and evaluation files for one job.

The API serves these files. It does not import the reconstruction engine.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_JOB_ID = __import__("re").compile(r"^[A-Za-z0-9_-]+$")


def valid_job_id(job_id: str) -> bool:
    return bool(_JOB_ID.fullmatch(job_id or ""))


def samples_root() -> Path:
    return _ROOT / "samples"


def frames_root() -> Path:
    return Path(os.environ.get("FRAMES_DIR", _ROOT / "data" / "frames"))


def library_record(job_id: str) -> dict[str, Any] | None:
    """A checked-in sample the UI can open before any upload exists."""
    if not valid_job_id(job_id):
        return None
    folder = samples_root() / job_id
    manifest = folder / "manifest.json"
    mesh = folder / "mesh.glb"
    if not manifest.is_file() and not mesh.is_file():
        return None
    filename = job_id
    if manifest.is_file():
        payload = _read_json(manifest) or {}
        filename = str(payload.get("source_video") or job_id)
    return {
        "job_id": job_id,
        "status": "succeeded",
        "filename": filename,
        "error": "",
        "ply_path": "",
        "source": "sample",
    }


def library_records(taken: set[str]) -> list[dict[str, Any]]:
    root = samples_root()
    if not root.is_dir():
        return []
    records = []
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        if folder.name in taken or not valid_job_id(folder.name):
            continue
        record = library_record(folder.name)
        if record is not None:
            records.append(record)
    return records


def mesh_path(record: dict[str, Any]) -> Path | None:
    return _first(
        _stored(record, "mesh_path"),
        frames_root() / record["job_id"] / "mesh.glb",
        samples_root() / record["job_id"] / "mesh.glb",
    )


def splat_path(record: dict[str, Any]) -> Path | None:
    return _first(
        _stored(record, "ply_path"),
        frames_root() / record["job_id"] / "splat" / "point_cloud.ply",
        samples_root() / record["job_id"] / "splat" / "point_cloud.ply",
        samples_root() / record["job_id"] / "point_cloud.ply",
    )


def scene_path(record: dict[str, Any]) -> Path | None:
    return _first(
        _stored(record, "scene_path"),
        frames_root() / record["job_id"] / "scene.json",
        samples_root() / record["job_id"] / "scene.json",
        _job_folder(record) / "scene.json" if _job_folder(record) else None,
    )


def evaluation_document(record: dict[str, Any]) -> dict[str, Any] | None:
    """Prefer a Phase 9 file. A sample manifest supplies the same counts."""
    path = _first(
        _stored(record, "evaluation_path"),
        frames_root() / record["job_id"] / "evaluation.json",
        samples_root() / record["job_id"] / "evaluation.json",
    )
    if path is not None:
        payload = _read_json(path)
        if payload is not None:
            return payload
    manifest_path = samples_root() / record["job_id"] / "manifest.json"
    manifest = _read_json(manifest_path)
    if manifest is None:
        return None
    selected = _int(manifest.get("selected_keyframes"))
    posed = _int(manifest.get("posed_keyframes"))
    ratio = round(posed / selected, 4) if selected and posed is not None else None
    return {
        "job_id": record["job_id"],
        "scale_meaning": "arbitrary_monocular",
        "posed_ratio": ratio,
        "selected_frames": selected,
        "posed_frames": posed,
        "filtered_points": _int(manifest.get("filtered_cloud_points")),
        "mesh_vertices": _int(manifest.get("vertex_count")),
        "mesh_triangles": _int(manifest.get("triangle_count")),
        "splat_walkable": False,
        "warnings": [
            {
                "severity": "info",
                "code": "relative_scale",
                "message": "Distances are relative, not metres.",
            }
        ],
    }


def summary_from(document: dict[str, Any] | None) -> dict[str, Any]:
    if not document:
        return {}
    keys = (
        "posed_ratio",
        "selected_frames",
        "posed_frames",
        "filtered_points",
        "mesh_vertices",
        "mesh_triangles",
        "scene_objects",
        "splat_walkable",
        "scale_meaning",
    )
    return {key: document[key] for key in keys if key in document and document[key] is not None}


def _stored(record: dict[str, Any], key: str) -> Path | None:
    raw = record.get(key) or ""
    if not raw:
        return None
    return Path(str(raw))


def _job_folder(record: dict[str, Any]) -> Path | None:
    source = record.get("source_path") or ""
    if not source:
        return None
    return Path(source).parent


def _first(*candidates: Path | None) -> Path | None:
    for candidate in candidates:
        if candidate is not None and candidate.is_file():
            return candidate
    return None


def _read_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def thumbnail_path(record: dict[str, Any]) -> Path | None:
    """A representative JPEG: a sample preview, else the first extracted frame."""
    job_id = record["job_id"]
    for folder in (samples_root() / job_id / "preview", frames_root() / job_id / "frames"):
        if folder.is_dir():
            try:
                names = sorted(entry.name for entry in os.scandir(folder) if entry.name.lower().endswith((".jpg", ".jpeg")))
            except OSError:
                continue
            if names:
                return folder / names[0]
    return None


def input_report(record: dict[str, Any]) -> dict[str, Any]:
    """Video facts and quality warnings written by Phase 1 (preprocessing manifest)."""
    manifest = _read_json(frames_root() / record["job_id"] / "manifest.json")
    if not manifest:
        return {}
    video = manifest.get("video") if isinstance(manifest.get("video"), dict) else {}
    warnings = manifest.get("warnings") if isinstance(manifest.get("warnings"), list) else []
    facts = {key: video.get(key) for key in ("width", "height", "fps", "duration_sec", "frame_count") if key in video}
    clean = [
        {"severity": str(w.get("severity", "info")), "code": str(w.get("code", "")), "message": str(w.get("message", ""))}
        for w in warnings
        if isinstance(w, dict)
    ]
    return {"video": facts, "warnings": clean, "frames": len(manifest.get("frames") or [])}
