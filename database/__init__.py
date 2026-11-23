"""Job metadata (Phase 11). SQLite locally, PostgreSQL when DATABASE_URL is set."""

from database.exceptions import DatabaseError
from database.repositories.jobs import JobRepository

__all__ = ["DatabaseError", "JobRepository"]
