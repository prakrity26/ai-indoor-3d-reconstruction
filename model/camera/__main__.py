"""CLI: python -m model.camera JOB_DIR"""

from __future__ import annotations

import argparse
import json
import sys

from model.camera.exceptions import CameraPoseError
from model.camera.pipeline import estimate_poses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Estimate monocular camera poses from selected keyframes.",
    )
    parser.add_argument(
        "source",
        help="Job directory, selection.json, or a folder of keyframes",
    )
    parser.add_argument("--job-id", default=None, help="Optional job identifier")
    parser.add_argument(
        "--output",
        default=None,
        help="Path for poses.json (default: <job>/poses.json)",
    )
    args = parser.parse_args(argv)

    try:
        result = estimate_poses(
            args.source,
            job_id=args.job_id,
            output_path=args.output,
        )
    except CameraPoseError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, indent=2))
        return 1

    summary = {
        "ok": True,
        "job_id": result.job_id,
        "strategy": result.strategy,
        "scale_meaning": result.scale_meaning,
        "input_count": result.input_count,
        "posed_count": result.posed_count,
        "failed_count": result.failed_count,
        "poses_path": result.poses_path,
        "intrinsics": result.intrinsics.matrix() if result.intrinsics else None,
        "warnings": [issue.message for issue in result.warnings],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
