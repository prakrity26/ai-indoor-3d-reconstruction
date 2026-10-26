"""python -m queue.workers

Claims uploaded videos and runs the splat trainer. Use --once to drain the queue and exit.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from model.splat.pipeline import reconstruct_gaussian_splat
from shared.jobs import default_store, serve


def train_upload(source: str, job_id: str):
    """One uploaded video, one scene. A keep-root gets a folder per job so scenes do not overwrite."""
    root = os.environ.get("SPLAT_KEEP_ROOT", "").strip()
    if root:
        os.environ["SPLAT_KEEP_DIR"] = str(Path(root) / job_id)
    return reconstruct_gaussian_splat(source, job_id=job_id)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train each uploaded video as its own scene.")
    parser.add_argument("--once", action="store_true", help="Process queued jobs, then exit.")
    args = parser.parse_args(argv)
    print("splat worker watching", default_store().root, flush=True)
    serve(default_store(), train_upload, once=args.once)


if __name__ == "__main__":
    main()
