"""Safe click-point computation (feature 013, overall_design.md §9.6).

Replaces mechanical bbox centers with a deterministic "safe point":

1. Base point is the bbox geometric center (same integer formula the policy
   used before: ``((x1 + x2) // 2, (y1 + y2) // 2)``).
2. The returned point MUST fall inside the *safe zone*: the bbox inset by
   ``edge_inset_ratio`` on every side (FR-003). An axis whose inset zone is
   empty degrades to the center coordinate for that axis.
3. Sibling bboxes (other OCR/template hits, other grounding candidates) that
   intersect the bbox are avoided: the point picked is the grid point with
   zero overlap closest to the center; when the safe zone is fully covered,
   the point with the smallest *overlap depth* is returned and flagged via
   ``residual_overlap=True`` (FR-004/005).
4. When ``screen_resolution`` is provided the final point is clamped into
   ``[0, w-1] x [0, h-1]`` (FR-006).

Pure function: no I/O, no randomness, no global state — identical inputs
always produce identical outputs (Constitution I, replay consistency).
Geometry only, no business semantics (Constitution VI).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

BBox = tuple[int, int, int, int]  # (x1, y1, x2, y2) original-image pixels

#: Default edge inset ratio (overall_design.md §9.6 "避开边缘 15%").
DEFAULT_EDGE_INSET_RATIO = 0.15

#: Fixed per-axis sample count for the deterministic candidate grid.
_GRID_POINTS_PER_AXIS = 9


class SafeClickPoint(NamedTuple):
    """Click point plus companion metadata (spec C-005 / FR-005)."""

    x: int
    y: int
    #: True = the chosen point still lies inside at least one intersecting
    #: sibling bbox (safe zone fully covered; minimal-overlap point chosen).
    residual_overlap: bool


def _axis_samples(lo: int, hi: int, center: int) -> list[int]:
    """Deterministic, sorted, de-duplicated integer samples covering [lo, hi]."""
    if lo >= hi:
        return [lo]
    span = hi - lo
    steps = _GRID_POINTS_PER_AXIS - 1
    values = {lo + round(span * i / steps) for i in range(_GRID_POINTS_PER_AXIS)}
    # The center always participates so "no interference -> exact center" holds.
    values.add(min(max(center, lo), hi))
    return sorted(values)


def safe_click_point(
    bbox: BBox,
    *,
    siblings: Sequence[BBox] = (),
    screen_resolution: tuple[int, int] | None = None,
    edge_inset_ratio: float = DEFAULT_EDGE_INSET_RATIO,
) -> SafeClickPoint:
    """Compute the safe click point for ``bbox`` (see module docstring).

    ``siblings`` are competing candidate rectangles; degenerate ones and ones
    that do not intersect ``bbox`` are ignored (spec Edge Cases). ``bbox`` is
    assumed ``x1 <= x2, y1 <= y2``.
    """
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

    # --- safe zone: inset each side, degrade per-axis to center (FR-003) ---
    inset_x = round((x2 - x1) * edge_inset_ratio)
    inset_y = round((y2 - y1) * edge_inset_ratio)
    sx1, sx2 = x1 + inset_x, x2 - inset_x
    sy1, sy2 = y1 + inset_y, y2 - inset_y
    if sx1 > sx2:
        sx1 = sx2 = cx
    if sy1 > sy2:
        sy1 = sy2 = cy

    # --- siblings: keep non-degenerate rectangles intersecting the bbox ---
    active = [
        s
        for s in siblings
        if s[0] < s[2]
        and s[1] < s[3]
        and s[0] <= x2
        and x1 <= s[2]
        and s[1] <= y2
        and y1 <= s[3]
    ]

    def overlap_depth(px: int, py: int) -> int:
        """Sum of escape distances w.r.t. every sibling containing the point.

        The escape distance (minimal displacement that moves the point out of
        the sibling rectangle) is the deterministic "overlap depth" metric of
        research.md D2. Containment uses closed intervals (conservative).
        """
        total = 0
        for ox1, oy1, ox2, oy2 in active:
            if ox1 <= px <= ox2 and oy1 <= py <= oy2:
                total += min(px - ox1 + 1, ox2 - px + 1, py - oy1 + 1, oy2 - py + 1)
        return total

    # --- deterministic grid search with a total order (research.md D1) ---
    best_key: tuple[int, int, int, int] | None = None
    best_x, best_y, best_depth = cx, cy, 0
    for py in _axis_samples(sy1, sy2, cy):
        for px in _axis_samples(sx1, sx2, cx):
            depth = overlap_depth(px, py)
            key = (depth, (px - cx) ** 2 + (py - cy) ** 2, py, px)
            if best_key is None or key < best_key:
                best_key = key
                best_x, best_y, best_depth = px, py, depth

    # --- screen clamp (FR-006); metadata judged before clamping ---
    if screen_resolution is not None:
        width, height = screen_resolution
        best_x = min(max(best_x, 0), width - 1)
        best_y = min(max(best_y, 0), height - 1)

    return SafeClickPoint(best_x, best_y, best_depth > 0)
