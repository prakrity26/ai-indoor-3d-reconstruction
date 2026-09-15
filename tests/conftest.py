"""Pytest hooks. Open3D pulls in Dash, which needs the stdlib queue module."""

from shared.stdlib_queue import ensure_stdlib_queue

ensure_stdlib_queue()
