"""Separate worker process. It never runs inside an upload request.

    python -m queue.workers --pipeline mesh                     # Phases 1–9, this machine
    python -m queue.workers --pipeline splat                    # GPU, shares the database
    python -m queue.workers --pipeline splat \\
        --gateway https://<tunnel-url> --token $WORKER_TOKEN     # GPU elsewhere (Colab)
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

from shared.broker import wait
from shared.jobs import default_store, serve
from shared.local_job import run_mesh_job


def train_mesh(source: str, job_id: str, report=None):
    return run_mesh_job(source, job_id, report=report)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run queued reconstructions outside the API.")
    parser.add_argument("--once", action="store_true", help="Process queued jobs, then exit.")
    parser.add_argument(
        "--pipeline",
        choices=("splat", "mesh"),
        default="mesh",
        help="mesh runs Phases 1–9 on this machine; splat trains Gaussian splats on a CUDA GPU.",
    )
    parser.add_argument("--gateway", default=os.environ.get("WORKER_GATEWAY_URL", ""), help="Worker gateway URL for a remote GPU worker.")
    parser.add_argument("--token", default=os.environ.get("WORKER_TOKEN", ""), help="Gateway token (or set WORKER_TOKEN).")
    parser.add_argument("--backend", choices=("splatfacto", "gsplat"), default=os.environ.get("SPLAT_BACKEND", "splatfacto"))
    parser.add_argument("--work-dir", default=os.environ.get("SPLAT_WORK_DIR", "data/splat_work"))
    parser.add_argument("--name", default=os.environ.get("WORKER_NAME", ""), help="Shown as the worker in job details.")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # docker stop sends SIGTERM: exit through SystemExit so the current job is marked failed.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))

    if args.pipeline == "mesh":
        store = default_store()
        print(f"mesh worker watching {store.root}", flush=True)
        serve(store, train_mesh, once=args.once, wait=wait)
        return

    from shared import splat_worker

    trainer = splat_worker.TRAINERS[args.backend]
    if args.gateway:
        if not args.token:
            parser.error("--gateway needs --token or WORKER_TOKEN")
        queue = splat_worker.GatewaySplatQueue(args.gateway, args.token, worker=args.name)
        queue.ping()
        print(f"splat worker ({args.backend}) connected to {args.gateway}", flush=True)
    else:
        store = default_store()
        queue = splat_worker.LocalSplatQueue(store, worker=args.name)
        print(f"splat worker ({args.backend}) watching {store.root}", flush=True)
    splat_worker.run(queue, trainer, Path(args.work_dir), once=args.once)


if __name__ == "__main__":
    main()
