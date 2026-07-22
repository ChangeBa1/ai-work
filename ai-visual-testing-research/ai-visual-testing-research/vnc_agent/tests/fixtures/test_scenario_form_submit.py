"""Feature 003 T040 — generic scenario 1 (research.md §13): form submission.

Proves, independent of any POS content, that a non-idempotent submit action
retried with reworded intent/description is still recognized as the same
logical action and not duplicated (FR-002/003/009/010, SC-001)."""

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.run import ActionIteration
from vnc_agent.execution.repeat_guard import RepeatGuard


def _submit(*, intent: str, description: str, role: str = "button") -> SemanticAction:
    return SemanticAction(
        action_id="submit-settings",
        intent=intent,
        action_type="click",
        target=TargetDescription(role=role, text="Save", description=description),
        action_kind="non_idempotent",
    )


def test_submit_reworded_across_iterations_is_not_duplicated() -> None:
    guard = RepeatGuard(micro_action_risk_thresholds={})
    first = _submit(intent="Click save button", description="Save the settings form")
    first_iteration = ActionIteration(
        iteration_index=0,
        semantic_action=first,
        action_effect=ActionEffect(
            status="expected_effect",
            evidence=ActionEffectEvidence(),
            reason="form saved",
        ),
    )

    reworded_attempts = [
        _submit(
            intent="Press the Save button to confirm settings",
            description="Confirms and persists the settings form",
        ),
        _submit(
            intent="Submit the settings form by clicking Save",
            description="Persist the current form state",
        ),
    ]

    for proposed in reworded_attempts:
        decision = guard.check(
            "settings-step", "save the settings form", proposed, first_iteration
        )
        assert decision.allowed is False, (
            "reworded retry of the same non-idempotent submit action MUST be "
            "recognized as the same logical action and blocked"
        )


def test_submit_action_executes_exactly_once_end_to_end() -> None:
    """Simulates the full retry loop: only the first attempt is ever sent."""
    guard = RepeatGuard(micro_action_risk_thresholds={})
    sent_count = 0
    previous_iteration = None

    wordings = [
        ("Click save button", "Save the settings form"),
        ("Press the Save button to confirm settings", "Confirms and persists the form"),
        ("Submit the settings form by clicking Save", "Persist the current form state"),
    ]

    for intent, description in wordings:
        action = _submit(intent=intent, description=description)
        decision = guard.check(
            "settings-step", "save the settings form", action, previous_iteration
        )
        if decision.allowed:
            sent_count += 1
        iteration = ActionIteration(
            iteration_index=sent_count,
            semantic_action=action,
            action_effect=ActionEffect(
                status="expected_effect",
                evidence=ActionEffectEvidence(),
                reason="form saved",
            )
            if decision.allowed
            else None,
        )
        if previous_iteration is None:
            previous_iteration = iteration
        # else: keep previous_iteration pointing at the first (allowed) attempt,
        # matching RepeatGuard's within-step "previous non-idempotent action"
        # semantics — a blocked attempt does not become the new baseline.

    assert sent_count == 1
