"""CLI: python -m model.splat VIDEO

Same git repository as the rest of the internship. Training needs CUDA (Colab).
"""

from __future__ import annotations

import argparse
import json
import sys

from model.splat.exceptions import SplatError
from model.splat.pipeline import reconstruct_gaussian_splat


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare frames and (on CUDA) train a 3D Gaussian splat in this repo.",
    )
    parser.add_argument("source", help="Indoor video, or a job directory that already has splat/images")
    parser.add_argument("--job-id", default=None, help="Job folder name under data/frames")
    parser.add_argument(
        "--frames-dir",
        default=None,
        help="Root for job folders (default FRAMES_DIR)",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Extract overlapping JPEGs on this machine; skip COLMAP and training",
    )
    args = parser.parse_args(argv)

    try:
        result = reconstruct_gaussian_splat(
            args.source,
            job_id=args.job_id,
            frames_dir=args.frames_dir,
            prepare_only=args.prepare_only,
        )
    except SplatError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, indent=2))
        return 1

    summary = {
        "ok": True,
        "job_id": result.job_id,
        "strategy": result.strategy,
        "image_count": result.image_count,
        "registered_images": result.registered_images,
        "ply_path": result.ply_path,
        "colmap_dir": result.colmap_dir,
        "manifest_path": result.manifest_path,
        "warnings": [issue.message for issue in result.warnings],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
