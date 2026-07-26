"""ActionEffect classification — local evidence independent of global threshold (FR-001~005).

Feature 022 (wrong-click-detection) adds pure geometry helpers on top of the
existing evidence: target-neighborhood expansion/intersection (shared by the
pre-click stale-frame guard and the wrong-target assessment) and
:func:`assess_wrong_target`. None of them changes the semantics of
:func:`classify_action_effect`, and none of them calls VNC or a model.
"""

from __future__ import annotations

import math
from pathlib import Path

from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.observation import Region, StructuredScreen
from vnc_agent.domain.recovery import WrongTargetDirection, WrongTargetEvidence
from vnc_agent.perception.screen_diff import compute_diff

_DEFAULT_ERROR_KEYWORDS = ["错误", "エラー", "Error", "失败", "失敗", "Failed"]


def _blob_area_ratio(blob: Region, width: int, height: int) -> float:
    total = max(width * height, 1)
    return max(0, (blob.x2 - blob.x1) * (blob.y2 - blob.y1)) / total


def _filter_blobs_outside_masks(
    blobs: list[Region], mask_regions: list[Region] | None
) -> list[Region]:
    if not mask_regions:
        return list(blobs)
    kept: list[Region] = []
    for b in blobs:
        cx, cy = b.center()
        if any(m.contains_point(cx, cy) for m in mask_regions):
            continue
        kept.append(b)
    return kept


def _ocr_texts(screen: StructuredScreen) -> set[str]:
    return {
        (i.normalized_text or i.text.strip().lower())
        for i in screen.ocr_items
        if (i.normalized_text or i.text).strip()
    }


def _template_ids(screen: StructuredScreen) -> set[str]:
    return {m.template_id for m in screen.template_matches if m.template_id}


def _structured_state_changed(before: StructuredScreen, after: StructuredScreen) -> bool:
    b = before.vision_understanding
    a = after.vision_understanding
    if b is None and a is None:
        return False
    if b is None or a is None:
        return True
    return (b.description or "").strip() != (a.description or "").strip()


def _classify_error_popup(
    after: StructuredScreen,
    *,
    error_keywords: list[str] | None,
) -> str:
    """
    Step 3 of classify_action_effect (research.md §6).

    Returns error_popup_signal: "ocr_keyword" | "template" | "none".
    """
    keywords = error_keywords if error_keywords is not None else _DEFAULT_ERROR_KEYWORDS
    if keywords:
        for item in after.ocr_items:
            text = item.text or ""
            norm = item.normalized_text or text.lower()
            for kw in keywords:
                if not kw:
                    continue
                if kw in text or kw.lower() in norm:
                    return "ocr_keyword"
    # Optional known error-dialog template ids
    for m in after.template_matches:
        tid = (m.template_id or "").lower()
        if any(k in tid for k in ("error", "err_dialog", "error_popup", "alert_error")):
            return "template"
    return "none"


def classify_action_effect(
    before: StructuredScreen,
    after: StructuredScreen,
    *,
    intent: str = "",
    mask_regions: list[Region] | None = None,
    local_blob_min_ratio: float = 0.0005,
    error_keywords: list[str] | None = None,
) -> ActionEffect:
    """
    Pure local-evidence combination → ActionEffect (contracts/action-effect-contract.md §1).

    MUST NOT call VNC or vision models. ``intent`` is ignored for classification
    (only used for logging/reason context).
    """
    del intent  # intent must not drive the verdict

    # Prefer precomputed local_blobs on after; recompute from images when both paths exist
    global_ratio = after.global_diff_ratio
    local_blobs = list(after.local_blobs)

    if before.image_path and after.image_path:
        b_path, a_path = Path(before.image_path), Path(after.image_path)
        if b_path.exists() and a_path.exists():
            _, _, global_ratio, local_blobs = compute_diff(
                b_path,
                a_path,
                threshold=1.0,  # force regions empty; we only want local_blobs + ratio
                mask_regions=mask_regions,
            )

    local_blobs = _filter_blobs_outside_masks(local_blobs, mask_regions)

    ocr_before = _ocr_texts(before)
    ocr_after = _ocr_texts(after)
    ocr_added = sorted(ocr_after - ocr_before)
    ocr_removed = sorted(ocr_before - ocr_after)

    tmpl_before = _template_ids(before)
    tmpl_after = _template_ids(after)
    template_added = sorted(tmpl_after - tmpl_before)
    template_removed = sorted(tmpl_before - tmpl_after)

    structured_changed = _structured_state_changed(before, after)

    error_signal = _classify_error_popup(after, error_keywords=error_keywords)

    evidence = ActionEffectEvidence(
        global_diff_ratio=global_ratio,
        local_blobs=local_blobs,
        ocr_added=ocr_added,
        ocr_removed=ocr_removed,
        template_added=template_added,
        template_removed=template_removed,
        structured_state_changed=structured_changed,
        error_popup_signal=error_signal,  # type: ignore[arg-type]
    )

    # 1) Error popup → unexpected_effect regardless of magnitude
    if error_signal != "none":
        return ActionEffect(
            status="unexpected_effect",
            evidence=evidence,
            reason=f"error_popup_signal={error_signal}",
        )

    width, height = after.resolution if after.resolution != (0, 0) else (1, 1)
    if width <= 0 or height <= 0:
        width, height = 1, 1

    significant_blobs = [
        b
        for b in local_blobs
        if _blob_area_ratio(b, width, height) >= local_blob_min_ratio
    ]
    has_ocr = bool(ocr_added or ocr_removed)
    has_tmpl = bool(template_added or template_removed)
    has_any_blob = bool(local_blobs)

    # 2) No signals at all → no_effect
    if not has_any_blob and not has_ocr and not has_tmpl and not structured_changed:
        return ActionEffect(
            status="no_effect",
            evidence=evidence,
            reason="no local_blobs, ocr/template diff, or structured state change",
        )

    # 3) Clear deterministic local signal → expected_effect
    if significant_blobs or has_ocr or has_tmpl or structured_changed:
        parts: list[str] = []
        if significant_blobs:
            b0 = significant_blobs[0]
            parts.append(
                f"local_blob@({b0.x1},{b0.y1},{b0.x2 - b0.x1},{b0.y2 - b0.y1}) "
                f"ratio={_blob_area_ratio(b0, width, height):.5f}"
            )
        if has_ocr:
            parts.append(f"ocr_added={ocr_added!r} ocr_removed={ocr_removed!r}")
        if has_tmpl:
            parts.append(
                f"template_added={template_added!r} template_removed={template_removed!r}"
            )
        if structured_changed:
            parts.append("structured_state_changed")
        parts.append(f"global_ratio={global_ratio:.5f}")
        return ActionEffect(
            status="expected_effect",
            evidence=evidence,
            reason=" while ".join(parts),
        )

    # 4) Weak/noise-level signals only → effect_uncertain
    return ActionEffect(
        status="effect_uncertain",
        evidence=evidence,
        reason=(
            f"sub-threshold local signals only "
            f"(blobs={len(local_blobs)}, global_ratio={global_ratio:.5f})"
        ),
    )


# ---------------------------------------------------------------------------
# Feature 022 (wrong-click-detection): pure geometry helpers + assessment.
# ---------------------------------------------------------------------------


def expand_target_region(
    region: Region,
    *,
    expand_ratio: float,
    resolution: tuple[int, int],
) -> Region:
    """Per-side expansion of ``region`` by ``expand_ratio`` of its own
    width/height, clamped to ``resolution`` (never inverted, never empty)."""
    width, height = resolution
    w = region.x2 - region.x1
    h = region.y2 - region.y1
    dx = int(round(w * expand_ratio))
    dy = int(round(h * expand_ratio))
    x1 = max(0, region.x1 - dx)
    y1 = max(0, region.y1 - dy)
    x2 = region.x2 + dx
    y2 = region.y2 + dy
    if width > 0:
        x2 = min(width, x2)
    if height > 0:
        y2 = min(height, y2)
    # Region requires x1<x2 / y1<y2; clamping can only shrink the outer edge,
    # never below the original box, so this stays valid.
    return Region(x1=x1, y1=y1, x2=max(x2, x1 + 1), y2=max(y2, y1 + 1))


def _regions_intersect(a: Region, b: Region) -> bool:
    return a.x1 < b.x2 and b.x1 < a.x2 and a.y1 < b.y2 and b.y1 < a.y2


def region_iou(a: Region, b: Region) -> float:
    """Intersection-over-union of two pixel regions (0.0 when disjoint)."""
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    if ix1 >= ix2 or iy1 >= iy2:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    area_a = (a.x2 - a.x1) * (a.y2 - a.y1)
    area_b = (b.x2 - b.x1) * (b.y2 - b.y1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def blobs_intersecting_neighborhood(
    blobs: list[Region],
    target_region: Region,
    *,
    expand_ratio: float,
    resolution: tuple[int, int],
) -> list[Region]:
    """Change blobs that touch the expanded target neighborhood — the shared
    primitive behind the pre-click stale-frame guard (expand default 0.25)
    and the wrong-target assessment (expand default 0.5)."""
    neighborhood = expand_target_region(
        target_region, expand_ratio=expand_ratio, resolution=resolution
    )
    return [b for b in blobs if _regions_intersect(b, neighborhood)]


_DIRECTION_SECTORS: tuple[WrongTargetDirection, ...] = (
    "right",
    "up_right",
    "up",
    "up_left",
    "left",
    "down_left",
    "down",
    "down_right",
)


def direction_8(dx: int, dy: int) -> WrongTargetDirection:
    """8-way compass direction of offset (dx, dy) in screen coordinates
    (y grows downward; "up" therefore means dy < 0)."""
    if dx == 0 and dy == 0:
        return "center"
    angle = math.degrees(math.atan2(-dy, dx)) % 360.0  # 0° = right, 90° = up
    return _DIRECTION_SECTORS[int(((angle + 22.5) % 360.0) // 45.0)]


def assess_wrong_target(
    effect: ActionEffect,
    *,
    target_region: Region | None,
    resolution: tuple[int, int],
    click_point: tuple[int, int] | None = None,
    neighborhood_expand_ratio: float = 0.5,
    global_diff_ratio_max: float = 0.10,
) -> WrongTargetEvidence:
    """Feature 022 (FR-B02): pure wrong-click assessment over an already
    classified :class:`ActionEffect` — zero VNC/model calls, no mutation.

    ``suspected`` is True iff ALL of:

    1. ``effect.status == "expected_effect"`` (something did change);
    2. a ``target_region`` exists and at least one change blob was observed;
    3. NO change blob intersects the target neighborhood
       (``target_region`` expanded per-side by ``neighborhood_expand_ratio``);
    4. ``global_diff_ratio < global_diff_ratio_max`` — a full-screen-scale
       change (dialog popped, page navigated) is exempt because the response
       legitimately covers regions far from the click.

    Nearest-blob distance/direction (target center → blob center) is always
    computed when blobs + target exist, suspected or not — feature 023
    consumes it as relocation guidance.
    """
    evidence = effect.evidence
    blobs = list(evidence.local_blobs)
    out = WrongTargetEvidence(
        suspected=False,
        target_region=target_region.as_tuple() if target_region is not None else None,
        click_point=click_point,
        neighborhood_expand_ratio=neighborhood_expand_ratio,
        global_diff_ratio_max=global_diff_ratio_max,
        global_diff_ratio=evidence.global_diff_ratio,
        blob_count=len(blobs),
    )
    if target_region is None or not blobs:
        out.reason = "no target_region or no change blobs — not assessable"
        return out

    intersecting = blobs_intersecting_neighborhood(
        blobs,
        target_region,
        expand_ratio=neighborhood_expand_ratio,
        resolution=resolution,
    )
    out.blobs_intersecting_neighborhood = len(intersecting)
    out.max_blob_target_iou = max(region_iou(b, target_region) for b in blobs)

    tcx, tcy = target_region.center()
    nearest = min(
        blobs,
        key=lambda b: math.hypot(b.center()[0] - tcx, b.center()[1] - tcy),
    )
    ncx, ncy = nearest.center()
    dx, dy = ncx - tcx, ncy - tcy
    out.nearest_blob_bbox = nearest.as_tuple()
    out.nearest_blob_distance_px = math.hypot(dx, dy)
    out.nearest_blob_offset = (dx, dy)
    out.nearest_blob_direction = direction_8(dx, dy)

    if effect.status != "expected_effect":
        out.reason = f"effect status {effect.status!r} — only expected_effect is assessed"
        return out
    if intersecting:
        out.reason = (
            f"{len(intersecting)}/{len(blobs)} blob(s) intersect the "
            f"x{neighborhood_expand_ratio} neighborhood — change is local to target"
        )
        return out
    if evidence.global_diff_ratio >= global_diff_ratio_max:
        out.reason = (
            f"global_diff_ratio {evidence.global_diff_ratio:.5f} >= "
            f"{global_diff_ratio_max} — screen-scale change (dialog/navigation) exempt"
        )
        return out

    out.suspected = True
    out.reason = (
        f"expected_effect but all {len(blobs)} change blob(s) miss the "
        f"x{neighborhood_expand_ratio} target neighborhood; nearest blob "
        f"{out.nearest_blob_distance_px:.1f}px {out.nearest_blob_direction} of target "
        f"(global_diff_ratio {evidence.global_diff_ratio:.5f} < {global_diff_ratio_max})"
    )
    return out
