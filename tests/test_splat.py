"""Tests for the in-repo Gaussian splat path. No Colab GPU required."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from model.splat.colmap_txt import load_colmap_txt, qvec_to_rotmat
from model.splat.exceptions import SplatError
from model.splat.pipeline import reconstruct_gaussian_splat
from model.splat.train import publish_splat, write_gaussian_ply
from shared.config.settings import SplatSettings
from tests.test_preprocessing import write_video


def _splat_settings(tmp_path: Path, **overrides) -> SplatSettings:
    values = dict(
        extract_fps=5.0,
        max_frames=20,
        image_max_size=640,
        colmap_bin="colmap",
        train_steps=100,
        densify_every=0,
        max_gaussians=200000,
        output_dir=tmp_path / "outputs",
    )
    values.update(overrides)
    settings = SplatSettings(**values)
    settings.validate()
    return settings


def test_qvec_identity() -> None:
    rot = qvec_to_rotmat(np.array([1.0, 0.0, 0.0, 0.0]))
    assert np.allclose(rot, np.eye(3), atol=1e-6)


def test_prepare_only_writes_images(tmp_path: Path) -> None:
    video = write_video(tmp_path / "room.avi", n_frames=30, fps=10)
    result = reconstruct_gaussian_splat(
        video,
        job_id="splatjob",
        frames_dir=tmp_path / "frames",
        prepare_only=True,
        settings=_splat_settings(tmp_path),
    )
    image_dir = tmp_path / "frames" / "splatjob" / "splat" / "images"
    assert result.image_count >= 8
    assert image_dir.is_dir()
    assert len(list(image_dir.glob("*.jpg"))) == result.image_count
    assert Path(result.manifest_path).is_file()
    assert result.ply_path == ""


def test_full_run_without_colmap_raises(tmp_path: Path) -> None:
    video = write_video(tmp_path / "room.avi", n_frames=30, fps=10)
    with pytest.raises(SplatError) as raised:
        reconstruct_gaussian_splat(
            video,
            job_id="needgpu",
            frames_dir=tmp_path / "frames",
            prepare_only=False,
            settings=_splat_settings(tmp_path, colmap_bin="colmap-not-installed-xyz"),
        )
    assert raised.value.code in {"colmap_missing", "too_few_images"}


def test_write_gaussian_ply_roundtrip_header(tmp_path: Path) -> None:
    path = tmp_path / "cloud.ply"
    n = 4
    write_gaussian_ply(
        path,
        np.zeros((n, 3), dtype=np.float32),
        np.zeros((n, 3), dtype=np.float32),
        np.full((n, 3), 0.01, dtype=np.float32),
        np.tile(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32), (n, 1)),
        np.full((n,), 0.5, dtype=np.float32),
    )
    raw = path.read_bytes()
    assert raw.startswith(b"ply\n")
    assert b"f_dc_0" in raw
    assert b"scale_0" in raw
    assert b"f_rest_0" not in raw


def test_write_gaussian_ply_includes_view_dependent_color(tmp_path: Path) -> None:
    path = tmp_path / "cloud.ply"
    n = 2
    rest = np.zeros((n, 45), dtype=np.float32)
    rest[:, 0] = 0.25
    write_gaussian_ply(
        path,
        np.zeros((n, 3), dtype=np.float32),
        np.zeros((n, 3), dtype=np.float32),
        np.full((n, 3), 0.01, dtype=np.float32),
        np.tile(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32), (n, 1)),
        np.full((n,), 0.5, dtype=np.float32),
        sh_rest=rest,
    )
    raw = path.read_bytes()
    assert b"property float f_rest_0\n" in raw
    assert b"property float f_rest_44\n" in raw


def test_publish_splat_replaces_the_kept_file(tmp_path: Path) -> None:
    source = tmp_path / "local" / "point_cloud.ply"
    source.parent.mkdir()
    source.write_bytes(b"ply-a")
    keep = tmp_path / "drive" / "img7916"
    assert publish_splat(source, str(keep)) == keep / "point_cloud.ply"
    assert (keep / "point_cloud.ply").read_bytes() == b"ply-a"
    source.write_bytes(b"ply-b")
    publish_splat(source, str(keep))
    assert (keep / "point_cloud.ply").read_bytes() == b"ply-b"
    assert not (keep / "point_cloud.ply.tmp").exists()


def test_load_colmap_txt(tmp_path: Path) -> None:
    model = tmp_path / "sparse_txt"
    model.mkdir()
    (model / "cameras.txt").write_text(
        "# comment\n1 PINHOLE 100 80 50 50 50 40\n",
        encoding="utf-8",
    )
    (model / "images.txt").write_text(
        "1 1 0 0 0 0 0 0 1 frame_000000.jpg\n"
        "0 0 0\n"
        "2 1 0 0 0 0 0 0.1 1 frame_000001.jpg\n"
        "0 0 0\n",
        encoding="utf-8",
    )
    (model / "points3D.txt").write_text(
        "1 0 0 0 255 0 0 0\n",
        encoding="utf-8",
    )
    payload = load_colmap_txt(model)
    assert len(payload["images"]) == 2
    assert payload["cameras"][1]["width"] == 100
    assert len(payload["points"]) == 1
