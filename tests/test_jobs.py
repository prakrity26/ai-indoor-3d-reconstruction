"""Upload creates a job. The worker, not the request, produces the splat."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from shared.jobs import JobStore, job_id_from_filename, process_next


class _Result:
    def __init__(self, ply_path: str) -> None:
        self.ply_path = ply_path


def test_two_uploads_stay_separate_scenes(tmp_path: Path) -> None:
    client = TestClient(create_app(JobStore(tmp_path / "jobs")))
    first = client.post("/jobs", files={"file": ("kitchen.mp4", b"kitchen", "video/mp4")})
    second = client.post("/jobs", files={"file": ("hallway.mov", b"hallway", "video/quicktime")})
    assert first.json()["job_id"] == "kitchen"
    assert second.json()["job_id"] == "hallway"
    listed = client.get("/jobs").json()["jobs"]
    assert [item["job_id"] for item in listed] == ["hallway", "kitchen"]


def test_job_id_uses_the_file_name() -> None:
    assert job_id_from_filename("My Room.mp4") == "my_room"


def test_upload_then_worker_writes_a_splat(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    client = TestClient(create_app(store))
    created = client.post("/jobs", files={"file": ("kitchen.mp4", b"fake-video", "video/mp4")})
    assert created.status_code == 200
    body = created.json()
    assert body["job_id"] == "kitchen"
    assert body["status"] == "queued"
    assert body["splat_url"] == ""

    def train(source: str, job_id: str) -> _Result:
        assert Path(source).is_file()
        ply = tmp_path / "frames" / job_id / "splat" / "point_cloud.ply"
        ply.parent.mkdir(parents=True)
        ply.write_bytes(b"ply")
        return _Result(str(ply))

    assert process_next(store, train) is True
    status = client.get("/jobs/kitchen")
    assert status.status_code == 200
    assert status.json()["status"] == "succeeded"
    assert status.json()["splat_url"] == "/jobs/kitchen/point_cloud.ply"
    downloaded = client.get("/jobs/kitchen/point_cloud.ply")
    assert downloaded.status_code == 200
    assert downloaded.content == b"ply"
    assert process_next(store, train) is False


def test_each_upload_trains_as_its_own_scene(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    client = TestClient(create_app(store))
    client.post("/jobs", files={"file": ("kitchen.mp4", b"kitchen-video", "video/mp4")})
    client.post("/jobs", files={"file": ("hallway.mov", b"hallway-video", "video/quicktime")})
    trained: list[str] = []

    def train(source: str, job_id: str) -> _Result:
        trained.append(job_id)
        assert Path(source).read_bytes().startswith(job_id.encode())
        ply = tmp_path / f"{job_id}.ply"
        ply.write_bytes(job_id.encode())
        return _Result(str(ply))

    assert process_next(store, train) is True
    assert process_next(store, train) is True
    assert process_next(store, train) is False
    assert trained == ["hallway", "kitchen"]
    assert client.get("/jobs/kitchen/point_cloud.ply").content == b"kitchen"
    assert client.get("/jobs/hallway/point_cloud.ply").content == b"hallway"


def test_worker_failure_is_visible_to_the_client(tmp_path: Path) -> None:
    store = JobStore(tmp_path / "jobs")
    client = TestClient(create_app(store))
    client.post("/jobs", files={"file": ("room.mov", b"video", "video/quicktime")})

    def train(source: str, job_id: str) -> _Result:
        raise RuntimeError("cuda required")

    process_next(store, train)
    body = client.get("/jobs/room").json()
    assert body["status"] == "failed"
    assert "cuda required" in body["error"]
    assert client.get("/jobs/room/point_cloud.ply").status_code == 409


def test_rejects_non_video(tmp_path: Path) -> None:
    client = TestClient(create_app(JobStore(tmp_path / "jobs")))
    response = client.post("/jobs", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400
