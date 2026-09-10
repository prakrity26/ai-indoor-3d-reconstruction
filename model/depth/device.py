"""Resolve COMPUTE_DEVICE without importing PyTorch at module load."""

from __future__ import annotations


def ensure_stdlib_queue() -> None:
    """Our package `queue/` shadows the stdlib module PyTorch needs."""
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


def _drop_partial_torch() -> None:
    import sys

    for name in list(sys.modules):
        if name == "torch" or name.startswith("torch."):
            del sys.modules[name]


def resolve_torch_device(preference: str, *, cuda: bool, mps: bool) -> str:
    """Pick a device. auto prefers CUDA, then MPS, then CPU."""
    pref = (preference or "auto").strip().lower()
    if pref == "cpu":
        return "cpu"
    if pref == "cuda":
        return "cuda" if cuda else "cpu"
    if pref == "mps":
        return "mps" if mps else "cpu"
    if cuda:
        return "cuda"
    if mps:
        return "mps"
    return "cpu"


def resolve_device(preference: str = "auto") -> str:
    ensure_stdlib_queue()
    cuda = False
    mps = False
    try:
        import torch

        cuda = bool(torch.cuda.is_available())
        mps_backend = getattr(torch.backends, "mps", None)
        mps = bool(mps_backend is not None and mps_backend.is_available())
    except ImportError:
        _drop_partial_torch()
        if preference in {"cuda", "mps"}:
            return "cpu"
        return resolve_torch_device(preference, cuda=False, mps=False)
    except Exception:
        _drop_partial_torch()
        return resolve_torch_device(preference, cuda=False, mps=False)
    return resolve_torch_device(preference, cuda=cuda, mps=mps)
