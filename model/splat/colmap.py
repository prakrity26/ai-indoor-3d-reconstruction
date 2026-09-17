"""Run COLMAP SfM via the ``colmap`` binary (intended for Linux/Colab CUDA hosts)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from model.splat.exceptions import SplatError


def require_colmap(binary: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise SplatError(
            "colmap_missing",
            "COLMAP is not on PATH. On Colab install it in the project notebook "
            "(apt-get install colmap). Do not create a second git repository.",
            {"binary": binary},
        )
    return path


def run_colmap(image_dir: Path, work_dir: Path, binary: str = "colmap") -> Path:
    """Feature match + incremental mapper. Writes ``work_dir/sparse_txt``."""
    colmap = require_colmap(binary)
    image_dir = Path(image_dir)
    work_dir = Path(work_dir)
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    database = work_dir / "database.db"
    sparse = work_dir / "sparse"
    sparse.mkdir(parents=True, exist_ok=True)
    jpegs = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png"))
    if len(jpegs) < 8:
        raise SplatError(
            "too_few_images",
            "Gaussian splat SfM needs more overlapping frames (at least 8).",
            {"count": len(jpegs)},
        )

    last_error: SplatError | None = None
    for use_gpu in ("1", "0"):
        if database.exists():
            database.unlink()
        try:
            _run_sfm(colmap, image_dir, database, sparse, use_gpu=use_gpu)
            last_error = None
            break
        except SplatError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error

    model_dir = _first_sparse_model(sparse)
    txt_dir = work_dir / "sparse_txt"
    txt_dir.mkdir(parents=True, exist_ok=True)
    _run(
        [
            colmap,
            "model_converter",
            "--input_path",
            str(model_dir),
            "--output_path",
            str(txt_dir),
            "--output_type",
            "TXT",
        ]
    )
    return txt_dir


def _run_sfm(colmap: str, image_dir: Path, database: Path, sparse: Path, *, use_gpu: str) -> None:
    commands = [
        [
            colmap,
            "feature_extractor",
            "--database_path",
            str(database),
            "--image_path",
            str(image_dir),
            "--ImageReader.single_camera",
            "1",
            "--ImageReader.camera_model",
            "OPENCV",
            "--SiftExtraction.use_gpu",
            use_gpu,
        ],
        [
            colmap,
            "exhaustive_matcher",
            "--database_path",
            str(database),
            "--SiftMatching.use_gpu",
            use_gpu,
        ],
        [
            colmap,
            "mapper",
            "--database_path",
            str(database),
            "--image_path",
            str(image_dir),
            "--output_path",
            str(sparse),
        ],
    ]
    for command in commands:
        _run(command)


def _first_sparse_model(sparse: Path) -> Path:
    candidates = sorted(p for p in sparse.iterdir() if p.is_dir())
    if not candidates:
        raise SplatError(
            "colmap_failed",
            "COLMAP produced no sparse model. Use a slower, overlapping indoor walk.",
        )
    return candidates[0]


def _run(command: list[str]) -> None:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise SplatError("colmap_exec", str(exc), {"command": command[:2]}) from exc
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "")[-2000:]
        raise SplatError(
            "colmap_failed",
            "COLMAP command failed.",
            {"command": command[:3], "log": tail},
        )
