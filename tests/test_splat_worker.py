"""Remote GPU splat workers: the gateway, the worker loop, and the splatfacto runner.

Nothing here needs a GPU. The gateway runs in-process (TestClient is an httpx client), the
trainer is a fake that writes a PLY, and splatfacto's commands are stand-in shell scripts.
"""

from __future__ import annotations

import os
import stat
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.worker_gateway import create_worker_app
from shared import splat_worker
from shared.jobs import JobStore

TOKEN = "t" * 32
PLY = b"ply\nformat binary_little_endian 1.0\nelement vertex 1\nend_header\n" + b"\0" * 64


@pytest.fixture
def rig(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("FRAMES_DIR", str(tmp_path / "frames"))
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path / "outputs"))
    store = JobStore(tmp_path / "jobs")
    api = TestClient(create_app(store))
    gateway = TestClient(create_worker_app(store, token=TOKEN))
    return store, api, gateway, tmp_path


def _upload(api: TestClient, splat: bool = True) -> str:
    response = api.post(
        "/jobs",
        files={"file": ("room.mp4", b"video-bytes", "video/mp4")},
        data={"name": "Room", "splat": "true" if splat else "false"},
    )
    assert response.status_code == 200, response.text
    return response.json()["job_id"]


def _queue(gateway: TestClient) -> splat_worker.GatewaySplatQueue:
    gateway.headers["Authorization"] = f"Bearer {TOKEN}"
    return splat_worker.GatewaySplatQueue("http://testserver", TOKEN, worker="test-gpu", client=gateway)


def test_gateway_needs_a_strong_token(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        create_worker_app(JobStore(tmp_path / "jobs"), token="short")


def test_gateway_rejects_a_wrong_token(rig) -> None:
    _, _, gateway, _ = rig
    assert gateway.get("/worker/ping").status_code == 401
    assert gateway.get("/worker/ping", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert gateway.get("/worker/ping", headers={"Authorization": f"Bearer {TOKEN}"}).json() == {"ok": True}
    # Only worker routes exist on the gateway; the platform is not reachable through the tunnel.
    assert gateway.get("/jobs", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 404
    assert gateway.get("/", headers={"Authorization": f"Bearer {TOKEN}"}).status_code == 404


def test_remote_worker_trains_and_delivers_a_splat(rig) -> None:
    store, api, gateway, tmp_path = rig
    mesh_only = _upload(api, splat=False)
    job_id = _upload(api)
    assert api.get(f"/jobs/{job_id}").json()["splat_status"] == "queued"
    assert api.get(f"/jobs/{mesh_only}").json()["splat_status"] == "none"
    seen: list[tuple[str, int]] = []

    def trainer(video: Path, work: Path, *, report, cancel) -> Path:
        assert video.read_bytes() == b"video-bytes"
        report("Training Gaussians · step 15000/30000", 55)
        record = store.get(job_id)
        seen.append((record["splat_stage"], record["splat_progress"]))
        ply = work / "splat.ply"
        ply.write_bytes(PLY)
        return ply

    assert splat_worker.process_one(_queue(gateway), trainer, tmp_path / "work") is True
    assert seen == [("Training Gaussians · step 15000/30000", 55)]
    body = api.get(f"/jobs/{job_id}").json()
    assert body["splat_status"] == "succeeded" and body["splat_progress"] == 100
    assert body["splat_url"] == f"/jobs/{job_id}/point_cloud.ply"
    assert body["status"] == "queued"  # the mesh is a separate job and has not run
    assert api.get(body["splat_url"]).content == PLY
    assert not (tmp_path / "work" / job_id).exists()  # work folder cleaned up
    # Only the job that asked for a splat was claimed.
    assert splat_worker.process_one(_queue(gateway), trainer, tmp_path / "work") is False


def test_failure_is_reported_and_can_be_retried(rig) -> None:
    store, api, gateway, tmp_path = rig
    job_id = _upload(api)

    def trainer(video, work, *, report, cancel):
        raise RuntimeError("COLMAP registered 4 of 180 frames")

    splat_worker.process_one(_queue(gateway), trainer, tmp_path / "work")
    body = api.get(f"/jobs/{job_id}").json()
    assert body["splat_status"] == "failed"
    assert "COLMAP registered 4" in body["splat_error"]
    again = api.post(f"/jobs/{job_id}/splat").json()
    assert again["splat_status"] == "queued" and again["splat_error"] == ""


def test_worker_stops_when_the_server_cancels(rig) -> None:
    store, api, gateway, tmp_path = rig
    job_id = _upload(api)

    def trainer(video, work, *, report, cancel):
        store.repo.save_splat(job_id, splat_status="failed", splat_error="stale")  # server gave up
        report("Exporting splat", 95)  # stage change → immediate post → 409
        assert cancel.wait(5)
        raise AssertionError("should not deliver")

    assert splat_worker.process_one(_queue(gateway), trainer, tmp_path / "work") is True
    assert store.get(job_id)["splat_error"] == "stale"  # not overwritten by the worker


def test_gateway_rejects_non_ply_and_stale_jobs(rig, monkeypatch: pytest.MonkeyPatch) -> None:
    store, api, gateway, _ = rig
    job_id = _upload(api)
    auth = {"Authorization": f"Bearer {TOKEN}"}
    claimed = gateway.post("/worker/claim", json={"worker": "x"}, headers=auth).json()
    assert claimed["job_id"] == job_id and claimed["source_suffix"] == ".mp4"
    assert gateway.put(f"/worker/jobs/{job_id}/result", content=b"<html>", headers=auth).status_code == 400
    assert store.get(job_id)["splat_status"] == "running"
    assert not list((Path(os.environ["FRAMES_DIR"]) / job_id / "splat").glob("*.uploading"))

    assert store.recover_stale_splats(minutes=-1) == [job_id]
    assert gateway.post(f"/worker/jobs/{job_id}/progress", json={"stage": "x"}, headers=auth).status_code == 409
    assert "Colab" in api.get(f"/jobs/{job_id}").json()["splat_error"]


def test_request_splat_needs_a_stored_video(rig) -> None:
    _, api, _, _ = rig
    api.app.state.jobs.register_sample("demo", "demo.mp4")
    assert api.post("/jobs/demo/splat").status_code == 409


def test_local_queue_delivers_into_frames(rig) -> None:
    store, api, _, tmp_path = rig
    job_id = _upload(api)
    queue = splat_worker.LocalSplatQueue(store, frames_dir=tmp_path / "frames", worker="local-gpu")

    def trainer(video, work, *, report, cancel):
        out = work / "x.ply"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(PLY)
        return out

    splat_worker.process_one(queue, trainer, tmp_path / "work")
    assert (tmp_path / "frames" / job_id / "splat" / "point_cloud.ply").read_bytes() == PLY
    assert store.get(job_id)["splat_worker"] == "local-gpu"


# ---- splatfacto runner with stand-in commands -----------------------------------------------

_LOG = 'echo "$(basename "$0") $*" >> "$FAKE_LOG"\n'
_ARG = 'out=""; prev=""; for a in "$@"; do [ "$prev" = "--output-dir" ] && out="$a"; prev="$a"; last="$a"; done\n'
_FAKES = {
    "colmap": "exit 0",
    "ffprobe": 'echo "60.0"',
    "ffmpeg": _ARG + 'd=$(dirname "$last"); mkdir -p "$d"; for i in $(seq 1 12); do echo x > "$d/frame_$i.jpg"; done',
    "ns-process-data": _ARG + 'mkdir -p "$out/images"; for i in 1 2 3; do echo x > "$out/images/f$i.png"; done\n'
    'echo "{}" > "$out/transforms.json"; echo db > "$out/database.db"; echo "poses done"',
    "ns-train": _ARG + 'echo "Step (% Done)   Train Iter"; echo "  100 (10.00%)   3 ms"; echo "  900 (90.00%)   3 ms"\n'
    'run="$out/run/splatfacto/$(date +%s%N)"; mkdir -p "$run/nerfstudio_models"; echo cfg > "$run/config.yml"\n'
    'echo ck > "$run/nerfstudio_models/step-000002000.ckpt"',
    "ns-export": _ARG + 'mkdir -p "$out"; printf "ply\\n%0200d" 0 > "$out/splat.ply"',
}


def _fake_tools(folder: Path, monkeypatch: pytest.MonkeyPatch, fail: str = "") -> Path:
    folder.mkdir()
    for name, body in _FAKES.items():
        script = folder / name
        script.write_text("#!/bin/sh\n" + _LOG + ("echo boom; exit 3" if name == fail else body) + "\n")
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    log = folder.parent / "calls.log"
    monkeypatch.setenv("FAKE_LOG", str(log))
    return log


def _video(tmp_path: Path, size: int = 1000) -> Path:
    video = tmp_path / "v.mp4"
    video.write_bytes(b"v" * size)
    return video


def test_splatfacto_runs_the_steps_and_reports_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from model.splat.splatfacto import train_splatfacto

    log = _fake_tools(tmp_path / "bin", monkeypatch)
    reports: list[tuple[str, int]] = []
    ply = train_splatfacto(_video(tmp_path), tmp_path / "work", report=lambda s, p: reports.append((s, p)), steps=1000, min_bytes=10)
    assert ply.read_bytes().startswith(b"ply")
    stages = [stage for stage, _ in reports]
    assert stages[:2] == ["Extracting frames", "Estimating camera poses (COLMAP)"]
    assert "Poses ready (3 frames)" in stages
    assert ("Training Gaussians · step 100/1000", 23) in reports
    assert ("Training Gaussians · step 900/1000", 87) in reports
    assert [p for _, p in reports] == sorted(p for _, p in reports)  # monotonic
    calls = log.read_text()
    # 180 frames over a 60 s video → 3 fps, shrunk to a 1600 px long side, never upscaled.
    assert "fps=3.00000,scale='min(1600,iw)':'min(1600,ih)':force_original_aspect_ratio=decrease" in calls
    assert "ns-process-data images --data" in calls and "--no-gpu" in calls
    assert "--load-dir" not in calls


def test_splatfacto_resumes_poses_and_checkpoints_from_drive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from model.splat.splatfacto import train_splatfacto

    log = _fake_tools(tmp_path / "bin", monkeypatch)
    drive = tmp_path / "drive" / "room" / "resume"
    video = _video(tmp_path)
    train_splatfacto(video, tmp_path / "work", persist_dir=drive, steps=1000, min_bytes=10)
    assert (drive / "ns_data" / "transforms.json").is_file()
    assert not (drive / "ns_data" / "database.db").exists()  # big COLMAP db is not copied to Drive
    assert list(drive.glob("ns_outputs/**/step-*.ckpt"))

    # Colab disconnects; a new worker gets the same job: no COLMAP, training continues.
    log.write_text("")
    reports: list[str] = []
    train_splatfacto(video, tmp_path / "work2", persist_dir=drive, steps=1000, min_bytes=10, report=lambda s, p: reports.append(s))
    calls = log.read_text()
    assert "ffmpeg" not in calls and "ns-process-data" not in calls
    assert "--load-dir" in calls and "nerfstudio_models" in calls
    assert "Restoring camera poses from Drive" in reports
    assert "Resuming training from the last checkpoint" in reports

    # A different video for the same folder must not reuse the old poses.
    log.write_text("")
    train_splatfacto(_video(tmp_path, size=2000), tmp_path / "work3", persist_dir=drive, steps=1000, min_bytes=10)
    calls = log.read_text()
    assert "ns-process-data" in calls and "--load-dir" not in calls


def test_resume_data_is_cleared_after_delivery_but_the_ply_copy_is_kept(rig, monkeypatch: pytest.MonkeyPatch) -> None:
    store, api, gateway, tmp_path = rig
    monkeypatch.setenv("SPLAT_KEEP_ROOT", str(tmp_path / "drive"))
    job_id = _upload(api)
    resume = splat_worker.resume_dir(job_id)
    (resume / "ns_data").mkdir(parents=True)

    def trainer(video, work, *, report, cancel):
        out = work / "s.ply"
        out.write_bytes(PLY)
        return out

    splat_worker.process_one(_queue(gateway), trainer, tmp_path / "work")
    assert not resume.exists()
    assert (tmp_path / "drive" / job_id / "point_cloud.ply").read_bytes() == PLY


def test_download_reports_fractions(rig) -> None:
    _, api, gateway, tmp_path = rig
    _upload(api)
    queue = _queue(gateway)
    job = queue.claim()
    fractions: list[float] = []
    queue.fetch_source(job, tmp_path / "dl", on_progress=fractions.append)
    assert fractions and fractions[-1] == 1.0


def test_splatfacto_failures_are_clear(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from model.splat.exceptions import SplatError
    from model.splat.splatfacto import train_splatfacto

    _fake_tools(tmp_path / "bin", monkeypatch, fail="ns-train")
    with pytest.raises(SplatError) as err:
        train_splatfacto(_video(tmp_path), tmp_path / "work", min_bytes=10)
    assert "Training Gaussians failed (exit 3)" in err.value.message and "boom" in err.value.message


def test_splatfacto_rejects_a_sparse_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from model.splat.exceptions import SplatError
    from model.splat.splatfacto import train_splatfacto

    _fake_tools(tmp_path / "bin", monkeypatch)
    with pytest.raises(SplatError) as err:
        train_splatfacto(_video(tmp_path), tmp_path / "work", min_bytes=10_000_000)
    assert err.value.code == "sparse_splat"


def test_splatfacto_cancel_stops_the_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from model.splat.exceptions import SplatError
    from model.splat.splatfacto import train_splatfacto

    _fake_tools(tmp_path / "bin", monkeypatch)
    (tmp_path / "bin" / "ns-process-data").write_text("#!/bin/sh\nsleep 30\n")
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()
    with pytest.raises(SplatError) as err:
        train_splatfacto(_video(tmp_path), tmp_path / "work", cancel=cancel, min_bytes=10)
    assert err.value.code == "cancelled"


def test_gateway_and_worker_entry_points_restore_stdlib_queue() -> None:
    """Run in a fresh interpreter: conftest's fix-up must not hide a broken entry point."""
    import subprocess
    import sys

    code = (
        "import importlib, sys; sys.modules.pop('queue', None); import queue;"  # repo package wins
        "import api.worker_gateway; import queue as q; assert hasattr(q, 'Queue'), q.__file__"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=Path(__file__).parents[1])
    assert result.returncode == 0, result.stderr
    help_run = subprocess.run([sys.executable, "-m", "queue.workers", "--help"], capture_output=True, text=True, cwd=Path(__file__).parents[1])
    assert help_run.returncode == 0 and "--gateway" in help_run.stdout, help_run.stderr
