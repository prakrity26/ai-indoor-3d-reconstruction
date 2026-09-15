"""Resolve COMPUTE_DEVICE without importing PyTorch at module load."""

from __future__ import annotations


from shared.stdlib_queue import ensure_stdlib_queue

__all__ = [
    "ensure_stdlib_queue",
    "resolve_device",
    "resolve_torch_device",
]


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
