"""ActionEffect classification — local evidence independent of global threshold (FR-001~005)."""

from __future__ import annotations

from pathlib import Path

from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.observation import Region, StructuredScreen
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
