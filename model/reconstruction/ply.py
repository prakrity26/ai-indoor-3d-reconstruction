"""Read and write colored XYZ RGB PLY (binary little-endian, this project's format)."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def write_ply_xyzrgb(path: Path, points: np.ndarray, colors: np.ndarray) -> None:
    if len(points) != len(colors):
        raise ValueError("points and colors must have the same length")
    path.parent.mkdir(parents=True, exist_ok=True)
    count = int(len(points))
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {count}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property uchar red\n"
        "property uchar green\n"
        "property uchar blue\n"
        "end_header\n"
    )
    dtype = np.dtype(
        [
            ("x", "<f4"),
            ("y", "<f4"),
            ("z", "<f4"),
            ("red", "u1"),
            ("green", "u1"),
            ("blue", "u1"),
        ]
    )
    vertices = np.empty(count, dtype=dtype)
    vertices["x"] = points[:, 0]
    vertices["y"] = points[:, 1]
    vertices["z"] = points[:, 2]
    vertices["red"] = colors[:, 0]
    vertices["green"] = colors[:, 1]
    vertices["blue"] = colors[:, 2]
    with path.open("wb") as handle:
        handle.write(header.encode("ascii"))
        vertices.tofile(handle)


_VERTEX_DTYPE = np.dtype(
    [
        ("x", "<f4"),
        ("y", "<f4"),
        ("z", "<f4"),
        ("red", "u1"),
        ("green", "u1"),
        ("blue", "u1"),
    ]
)


def read_ply_xyzrgb(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read a PLY written by `write_ply_xyzrgb`."""
    raw = Path(path).read_bytes()
    marker = b"end_header\n"
    offset = raw.find(marker)
    if offset < 0:
        raise ValueError(f"PLY header not found: {path}")
    header = raw[: offset + len(marker)].decode("ascii", errors="replace")
    count = 0
    for line in header.splitlines():
        if line.startswith("element vertex"):
            count = int(line.split()[-1])
            break
    body = raw[offset + len(marker) :]
    vertices = np.frombuffer(body, dtype=_VERTEX_DTYPE, count=count)
    points = np.stack([vertices["x"], vertices["y"], vertices["z"]], axis=1).astype(np.float32)
    colors = np.stack([vertices["red"], vertices["green"], vertices["blue"]], axis=1).astype(np.uint8)
    return points, colors
