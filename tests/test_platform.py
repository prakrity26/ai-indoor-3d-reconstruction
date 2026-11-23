"""Projects, progress, the studio document, sharing, and deletion through the API."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from api import studio
from api.app import create_app
from database.session import migrate
from shared.jobs import JobStore, process_next
from shared.local_job import run_mesh_job


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("FRAMES_DIR", str(tmp_path / "frames"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    store = JobStore(tmp_path / "jobs")
    return store, TestClient(create_app(store, include_library=True)), tmp_path


def _upload(client: TestClient, name: str = "Living room", filename: str = "living.mp4") -> dict:
    response = client.post(
        "/jobs",
        files={"file": (filename, b"video-bytes", "video/mp4")},
        data={"name": name, "description": "South-facing.\nTwo windows."},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_upload_keeps_name_description_and_source(env) -> None:
    _, client, _ = env
    body = _upload(client)
    assert body["job_id"] == "living_room"
    assert body["name"] == "Living room"
    assert body["description"] == "South-facing.\nTwo windows."
    assert body["status"] == "queued"
    assert body["stage"] == "queued"
    assert body["source_url"] == "/jobs/living_room/source"
    assert client.get(body["source_url"]).content == b"video-bytes"


def test_upload_limits(env, monkeypatch: pytest.MonkeyPatch) -> None:
    _, client, _ = env
    assert client.post("/jobs", files={"file": ("notes.txt", b"x", "text/plain")}).status_code == 400
    assert client.post("/jobs", files={"file": ("empty.mp4", b"", "video/mp4")}).status_code == 400
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    big = b"0" * (1024 * 1024 + 1)
    response = client.post("/jobs", files={"file": ("big.mp4", big, "video/mp4")})
    assert response.status_code == 413
    # The partial upload folder is cleaned up.
    assert not any(p.name.startswith("big") for p in (env[2] / "jobs").iterdir())


def test_rename_retry_and_delete(env) -> None:
    store, client, tmp_path = env
    body = _upload(client)
    job_id = body["job_id"]
    renamed = client.patch(f"/jobs/{job_id}", json={"name": "  Front   room ", "description": "Updated"})
    assert renamed.json()["name"] == "Front room"
    assert client.patch(f"/jobs/{job_id}", json={"name": "   "}).status_code == 400
    assert client.post(f"/jobs/{job_id}/retry").status_code == 409  # still queued

    store.claim_next()
    assert client.delete(f"/jobs/{job_id}").status_code == 409  # running
    store.fail(job_id, "boom")
    retried = client.post(f"/jobs/{job_id}/retry").json()
    assert retried["status"] == "queued" and retried["error"] == ""

    (tmp_path / "frames" / job_id).mkdir(parents=True)
    (tmp_path / "frames" / job_id / "mesh.glb").write_bytes(b"glTF")
    studio.save(store.root, job_id, studio.empty_document())
    assert client.delete(f"/jobs/{job_id}").status_code == 204
    assert client.get(f"/jobs/{job_id}").status_code == 404
    assert not (tmp_path / "frames" / job_id).exists()
    assert not (store.root / job_id).exists()
    assert not studio.studio_path(store.root, job_id).exists()


def test_samples_are_projects_but_cannot_be_deleted(env) -> None:
    _, client, _ = env
    listed = client.get("/jobs").json()["jobs"]
    sample = next(item for item in listed if item["job_id"] == "img7916")
    assert sample["origin"] == "sample"
    assert sample["thumbnail_url"] == "/jobs/img7916/thumbnail.jpg"
    assert client.get(sample["thumbnail_url"]).headers["content-type"] == "image/jpeg"
    assert client.delete("/jobs/img7916").status_code == 403


def test_worker_reports_stage_progress(env) -> None:
    store, client, tmp_path = env
    job_id = _upload(client)["job_id"]
    mesh = tmp_path / "mesh.glb"
    mesh.write_bytes(b"glTF")
    seen: list[tuple[str, int]] = []

    def first(state: dict) -> None:
        seen.append((store.get(job_id)["stage"], store.get(job_id)["progress"]))

    def second(state: dict) -> None:
        seen.append((store.get(job_id)["stage"], store.get(job_id)["progress"]))
        state["mesh_path"] = str(mesh)

    def train(source: str, job_id: str, report=None):
        return run_mesh_job(source, job_id, stages=[first, second], report=report)

    assert process_next(store, train)
    assert seen == [("Stage 1", 0), ("Stage 2", 50)]
    done = client.get(f"/jobs/{job_id}").json()
    assert done["status"] == "succeeded" and done["progress"] == 100 and done["stage"] == "done"
    assert done["mesh_url"] == f"/jobs/{job_id}/mesh.glb"
    assert client.get(done["mesh_url"]).content == b"glTF"


def test_studio_document_round_trip_and_validation(env) -> None:
    _, client, _ = env
    empty = client.get("/jobs/img7916/studio.json").json()
    assert empty["hotspots"] == [] and empty["settings"]["exposure"] == 1.0
    doc = {
        "hotspots": [
            {"id": "door", "kind": "info", "title": " Front   door ", "description": "Oak.\nOriginal.", "position": "0.1m 0.5m -0.2m", "normal": "0m 1m 0m", "color": "#22c55e"},
            {"kind": "media", "title": "Photo", "position": "1 2 3", "media_url": "https://example.com/a.jpg"},
        ],
        "viewpoints": [{"id": "v1", "name": "Entrance", "orbit": "0.5rad 1.2rad 2.4m", "target": "0m 0.4m 0m", "fov": "45deg"}],
        "settings": {"background": "#101010", "exposure": 9, "auto_rotate": True, "default_viewpoint": "v1"},
    }
    saved = client.put("/jobs/img7916/studio.json", json=doc)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["hotspots"][0]["title"] == "Front door"
    assert body["hotspots"][0]["description"] == "Oak.\nOriginal."
    assert len(body["hotspots"][1]["id"]) == 12  # generated
    assert body["settings"]["exposure"] == 2.5  # clamped
    assert body["settings"]["default_viewpoint"] == "v1"
    assert client.get("/jobs/img7916/studio.json").json() == body

    bad_media = {**doc, "hotspots": [{**doc["hotspots"][1], "media_url": "javascript:alert(1)"}]}
    assert client.put("/jobs/img7916/studio.json", json=bad_media).status_code == 400
    bad_position = {**doc, "hotspots": [{**doc["hotspots"][0], "position": "here"}]}
    assert client.put("/jobs/img7916/studio.json", json=bad_position).status_code == 400
    assert client.put("/jobs/img7916/studio.json", json=[1, 2]).status_code == 400


def test_sharing_publishes_a_read_only_link(env) -> None:
    _, client, _ = env
    client.put("/jobs/img7916/studio.json", json={"hotspots": [{"title": "Lamp", "position": "0 1 0"}]})
    private = client.get("/jobs/img7916").json()
    assert private["visibility"] == "private" and private["share_url"] == ""

    public = client.put("/jobs/img7916/visibility", json={"visibility": "public"}).json()
    token = public["share_url"].rsplit("/", 1)[1]
    assert public["embed_url"] == f"/embed/{token}"
    shared = client.get(f"/shared/{token}").json()
    assert shared["project"]["mesh_url"] == "/jobs/img7916/mesh.glb"
    assert shared["studio"]["hotspots"][0]["title"] == "Lamp"
    assert "source_path" not in shared["project"]
    assert client.get(f"/s/{token}").status_code == 200
    assert client.get(f"/embed/{token}").status_code == 200

    rotated = client.post("/jobs/img7916/share/rotate").json()
    assert rotated["share_url"] != public["share_url"]
    assert client.get(f"/shared/{token}").status_code == 404

    client.put("/jobs/img7916/visibility", json={"visibility": "private"})
    new_token = rotated["share_url"].rsplit("/", 1)[1]
    assert client.get(f"/shared/{new_token}").status_code == 404
    assert client.put("/jobs/img7916/visibility", json={"visibility": "everyone"}).status_code == 400


def test_health_and_config(env) -> None:
    _, client, _ = env
    assert client.get("/health").json()["status"] == "ok"
    config = client.get("/api/config").json()
    assert ".mp4" in config["video_extensions"]
    assert config["database"] == "sqlite"


def test_old_database_gains_project_columns(tmp_path: Path) -> None:
    """A Phase 11 database (only 001 applied, no version table) upgrades in place."""
    url = "sqlite:///" + (tmp_path / "index.sqlite").as_posix()
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE jobs (job_id TEXT PRIMARY KEY, status TEXT NOT NULL, filename TEXT NOT NULL,"
                " source_path TEXT NOT NULL, ply_path TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '',"
                " created_at TEXT NOT NULL)"
            )
        )
        connection.execute(text("INSERT INTO jobs VALUES ('old', 'succeeded', 'old.mp4', '', '', '', '2026-10-01T00:00:00+00:00')"))
    assert migrate(engine) == ["001_jobs", "002_projects"]
    assert migrate(engine) == []
    store = JobStore(tmp_path)
    old = store.get("old")
    assert old["visibility"] == "private" and old["origin"] == "upload" and old["progress"] == 0
