"""Runtime hook. A stage calls this; Phase 9 copies the numbers into evaluation.json."""

from __future__ import annotations

import json
from pathlib import Path


def note_duration(job_dir: str | Path, stage: str, seconds: float) -> Path:
    """Record one stage duration in ``<job>/timings.json``."""
    folder = Path(job_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "timings.json"
    payload: dict[str, float] = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict):
            payload = {str(key): float(value) for key, value in loaded.items()}
    payload[stage] = round(float(seconds), 4)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
