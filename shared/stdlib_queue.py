"""Load the stdlib ``queue`` module.

This repo has a ``queue/`` package (Phase 12 placeholder) that shadows the
standard library. Open3D, Dash, Janus, and PyTorch all import ``queue.Empty``.
"""

from __future__ import annotations


def ensure_stdlib_queue() -> None:
    import importlib.util
    import os
    import sys
    from pathlib import Path

    stdlib_queue = Path(os.__file__).resolve().parent / "queue.py"
    current = sys.modules.get("queue")
    current_file = getattr(current, "__file__", None)
    if current_file:
        try:
            if Path(current_file).resolve() == stdlib_queue:
                return
        except OSError:
            pass
    spec = importlib.util.spec_from_file_location("queue", stdlib_queue)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load stdlib queue from {stdlib_queue}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["queue"] = module
    spec.loader.exec_module(module)
