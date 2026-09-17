"""Phase 7: Poisson mesh and GLB/PLY export from a filtered cloud."""

from __future__ import annotations

from pathlib import Path
from shutil import copy2

from model.mesh.exceptions import MeshError
from model.mesh.io import load_filtered_cloud
from model.mesh.reconstruct import poisson_from_points, write_mesh
from model.mesh.types import (
    STRATEGY_NAME,
    MeshIssue,
    MeshResult,
    dump_mesh_manifest,
)
from shared.config.settings import MeshSettings, load_mesh_settings


def _copy_output(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.resolve() != src.resolve():
        copy2(src, dest)


def reconstruct_mesh(
    source: str | Path,
    *,
    output_ply: str | Path | None = None,
    output_glb: str | Path | None = None,
    settings: MeshSettings | None = None,
) -> MeshResult:
    """Turn `cloud_filtered.ply` into a triangle mesh. Detection is Phase 8."""
    settings = settings or load_mesh_settings()
    try:
        settings.validate()
    except ValueError as exc:
        raise MeshError("invalid_settings", str(exc)) from exc

    points, colors, job_dir, job_id = load_filtered_cloud(source)
    warnings: list[MeshIssue] = [
        MeshIssue(
            "info",
            "relative_scale",
            "The mesh inherits relative monocular scale. Poisson can fill holes and balloon; vertices outside the cloud box are cropped.",
        )
    ]
    mesh = poisson_from_points(points, colors, settings)
    triangle_count = int(len(mesh.triangles))
    vertex_count = int(len(mesh.vertices))
    if triangle_count < settings.min_triangles:
        raise MeshError(
            "too_few_triangles",
            "Poisson reconstruction left too few triangles for a usable mesh.",
            {"triangles": triangle_count, "min_triangles": settings.min_triangles},
        )

    ply_path = Path(output_ply) if output_ply is not None else job_dir / "mesh.ply"
    write_mesh(ply_path, mesh)
    extra_dir = settings.output_dir / job_id
    _copy_output(ply_path, extra_dir / "mesh.ply")

    glb_path = ""
    if settings.write_glb:
        glb = Path(output_glb) if output_glb is not None else job_dir / "mesh.glb"
        write_mesh(glb, mesh)
        _copy_output(glb, extra_dir / "mesh.glb")
        glb_path = str(glb.resolve())
    else:
        warnings.append(
            MeshIssue("info", "glb_skipped", "MESH_WRITE_GLB is off; only mesh.ply was written.")
        )

    result = MeshResult(
        job_id=job_id,
        strategy=STRATEGY_NAME,
        input_count=int(len(points)),
        vertex_count=vertex_count,
        triangle_count=triangle_count,
        ply_path=str(ply_path.resolve()),
        glb_path=glb_path,
        manifest_path=str((job_dir / "mesh.json").resolve()),
        warnings=warnings,
    )
    dump_mesh_manifest(result, job_dir / "mesh.json")
    return result
