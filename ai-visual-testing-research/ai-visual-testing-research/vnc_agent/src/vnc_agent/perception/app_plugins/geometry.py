"""Feature 024: generic geometry helpers — coordinate-space projection,
containment, and AnchorConstraint relation evaluation.

Everything here is pure geometry over bboxes. No application vocabulary.
"""

from __future__ import annotations

from vnc_agent.domain.app_perception import (
    AnchorConstraint,
    AnchorHit,
    ConstraintViolation,
)

Bbox = tuple[int, int, int, int]


def centre(bbox: Bbox) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def is_inside(region: Bbox, bbox: Bbox) -> bool:
    """True when ``bbox``'s centre falls inside ``region``."""
    rx1, ry1, rx2, ry2 = region
    cx, cy = centre(bbox)
    return rx1 <= cx <= rx2 and ry1 <= cy <= ry2


def area_ratio(region: Bbox, resolution: tuple[int, int]) -> float:
    w, h = resolution
    if w <= 0 or h <= 0:
        return 0.0
    x1, y1, x2, y2 = region
    return max(0.0, (x2 - x1) * (y2 - y1)) / float(w * h)


def project_to_zoom_space(
    bbox: Bbox,
    *,
    crop_offset: tuple[int, int],
    scale_factor: float,
    zoom_resolution: tuple[int, int] | None = None,
) -> Bbox | None:
    """Original-frame bbox -> upscaled-crop coordinates (FR-017).

    The inverse of the click-restoration formula, applied to *hints* so the
    image and its hint boxes always live in one coordinate space. Anything
    that leaves the crop is dropped rather than clamped.
    """
    if scale_factor <= 0:
        return None
    ox, oy = crop_offset
    x1, y1, x2, y2 = bbox
    projected = (
        round((x1 - ox) * scale_factor),
        round((y1 - oy) * scale_factor),
        round((x2 - ox) * scale_factor),
        round((y2 - oy) * scale_factor),
    )
    px1, py1, px2, py2 = projected
    if not (px1 < px2 and py1 < py2):
        return None
    if px1 < 0 or py1 < 0:
        return None
    if zoom_resolution is not None:
        zw, zh = zoom_resolution
        if px2 > zw or py2 > zh:
            return None
    return projected


def in_edge_band(region: Bbox, bbox: Bbox, ratio: float) -> bool:
    """True when ``bbox`` hugs the border of ``region`` — the candidate may
    have been clipped by the crop, which is worth recording."""
    if ratio <= 0:
        return False
    rx1, ry1, rx2, ry2 = region
    bw, bh = (rx2 - rx1) * ratio, (ry2 - ry1) * ratio
    x1, y1, x2, y2 = bbox
    return x1 <= rx1 + bw or y1 <= ry1 + bh or x2 >= rx2 - bw or y2 >= ry2 - bh


def _anchor_bbox(anchor_text: str, anchors: list[AnchorHit]) -> Bbox | None:
    matches = [a for a in anchors if a.anchor_text == anchor_text or a.matched_text == anchor_text]
    if not matches:
        return None
    return max(matches, key=lambda a: a.confidence).bbox


def satisfies(
    constraint: AnchorConstraint,
    candidate: Bbox,
    anchors: list[AnchorHit],
) -> bool | None:
    """Evaluate one generic relation. Returns None when the relation cannot be
    evaluated (anchor not on screen) — unevaluable is never a violation."""
    boxes = [_anchor_bbox(t, anchors) for t in constraint.anchors]
    if any(b is None for b in boxes):
        return None
    cx, cy = centre(candidate)
    cx1, cy1, cx2, cy2 = candidate
    height = max(1.0, cy2 - cy1)
    width = max(1.0, cx2 - cx1)

    if constraint.relation == "between":
        a, b = boxes[0], boxes[1]  # type: ignore[assignment]
        ax, ay = centre(a)
        bx, by = centre(b)
        if abs(ax - bx) >= abs(ay - by):  # mostly horizontal separation
            lo, hi = sorted((ax, bx))
            return lo <= cx <= hi
        lo, hi = sorted((ay, by))
        return lo <= cy <= hi

    anchor = boxes[0]  # type: ignore[assignment]
    ax1, ay1, ax2, ay2 = anchor
    ax, ay = centre(anchor)
    tol_y = constraint.tolerance_ratio * max(height, ay2 - ay1)
    tol_x = constraint.tolerance_ratio * max(width, ax2 - ax1)

    if constraint.relation == "same_row":
        return abs(cy - ay) <= tol_y
    if constraint.relation == "same_column":
        return abs(cx - ax) <= tol_x
    if constraint.relation == "right_of":
        return cx1 >= ax2 - tol_x
    if constraint.relation == "left_of":
        return cx2 <= ax1 + tol_x
    if constraint.relation == "above":
        return cy2 <= ay1 + tol_y
    if constraint.relation == "below":
        return cy1 >= ay2 - tol_y
    return None


def evaluate_constraints(
    constraints: list[AnchorConstraint],
    candidates: list[Bbox],
    anchors: list[AnchorHit],
    *,
    mode: str = "respect_profile",
) -> tuple[list[Bbox], list[ConstraintViolation]]:
    """Apply profile constraints to restored candidates (FR-018).

    ``enforce=True`` constraints reject the violating candidate (strong
    prior); ``enforce=False`` ones only record. ``mode="record_only"``
    downgrades every constraint to audit-only (emergency switch).

    Returns (kept_candidates, violations). An empty kept list is a legitimate
    outcome — the caller falls back to the existing target_not_found path; no
    new FailureType is introduced.
    """
    violations: list[ConstraintViolation] = []
    if not constraints:
        return list(candidates), violations

    kept: list[Bbox] = []
    for candidate in candidates:
        rejected = False
        for constraint in constraints:
            ok = satisfies(constraint, candidate, anchors)
            if ok is None or ok:
                continue
            enforced = constraint.enforce and mode != "record_only"
            violations.append(
                ConstraintViolation(
                    subject=constraint.subject,
                    relation=constraint.relation,
                    anchors=list(constraint.anchors),
                    candidate_bbox=candidate,
                    mode="enforced" if enforced else "record_only",
                )
            )
            if enforced:
                rejected = True
        if not rejected:
            kept.append(candidate)
    return kept, violations
