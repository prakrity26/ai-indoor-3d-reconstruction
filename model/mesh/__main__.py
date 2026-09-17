"""CLI: python -m model.mesh JOB_DIR"""

from __future__ import annotations

import argparse
import json
import sys

from model.mesh.exceptions import MeshError
from model.mesh.pipeline import reconstruct_mesh


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Poisson-mesh a Phase 6 filtered point cloud and export PLY/GLB.",
    )
    parser.add_argument("source", help="Job directory or cloud_filtered.ply from Phase 6")
    parser.add_argument(
        "--output",
        default=None,
        help="Triangle-mesh PLY path (default: <job>/mesh.ply)",
    )
    parser.add_argument(
        "--glb",
        default=None,
        help="GLB path (default: <job>/mesh.glb)",
    )
    args = parser.parse_args(argv)

    try:
        result = reconstruct_mesh(args.source, output_ply=args.output, output_glb=args.glb)
    except MeshError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, indent=2))
        return 1

    summary = {
        "ok": True,
        "job_id": result.job_id,
        "strategy": result.strategy,
        "input_count": result.input_count,
        "vertex_count": result.vertex_count,
        "triangle_count": result.triangle_count,
        "ply_path": result.ply_path,
        "glb_path": result.glb_path,
        "manifest_path": result.manifest_path,
        "warnings": [issue.message for issue in result.warnings],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
