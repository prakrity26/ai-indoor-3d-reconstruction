"""Poisson surface reconstruction from a colored point cloud."""

from __future__ import annotations

import numpy as np

from model.mesh.exceptions import MeshError
from shared.config.settings import MeshSettings


def _require_open3d():
    from shared.stdlib_queue import ensure_stdlib_queue

    ensure_stdlib_queue()
    try:
        import open3d as o3d
    except ImportError as exc:
        raise MeshError(
            "missing_dependency",
            "Mesh reconstruction needs the optional cloud extra: pip install -e '.[cloud]'",
            {"import_error": str(exc)},
        ) from exc
    return o3d


def _transfer_vertex_colors(mesh, points: np.ndarray, colors: np.ndarray):
    vertices = np.asarray(mesh.vertices)
    if len(vertices) == 0:
        return mesh
    try:
        from scipy.spatial import cKDTree
    except ImportError:
        cKDTree = None  # type: ignore[assignment]
    if cKDTree is not None:
        tree = cKDTree(np.asarray(points, dtype=np.float64))
        _, idx = tree.query(vertices, k=1)
        src = np.asarray(colors, dtype=np.float64) / 255.0
        mesh.vertex_colors = _require_open3d().utility.Vector3dVector(src[idx])
        return mesh

    o3d = _require_open3d()
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(np.asarray(points, dtype=np.float64))
    knn = o3d.geometry.KDTreeFlann(pcd)
    src = np.asarray(colors, dtype=np.float64) / 255.0
    painted = np.zeros((len(vertices), 3), dtype=np.float64)
    for i, vertex in enumerate(vertices):
        _, idx, _ = knn.search_knn_vector_3d(vertex, 1)
        painted[i] = src[idx[0]]
    mesh.vertex_colors = o3d.utility.Vector3dVector(painted)
    return mesh


def poisson_from_points(
    points: np.ndarray,
    colors: np.ndarray,
    settings: MeshSettings,
):
    """Build an Open3D triangle mesh. Scale remains relative to the Phase 5 cloud."""
    o3d = _require_open3d()
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(np.asarray(points, dtype=np.float64))
    cloud.colors = o3d.utility.Vector3dVector(np.asarray(colors, dtype=np.float64) / 255.0)
    cloud.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=settings.normal_radius,
            max_nn=settings.normal_max_nn,
        )
    )
    try:
        cloud.orient_normals_consistent_tangent_plane(settings.orient_k)
    except RuntimeError:
        cloud.orient_normals_towards_camera_location(cloud.get_center())

    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        cloud,
        depth=settings.poisson_depth,
    )
    densities = np.asarray(densities)
    if densities.size and settings.density_quantile > 0:
        cutoff = float(np.quantile(densities, settings.density_quantile))
        mesh.remove_vertices_by_mask(densities < cutoff)

    aabb = cloud.get_axis_aligned_bounding_box()
    center = aabb.get_center()
    extent = aabb.get_extent()
    half = extent * (settings.bbox_scale / 2.0)
    crop_box = o3d.geometry.AxisAlignedBoundingBox(center - half, center + half)
    mesh = mesh.crop(crop_box)
    mesh.remove_duplicated_vertices()
    mesh.remove_duplicated_triangles()
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()

    triangle_count = int(len(mesh.triangles))
    if settings.max_triangles > 0 and triangle_count > settings.max_triangles:
        mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=settings.max_triangles)
        mesh.remove_degenerate_triangles()
        mesh.remove_unreferenced_vertices()

    mesh = _transfer_vertex_colors(mesh, points, colors)
    mesh.compute_vertex_normals()
    return mesh


def write_mesh(path, mesh) -> None:
    o3d = _require_open3d()
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = o3d.io.write_triangle_mesh(
        str(path),
        mesh,
        write_ascii=False,
        write_vertex_normals=True,
        write_vertex_colors=True,
    )
    if not ok:
        raise MeshError("write_failed", f"Open3D could not write {path}")
