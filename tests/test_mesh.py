"""Tests for Phase 7 Poisson meshing. Open3D is optional except for the sphere case."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from model.mesh.exceptions import MeshError
from model.mesh.pipeline import reconstruct_mesh
from model.reconstruction.ply import write_ply_xyzrgb
from shared.config.settings import MeshSettings


def _settings(tmp_path: Path, **overrides) -> MeshSettings:
    values = dict(
        poisson_depth=6,
        normal_radius=0.2,
        normal_max_nn=20,
        orient_k=10,
        density_quantile=0.05,
        bbox_scale=1.2,
        min_triangles=10,
        max_triangles=20000,
        write_glb=True,
        output_dir=tmp_path / "outputs",
    )
    values.update(overrides)
    settings = MeshSettings(**values)
    settings.validate()
    return settings


def _sphere_points(n: int = 1200, radius: float = 1.0, seed: int = 2) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    vec = rng.normal(size=(n, 3))
    vec /= np.linalg.norm(vec, axis=1, keepdims=True)
    points = (vec * radius).astype(np.float32)
    colors = ((vec * 0.5 + 0.5) * 255.0).clip(0, 255).astype(np.uint8)
    return points, colors


def test_missing_filtered_cloud_raises(tmp_path: Path) -> None:
    job = tmp_path / "empty"
    job.mkdir()
    with pytest.raises(MeshError) as err:
        reconstruct_mesh(job, settings=_settings(tmp_path))
    assert err.value.code == "filtered_cloud_missing"


def test_poisson_sphere_writes_ply_and_glb(tmp_path: Path) -> None:
    pytest.importorskip("open3d")
    points, colors = _sphere_points()
    job = tmp_path / "job"
    job.mkdir()
    write_ply_xyzrgb(job / "cloud_filtered.ply", points, colors)
    (job / "cloud_filtered.json").write_text('{"job_id":"job"}\n', encoding="utf-8")

    result = reconstruct_mesh(job, settings=_settings(tmp_path))
    assert result.triangle_count >= 10
    assert result.vertex_count >= 10
    assert Path(result.ply_path).is_file()
    assert Path(result.glb_path).is_file()
    assert Path(result.manifest_path).is_file()
    assert (tmp_path / "outputs" / "job" / "mesh.ply").is_file()
    assert (tmp_path / "outputs" / "job" / "mesh.glb").is_file()
    assert Path(result.glb_path).stat().st_size > 0
