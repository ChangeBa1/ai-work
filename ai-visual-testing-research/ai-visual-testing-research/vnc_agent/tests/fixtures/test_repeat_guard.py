"""US2 T021: RepeatGuard.check branches including no_effect_confirmed."""

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.repeat_guard import RepeatGuardDecision
from vnc_agent.domain.run import ActionIteration
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.execution.repeat_guard import RepeatGuard


def _action(
    *,
    intent: str = "点击レジ袋加入购物袋",
    kind: str | None = "non_idempotent",
    text: str = "レジ袋",
) -> SemanticAction:
    return SemanticAction(
        action_id="add-bag",
        intent=intent,
        action_type="click",
        target=TargetDescription(text=text),
        action_kind=kind,  # type: ignore[arg-type]
    )


def _prev(
    *,
    ae_status: str,
    vr_status: str = "uncertain",
    action: SemanticAction | None = None,
) -> ActionIteration:
    return ActionIteration(
        iteration_index=0,
        semantic_action=action or _action(),
        action_effect=ActionEffect(
            status=ae_status,  # type: ignore[arg-type]
            evidence=ActionEffectEvidence(),
            reason="test",
        ),
        verification_result=VerificationResult(status=vr_status, reason="test"),  # type: ignore[arg-type]
    )


def test_first_iteration_always_allowed():
    g = RepeatGuard()
    d = g.check(_action(), None)
    assert d.allowed is True
    assert d.reason == "first_attempt"


def test_blocked_after_expected_effect_uncertain():
    g = RepeatGuard()
    d = g.check(_action(), _prev(ae_status="expected_effect", vr_status="uncertain"))
    assert d.allowed is False
    assert d.reason == "blocked_effect_pending"


def test_effect_uncertain_escalates_blocked():
    """Scenario 3 / quickstart: effect_uncertain + uncertain → blocked_uncertain."""
    g = RepeatGuard()
    d = g.check(_action(), _prev(ae_status="effect_uncertain", vr_status="uncertain"))
    assert d.allowed is False
    assert d.reason == "blocked_uncertain"


def test_idempotent_never_blocked():
    g = RepeatGuard()
    d = g.check(
        _action(kind="idempotent", intent="refresh view"),
        _prev(
            ae_status="expected_effect",
            action=_action(kind="idempotent", intent="refresh view"),
        ),
    )
    assert d.allowed is True
    assert d.reason == "idempotent_action"


def test_different_target_never_blocked():
    g = RepeatGuard()
    d = g.check(
        _action(intent="click checkout", text="会計"),
        _prev(ae_status="expected_effect", action=_action()),
    )
    assert d.allowed is True
    assert d.reason == "different_action"


def test_no_effect_confirmed():
    """F2 / FR-016 positive branch: no_effect after strengthened verification → allow."""
    g = RepeatGuard()
    d = g.check(_action(), _prev(ae_status="no_effect", vr_status="uncertain"))
    assert d.allowed is True
    assert d.reason == "no_effect_confirmed"
    assert d.previous_action_effect_status == "no_effect"
