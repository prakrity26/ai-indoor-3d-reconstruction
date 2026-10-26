"""CLI: python -m model.scene_understanding JOB_DIR"""

from __future__ import annotations

import argparse
import json
import sys

from model.scene_understanding.exceptions import SceneError
from model.scene_understanding.pipeline import understand_scene


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Label indoor objects on keyframes and place them when depth and pose exist.",
    )
    parser.add_argument("source", help="Job directory from Phases 1–4")
    parser.add_argument("--job-id", default=None, help="Optional job identifier")
    args = parser.parse_args(argv)

    try:
        result = understand_scene(args.source, job_id=args.job_id)
    except SceneError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, indent=2))
        return 1

    summary = {
        "ok": True,
        "job_id": result.job_id,
        "strategy": result.strategy,
        "scale_meaning": result.scale_meaning,
        "frame_count": result.frame_count,
        "detection_count": result.detection_count,
        "objects": len(result.objects),
        "manifest_path": result.manifest_path,
        "warnings": [issue.message for issue in result.warnings],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
