"""US2 T021: RepeatGuard.check branches including no_effect_confirmed."""

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.run import ActionIteration
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.execution.repeat_guard import RepeatGuard


def _action(
    *,
    intent: str = "点击レジ袋加入购物袋",
    kind: str | None = "non_idempotent",
    text: str = "レジ袋",
    action_id: str = "add-bag",
    role: str | None = None,
    description: str = "",
) -> SemanticAction:
    return SemanticAction(
        action_id=action_id,
        intent=intent,
        action_type="click",
        target=TargetDescription(text=text, role=role, description=description),
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
    d = g.check("add-bag", "点击レジ袋", _action(), None)
    assert d.allowed is True
    assert d.reason == "first_attempt"


def test_blocked_after_expected_effect_uncertain():
    g = RepeatGuard()
    d = g.check(
        "add-bag",
        "点击レジ袋",
        _action(),
        _prev(ae_status="expected_effect", vr_status="uncertain"),
    )
    assert d.allowed is False
    assert d.reason == "blocked_effect_pending"


def test_effect_uncertain_escalates_blocked():
    """Scenario 3 / quickstart: effect_uncertain + uncertain → blocked_uncertain."""
    g = RepeatGuard()
    d = g.check(
        "add-bag",
        "点击レジ袋",
        _action(),
        _prev(ae_status="effect_uncertain", vr_status="uncertain"),
    )
    assert d.allowed is False
    assert d.reason == "blocked_uncertain"


def test_idempotent_never_blocked():
    g = RepeatGuard()
    d = g.check(
        "refresh",
        "refresh view",
        _action(kind="idempotent", intent="refresh view"),
        _prev(
            ae_status="expected_effect",
            action=_action(kind="idempotent", intent="refresh view"),
        ),
    )
    assert d.allowed is True
    assert d.reason == "idempotent_action"


def test_ambiguous_target_fails_safe():
    g = RepeatGuard()
    d = g.check(
        "add-bag",
        "点击レジ袋",
        _action(intent="处理界面", text="未知", action_id="other"),
        _prev(ae_status="expected_effect", action=_action()),
    )
    assert d.allowed is False
    assert d.reason == "ambiguous_fail_safe"


def test_no_effect_confirmed():
    """F2 / FR-016 positive branch: no_effect after strengthened verification → allow."""
    g = RepeatGuard()
    d = g.check(
        "add-bag",
        "点击レジ袋",
        _action(),
        _prev(ae_status="no_effect", vr_status="uncertain"),
    )
    assert d.allowed is True
    assert d.reason == "no_effect_confirmed"
    assert d.previous_action_effect_status == "no_effect"


def test_real_incident_replay_blocks_reworded_retries() -> None:
    actions = [
        _action(
            action_id="act-1",
            intent="点击购物袋按钮",
            text="ジ袋",
            description="购物袋按钮，用于将购物袋商品加入购物车",
        ),
        _action(
            action_id="act-1",
            intent='点击"ジ袋"（购物袋）按钮，将一个购物袋商品加入购物车',
            text="ジ袋",
            role="button",
            description="购物袋按钮，用于添加一个购物袋商品到购物车",
        ),
        _action(
            action_id="act-1",
            intent="点击购物袋（レジ袋）商品行，将其加入购物车",
            text="ジ袋",
            description="点击OCR文字为'ジ袋'的区域，该区域位于商品列表中，表示一个购物袋商品行",
        ),
    ]
    guard = RepeatGuard()
    previous = _prev(ae_status="expected_effect", action=actions[0])

    for proposed in actions[1:]:
        decision = guard.check("add-shopping-bag", "点击レジ袋加入购物车", proposed, previous)
        assert decision.allowed is False
        assert decision.reason == "blocked_effect_pending"


def test_normalized_target_match_has_distinct_audit_reason() -> None:
    previous_action = _action(action_id="", text="レジ袋")
    proposed = _action(action_id="new", text="ジ袋")
    decision = RepeatGuard().check(
        "add-bag",
        "点击レジ袋",
        proposed,
        _prev(ae_status="effect_uncertain", action=previous_action),
    )
    assert decision.allowed is False
    assert decision.reason == "blocked_uncertain_normalized_target"
