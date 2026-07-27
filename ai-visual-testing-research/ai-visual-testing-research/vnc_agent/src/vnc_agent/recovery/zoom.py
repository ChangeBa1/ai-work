"""Feature 014 (FR-002): deterministic ROI derivation for zoom_reground.

The ROI is a *viewing window* for the crop+upscale observation — shifting or
shrinking it into frame bounds is legitimate and does NOT touch the strict
no-clamp semantics of click-coordinate resolution (models/coordinate_space.py).
"""

from __future__ import annotations

from typing import Any

from vnc_agent.domain.grounding import GroundingResult
from vnc_agent.domain.observation import OCRItem, Region


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


def expand_region(
    bbox: tuple[int, int, int, int],
    *,
    factor: float,
    min_size_px: int,
    resolution: tuple[int, int],
) -> Region | None:
    """Center-expand ``bbox`` by ``factor``, enforce ``min_size_px``, then
    shift/shrink the window into ``resolution`` bounds. Returns None when no
    valid window exists (degenerate screen or bbox entirely unusable)."""
    width, height = resolution
    if width <= 1 or height <= 1:
        return None
    x1, y1, x2, y2 = bbox
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    w = max((x2 - x1) * factor, float(min_size_px))
    h = max((y2 - y1) * factor, float(min_size_px))
    w = min(w, float(width))
    h = min(h, float(height))
    nx1 = int(round(cx - w / 2.0))
    ny1 = int(round(cy - h / 2.0))
    nx2 = int(round(cx + w / 2.0))
    ny2 = int(round(cy + h / 2.0))
    # Shift the window inside the frame (viewing-window clamping).
    if nx1 < 0:
        nx2 -= nx1
        nx1 = 0
    if ny1 < 0:
        ny2 -= ny1
        ny1 = 0
    if nx2 > width:
        nx1 -= nx2 - width
        nx2 = width
    if ny2 > height:
        ny1 -= ny2 - height
        ny2 = height
    nx1 = max(0, nx1)
    ny1 = max(0, ny1)
    if not (nx1 < nx2 and ny1 < ny2):
        return None
    return Region(x1=nx1, y1=ny1, x2=nx2, y2=ny2)


def _roi_from_grounding(
    grounding_result: GroundingResult | None,
    *,
    expand_factor: float,
    min_size_px: int,
    resolution: tuple[int, int],
) -> Region | None:
    """Priority (a): highest-confidence candidate bbox of the failed grounding
    attempt, center-expanded. Candidates may be out of bounds (that is often
    the very failure) — the expanded window is shifted into frame."""
    if grounding_result is None or not grounding_result.candidates:
        return None
    top = max(grounding_result.candidates, key=lambda c: c.confidence)
    return expand_region(
        top.bbox,
        factor=expand_factor,
        min_size_px=min_size_px,
        resolution=resolution,
    )


def _roi_from_anchor_texts(
    target: dict[str, Any] | None,
    ocr_items: list[OCRItem],
    *,
    expand_factor: float,
    min_size_px: int,
    resolution: tuple[int, int],
) -> Region | None:
    """Priority (b): target.nearby_texts anchors matched against the current
    screen's OCR items (bidirectional normalized containment). Multiple hits →
    the single highest-confidence one (deterministic). The neighborhood uses
    2× the expand factor — anchors sit *near* the target, not on it (spec
    decision 5)."""
    if not target or not ocr_items:
        return None
    needles = [_normalize(t) for t in (target.get("nearby_texts") or []) if _normalize(t)]
    if not needles:
        return None
    hits: list[OCRItem] = []
    for item in ocr_items:
        hay = _normalize(item.normalized_text or item.text)
        if not hay:
            continue
        if any(n in hay or hay in n for n in needles):
            hits.append(item)
    if not hits:
        return None
    anchor = max(hits, key=lambda i: i.confidence)
    return expand_region(
        anchor.bbox,
        factor=expand_factor * 2.0,
        min_size_px=min_size_px,
        resolution=resolution,
    )


def determine_zoom_roi(
    *,
    resolution: tuple[int, int],
    grounding_result: GroundingResult | None = None,
    ocr_items: list[OCRItem] | None = None,
    target: dict[str, Any] | None = None,
    expand_factor: float = 2.0,
    min_size_px: int = 64,
) -> tuple[Region, str] | None:
    """FR-002 ROI derivation order:

    a) highest-confidence bbox of the last failed grounding attempt, expanded;
    b) target.nearby_texts anchor hit in OCR, expanded neighborhood;
    c) neither available → None (no grid sweep — spec decision 2: the caller
       skips the escalation and continues the existing strategy sequence).

    Returns (roi, roi_source) or None.
    """
    roi = _roi_from_grounding(
        grounding_result,
        expand_factor=expand_factor,
        min_size_px=min_size_px,
        resolution=resolution,
    )
    if roi is not None:
        return roi, "grounding_candidate"
    roi = _roi_from_anchor_texts(
        target,
        list(ocr_items or []),
        expand_factor=expand_factor,
        min_size_px=min_size_px,
        resolution=resolution,
    )
    if roi is not None:
        return roi, "anchor_text"
    return None
