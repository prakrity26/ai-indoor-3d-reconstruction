"""Run COLMAP SfM via the ``colmap`` binary (intended for Linux/Colab CUDA hosts)."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections import deque
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


def run_colmap(image_dir: Path, work_dir: Path, binary: str = "colmap") -> tuple[Path, Path]:
    """Feature match, map, then undistort. Returns COLMAP TXT and the pinhole images to train on."""
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

    model_dir = _largest_sparse_model(sparse)
    undistorted = work_dir / "undistorted"
    _run(
        [
            colmap,
            "image_undistorter",
            "--image_path",
            str(image_dir),
            "--input_path",
            str(model_dir),
            "--output_path",
            str(undistorted),
            "--output_type",
            "COLMAP",
        ]
    )
    # Phone video is radially distorted. Training on the raw frames paints every wall twice.
    # Captures-style splats train on the undistorted pinhole images.
    model_dir, train_images = _undistorted_paths(undistorted)
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
    return txt_dir, train_images


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
            "SIMPLE_RADIAL",
            "--SiftExtraction.use_gpu",
            use_gpu,
        ],
        [
            colmap,
            "sequential_matcher",
            "--database_path",
            str(database),
            "--SiftMatching.use_gpu",
            use_gpu,
            "--SequentialMatching.overlap",
            "20",
            "--SequentialMatching.quadratic_overlap",
            "1",
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
            "--Mapper.multiple_models",
            "1",
            "--Mapper.min_num_matches",
            "12",
            "--Mapper.init_min_tri_angle",
            "4",
            "--Mapper.init_num_trials",
            "300",
        ],
    ]
    for command in commands:
        _run(command)


def _largest_sparse_model(sparse: Path) -> Path:
    candidates = [path for path in sparse.iterdir() if path.is_dir()]
    if not candidates:
        raise SplatError(
            "colmap_failed",
            "COLMAP produced no sparse model. The frames do not overlap enough to recover a camera path.",
        )

    def _size(path: Path) -> int:
        for name in ("images.bin", "images.txt"):
            file = path / name
            if file.is_file():
                return file.stat().st_size
        return 0

    return max(candidates, key=_size)


def _undistorted_paths(root: Path) -> tuple[Path, Path]:
    images = root / "images"
    sparse = root / "sparse"
    if (sparse / "0").is_dir():
        sparse = sparse / "0"
    has_images = images.is_dir() and (any(images.glob("*.jpg")) or any(images.glob("*.png")))
    if not has_images:
        raise SplatError(
            "undistort_failed",
            "COLMAP undistortion wrote no images. The camera model could not be removed.",
        )
    if not sparse.is_dir():
        raise SplatError("undistort_failed", "COLMAP undistortion wrote no sparse model.")
    return sparse, images


def _run(command: list[str]) -> None:
    print("COLMAP:", " ".join(command[:4]), flush=True)
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    tail: deque[str] = deque(maxlen=40)
    try:
        completed = subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except OSError as exc:
        raise SplatError("colmap_exec", str(exc), {"command": command[:2]}) from exc
    assert completed.stdout is not None
    for line in completed.stdout:
        print(line, end="", flush=True)
        tail.append(line.rstrip())
    returncode = completed.wait()
    if returncode != 0:
        log_tail = "\n".join(tail)
        print(f"ERROR colmap_failed: COLMAP exited {returncode}", flush=True)
        raise SplatError(
            "colmap_failed",
            "COLMAP command failed.",
            {"command": command[:4], "returncode": returncode, "log_tail": log_tail},
        )
