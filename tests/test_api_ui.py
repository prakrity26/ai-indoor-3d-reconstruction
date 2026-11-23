"""The UI reads jobs from the API, including the checked-in sample mesh."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from shared.jobs import JobStore
from ui.board import describe


def test_sample_mesh_is_listed_and_downloadable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FRAMES_DIR", str(tmp_path / "frames"))
    client = TestClient(create_app(JobStore(tmp_path / "jobs"), include_library=True))
    listed = client.get("/jobs")
    assert listed.status_code == 200
    sample = next(item for item in listed.json()["jobs"] if item["job_id"] == "img7916")
    assert sample["status"] == "succeeded"
    assert sample["mesh_url"] == "/jobs/img7916/mesh.glb"
    assert sample["splat_url"] == ""
    assert sample["summary"]["mesh_vertices"] == 17187
    assert sample["summary"]["posed_frames"] == 17
    assert sample["summary"]["selected_frames"] == 70
    assert describe(sample) == "succeeded · 17/70 posed · 17187 vertices · mesh ready"

    mesh = client.get("/jobs/img7916/mesh.glb")
    assert mesh.status_code == 200
    assert mesh.content.startswith(b"glTF")
    # The walk viewer probes with HEAD before downloading, so HEAD must not be a 405.
    head = client.head("/jobs/img7916/mesh.glb")
    assert head.status_code == 200 and head.content == b""

    evaluation = client.get("/jobs/img7916/evaluation.json")
    assert evaluation.status_code == 200
    body = evaluation.json()
    assert body["scale_meaning"] == "arbitrary_monocular"
    assert body["posed_ratio"] == round(17 / 70, 4)
    assert client.get("/jobs/img7916/scene.json").status_code == 404
    assert client.get("/jobs/img7916/point_cloud.ply").status_code == 409
    assert client.head("/jobs/img7916/point_cloud.ply").status_code == 409


def test_platform_and_orbit_pages_load(tmp_path: Path) -> None:
    client = TestClient(create_app(JobStore(tmp_path / "jobs"), include_library=True))
    platform = client.get("/")
    orbit = client.get("/orbit")
    assert platform.status_code == 200
    assert "Indoor Spaces" in platform.text
    assert "/assets/js/main.js" in platform.text
    assert client.get("/assets/js/main.js").status_code == 200
    assert client.get("/assets/app.css").status_code == 200
    assert orbit.status_code == 200
    assert "model-viewer" in orbit.text


def test_unknown_job_id_is_rejected(tmp_path: Path) -> None:
    client = TestClient(create_app(JobStore(tmp_path / "jobs"), include_library=True))
    assert client.get("/jobs/not-a-room").status_code == 404
    assert client.get("/jobs/../mesh.glb").status_code == 404
