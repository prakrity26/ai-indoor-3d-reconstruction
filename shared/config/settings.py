"""Environment-backed settings used by preprocessing through mesh export."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_EXTENSIONS = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v")


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


@dataclass(frozen=True)
class PreprocessSettings:
    frames_dir: Path
    max_upload_mb: int
    min_width: int
    min_height: int
    min_duration_sec: float
    max_duration_sec: float
    min_fps: float
    target_extract_fps: float
    max_extracted_frames: int
    jpeg_quality: int
    allowed_extensions: tuple[str, ...]
    quality_sample_count: int
    dark_mean_threshold: float
    bright_mean_threshold: float
    blur_laplacian_threshold: float

    @classmethod
    def from_env(cls) -> PreprocessSettings:
        extensions = os.environ.get("ALLOWED_VIDEO_EXTENSIONS", "")
        allowed = tuple(
            item.strip().lower()
            for item in extensions.split(",")
            if item.strip()
        ) or _DEFAULT_EXTENSIONS
        allowed = tuple(
            ext if ext.startswith(".") else f".{ext}" for ext in allowed
        )
        return cls(
            frames_dir=Path(os.environ.get("FRAMES_DIR", "./data/frames")),
            max_upload_mb=_int("MAX_UPLOAD_MB", 500),
            min_width=_int("MIN_VIDEO_WIDTH", 320),
            min_height=_int("MIN_VIDEO_HEIGHT", 240),
            min_duration_sec=_float("MIN_DURATION_SEC", 1.0),
            max_duration_sec=_float("MAX_DURATION_SEC", 600.0),
            min_fps=_float("MIN_FPS", 5.0),
            target_extract_fps=_float("TARGET_EXTRACT_FPS", 5.0),
            max_extracted_frames=_int("MAX_EXTRACTED_FRAMES", 400),
            jpeg_quality=_int("FRAME_JPEG_QUALITY", 95),
            allowed_extensions=allowed,
            quality_sample_count=_int("QUALITY_SAMPLE_COUNT", 12),
            dark_mean_threshold=_float("DARK_MEAN_THRESHOLD", 12.0),
            bright_mean_threshold=_float("BRIGHT_MEAN_THRESHOLD", 245.0),
            blur_laplacian_threshold=_float("BLUR_LAPLACIAN_THRESHOLD", 20.0),
        )


def load_settings() -> PreprocessSettings:
    return PreprocessSettings.from_env()


@dataclass(frozen=True)
class FrameSelectionSettings:
    min_count: int
    max_count: int
    min_gap: int
    max_gap: int
    diff_threshold: float
    thumbnail_size: int
    sharpness_width: int

    @classmethod
    def from_env(cls) -> FrameSelectionSettings:
        return cls(
            min_count=_int("KEYFRAME_MIN_COUNT", 8),
            max_count=_int("KEYFRAME_MAX_COUNT", 120),
            min_gap=_int("KEYFRAME_MIN_GAP", 1),
            max_gap=_int("KEYFRAME_MAX_GAP", 8),
            diff_threshold=_float("KEYFRAME_DIFF_THRESHOLD", 0.08),
            thumbnail_size=_int("KEYFRAME_THUMBNAIL_SIZE", 64),
            sharpness_width=_int("KEYFRAME_SHARPNESS_WIDTH", 320),
        )

    def validate(self) -> None:
        if self.min_count < 1:
            raise ValueError("KEYFRAME_MIN_COUNT must be >= 1")
        if self.max_count < self.min_count:
            raise ValueError("KEYFRAME_MAX_COUNT must be >= KEYFRAME_MIN_COUNT")
        if self.min_gap < 1:
            raise ValueError("KEYFRAME_MIN_GAP must be >= 1")
        if self.max_gap < self.min_gap:
            raise ValueError("KEYFRAME_MAX_GAP must be >= KEYFRAME_MIN_GAP")
        if not 0.0 <= self.diff_threshold <= 1.0:
            raise ValueError("KEYFRAME_DIFF_THRESHOLD must be in [0, 1]")
        if self.thumbnail_size < 8:
            raise ValueError("KEYFRAME_THUMBNAIL_SIZE must be >= 8")
        if self.sharpness_width < 16:
            raise ValueError("KEYFRAME_SHARPNESS_WIDTH must be >= 16")


def load_frame_selection_settings() -> FrameSelectionSettings:
    settings = FrameSelectionSettings.from_env()
    settings.validate()
    return settings


@dataclass(frozen=True)
class CameraPoseSettings:
    focal_scale: float
    fx: float | None
    fy: float | None
    cx: float | None
    cy: float | None
    orb_features: int
    ratio_test: float
    ransac_thresh: float
    min_matches: int
    min_inliers: int
    max_pair_skip: int

    @classmethod
    def from_env(cls) -> CameraPoseSettings:
        return cls(
            focal_scale=_float("POSE_FOCAL_SCALE", 1.2),
            fx=_optional_float("POSE_FX"),
            fy=_optional_float("POSE_FY"),
            cx=_optional_float("POSE_CX"),
            cy=_optional_float("POSE_CY"),
            orb_features=_int("POSE_ORB_FEATURES", 2000),
            ratio_test=_float("POSE_RATIO_TEST", 0.75),
            ransac_thresh=_float("POSE_RANSAC_THRESH", 1.0),
            min_matches=_int("POSE_MIN_MATCHES", 40),
            min_inliers=_int("POSE_MIN_INLIERS", 20),
            max_pair_skip=_int("POSE_MAX_PAIR_SKIP", 2),
        )

    def validate(self) -> None:
        if self.focal_scale <= 0:
            raise ValueError("POSE_FOCAL_SCALE must be > 0")
        if self.orb_features < 100:
            raise ValueError("POSE_ORB_FEATURES must be >= 100")
        if not 0.5 <= self.ratio_test <= 1.0:
            raise ValueError("POSE_RATIO_TEST must be in [0.5, 1]")
        if self.ransac_thresh <= 0:
            raise ValueError("POSE_RANSAC_THRESH must be > 0")
        if self.min_matches < 8:
            raise ValueError("POSE_MIN_MATCHES must be >= 8")
        if self.min_inliers < 8:
            raise ValueError("POSE_MIN_INLIERS must be >= 8")
        if self.max_pair_skip < 1:
            raise ValueError("POSE_MAX_PAIR_SKIP must be >= 1")


def _optional_float(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return float(raw)


def load_camera_pose_settings() -> CameraPoseSettings:
    settings = CameraPoseSettings.from_env()
    settings.validate()
    return settings


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class DepthSettings:
    model_id: str
    local_files_only: bool
    max_size: int
    write_preview: bool
    compute_device: str

    @classmethod
    def from_env(cls) -> DepthSettings:
        return cls(
            model_id=os.environ.get(
                "DEPTH_MODEL_ID",
                "depth-anything/Depth-Anything-V2-Small-hf",
            ).strip()
            or "depth-anything/Depth-Anything-V2-Small-hf",
            local_files_only=_bool("DEPTH_LOCAL_FILES_ONLY", False),
            max_size=_int("DEPTH_MAX_SIZE", 768),
            write_preview=_bool("DEPTH_WRITE_PREVIEW", True),
            compute_device=os.environ.get("COMPUTE_DEVICE", "auto").strip().lower() or "auto",
        )

    def validate(self) -> None:
        if not self.model_id:
            raise ValueError("DEPTH_MODEL_ID must not be empty")
        if self.max_size < 64:
            raise ValueError("DEPTH_MAX_SIZE must be >= 64")
        if self.compute_device not in {"auto", "cpu", "mps", "cuda"}:
            raise ValueError("COMPUTE_DEVICE must be auto, cpu, mps, or cuda")


def load_depth_settings() -> DepthSettings:
    settings = DepthSettings.from_env()
    settings.validate()
    return settings


@dataclass(frozen=True)
class ReconstructionSettings:
    stride: int
    min_depth: float
    max_depth: float
    median_target: float
    max_points: int
    output_dir: Path

    @classmethod
    def from_env(cls) -> ReconstructionSettings:
        return cls(
            stride=_int("CLOUD_STRIDE", 8),
            min_depth=_float("CLOUD_MIN_DEPTH", 0.05),
            max_depth=_float("CLOUD_MAX_DEPTH", 20.0),
            median_target=_float("CLOUD_MEDIAN_TARGET", 1.0),
            max_points=_int("CLOUD_MAX_POINTS", 400000),
            output_dir=Path(os.environ.get("OUTPUT_DIR", "./data/outputs")),
        )

    def validate(self) -> None:
        if self.stride < 1:
            raise ValueError("CLOUD_STRIDE must be >= 1")
        if self.min_depth <= 0:
            raise ValueError("CLOUD_MIN_DEPTH must be > 0")
        if self.max_depth <= self.min_depth:
            raise ValueError("CLOUD_MAX_DEPTH must be > CLOUD_MIN_DEPTH")
        if self.median_target < 0:
            raise ValueError("CLOUD_MEDIAN_TARGET must be >= 0")
        if self.max_points < 100:
            raise ValueError("CLOUD_MAX_POINTS must be >= 100")


def load_reconstruction_settings() -> ReconstructionSettings:
    settings = ReconstructionSettings.from_env()
    settings.validate()
    return settings


@dataclass(frozen=True)
class PointCloudFilterSettings:
    nb_neighbors: int
    std_ratio: float
    voxel_size: float
    crop_percentile: float
    min_points: int
    output_dir: Path

    @classmethod
    def from_env(cls) -> PointCloudFilterSettings:
        return cls(
            nb_neighbors=_int("CLOUD_FILTER_NB_NEIGHBORS", 20),
            std_ratio=_float("CLOUD_FILTER_STD_RATIO", 2.0),
            voxel_size=_float("CLOUD_VOXEL_SIZE", 0.02),
            crop_percentile=_float("CLOUD_CROP_PERCENTILE", 1.0),
            min_points=_int("CLOUD_FILTER_MIN_POINTS", 100),
            output_dir=Path(os.environ.get("OUTPUT_DIR", "./data/outputs")),
        )

    def validate(self) -> None:
        if self.nb_neighbors < 4:
            raise ValueError("CLOUD_FILTER_NB_NEIGHBORS must be >= 4")
        if self.std_ratio <= 0:
            raise ValueError("CLOUD_FILTER_STD_RATIO must be > 0")
        if self.voxel_size <= 0:
            raise ValueError("CLOUD_VOXEL_SIZE must be > 0")
        if not 0.0 <= self.crop_percentile < 50.0:
            raise ValueError("CLOUD_CROP_PERCENTILE must be in [0, 50)")
        if self.min_points < 10:
            raise ValueError("CLOUD_FILTER_MIN_POINTS must be >= 10")


def load_pointcloud_filter_settings() -> PointCloudFilterSettings:
    settings = PointCloudFilterSettings.from_env()
    settings.validate()
    return settings


@dataclass(frozen=True)
class MeshSettings:
    poisson_depth: int
    normal_radius: float
    normal_max_nn: int
    orient_k: int
    density_quantile: float
    bbox_scale: float
    min_triangles: int
    max_triangles: int
    write_glb: bool
    output_dir: Path

    @classmethod
    def from_env(cls) -> MeshSettings:
        return cls(
            poisson_depth=_int("MESH_POISSON_DEPTH", 8),
            normal_radius=_float("MESH_NORMAL_RADIUS", 0.05),
            normal_max_nn=_int("MESH_NORMAL_MAX_NN", 30),
            orient_k=_int("MESH_ORIENT_K", 15),
            density_quantile=_float("MESH_DENSITY_QUANTILE", 0.02),
            bbox_scale=_float("MESH_BBOX_SCALE", 1.1),
            min_triangles=_int("MESH_MIN_TRIANGLES", 50),
            max_triangles=_int("MESH_MAX_TRIANGLES", 200000),
            write_glb=_bool("MESH_WRITE_GLB", True),
            output_dir=Path(os.environ.get("OUTPUT_DIR", "./data/outputs")),
        )

    def validate(self) -> None:
        if self.poisson_depth < 5 or self.poisson_depth > 12:
            raise ValueError("MESH_POISSON_DEPTH must be in [5, 12]")
        if self.normal_radius <= 0:
            raise ValueError("MESH_NORMAL_RADIUS must be > 0")
        if self.normal_max_nn < 8:
            raise ValueError("MESH_NORMAL_MAX_NN must be >= 8")
        if self.orient_k < 4:
            raise ValueError("MESH_ORIENT_K must be >= 4")
        if not 0.0 <= self.density_quantile < 0.5:
            raise ValueError("MESH_DENSITY_QUANTILE must be in [0, 0.5)")
        if self.bbox_scale < 1.0 or self.bbox_scale > 2.0:
            raise ValueError("MESH_BBOX_SCALE must be in [1, 2]")
        if self.min_triangles < 1:
            raise ValueError("MESH_MIN_TRIANGLES must be >= 1")
        if self.max_triangles < 0:
            raise ValueError("MESH_MAX_TRIANGLES must be >= 0")


def load_mesh_settings() -> MeshSettings:
    settings = MeshSettings.from_env()
    settings.validate()
    return settings


@dataclass(frozen=True)
class SplatSettings:
    extract_fps: float
    max_frames: int
    image_max_size: int
    colmap_bin: str
    train_steps: int
    output_dir: Path

    @classmethod
    def from_env(cls) -> SplatSettings:
        return cls(
            extract_fps=_float("SPLAT_EXTRACT_FPS", 8.0),
            max_frames=_int("SPLAT_MAX_FRAMES", 250),
            image_max_size=_int("SPLAT_IMAGE_MAX_SIZE", 1280),
            colmap_bin=os.environ.get("SPLAT_COLMAP_BIN", "colmap").strip() or "colmap",
            train_steps=_int("SPLAT_TRAIN_STEPS", 3000),
            output_dir=Path(os.environ.get("OUTPUT_DIR", "./data/outputs")),
        )

    def validate(self) -> None:
        if self.extract_fps <= 0:
            raise ValueError("SPLAT_EXTRACT_FPS must be > 0")
        if self.max_frames < 8:
            raise ValueError("SPLAT_MAX_FRAMES must be >= 8")
        if self.image_max_size < 256:
            raise ValueError("SPLAT_IMAGE_MAX_SIZE must be >= 256")
        if self.train_steps < 100:
            raise ValueError("SPLAT_TRAIN_STEPS must be >= 100")


def load_splat_settings() -> SplatSettings:
    settings = SplatSettings.from_env()
    settings.validate()
    return settings
