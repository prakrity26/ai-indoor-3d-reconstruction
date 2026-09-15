"""CLI: python -m model.pointcloud JOB_DIR"""

from __future__ import annotations

import argparse
import json
import sys

from model.pointcloud.exceptions import PointCloudError
from model.pointcloud.pipeline import filter_point_cloud


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Denoise, crop, and voxel-fuse a Phase 5 point cloud.",
    )
    parser.add_argument("source", help="Job directory or cloud.ply from Phase 5")
    parser.add_argument(
        "--output",
        default=None,
        help="PLY path (default: <job>/cloud_filtered.ply)",
    )
    args = parser.parse_args(argv)

    try:
        result = filter_point_cloud(args.source, output_ply=args.output)
    except PointCloudError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, indent=2))
        return 1

    summary = {
        "ok": True,
        "job_id": result.job_id,
        "strategy": result.strategy,
        "input_count": result.input_count,
        "after_crop": result.after_crop,
        "after_outlier": result.after_outlier,
        "output_count": result.output_count,
        "ply_path": result.ply_path,
        "manifest_path": result.manifest_path,
        "warnings": [issue.message for issue in result.warnings],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
