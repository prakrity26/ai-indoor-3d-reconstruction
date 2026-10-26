"""Phase 9 reads existing artifacts. It does not train a splat or rebuild a mesh."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from model.evaluation.__main__ import main
from model.evaluation.exceptions import EvaluationError
from model.evaluation.pipeline import WALKABLE_MIN_BYTES, WALKABLE_MIN_GAUSSIANS, evaluate_job
from model.evaluation.timing import note_duration
from model.reconstruction.ply import write_ply_xyzrgb


def _job(tmp_path: Path) -> Path:
    job = tmp_path / "img7916"
    job.mkdir()
    (job / "selection.json").write_text(
        json.dumps({"job_id": "img7916", "selected_count": 4, "selected": [{}, {}, {}, {}]}),
        encoding="utf-8",
    )
    (job / "poses.json").write_text(
        json.dumps(
            {
                "job_id": "img7916",
                "strategy": "opencv_orb_essential",
                "scale_meaning": "arbitrary_monocular",
                "cameras": [
                    {"status": "reference"},
                    {"status": "estimated"},
                    {"status": "failed"},
                    {"status": "failed"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (job / "depth.json").write_text(
        json.dumps({"model_id": "local-fake", "device": "cpu", "maps": [{}, {}]}),
        encoding="utf-8",
    )
    (job / "cloud.json").write_text(
        json.dumps({"strategy": "depth_unproject_concat", "point_count": 20}),
        encoding="utf-8",
    )
    (job / "cloud_filtered.json").write_text(
        json.dumps({"strategy": "open3d_stat_voxel", "output_count": 12}),
        encoding="utf-8",
    )
    (job / "mesh.json").write_text(
        json.dumps({"strategy": "open3d_poisson", "vertex_count": 8, "triangle_count": 10}),
        encoding="utf-8",
    )
    (job / "scene.json").write_text(
        json.dumps({"strategy": "test_boxes", "detection_count": 2, "object_count": 1}),
        encoding="utf-8",
    )
    note_duration(job, "mesh", 1.25)
    return job


def test_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(EvaluationError) as err:
        evaluate_job(tmp_path / "missing")
    assert err.value.code == "source_not_found"


def test_empty_directory_raises(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(EvaluationError) as err:
        evaluate_job(empty)
    assert err.value.code == "nothing_to_score"


def test_scores_pose_ratio_and_keeps_relative_scale(tmp_path: Path) -> None:
    job = _job(tmp_path)
    result = evaluate_job(job)
    assert result.job_id == "img7916"
    assert result.scale_meaning == "arbitrary_monocular"
    assert result.selected_frames == 4
    assert result.posed_frames == 2
    assert result.failed_frames == 2
    assert result.posed_ratio == 0.5
    assert result.depth_maps == 2
    assert result.cloud_points == 20
    assert result.filtered_points == 12
    assert result.mesh_vertices == 8
    assert result.mesh_triangles == 10
    assert result.scene_objects == 1
    assert result.detection_count == 2
    assert result.timings_sec["mesh"] == 1.25
    assert result.settings["pose_strategy"] == "opencv_orb_essential"
    assert result.settings["depth_model"] == "local-fake"
    assert result.splat_walkable is False
    payload = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
    assert payload["posed_ratio"] == 0.5
    assert any(issue["code"] == "relative_scale" for issue in payload["warnings"])


def test_small_splat_stays_sparse(tmp_path: Path) -> None:
    job = _job(tmp_path)
    ply = job / "splat" / "point_cloud.ply"
    points = np.zeros((3, 3), dtype=np.float32)
    colors = np.zeros((3, 3), dtype=np.uint8)
    write_ply_xyzrgb(ply, points, colors)
    result = evaluate_job(job)
    assert result.splat_gaussians == 3
    assert result.splat_bytes == ply.stat().st_size
    assert result.splat_bytes < WALKABLE_MIN_BYTES
    assert result.splat_gaussians < WALKABLE_MIN_GAUSSIANS
    assert result.splat_walkable is False
    assert any(issue.code == "splat_sparse" for issue in result.warnings)


def test_sample_manifest_counts(tmp_path: Path) -> None:
    job = tmp_path / "img7916"
    job.mkdir()
    (job / "manifest.json").write_text(
        json.dumps(
            {
                "job_id": "img7916",
                "posed_keyframes": 17,
                "selected_keyframes": 70,
                "filtered_cloud_points": 80032,
                "vertex_count": 17187,
                "triangle_count": 34213,
                "scale": "relative_monocular",
            }
        ),
        encoding="utf-8",
    )
    result = evaluate_job(job)
    assert result.posed_ratio == round(17 / 70, 4)
    assert result.filtered_points == 80032
    assert result.mesh_vertices == 17187
    assert result.mesh_triangles == 34213
    assert result.splat_walkable is False


def test_large_enough_splat_is_a_walk_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("model.evaluation.pipeline.WALKABLE_MIN_BYTES", 1)
    monkeypatch.setattr("model.evaluation.pipeline.WALKABLE_MIN_GAUSSIANS", 1)
    job = _job(tmp_path)
    ply = job / "splat" / "point_cloud.ply"
    points = np.zeros((3, 3), dtype=np.float32)
    colors = np.zeros((3, 3), dtype=np.uint8)
    write_ply_xyzrgb(ply, points, colors)
    result = evaluate_job(job)
    assert result.splat_walkable is True
    assert any(issue.code == "splat_size" for issue in result.warnings)


def test_cli_missing_source(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main([str(tmp_path / "missing")])
    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "source_not_found"
