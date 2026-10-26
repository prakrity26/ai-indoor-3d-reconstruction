"""Read counts from job JSON and PLY headers. Does not rerun reconstruction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def ply_counts(path: Path) -> dict[str, int] | None:
    """Return element counts from a PLY header. Git LFS pointers are skipped."""
    if not path.is_file():
        return None
    raw = path.read_bytes()[:65536]
    if raw.startswith(b"version https://git-lfs.github.com/spec"):
        return None
    header = raw.split(b"end_header", 1)[0].decode("ascii", errors="replace")
    if not header.startswith("ply"):
        return None
    counts: dict[str, int] = {}
    for line in header.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "element":
            counts[parts[1]] = int(parts[2])
    return counts or None


def int_or_none(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None
