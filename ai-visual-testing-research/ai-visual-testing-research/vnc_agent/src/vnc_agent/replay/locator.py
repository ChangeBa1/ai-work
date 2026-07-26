"""Pure replay target-location functions (feature 016, spec FR-006).

Implements the direct-locate chain of design §11 for one ReplayStep on one
current observation:

    目标模板匹配 → OCR 锚点匹配 → 历史归一化 bbox（仅同分辨率）

The page-fingerprint tier gate happens in the player (it needs config
thresholds); everything here is deterministic geometry/text/pixel matching —
no I/O besides the frame/template arrays handed in, no randomness, no
business vocabulary (Constitution I/VI). Reuses feature 015's pure template
matcher unchanged (spec FR-010 boundary: consume, never modify).
"""

from __future__ import annotations

import statistics
from typing import Literal, NamedTuple

import numpy as np

from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.observation import OCRItem
from vnc_agent.domain.replay import BBox, NormalizedBBox, ReplayAnchor, ReplayStep
from vnc_agent.memory.retrieval import match_element_template
from vnc_agent.memory.service import normalize_target_label

DirectLocateMethod = Literal["template", "anchor", "bbox"]


class LocateResult(NamedTuple):
    method: DirectLocateMethod
    bbox: BBox
    template_score: float | None


def semantic_target_label(sa: SemanticAction) -> str:
    """Same label recipe the runtime uses for its target hint (015 parity)."""
    if sa.target is not None:
        raw = sa.target.text or sa.target.description or sa.target.role or sa.intent or ""
    else:
        raw = sa.intent or ""
    return raw.strip()


def restore_bbox_from_normalized(
    normalized_bbox: NormalizedBBox,
    *,
    recorded_resolution: tuple[int, int],
    current_resolution: tuple[int, int],
) -> BBox | None:
    """Historical-bbox stage (spec FR-006/Clarification 3): direct use is
    same-resolution only — a resolution change returns None (never a scaled
    guess). Kept as a function of the *normalized* form so the same-resolution
    restore is an exact round-trip of the recorded pixels."""
    if tuple(recorded_resolution) != tuple(current_resolution):
        return None
    w, h = current_resolution
    x1 = round(normalized_bbox[0] * w)
    y1 = round(normalized_bbox[1] * h)
    x2 = round(normalized_bbox[2] * w)
    y2 = round(normalized_bbox[3] * h)
    if x1 >= x2 or y1 >= y2:
        return None
    return (x1, y1, x2, y2)


def _unique_ocr_bbox(ocr_items: list[OCRItem], normalized_text: str) -> BBox | None:
    """The bbox of the unique OCR item matching ``normalized_text``; None
    when absent or ambiguous (spec Edge Cases: non-unique anchors abstain)."""
    if not normalized_text:
        return None
    matches = [i for i in ocr_items if i.normalized_text == normalized_text]
    if len(matches) != 1:
        return None
    return matches[0].bbox


def match_anchor_offset(
    anchors: list[ReplayAnchor],
    ocr_items: list[OCRItem],
    recorded_bbox: BBox,
    *,
    tolerance_px: int,
    resolution: tuple[int, int],
) -> BBox | None:
    """Anchor-translation stage (spec Clarification 2b): every recorded
    anchor that appears *uniquely* on the current screen contributes a center
    offset; all contributing offsets must agree pairwise within
    ``tolerance_px`` per axis, and the median offset translates the recorded
    bbox (clamped-out boxes fail). Deterministic, no randomness."""
    deltas: list[tuple[float, float]] = []
    for anchor in anchors:
        current = _unique_ocr_bbox(ocr_items, normalize_target_label(anchor.text))
        if current is None:
            continue
        ax1, ay1, ax2, ay2 = anchor.bbox
        cx1, cy1, cx2, cy2 = current
        deltas.append(
            (
                (cx1 + cx2) / 2 - (ax1 + ax2) / 2,
                (cy1 + cy2) / 2 - (ay1 + ay2) / 2,
            )
        )
    if not deltas:
        return None
    xs = [d[0] for d in deltas]
    ys = [d[1] for d in deltas]
    if (max(xs) - min(xs)) > tolerance_px or (max(ys) - min(ys)) > tolerance_px:
        return None
    dx = round(statistics.median(xs))
    dy = round(statistics.median(ys))
    x1, y1, x2, y2 = recorded_bbox
    moved = (x1 + dx, y1 + dy, x2 + dx, y2 + dy)
    w, h = resolution
    if moved[0] < 0 or moved[1] < 0 or moved[2] > w or moved[3] > h:
        return None
    if moved[0] >= moved[2] or moved[1] >= moved[3]:
        return None
    return moved


def locate_target(
    frame: np.ndarray | None,
    ocr_items: list[OCRItem],
    step: ReplayStep,
    template: np.ndarray | None,
    *,
    current_resolution: tuple[int, int],
    template_match_threshold: float,
    bbox_expand_ratio: float,
    anchor_offset_tolerance_px: int,
) -> LocateResult | None:
    """Run the direct-locate chain for a mouse ReplayStep (spec FR-006).

    Caller has already gated on the page-fingerprint tier. Returns the first
    stage hit or None (caller proceeds to grounder fallback). A
    ``direct_fallback_only`` step never locates directly (spec FR-004).
    """
    if step.direct_fallback_only or step.bbox is None:
        return None

    # 1. template match in the recorded-bbox neighborhood (015 pure matcher)
    if frame is not None and template is not None and template.size:
        matched = match_element_template(
            frame,
            template,
            step.bbox,
            expand_ratio=bbox_expand_ratio,
            threshold=template_match_threshold,
            resolution=current_resolution,
        )
        if matched is not None:
            bbox, score = matched
            return LocateResult("template", bbox, score)

    # 2a. the target's own label as the strongest anchor: unique OCR hit
    label = normalize_target_label(semantic_target_label(step.semantic_action))
    label_bbox = _unique_ocr_bbox(ocr_items, label)
    if label_bbox is not None:
        return LocateResult("anchor", label_bbox, None)

    # 2b. recorded-anchor translation
    anchor_bbox = match_anchor_offset(
        step.anchors,
        ocr_items,
        step.bbox,
        tolerance_px=anchor_offset_tolerance_px,
        resolution=current_resolution,
    )
    if anchor_bbox is not None:
        return LocateResult("anchor", anchor_bbox, None)

    # 3. historical normalized bbox — same resolution only
    if step.normalized_bbox is not None:
        restored = restore_bbox_from_normalized(
            step.normalized_bbox,
            recorded_resolution=tuple(step.page_fingerprint.resolution),
            current_resolution=current_resolution,
        )
        if restored is not None:
            return LocateResult("bbox", restored, None)

    return None
