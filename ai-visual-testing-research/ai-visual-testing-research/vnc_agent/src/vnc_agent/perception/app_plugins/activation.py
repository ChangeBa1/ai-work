"""Feature 024 (FR-011/FR-012): the activation decision ladder.

ONE source of activation: the test step's explicit `perception_scope`
declaration. Detecting a sub-window is a *precondition*, never a reason — a
frame containing a known window must not enable enhancement for a step that
operates on what is behind it.

The asymmetry is deliberate. A false positive crops the grounder's field of
view to the sub-window, so a target outside it is either missed or, worse,
"found" nearby and clicked — an irreversible wrong action. A false negative
merely falls back to today's behaviour. Hence: no inference, no heuristics,
and the default (undeclared) exit is the very first rung and costs nothing.
"""

from __future__ import annotations

from typing import Any

from vnc_agent.domain.app_perception import (
    ActivationDecision,
    ActivationReason,
    ScopeHintMismatch,
    SubWindowDetection,
)
from vnc_agent.domain.observation import OCRItem
from vnc_agent.perception.app_plugins.detector import normalize
from vnc_agent.perception.app_plugins.geometry import is_inside

# Actions that produce a coordinate; anything else has no use for a zoom.
POSITIONAL_ACTIONS = frozenset({"click", "double_click", "right_click"})

SCOPE_OFF = "none"


def is_declared(scope: str | None) -> bool:
    return bool(scope) and scope != SCOPE_OFF


def _decision(
    reason: ActivationReason,
    *,
    scope: str | None = None,
    undetected: bool = False,
) -> ActivationDecision:
    return ActivationDecision(
        activated=reason == "activated",
        reason_code=reason,
        declared_scope=scope,
        declared_but_undetected=undetected,
    )


def decide_precondition(
    *,
    declared_scope: str | None,
    enabled: bool,
    plugin_registered: bool,
    plugin_allowed: bool,
) -> ActivationDecision | None:
    """Rungs 1-4: everything decidable BEFORE any detection work.

    Returns a terminal decision, or None meaning "keep going". Rung 1 is the
    undeclared exit and must stay first: callers rely on it to guarantee that
    an undeclared step never runs a single detection (spec SC-002).

    There is deliberately no action-type gate any more. The refinement now
    happens at observation time and improves the OCR that assertions,
    OCR-direct clicks and grounding all read, so gating it on "this action
    produces a coordinate" would withhold it from exactly the cases (business
    assertions, text entry verification) that motivated moving it here.
    Budget is checked by the caller AFTER the content-hash cache lookup, so a
    re-observation of an unchanged screen never consumes it.
    """
    if not is_declared(declared_scope):
        reason: ActivationReason = "declared_off" if declared_scope == SCOPE_OFF else "not_declared"
        return _decision(reason, scope=declared_scope)
    if not enabled:
        return _decision("disabled", scope=declared_scope)
    if not plugin_registered:
        return _decision("plugin_not_registered", scope=declared_scope)
    if not plugin_allowed:
        return _decision("plugin_not_allowed", scope=declared_scope)
    return None


def decide_detection(
    *,
    declared_scope: str,
    detection: SubWindowDetection | None,
    min_detection_confidence: float,
    roi_area_ratio_max: float,
    min_roi_size_px: int,
) -> ActivationDecision | None:
    """Rung 6: detection outcome. None means "detection accepted"."""
    if detection is None:
        return _decision("not_detected", scope=declared_scope, undetected=True)
    if detection.confidence < min_detection_confidence:
        return _decision("low_detection_confidence", scope=declared_scope, undetected=True)
    x1, y1, x2, y2 = detection.region
    if min(x2 - x1, y2 - y1) < min_roi_size_px:
        return _decision("roi_not_subwindow", scope=declared_scope, undetected=True)
    if detection.area_ratio > roi_area_ratio_max:
        # The "window" is basically the whole screen: cropping buys nothing
        # and would hide everything outside it.
        return _decision("roi_not_subwindow", scope=declared_scope, undetected=True)
    return None


def scope_hint_mismatch(
    target: dict[str, Any] | None,
    ocr_items: list[OCRItem],
    region: tuple[int, int, int, int],
) -> ScopeHintMismatch | None:
    """Read-only warning that the declaration may sit on the wrong step.

    Clues are the target's own locating hints (`text` + `nearby_texts`) —
    deliberately NOT the step intent, whose prose routinely names both the
    sub-window and the main screen ("do not click inside the ... window"), so
    matching against it would produce noise in exactly the wrong direction.

    NEVER changes the outcome (spec FR-011 / Edge Cases).
    """
    if not target:
        return None
    clues: list[str] = []
    text = target.get("text")
    if isinstance(text, str) and text.strip():
        clues.append(text)
    for item in target.get("nearby_texts") or []:
        if isinstance(item, str) and item.strip():
            clues.append(item)
    if not clues:
        return None

    needles = [normalize(c) for c in clues]
    inside = outside = 0
    for ocr in ocr_items:
        hay = normalize(ocr.normalized_text or ocr.text)
        if not hay:
            continue
        if not any(n and (n in hay or hay in n) for n in needles):
            continue
        if is_inside(region, ocr.bbox):
            inside += 1
        else:
            outside += 1
    if outside == 0:
        return None
    return ScopeHintMismatch(
        clue_texts=clues,
        hits_inside=inside,
        hits_outside=outside,
        kind="straddling" if inside else "all_outside",
    )
