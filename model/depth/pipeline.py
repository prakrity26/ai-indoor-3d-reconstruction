"""Phase 4: per-keyframe monocular depth. Point-cloud fusion is Phase 5."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from model.depth.device import resolve_device
from model.depth.exceptions import DepthEstimationError
from model.depth.io import load_depth_frames
from model.depth.types import (
    STRATEGY_NAME,
    DepthIssue,
    DepthMapRecord,
    DepthResult,
    dump_depth_manifest,
)
from shared.config.settings import DepthSettings, load_depth_settings


def estimate_depth(
    source: str | Path,
    *,
    job_id: str | None = None,
    output_dir: str | Path | None = None,
    settings: DepthSettings | None = None,
    estimator=None,
) -> DepthResult:
    """Write a relative depth map for each selected (preferably posed) keyframe.

    Input is a local job folder from Phases 1–3. This does not download videos
    from Hugging Face. The user supplies their own indoor recording.
    """
    settings = settings or load_depth_settings()
    try:
        settings.validate()
    except ValueError as exc:
        raise DepthEstimationError("invalid_settings", str(exc)) from exc

    frames, job_dir, resolved_id, load_notes = load_depth_frames(source, job_id=job_id)
    if not frames:
        raise DepthEstimationError("empty_frames", "No keyframes found for depth estimation.")

    backend = estimator or _load_backend(settings)
    device = getattr(backend, "device", "cpu")
    strategy = getattr(backend, "name", STRATEGY_NAME)
    model_id = getattr(backend, "model_id", settings.model_id if strategy == STRATEGY_NAME else strategy)

    depth_dir = Path(output_dir) if output_dir is not None else job_dir / "depth"
    depth_dir.mkdir(parents=True, exist_ok=True)

    records: list[DepthMapRecord] = []
    warnings = _load_warnings(load_notes)
    for frame in frames:
        image = cv2.imread(frame.path, cv2.IMREAD_COLOR)
        if image is None:
            warnings.append(
                DepthIssue("warning", "unreadable_frame", f"Could not read {frame.path}")
            )
            continue
        depth = np.asarray(backend.infer(image), dtype=np.float32)
        if depth.shape[:2] != image.shape[:2]:
            depth = cv2.resize(depth, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_CUBIC)
        stem = Path(frame.path).stem
        depth_path = depth_dir / f"{stem}.npy"
        np.save(depth_path, depth)
        preview_path = None
        if settings.write_preview:
            preview_path = depth_dir / f"{stem}.png"
            cv2.imwrite(str(preview_path), _colorize(depth))
        finite = depth[np.isfinite(depth)]
        records.append(
            DepthMapRecord(
                index=frame.index,
                source_path=str(Path(frame.path).resolve()),
                depth_path=str(depth_path.resolve()),
                preview_path=str(preview_path.resolve()) if preview_path is not None else None,
                height=int(depth.shape[0]),
                width=int(depth.shape[1]),
                min_value=round(float(finite.min()), 6) if finite.size else 0.0,
                max_value=round(float(finite.max()), 6) if finite.size else 0.0,
            )
        )

    if not records:
        raise DepthEstimationError("depth_failed", "No depth maps could be written.")

    manifest_path = job_dir / "depth.json"
    result = DepthResult(
        job_id=resolved_id,
        strategy=strategy,
        scale_meaning="relative_affine_invariant",
        device=str(device),
        model_id=str(model_id),
        input_count=len(frames),
        maps=records,
        warnings=warnings,
        depth_dir=str(depth_dir.resolve()),
        manifest_path=str(manifest_path.resolve()),
    )
    dump_depth_manifest(result, manifest_path)
    return result


def _load_backend(settings: DepthSettings):
    from model.depth.depth_anything import DepthAnythingV2Estimator
    from model.depth.device import ensure_stdlib_queue

    ensure_stdlib_queue()
    device = resolve_device(settings.compute_device)
    return DepthAnythingV2Estimator(
        settings.model_id,
        device,
        local_files_only=settings.local_files_only,
        max_size=settings.max_size,
    )


def _load_warnings(notes: list[str]) -> list[DepthIssue]:
    mapping = {
        "poses_missing": (
            "info",
            "Depth is running on keyframes without poses.json. Phase 5 fusion will need poses.",
        ),
        "poses_unreadable": ("warning", "poses.json could not be parsed; using all keyframes."),
        "no_posed_cameras": ("warning", "No successfully posed cameras; using all keyframes."),
        "pose_paths_mismatch": ("warning", "Pose paths did not match keyframes; using all keyframes."),
    }
    warnings = [
        DepthIssue(
            "info",
            "local_video_only",
            "Depth uses your local job frames. Hugging Face demo videos are not used.",
        )
    ]
    for note in notes:
        if note in mapping:
            severity, message = mapping[note]
            warnings.append(DepthIssue(severity, note, message))
    return warnings


def _colorize(depth: np.ndarray) -> np.ndarray:
    finite = depth[np.isfinite(depth)]
    if finite.size == 0:
        return np.zeros((*depth.shape, 3), dtype=np.uint8)
    lo, hi = float(finite.min()), float(finite.max())
    if hi - lo < 1e-6:
        scaled = np.zeros(depth.shape, dtype=np.uint8)
    else:
        scaled = np.clip((depth - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
    return cv2.applyColorMap(scaled, cv2.COLORMAP_INFERNO)
