"""Wake the worker. The database is the queue. Redis only notifies when configured."""

from __future__ import annotations

import os
import time

from database.exceptions import DatabaseError

QUEUE_KEY = "reconstruction.jobs"


class QueueError(DatabaseError):
    """Redis was requested and could not be used."""


def publish(job_id: str) -> str:
    """Notify a worker. With no REDIS_URL the database row is the only signal."""
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return "database"
    client = _client(url)
    try:
        client.lpush(QUEUE_KEY, job_id)
    except Exception as exc:
        if exc.__class__.__name__ == "QueueError":
            raise
        raise QueueError("redis_unavailable", str(exc)) from exc
    return "redis"


def wait(timeout: float) -> None:
    """Block until Redis delivers a job id, or sleep when Redis is not configured."""
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        time.sleep(timeout)
        return
    try:
        _client(url).brpop(QUEUE_KEY, timeout=max(1, int(timeout)))
    except Exception:
        time.sleep(timeout)


def _client(url: str):
    try:
        import redis
    except ImportError as exc:
        raise QueueError(
            "redis_driver_missing",
            'Redis needs the queue extra: pip install -e ".[queue]"',
        ) from exc
    return redis.Redis.from_url(url, socket_connect_timeout=0.3)
