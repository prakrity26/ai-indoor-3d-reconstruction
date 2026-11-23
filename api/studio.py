"""The 3D Studio document for one project: hotspots, saved viewpoints, presentation settings.

Stored as JSON next to the job folders (``JOBS_DIR/_studio/<job_id>.json``). Job ids never
start with an underscore, so the folder cannot collide with a job.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

MAX_HOTSPOTS = 200
MAX_VIEWPOINTS = 50
HOTSPOT_KINDS = ("info", "label", "media")
SPLAT_UP = ("auto", "-y", "+z", "+y", "-z", "+x", "-x")

_VEC3 = re.compile(r"^\s*-?\d+(\.\d+)?(e-?\d+)?m?(\s+-?\d+(\.\d+)?(e-?\d+)?m?){2}\s*$", re.I)
_ORBIT = re.compile(r"^\s*-?\d+(\.\d+)?(deg|rad)\s+-?\d+(\.\d+)?(deg|rad)\s+\d+(\.\d+)?(e-?\d+)?(m|%)?\s*$", re.I)
_FOV = re.compile(r"^\s*\d+(\.\d+)?(deg|rad)\s*$", re.I)
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_ID = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class StudioError(ValueError):
    """The submitted studio document is not valid."""


def empty_document() -> dict[str, Any]:
    return {
        "version": 1,
        "hotspots": [],
        "viewpoints": [],
        "settings": {
            "background": "#0b0d12",
            "exposure": 1.0,
            "shadow": 0.6,
            "auto_rotate": False,
            "default_viewpoint": "",
            "splat_up": "auto",
        },
    }


def studio_path(jobs_root: Path, job_id: str) -> Path:
    return Path(jobs_root) / "_studio" / f"{job_id}.json"


def load(jobs_root: Path, job_id: str) -> dict[str, Any]:
    path = studio_path(jobs_root, job_id)
    if not path.is_file():
        return empty_document()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return validate(raw)
    except (json.JSONDecodeError, StudioError):
        return empty_document()


def save(jobs_root: Path, job_id: str, document: Any) -> dict[str, Any]:
    clean = validate(document)
    path = studio_path(jobs_root, job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return clean


def remove(jobs_root: Path, job_id: str) -> None:
    studio_path(jobs_root, job_id).unlink(missing_ok=True)


def validate(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise StudioError("The studio document must be an object.")
    hotspots = document.get("hotspots") or []
    viewpoints = document.get("viewpoints") or []
    if not isinstance(hotspots, list) or not isinstance(viewpoints, list):
        raise StudioError("hotspots and viewpoints must be lists.")
    if len(hotspots) > MAX_HOTSPOTS:
        raise StudioError(f"At most {MAX_HOTSPOTS} hotspots.")
    if len(viewpoints) > MAX_VIEWPOINTS:
        raise StudioError(f"At most {MAX_VIEWPOINTS} viewpoints.")
    out = empty_document()
    out["hotspots"] = [_hotspot(item) for item in hotspots]
    out["viewpoints"] = [_viewpoint(item) for item in viewpoints]
    out["settings"] = _settings(document.get("settings") or {}, {v["id"] for v in out["viewpoints"]})
    return out


def _hotspot(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise StudioError("Each hotspot must be an object.")
    position = str(item.get("position") or "")
    if not _VEC3.match(position):
        raise StudioError("Hotspot position must be three numbers, e.g. '0.1m 0.5m -0.2m'.")
    normal = str(item.get("normal") or "0m 1m 0m")
    if not _VEC3.match(normal):
        normal = "0m 1m 0m"
    kind = str(item.get("kind") or "info")
    if kind not in HOTSPOT_KINDS:
        raise StudioError(f"Hotspot kind must be one of {', '.join(HOTSPOT_KINDS)}.")
    title = _text(item.get("title"), 80)
    if not title:
        raise StudioError("Each hotspot needs a title.")
    color = str(item.get("color") or "#6e8bff")
    return {
        "id": _ident(item.get("id")),
        "kind": kind,
        "title": title,
        "description": _text(item.get("description"), 1000, multiline=True),
        "position": " ".join(position.split()),
        "normal": " ".join(normal.split()),
        "media_url": _media(item.get("media_url")),
        "color": color if _COLOR.match(color) else "#6e8bff",
    }


def _viewpoint(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise StudioError("Each viewpoint must be an object.")
    orbit = str(item.get("orbit") or "")
    target = str(item.get("target") or "")
    if not _ORBIT.match(orbit) or not _VEC3.match(target):
        raise StudioError("Viewpoints need an orbit like '30deg 75deg 2.5m' and a target 'x y z'.")
    fov = str(item.get("fov") or "45deg")
    name = _text(item.get("name"), 60)
    if not name:
        raise StudioError("Each viewpoint needs a name.")
    return {
        "id": _ident(item.get("id")),
        "name": name,
        "orbit": " ".join(orbit.split()),
        "target": " ".join(target.split()),
        "fov": fov.strip() if _FOV.match(fov) else "45deg",
    }


def _settings(raw: Any, viewpoint_ids: set[str]) -> dict[str, Any]:
    base = empty_document()["settings"]
    if not isinstance(raw, dict):
        return base
    background = str(raw.get("background") or base["background"])
    default_view = str(raw.get("default_viewpoint") or "")
    return {
        "background": background if _COLOR.match(background) else base["background"],
        "exposure": _clamp(raw.get("exposure"), 0.2, 2.5, base["exposure"]),
        "shadow": _clamp(raw.get("shadow"), 0.0, 1.0, base["shadow"]),
        "auto_rotate": bool(raw.get("auto_rotate")),
        "default_viewpoint": default_view if default_view in viewpoint_ids else "",
        "splat_up": str(raw.get("splat_up")) if raw.get("splat_up") in SPLAT_UP else "auto",
    }


def _ident(value: Any) -> str:
    text = str(value or "")
    return text if _ID.match(text) else uuid.uuid4().hex[:12]


def _text(value: Any, limit: int, *, multiline: bool = False) -> str:
    text = str(value or "")
    if multiline:
        return text.strip()[:limit]
    return " ".join(text.split())[:limit]


def _media(value: Any) -> str:
    """Only http(s) links or same-site paths; never javascript: or data: URLs."""
    url = str(value or "").strip()
    if not url:
        return ""
    if url.startswith("https://") or url.startswith("http://") or (url.startswith("/") and not url.startswith("//")):
        return url[:1000]
    raise StudioError("Media links must start with https://, http://, or /.")


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:  # NaN
        return default
    return round(min(high, max(low, number)), 3)
