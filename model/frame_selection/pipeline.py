"""Phase 2: select keyframes from uniformly extracted frames."""

from __future__ import annotations

import shutil
from pathlib import Path

import cv2
import numpy as np

from model.frame_selection.exceptions import FrameSelectionError
from model.frame_selection.io import load_source
from model.frame_selection.metrics import sharpness, thumbnail, to_gray
from model.frame_selection.selection import select_indices
from model.frame_selection.types import (
    STRATEGY_NAME,
    KeyframeRecord,
    SelectionIssue,
    SelectionResult,
    dump_selection,
)
from model.preprocessing.types import FrameRecord
from shared.config.settings import FrameSelectionSettings, load_frame_selection_settings


def select_keyframes(
    source: str | Path,
    *,
    job_id: str | None = None,
    output_dir: str | Path | None = None,
    settings: FrameSelectionSettings | None = None,
) -> SelectionResult:
    """Reduce Phase 1 frames to a coverage-preserving keyframe set.

    Camera pose is intentionally not estimated here (Phase 3).
    """
    settings = settings or load_frame_selection_settings()
    try:
        settings.validate()
    except ValueError as exc:
        raise FrameSelectionError("invalid_settings", str(exc)) from exc

    frames, job_dir, resolved_id = load_source(source, job_id=job_id)
    thumbs, sharpness_values, readable = _analyze_frames(frames, settings)
    if not readable:
        raise FrameSelectionError(
            "unreadable_frames",
            "None of the extracted frames could be decoded.",
            {"job_dir": str(job_dir)},
        )

    chosen = select_indices(thumbs, sharpness_values, settings)
    selected_root = Path(output_dir) if output_dir is not None else job_dir / "selected"
    selected_root.mkdir(parents=True, exist_ok=True)

    records = _write_selected(
        chosen,
        readable,
        sharpness_values,
        selected_root,
    )
    warnings = _warnings(len(readable), records)

    selection_path = job_dir / "selection.json"
    result = SelectionResult(
        job_id=resolved_id,
        strategy=STRATEGY_NAME,
        input_count=len(readable),
        selected=records,
        warnings=warnings,
        selected_dir=str(selected_root.resolve()),
        selection_path=str(selection_path.resolve()),
    )
    dump_selection(result, selection_path)
    return result


def _analyze_frames(
    frames: list[FrameRecord],
    settings: FrameSelectionSettings,
) -> tuple[list[np.ndarray], list[float], list[FrameRecord]]:
    thumbs = []
    sharpness_values: list[float] = []
    readable: list[FrameRecord] = []
    for frame in frames:
        image = cv2.imread(frame.path, cv2.IMREAD_COLOR)
        if image is None:
            continue
        gray = to_gray(image)
        thumbs.append(thumbnail(gray, settings.thumbnail_size))
        sharpness_values.append(sharpness(gray, settings.sharpness_width))
        readable.append(frame)
    return thumbs, sharpness_values, readable


def _write_selected(
    chosen: list[tuple[int, str, float]],
    readable: list[FrameRecord],
    sharpness_values: list[float],
    selected_root: Path,
) -> list[KeyframeRecord]:
    records: list[KeyframeRecord] = []
    for seq_index, reason, change in chosen:
        source = readable[seq_index]
        source_path = Path(source.path)
        dest = selected_root / source_path.name
        shutil.copy2(source_path, dest)
        records.append(
            KeyframeRecord(
                index=seq_index,
                source_index=source.index,
                timestamp_sec=source.timestamp_sec,
                path=str(dest.resolve()),
                source_path=str(source_path.resolve()),
                sharpness=round(sharpness_values[seq_index], 3),
                change_from_previous=change,
                reason=reason,
            )
        )
    return records


def _warnings(input_count: int, records: list[KeyframeRecord]) -> list[SelectionIssue]:
    warnings: list[SelectionIssue] = []
    skipped = input_count - len(records)
    if skipped > 0:
        warnings.append(
            SelectionIssue(
                "info",
                "duplicates_dropped",
                f"Dropped {skipped} near-duplicate or budget-excess frames.",
            )
        )
    reasons = {item.reason for item in records}
    if "coverage_fill" in reasons:
        warnings.append(
            SelectionIssue(
                "info",
                "coverage_fill",
                "Inserted extra frames so the selection meets KEYFRAME_MIN_COUNT.",
            )
        )
    if "max_gap" in reasons:
        warnings.append(
            SelectionIssue(
                "info",
                "forced_coverage",
                "Kept some low-change frames to avoid long gaps in the trajectory.",
            )
        )
    return warnings
