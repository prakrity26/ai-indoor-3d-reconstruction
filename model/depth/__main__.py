"""CLI: python -m model.depth JOB_DIR

Runs on a local Phase 1–3 job. Does not download Hugging Face videos.
Copy your own indoor recording to data/uploads and run Phases 1–3 first.
"""

from __future__ import annotations

import argparse
import json
import sys

from model.depth.exceptions import DepthEstimationError
from model.depth.pipeline import estimate_depth


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate relative depth for local keyframes. "
            "Use your own indoor video; Hugging Face demo clips are not used."
        ),
    )
    parser.add_argument(
        "source",
        help="Job directory from Phases 1–3 (not a Hugging Face dataset URL)",
    )
    parser.add_argument("--job-id", default=None, help="Optional job identifier")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for .npy depth maps (default: <job>/depth)",
    )
    args = parser.parse_args(argv)

    try:
        result = estimate_depth(
            args.source,
            job_id=args.job_id,
            output_dir=args.output_dir,
        )
    except DepthEstimationError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, indent=2))
        return 1

    summary = {
        "ok": True,
        "job_id": result.job_id,
        "strategy": result.strategy,
        "device": result.device,
        "model_id": result.model_id,
        "input_count": result.input_count,
        "depth_maps": len(result.maps),
        "depth_dir": result.depth_dir,
        "manifest_path": result.manifest_path,
        "warnings": [issue.message for issue in result.warnings],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
