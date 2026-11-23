"""Open SQLite by default. PostgreSQL is used only when DATABASE_URL says so."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from database.exceptions import DatabaseError

_MIGRATION = Path(__file__).resolve().parent / "migrations" / "001_jobs.sql"


def sqlite_url(root: Path) -> str:
    folder = Path(root)
    folder.mkdir(parents=True, exist_ok=True)
    return "sqlite:///" + (folder / "index.sqlite").resolve().as_posix()


def normalize_url(url: str) -> str:
    raw = url.strip()
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        try:
            import psycopg  # noqa: F401
        except ImportError as exc:
            raise DatabaseError(
                "postgres_driver_missing",
                'PostgreSQL needs the db extra: pip install -e ".[db]"',
            ) from exc
        return "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


def connect(url: str) -> Engine:
    engine = create_engine(normalize_url(url), future=True)
    migrate(engine)
    return engine


def migrate(engine: Engine) -> None:
    lines = [line for line in _MIGRATION.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("--")]
    statements = [part.strip() for part in "\n".join(lines).split(";") if part.strip()]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
