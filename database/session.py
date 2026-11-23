"""Open SQLite by default. PostgreSQL is used only when DATABASE_URL says so."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from database.exceptions import DatabaseError

_MIGRATIONS = Path(__file__).resolve().parent / "migrations"


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
    normalized = normalize_url(url)
    if normalized.startswith("sqlite"):
        # The API and the worker open the same file; wait for the lock instead of failing.
        engine = create_engine(normalized, future=True, connect_args={"timeout": 30})

        @event.listens_for(engine, "connect")
        def _wal(dbapi_connection, _record) -> None:  # pragma: no cover - driver hook
            dbapi_connection.execute("PRAGMA journal_mode=WAL")
    else:
        engine = create_engine(normalized, future=True, pool_pre_ping=True)
    migrate(engine)
    return engine


def migration_files() -> list[Path]:
    return sorted(_MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))


def migrate(engine: Engine) -> list[str]:
    """Apply each numbered SQL file once. Returns the versions applied by this call."""
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)"))
    applied: list[str] = []
    for path in migration_files():
        version = path.stem
        with engine.connect() as connection:
            done = connection.execute(
                text("SELECT 1 FROM schema_migrations WHERE version = :v"), {"v": version}
            ).first()
        if done:
            continue
        try:
            with engine.begin() as connection:
                # Claim the version first so a second process blocks here and then skips.
                connection.execute(text("INSERT INTO schema_migrations (version) VALUES (:v)"), {"v": version})
                for statement in _statements(path):
                    connection.execute(text(statement))
        except IntegrityError:
            continue
        except (OperationalError, ProgrammingError) as exc:
            if "duplicate column" in str(exc).lower() or "already exists" in str(exc).lower():
                # A database created before version tracking existed: record and move on.
                with engine.begin() as connection:
                    connection.execute(
                        text("INSERT INTO schema_migrations (version) VALUES (:v)"), {"v": version}
                    )
                continue
            raise DatabaseError("migration_failed", f"{path.name}: {exc}") from exc
        applied.append(version)
    return applied


def _statements(path: Path) -> list[str]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("--")]
    return [part.strip() for part in "\n".join(lines).split(";") if part.strip()]
