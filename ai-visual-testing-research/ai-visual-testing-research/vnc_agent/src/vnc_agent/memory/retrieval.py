"""Pure page/element retrieval helpers (feature 015, spec FR-006/FR-007).

No persistence here — these functions take already-loaded memories plus the
current decoded frame and return matching evidence. They are the pure half of
the "016 扩展点" contract: a replay player can call them without any runtime.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from vnc_agent.domain.memory import ElementMemory, PageFingerprint, PageMatchLevel, PageMemory
from vnc_agent.memory.fingerprint import classify_page_match, page_similarity
from vnc_agent.perception.template.matcher import match_template_array

BBox = tuple[int, int, int, int]


def region_intersects_any(region: BBox, rects: Sequence[Sequence[int]]) -> bool:
    """True when ``region`` (x1,y1,x2,y2) overlaps any 4-tuple rect in
    ``rects`` (closed-open box semantics; degenerate rects ignored)."""
    x1, y1, x2, y2 = region
    for r in rects:
        if len(r) != 4:
            continue
        rx1, ry1, rx2, ry2 = r
        if rx1 >= rx2 or ry1 >= ry2:
            continue
        if x1 < rx2 and rx1 < x2 and y1 < ry2 and ry1 < y2:
            return True
    return False


def find_best_page(
    fingerprint: PageFingerprint,
    pages: Sequence[PageMemory],
    *,
    high: float,
    medium: float,
    low: float,
) -> tuple[PageMemory | None, float, PageMatchLevel]:
    """Best-scoring remembered page for ``fingerprint`` plus its match tier.

    Deterministic: ties broken by page_id lexicographic order. Resolution
    mismatch caps the tier at "low" (classify_page_match). Pure 016
    extension point.
    """
    best: PageMemory | None = None
    best_score = 0.0
    for page in sorted(pages, key=lambda p: p.page_id):
        score = page_similarity(fingerprint, page.fingerprint)
        if best is None or score > best_score:
            best, best_score = page, score
    if best is None:
        return None, 0.0, "none"
    level = classify_page_match(
        best_score,
        same_resolution=tuple(best.resolution) == tuple(fingerprint.resolution),
        high=high,
        medium=medium,
        low=low,
    )
    return best, best_score, level


def expand_bbox(
    bbox: BBox, *, expand_ratio: float, resolution: tuple[int, int]
) -> BBox | None:
    """Remembered-bbox search neighborhood: each side expanded by
    ``expand_ratio`` x the bbox's own width/height, clamped to the frame.
    Returns None when the clamped window is degenerate."""
    x1, y1, x2, y2 = bbox
    w, h = x2 - x1, y2 - y1
    dx, dy = round(w * expand_ratio), round(h * expand_ratio)
    ex1 = max(0, x1 - dx)
    ey1 = max(0, y1 - dy)
    ex2 = min(resolution[0], x2 + dx)
    ey2 = min(resolution[1], y2 + dy)
    if ex1 >= ex2 or ey1 >= ey2:
        return None
    return (ex1, ey1, ex2, ey2)


def match_element_template(
    frame: np.ndarray,
    template: np.ndarray,
    bbox: BBox,
    *,
    expand_ratio: float,
    threshold: float,
    resolution: tuple[int, int],
) -> tuple[BBox, float] | None:
    """Template-match ``template`` inside the expanded neighborhood of the
    remembered ``bbox`` on the current ``frame`` (spec FR-006).

    Returns the best (bbox, score) at/above ``threshold`` in current-frame
    pixels, or None (caller falls back to the grounder). Pure 016 extension
    point — reuses the existing perception matcher unchanged.
    """
    from vnc_agent.domain.observation import Region

    window = expand_bbox(bbox, expand_ratio=expand_ratio, resolution=resolution)
    if window is None:
        return None
    if template.size == 0:
        return None
    matches = match_template_array(
        frame,
        template,
        template_id="element_memory",
        threshold=threshold,
        roi=Region(x1=window[0], y1=window[1], x2=window[2], y2=window[3]),
    )
    if not matches:
        return None
    best = matches[0]
    return best.bbox, best.confidence
