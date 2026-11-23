"""Text the Streamlit page and the studio share. No reconstruction imports."""

from __future__ import annotations

from typing import Any


def describe(job: dict[str, Any]) -> str:
    """One line for a job card: status, pose coverage, and mesh size."""
    bits = [str(job.get("status") or "")]
    summary = job.get("summary") or {}
    posed = summary.get("posed_frames")
    selected = summary.get("selected_frames")
    if posed is not None and selected:
        bits.append(f"{posed}/{selected} posed")
    vertices = summary.get("mesh_vertices")
    if vertices:
        bits.append(f"{vertices} vertices")
    if job.get("splat_url"):
        bits.append("splat ready")
    elif job.get("mesh_url"):
        bits.append("mesh ready")
    return " · ".join(bit for bit in bits if bit)
