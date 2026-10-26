"""GPU worker entry. Implementation lives in shared.jobs so it can load beside the API."""

from shared.jobs import default_store, process_next, serve

__all__ = ["default_store", "process_next", "serve"]
