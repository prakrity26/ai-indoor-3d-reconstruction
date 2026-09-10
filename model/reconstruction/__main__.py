"""CLI: python -m model.reconstruction JOB_DIR"""

from __future__ import annotations

import argparse
import json
import sys

from model.reconstruction.exceptions import ReconstructionError
from model.reconstruction.pipeline import build_point_cloud


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Back-project posed depth maps into a colored PLY point cloud.",
    )
    parser.add_argument("source", help="Job directory that contains poses.json and depth.json")
    parser.add_argument(
        "--output",
        default=None,
        help="PLY path (default: <job>/cloud.ply)",
    )
    args = parser.parse_args(argv)

    try:
        result = build_point_cloud(args.source, output_ply=args.output)
    except ReconstructionError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, indent=2))
        return 1

    summary = {
        "ok": True,
        "job_id": result.job_id,
        "strategy": result.strategy,
        "frame_count": result.frame_count,
        "point_count": result.point_count,
        "ply_path": result.ply_path,
        "manifest_path": result.manifest_path,
        "warnings": [issue.message for issue in result.warnings],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
