"""CLI: python -m model.frame_selection JOB_DIR"""

from __future__ import annotations

import argparse
import json
import sys

from model.frame_selection.exceptions import FrameSelectionError
from model.frame_selection.pipeline import select_keyframes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Select coverage-preserving keyframes from extracted frames.",
    )
    parser.add_argument(
        "source",
        help="Job directory, frames directory, or Phase 1 manifest.json",
    )
    parser.add_argument("--job-id", default=None, help="Optional job identifier")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for copied keyframes (default: <job>/selected)",
    )
    args = parser.parse_args(argv)

    try:
        result = select_keyframes(
            args.source,
            job_id=args.job_id,
            output_dir=args.output_dir,
        )
    except FrameSelectionError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, indent=2))
        return 1

    summary = {
        "ok": True,
        "job_id": result.job_id,
        "strategy": result.strategy,
        "input_count": result.input_count,
        "selected_count": len(result.selected),
        "selected_dir": result.selected_dir,
        "selection_path": result.selection_path,
        "reasons": sorted({item.reason for item in result.selected}),
        "warnings": [issue.message for issue in result.warnings],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
