"""Deterministic consistency/conflict gates for targets proposed within one
test step (Feature 003 T007/T015 — safety issues A and B).

Neither function in this module depends on any business-specific keyword
list. Role/interactivity comparisons use only structural fields the Planner/
Grounder already produce; "legitimate micro-action" classification is driven
by the Planner's declared ``SemanticAction.micro_action_purpose`` (a closed,
UI-generic enum), not by scanning free text for business vocabulary.
"""

from __future__ import annotations

import re
from typing import Literal

from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.observation import Region

ConsistencyOutcome = Literal[
    "legitimate_micro_action",
    "dangerous_drift",
    "ambiguous",
]

_INTERACTIVE_ROLES = ("button", "control", "link", "menu", "tab", "按钮", "ボタン")
_GENERIC_TERMS = (
    "click",
    "点击",
    "操作",
    "button",
    "control",
    "按钮",
    "ボタン",
)

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

# Generic UI-interaction risk defaults — structural categories, not business
# vocabulary. Deployments MAY override via
# config.agent.planning.micro_action_risk_thresholds.
DEFAULT_MICRO_ACTION_RISK_THRESHOLDS: dict[str, str] = {
    "dismiss_overlay": "medium",
    "scroll_reveal": "medium",
    "refocus": "medium",
    "wait": "high",
    "re_observe": "high",
}


def _normalized_role(action: SemanticAction) -> str:
    role = (action.target.role if action.target else None) or ""
    return role.strip().lower()


def _action_text(action: SemanticAction) -> str:
    target = action.target
    values = [action.intent]
    if target is not None:
        values.extend([target.role or "", target.text or "", target.description])
    return " ".join(values).lower()


def _business_text(text: str) -> str:
    value = text.lower()
    for term in _GENERIC_TERMS:
        value = value.replace(term, "")
    return re.sub(r"[^0-9a-z぀-ヿ㐀-鿿]+", "", value)


def _longest_common_substring(left: str, right: str) -> int:
    if not left or not right:
        return 0
    previous = [0] * (len(right) + 1)
    best = 0
    for lch in left:
        current = [0]
        for index, rch in enumerate(right, start=1):
            size = previous[index - 1] + 1 if lch == rch else 0
            current.append(size)
            best = max(best, size)
        previous = current
    return best


def _is_interactive(action: SemanticAction) -> bool:
    role = _normalized_role(action)
    return any(marker in role for marker in _INTERACTIVE_ROLES)


def _iou(a: Region, b: Region) -> float:
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    area_a = (a.x2 - a.x1) * (a.y2 - a.y1)
    area_b = (b.x2 - b.x1) * (b.y2 - b.y1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def has_target_evidence_conflict(
    previous_action: SemanticAction,
    proposed_action: SemanticAction,
    *,
    previous_resolved_region: Region | None = None,
    proposed_resolved_region: Region | None = None,
    target_region_conflict_iou_threshold: float = 0.10,
) -> bool:
    """Safety issue A: a matching action_id proves only "same logical action
    attempt," never that a new round's target is safe. This function checks
    whether the new round's role, interaction nature, or spatial evidence
    substantially conflicts with the previous round's — independent of
    whether identity_match() found a strong match, and independent of
    whether the previous ActionEffect was no_effect. MUST be computed
    unconditionally by RepeatGuard.check() whenever a previous action exists.

    A dimension that lacks evidence on either side (role unset, or a region
    not yet resolved) does not participate in the decision — it never
    manufactures a conflict out of missing information.
    """
    prev_role = _normalized_role(previous_action)
    prop_role = _normalized_role(proposed_action)
    if prev_role and prop_role:
        if prev_role != prop_role:
            return True
        if _is_interactive(previous_action) != _is_interactive(proposed_action):
            return True

    if previous_resolved_region is not None and proposed_resolved_region is not None:
        if _iou(previous_resolved_region, proposed_resolved_region) < (
            target_region_conflict_iou_threshold
        ):
            return True

    return False


def _risk_exceeds(risk: str, threshold: str) -> bool:
    return _RISK_ORDER.get(risk, 0) > _RISK_ORDER.get(threshold, 0)


def _intent_overlaps(
    step_intent: str,
    previous_action: SemanticAction,
    proposed_action: SemanticAction,
) -> tuple[int, int]:
    """Text-overlap heuristic used to judge whether a *replacement* target
    (no declared micro_action_purpose) still plausibly continues toward the
    same primary intent — distinct from the micro-action legitimacy test,
    which FR-006 defines directly via the declared purpose (see
    evaluate_target_consistency). Returns (previous_overlap, proposed_overlap)."""
    business_intent = _business_text(step_intent)
    previous_overlap = _longest_common_substring(
        business_intent, _business_text(_action_text(previous_action))
    )
    proposed_overlap = _longest_common_substring(
        business_intent, _business_text(_action_text(proposed_action))
    )
    return previous_overlap, proposed_overlap


def evaluate_target_consistency(
    step_intent: str,
    previous_action: SemanticAction | None,
    proposed_action: SemanticAction,
    *,
    micro_action_risk_thresholds: dict[str, str] | None = None,
) -> ConsistencyOutcome:
    """Safety issue B: an action_type change between rounds is only a risk
    SIGNAL that requires this check to run — it MUST NOT by itself decide
    the outcome. `"legitimate_micro_action"` requires the AND of: (a) a
    declared, independent micro_action_purpose (FR-006 defines a declared
    purpose in the closed enum as *how* step-intent-consistency is satisfied
    for this branch — there is no separate free-text overlap gate on top of
    it); (b) the declared risk_level not exceeding that purpose's threshold.
    When no purpose is declared, the target is evaluated as a potential
    *replacement* for the same primary intent instead (text-overlap
    consistency), and drift is judged from that.
    """
    if previous_action is None:
        return "legitimate_micro_action"

    thresholds = micro_action_risk_thresholds
    if thresholds is None:
        thresholds = DEFAULT_MICRO_ACTION_RISK_THRESHOLDS

    purpose = proposed_action.micro_action_purpose
    if purpose is not None:
        threshold = thresholds.get(purpose, "low")
        if not _risk_exceeds(proposed_action.risk_level, threshold):
            return "legitimate_micro_action"
        # Declared purpose recognized but risk exceeds its threshold: this is
        # not a confident drift verdict either (the purpose itself was
        # legitimate) — route to "ambiguous" so RepeatGuard/RecoveryEngine's
        # existing six-field contract (requires_human_confirmation/
        # requires_strong_model) decides next steps, per FR-013.
        return "ambiguous"

    previous_interactive = _is_interactive(previous_action)
    proposed_interactive = _is_interactive(proposed_action)

    if previous_interactive and not proposed_interactive:
        return "dangerous_drift"

    if previous_interactive and proposed_interactive:
        previous_overlap, proposed_overlap = _intent_overlaps(
            step_intent, previous_action, proposed_action
        )
        # A replacement target that is now MORE aligned with the step intent
        # than the previous one was is a legitimate new target within the
        # step (FR-003/FR-005) — a second, independent path to
        # "legitimate_micro_action" alongside the declared-purpose path above.
        if proposed_overlap >= 2 and proposed_overlap > previous_overlap:
            return "legitimate_micro_action"
        # A replacement that abandons a previously well-aligned target for
        # one with no remaining alignment is a drift.
        if previous_overlap >= 2 and proposed_overlap < 2:
            return "dangerous_drift"
        return "ambiguous"

    return "ambiguous"
