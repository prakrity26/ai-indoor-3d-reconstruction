"""Greedy adaptive keyframe indices. Pose estimation belongs to Phase 3."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from model.frame_selection.metrics import change_score
from shared.config.settings import FrameSelectionSettings


def _even_indices(count: int, take: int) -> list[int]:
    if take >= count:
        return list(range(count))
    if take <= 1:
        return [0]
    return [int(round(i * (count - 1) / (take - 1))) for i in range(take)]


def _even_pick(values: Sequence[int], take: int) -> list[int]:
    if take >= len(values):
        return list(values)
    positions = _even_indices(len(values), take)
    picked: list[int] = []
    for pos in positions:
        value = values[pos]
        if not picked or picked[-1] != value:
            picked.append(value)
    return picked


def select_indices(
    thumbs: Sequence[np.ndarray],
    sharpness_values: Sequence[float],
    settings: FrameSelectionSettings,
) -> list[tuple[int, str, float]]:
    """Return (index, reason, change_from_previous_kept) in order."""
    n = len(thumbs)
    if n == 0:
        return []
    if n == 1:
        return [(0, "first", 0.0)]

    kept: list[tuple[int, str, float]] = [(0, "first", 0.0)]
    last = 0

    for i in range(1, n):
        gap = i - last
        if gap < settings.min_gap:
            continue
        change = change_score(thumbs[last], thumbs[i])
        if change >= settings.diff_threshold:
            kept.append((i, "content_change", round(change, 4)))
            last = i
            continue
        if gap >= settings.max_gap:
            start = last + settings.min_gap
            window = range(start, i + 1)
            best = max(window, key=lambda j: (sharpness_values[j], -j))
            forced = change_score(thumbs[last], thumbs[best])
            kept.append((best, "max_gap", round(forced, 4)))
            last = best

    if kept[-1][0] != n - 1:
        change = change_score(thumbs[kept[-1][0]], thumbs[n - 1])
        kept.append((n - 1, "last", round(change, 4)))

    return _enforce_counts(kept, n, settings)


def _enforce_counts(
    kept: list[tuple[int, str, float]],
    n: int,
    settings: FrameSelectionSettings,
) -> list[tuple[int, str, float]]:
    by_index = {index: (index, reason, change) for index, reason, change in kept}
    ordered = [by_index[i] for i in sorted(by_index)]

    max_count = min(settings.max_count, n)
    min_count = min(settings.min_count, n)

    if len(ordered) > max_count:
        indices = [item[0] for item in ordered]
        reduced = _even_pick(indices, max_count)
        if reduced:
            reduced[0] = indices[0]
            reduced[-1] = indices[-1]
        unique: list[int] = []
        for index in reduced:
            if index not in unique:
                unique.append(index)
        ordered = [by_index[index] for index in unique if index in by_index]

    if len(ordered) < min_count:
        selected = {item[0] for item in ordered}
        available = [i for i in range(n) if i not in selected]
        need = min_count - len(ordered)
        extras = _even_pick(available, need)
        for index in extras:
            ordered.append((index, "coverage_fill", 0.0))
        ordered.sort(key=lambda item: item[0])

    return ordered
