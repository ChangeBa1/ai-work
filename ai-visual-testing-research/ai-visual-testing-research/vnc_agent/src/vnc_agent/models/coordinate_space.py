"""Strict, single-point Grounder coordinate-space resolution."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from vnc_agent.domain.grounding import GroundingCandidate

CoordinateSpace = Literal["pixel", "normalized_1000"]


def _valid_bbox(bbox: tuple[int, int, int, int], resolution: tuple[int, int]) -> bool:
    x1, y1, x2, y2 = bbox
    width, height = resolution
    return 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height


def _convert(
    raw_bbox: tuple[int, int, int, int],
    space: str,
    resolution: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    if space == "pixel":
        resolved = raw_bbox
    elif space == "normalized_1000":
        if any(value < 0 or value > 1000 for value in raw_bbox):
            return None
        width, height = resolution
        x1, y1, x2, y2 = raw_bbox
        resolved = (
            round(x1 * width / 1000),
            round(y1 * height / 1000),
            round(x2 * width / 1000),
            round(y2 * height / 1000),
        )
    else:
        return None
    return resolved if _valid_bbox(resolved, resolution) else None


def _sibling_space(siblings: Sequence[GroundingCandidate]) -> CoordinateSpace | None:
    declared = {item.coordinate_space for item in siblings if item.coordinate_space is not None}
    if len(declared) == 1:
        return next(iter(declared))
    return None


def restore_original_bbox(
    bbox: tuple[int, int, int, int],
    *,
    scale_factor: float = 1.0,
    crop_offset: tuple[int, int] = (0, 0),
    original_resolution: tuple[int, int] | None = None,
) -> tuple[int, int, int, int] | None:
    """Feature 014 (FR-004): map a bbox from the model-seen (cropped and/or
    upscaled) image back to original full-frame pixel coordinates.

    ``bbox' = round(v / scale_factor) + crop_offset`` per coordinate. Strict
    rejection semantics — never clamp, never guess:

    - ``scale_factor <= 0`` → None
    - degenerate result (x1 >= x2 or y1 >= y2 after rounding) → None
    - outside ``original_resolution`` (when provided) → None

    ``scale_factor=1.0`` + ``crop_offset=(0, 0)`` is the identity (legacy
    full-screen path byte-for-byte unchanged).
    """
    if scale_factor <= 0:
        return None
    ox, oy = crop_offset
    x1, y1, x2, y2 = bbox
    restored = (
        round(x1 / scale_factor) + ox,
        round(y1 / scale_factor) + oy,
        round(x2 / scale_factor) + ox,
        round(y2 / scale_factor) + oy,
    )
    rx1, ry1, rx2, ry2 = restored
    if not (rx1 < rx2 and ry1 < ry2):
        return None
    if original_resolution is not None and not _valid_bbox(restored, original_resolution):
        return None
    return restored


def resolve_pixel_bbox(
    raw_bbox: tuple[int, int, int, int],
    declared_space: Literal["pixel", "normalized_1000"] | None,
    resolution: tuple[int, int],
    *,
    siblings: Sequence[GroundingCandidate] = (),
) -> tuple[int, int, int, int] | None:
    """Resolve one candidate or reject it; values are never clamped or guessed."""
    if declared_space is not None:
        return _convert(raw_bbox, declared_space, resolution)

    inferred_from_siblings = _sibling_space(siblings)
    if inferred_from_siblings is not None:
        return _convert(raw_bbox, inferred_from_siblings, resolution)

    interpretations = [
        _convert(raw_bbox, "pixel", resolution),
        _convert(raw_bbox, "normalized_1000", resolution),
    ]
    passing = [value for value in interpretations if value is not None]
    return passing[0] if len(passing) == 1 else None
