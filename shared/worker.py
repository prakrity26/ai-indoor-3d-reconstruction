"""Separate worker process. It never runs inside an upload request."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from shared.broker import wait
from shared.jobs import default_store, serve
from shared.local_job import run_mesh_job


def train_splat(source: str, job_id: str, report=None):
    from model.splat.pipeline import reconstruct_gaussian_splat

    if report is not None:
        report("Training Gaussian splat (GPU)", 5)
    root = os.environ.get("SPLAT_KEEP_ROOT", "").strip()
    if root:
        os.environ["SPLAT_KEEP_DIR"] = str(Path(root) / job_id)
    return reconstruct_gaussian_splat(source, job_id=job_id)


def train_mesh(source: str, job_id: str, report=None):
    return run_mesh_job(source, job_id, report=report)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run queued reconstructions outside the API.")
    parser.add_argument("--once", action="store_true", help="Process queued jobs, then exit.")
    parser.add_argument(
        "--pipeline",
        choices=("splat", "mesh"),
        default="splat",
        help="splat needs CUDA. mesh runs Phases 1–9 on this machine.",
    )
    args = parser.parse_args(argv)
    store = default_store()
    train = train_mesh if args.pipeline == "mesh" else train_splat
    print(f"{args.pipeline} worker watching {store.root}", flush=True)
    serve(store, train, once=args.once, wait=wait)


if __name__ == "__main__":
    main()
