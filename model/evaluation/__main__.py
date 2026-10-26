"""CLI: python -m model.evaluation JOB_DIR"""

from __future__ import annotations

import argparse
import json
import sys

from model.evaluation.exceptions import EvaluationError
from model.evaluation.pipeline import evaluate_job


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score an existing reconstruction and write evaluation.json.",
    )
    parser.add_argument("source", help="Job directory with poses, a cloud, a mesh, or a splat")
    parser.add_argument("--job-id", default=None, help="Optional job identifier")
    args = parser.parse_args(argv)

    try:
        result = evaluate_job(args.source, job_id=args.job_id)
    except EvaluationError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, indent=2))
        return 1

    summary = {
        "ok": True,
        "job_id": result.job_id,
        "strategy": result.strategy,
        "scale_meaning": result.scale_meaning,
        "posed_ratio": result.posed_ratio,
        "filtered_points": result.filtered_points,
        "mesh_vertices": result.mesh_vertices,
        "mesh_triangles": result.mesh_triangles,
        "splat_walkable": result.splat_walkable,
        "manifest_path": result.manifest_path,
        "warnings": [issue.message for issue in result.warnings],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
