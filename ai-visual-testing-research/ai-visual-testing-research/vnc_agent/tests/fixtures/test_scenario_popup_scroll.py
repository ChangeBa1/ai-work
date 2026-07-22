"""Feature 003 T042 — generic scenario 3 (research.md §13): popup dismiss /
scroll legitimate micro-actions.

Proves, independent of any POS content, that a target with a different
action_id serving a declared, independent micro-action purpose (dismissing an
overlay, scrolling to reveal the real target) is NOT misclassified as
dangerous_drift, and is not used to re-execute the still-undetermined primary
non-idempotent action (FR-005/006/012/013, SC-004)."""

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.run import ActionIteration
from vnc_agent.execution.repeat_guard import RepeatGuard
from vnc_agent.execution.target_consistency import evaluate_target_consistency

_RISK_THRESHOLDS = {"dismiss_overlay": "medium", "scroll_reveal": "medium"}


def _primary_action() -> SemanticAction:
    return SemanticAction(
        action_id="confirm-purchase",
        intent="click the confirm button",
        action_type="click",
        target=TargetDescription(role="button", text="Confirm"),
        action_kind="non_idempotent",
    )


def test_dismiss_overlay_is_legitimate_not_drift() -> None:
    dismiss = SemanticAction(
        action_id="close-overlay",
        intent="close the blocking dialog",
        action_type="click",
        target=TargetDescription(role="button", text="X"),
        action_kind="non_idempotent",
        micro_action_purpose="dismiss_overlay",
        risk_level="low",
    )
    outcome = evaluate_target_consistency(
        "click the confirm button",
        _primary_action(),
        dismiss,
        micro_action_risk_thresholds=_RISK_THRESHOLDS,
    )
    assert outcome == "legitimate_micro_action"


def test_scroll_reveal_is_legitimate_not_drift() -> None:
    scroll = SemanticAction(
        action_id="scroll-down",
        intent="scroll down to reveal the confirm button",
        action_type="scroll",
        target=TargetDescription(role="scrollbar"),
        action_kind="non_idempotent",
        micro_action_purpose="scroll_reveal",
        risk_level="medium",
    )
    outcome = evaluate_target_consistency(
        "click the confirm button",
        _primary_action(),
        scroll,
        micro_action_risk_thresholds=_RISK_THRESHOLDS,
    )
    assert outcome == "legitimate_micro_action"


def test_legitimate_micro_action_does_not_replace_the_primary_action() -> None:
    """A legitimate micro-action MUST NOT itself be treated as executing the
    still-undetermined primary non-idempotent action (FR-006)."""
    guard = RepeatGuard(micro_action_risk_thresholds=_RISK_THRESHOLDS)
    previous_iteration = ActionIteration(
        iteration_index=0,
        semantic_action=_primary_action(),
        action_effect=ActionEffect(
            status="effect_uncertain",
            evidence=ActionEffectEvidence(),
            reason="blocked by overlay",
        ),
    )
    dismiss = SemanticAction(
        action_id="close-overlay",
        intent="close the blocking dialog",
        action_type="click",
        target=TargetDescription(role="button", text="X"),
        action_kind="non_idempotent",
        micro_action_purpose="dismiss_overlay",
        risk_level="low",
    )
    decision = guard.check(
        "confirm-step", "click the confirm button", dismiss, previous_iteration
    )
    assert decision.allowed is True
    assert decision.reason == "legitimate_micro_action"
    # The primary action's own business result remains undetermined —
    # allowing the micro-action is not the same as confirming the primary
    # action succeeded (that remains the caller's separate verification step).


def test_action_type_change_without_declared_purpose_is_not_automatically_legitimate() -> None:
    """Edge of the AND semantics: changing action_type alone, with no
    declared purpose, does not earn a free pass either — it falls to
    "ambiguous" (fail-safe), matching safety issue B's requirement that
    action_type change is a signal, not a verdict, in either direction."""
    undeclared = SemanticAction(
        action_id="mystery-scroll",
        intent="do something else",
        action_type="scroll",
        target=TargetDescription(role="button", text="Confirm"),
        action_kind="non_idempotent",
    )
    outcome = evaluate_target_consistency(
        "click the confirm button",
        _primary_action(),
        undeclared,
        micro_action_risk_thresholds=_RISK_THRESHOLDS,
    )
    assert outcome != "dangerous_drift"
    assert outcome == "ambiguous"
