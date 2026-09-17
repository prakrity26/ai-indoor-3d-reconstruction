"""Load a COLMAP TXT model (cameras.txt / images.txt / points3D.txt)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from model.splat.exceptions import SplatError


def qvec_to_rotmat(qvec: np.ndarray) -> np.ndarray:
    qw, qx, qy, qz = qvec
    return np.array(
        [
            [1 - 2 * qy * qy - 2 * qz * qz, 2 * qx * qy - 2 * qz * qw, 2 * qx * qz + 2 * qy * qw],
            [2 * qx * qy + 2 * qz * qw, 1 - 2 * qx * qx - 2 * qz * qz, 2 * qy * qz - 2 * qx * qw],
            [2 * qx * qz - 2 * qy * qw, 2 * qy * qz + 2 * qx * qw, 1 - 2 * qx * qx - 2 * qy * qy],
        ],
        dtype=np.float64,
    )


def load_colmap_txt(model_dir: Path) -> dict:
    model_dir = Path(model_dir)
    cameras_path = model_dir / "cameras.txt"
    images_path = model_dir / "images.txt"
    points_path = model_dir / "points3D.txt"
    if not cameras_path.is_file() or not images_path.is_file():
        raise SplatError("colmap_model_missing", f"No COLMAP TXT model in {model_dir}")

    cameras = _parse_cameras(cameras_path)
    images = _parse_images(images_path)
    points, colors = _parse_points(points_path) if points_path.is_file() else (
        np.zeros((0, 3), dtype=np.float32),
        np.zeros((0, 3), dtype=np.float32),
    )
    if not images:
        raise SplatError("colmap_no_images", "COLMAP registered zero images.")
    return {"cameras": cameras, "images": images, "points": points, "colors": colors}


def _parse_cameras(path: Path) -> dict[int, dict]:
    cameras: dict[int, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        camera_id = int(parts[0])
        model = parts[1]
        width, height = int(parts[2]), int(parts[3])
        params = [float(x) for x in parts[4:]]
        if model in {"SIMPLE_PINHOLE", "SIMPLE_RADIAL"}:
            fx = fy = params[0]
            cx, cy = params[1], params[2]
        else:
            fx, fy, cx, cy = params[0], params[1], params[2], params[3]
        K = np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=np.float32)
        cameras[camera_id] = {"K": K, "width": width, "height": height, "model": model}
    return cameras


def _parse_images(path: Path) -> list[dict]:
    images: list[dict] = []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    i = 0
    while i < len(lines):
        parts = lines[i].split()
        qvec = np.array([float(x) for x in parts[1:5]], dtype=np.float64)
        tvec = np.array([float(x) for x in parts[5:8]], dtype=np.float64)
        camera_id = int(parts[8])
        name = parts[9]
        rot = qvec_to_rotmat(qvec)
        viewmat = np.eye(4, dtype=np.float32)
        viewmat[:3, :3] = rot
        viewmat[:3, 3] = tvec
        images.append({"name": name, "camera_id": camera_id, "viewmat": viewmat})
        i += 2
    return images


def _parse_points(path: Path) -> tuple[np.ndarray, np.ndarray]:
    xyz: list[list[float]] = []
    rgb: list[list[float]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        xyz.append([float(parts[1]), float(parts[2]), float(parts[3])])
        rgb.append([float(parts[4]) / 255.0, float(parts[5]) / 255.0, float(parts[6]) / 255.0])
    if not xyz:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.float32)
    return np.asarray(xyz, dtype=np.float32), np.asarray(rgb, dtype=np.float32)
