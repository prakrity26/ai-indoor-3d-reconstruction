"""Phase 11 stores job status in SQLite. Postgres is the same table when configured."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from database.exceptions import DatabaseError
from database.repositories.jobs import JobRepository
from database.session import migrate, sqlite_url
from shared.jobs import JobStore


def test_round_trip_and_second_migrate(tmp_path: Path) -> None:
    repo = JobRepository(sqlite_url(tmp_path))
    migrate(repo.engine)
    saved = repo.insert(
        {
            "job_id": "kitchen",
            "status": "queued",
            "filename": "kitchen.mp4",
            "source_path": "/tmp/kitchen.mp4",
            "ply_path": "",
            "error": "",
        }
    )
    assert saved["status"] == "queued"
    assert repo.get("kitchen")["filename"] == "kitchen.mp4"
    assert repo.get("missing") is None
    claimed = repo.claim_next()
    assert claimed is not None
    assert claimed["status"] == "running"
    assert repo.claim_next() is None
    done = repo.save_status("kitchen", "succeeded", ply_path="/tmp/point_cloud.ply", error="")
    assert done["ply_path"] == "/tmp/point_cloud.ply"
    assert [item["job_id"] for item in repo.list_jobs()] == ["kitchen"]


def test_store_keeps_the_video_and_the_row(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    record = store.create("Hall.mov", b"video-bytes")
    assert record["job_id"] == "hall"
    assert Path(record["source_path"]).read_bytes() == b"video-bytes"
    assert (tmp_path / "jobs" / "index.sqlite").is_file()
    failed = store.fail("hall", "cuda required")
    assert failed["status"] == "failed"
    assert store.get("hall")["error"] == "cuda required"


def test_postgres_url_needs_the_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate the driver being absent even where the db extra is installed (CI installs it).
    monkeypatch.setitem(sys.modules, "psycopg", None)
    with pytest.raises(DatabaseError) as err:
        JobRepository("postgresql://reconstruction:change-me@localhost:5432/reconstruction")
    assert err.value.code == "postgres_driver_missing"
