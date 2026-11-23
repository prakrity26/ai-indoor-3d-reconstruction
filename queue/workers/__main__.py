"""python -m queue.workers

Claims uploaded videos in a separate process. --pipeline splat is the GPU path.
--pipeline mesh runs Phases 1–9 on this machine. --once drains the queue and exits.
"""

from shared.stdlib_queue import ensure_stdlib_queue

# `python -m queue.workers` imports this repo's queue/ package as `queue`; restore the stdlib
# module before httpx, anyio, torch, or Open3D look for queue.Queue.
ensure_stdlib_queue()

from shared.worker import main  # noqa: E402

if __name__ == "__main__":
    main()
