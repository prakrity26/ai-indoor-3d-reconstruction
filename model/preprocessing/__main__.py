"""CLI: python -m model.preprocessing VIDEO"""

from __future__ import annotations

import argparse
import json
import sys

from model.preprocessing.exceptions import VideoValidationError
from model.preprocessing.pipeline import ingest_video


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate an indoor video and extract uniformly sampled frames.",
    )
    parser.add_argument("video", help="Path to a monocular indoor video file")
    parser.add_argument("--job-id", default=None, help="Optional job identifier")
    parser.add_argument(
        "--frames-dir",
        default=None,
        help="Root directory for extracted frames (default: FRAMES_DIR / data/frames)",
    )
    parser.add_argument(
        "--target-fps",
        type=float,
        default=None,
        help="Uniform extraction rate. Default comes from TARGET_EXTRACT_FPS.",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Safety cap on extracted frames.",
    )
    args = parser.parse_args(argv)

    try:
        result = ingest_video(
            args.video,
            job_id=args.job_id,
            frames_dir=args.frames_dir,
            target_fps=args.target_fps,
            max_frames=args.max_frames,
        )
    except VideoValidationError as exc:
        print(json.dumps({"ok": False, "error": exc.to_dict()}, indent=2))
        return 1

    summary = {
        "ok": True,
        "job_id": result.job_id,
        "extracted_frames": len(result.frames),
        "stride": result.stride,
        "manifest_path": result.manifest_path,
        "frames_dir": result.frames_dir,
        "video": {
            "width": result.video.width,
            "height": result.video.height,
            "fps": result.video.fps,
            "duration_sec": result.video.duration_sec,
            "codec": result.video.codec,
        },
        "quality": {
            "mean_brightness": result.quality.mean_brightness,
            "mean_laplacian_variance": result.quality.mean_laplacian_variance,
            "likely_blurry": result.quality.likely_blurry,
            "likely_dark": result.quality.likely_dark,
        },
        "warnings": [issue.message for issue in result.warnings],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
