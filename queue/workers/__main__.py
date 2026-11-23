"""python -m queue.workers

Claims uploaded videos in a separate process. --pipeline splat is the GPU path.
--pipeline mesh runs Phases 1–9 on this machine. --once drains the queue and exits.
"""

from shared.worker import main

if __name__ == "__main__":
    main()
