"""Phase 12: the database is the queue. Redis is an optional wake-up."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.broker import QueueError, publish
from shared.jobs import JobStore, process_next
from shared.local_job import run_mesh_job
from shared.worker import main


def test_publish_without_redis_uses_the_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert publish("kitchen") == "database"


def test_redis_url_without_a_server_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    with pytest.raises(QueueError) as err:
        publish("kitchen")
    assert err.value.code in {"redis_driver_missing", "redis_unavailable"}


def test_mesh_job_can_finish_without_a_splat(tmp_path: Path) -> None:
    mesh = tmp_path / "mesh.glb"
    mesh.write_bytes(b"glb")

    def stage(state: dict) -> None:
        assert state["job_id"] == "room"
        state["mesh_path"] = str(mesh)

    result = run_mesh_job(str(tmp_path / "clip.mp4"), "room", stages=[stage])
    store = JobStore(tmp_path / "jobs")
    store.create("room.mp4", b"video")

    def train(source: str, job_id: str):
        assert Path(source).is_file()
        return result

    assert process_next(store, train) is True
    saved = store.get("room")
    assert saved is not None
    assert saved["status"] == "succeeded"
    assert saved["ply_path"] == ""


def test_worker_once_drains_with_the_mesh_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    store.create("room.mp4", b"video")
    mesh = tmp_path / "mesh.glb"
    mesh.write_bytes(b"glb")

    def fake_mesh(source: str, job_id: str):
        return run_mesh_job(source, job_id, stages=[lambda state: state.update(mesh_path=str(mesh))])

    monkeypatch.setattr("shared.worker.default_store", lambda: store)
    monkeypatch.setattr("shared.worker.train_mesh", fake_mesh)
    main(["--once", "--pipeline", "mesh"])
    assert store.get("room")["status"] == "succeeded"
