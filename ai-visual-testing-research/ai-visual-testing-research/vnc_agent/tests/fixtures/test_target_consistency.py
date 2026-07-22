"""Feature 003 target-consistency tests (T004/T011, safety issues A/B)."""

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.observation import Region
from vnc_agent.domain.run import ActionIteration
from vnc_agent.execution.repeat_guard import RepeatGuard
from vnc_agent.execution.target_consistency import (
    evaluate_target_consistency,
    has_target_evidence_conflict,
)


def _action(
    *,
    action_id: str,
    text: str,
    role: str | None,
    description: str = "",
    action_type: str = "click",
    micro_action_purpose: str | None = None,
    risk_level: str = "low",
) -> SemanticAction:
    return SemanticAction(
        action_id=action_id,
        intent=f"操作{text}" if text else "微动作",
        action_type=action_type,  # type: ignore[arg-type]
        target=TargetDescription(role=role, text=text, description=description),
        action_kind="non_idempotent",
        micro_action_purpose=micro_action_purpose,  # type: ignore[arg-type]
        risk_level=risk_level,  # type: ignore[arg-type]
    )


# --- T004: has_target_evidence_conflict() (US1, safety issue A) ---


def test_conflict_role_mismatch() -> None:
    previous = _action(action_id="a", text="x", role="button")
    proposed = _action(action_id="a", text="x", role="text")
    assert has_target_evidence_conflict(previous, proposed) is True


def test_conflict_role_case_and_whitespace_normalized_not_a_conflict() -> None:
    previous = _action(action_id="a", text="x", role="Button")
    proposed = _action(action_id="a", text="x", role=" button ")
    assert has_target_evidence_conflict(previous, proposed) is False


def test_missing_role_on_either_side_does_not_trigger_conflict() -> None:
    """Real-incident regression: role going from unset to a known value (Planner
    supplying more information in a later round) MUST NOT itself be treated as a
    role/interactivity conflict — only two *asserted* roles that actually differ
    count."""
    previous = _action(action_id="act-1", text="ジ袋", role=None)
    proposed = _action(action_id="act-1", text="ジ袋", role="button")
    assert has_target_evidence_conflict(previous, proposed) is False


def test_conflict_spatial_iou_below_threshold() -> None:
    previous = _action(action_id="a", text="x", role="button")
    proposed = _action(action_id="a", text="x", role="button")
    prev_region = Region(x1=0, y1=0, x2=100, y2=100)
    prop_region = Region(x1=500, y1=500, x2=600, y2=600)
    assert (
        has_target_evidence_conflict(
            previous,
            proposed,
            previous_resolved_region=prev_region,
            proposed_resolved_region=prop_region,
        )
        is True
    )


def test_no_conflict_when_role_interactivity_and_region_all_consistent() -> None:
    previous = _action(action_id="a", text="x", role="button")
    proposed = _action(action_id="a", text="x reworded", role="button")
    prev_region = Region(x1=0, y1=0, x2=100, y2=100)
    prop_region = Region(x1=5, y1=5, x2=105, y2=105)
    assert (
        has_target_evidence_conflict(
            previous,
            proposed,
            previous_resolved_region=prev_region,
            proposed_resolved_region=prop_region,
        )
        is False
    )


def test_missing_region_does_not_trigger_spatial_conflict() -> None:
    previous = _action(action_id="a", text="x", role="button")
    proposed = _action(action_id="a", text="x", role="button")
    # proposed_resolved_region is None (not yet grounded) -> spatial dimension
    # MUST NOT participate in the conflict decision.
    assert (
        has_target_evidence_conflict(
            previous,
            proposed,
            previous_resolved_region=Region(x1=0, y1=0, x2=10, y2=10),
            proposed_resolved_region=None,
        )
        is False
    )


def test_no_conflict_when_no_keyword_list_is_involved() -> None:
    """has_target_evidence_conflict MUST NOT depend on any business keyword list."""
    previous = _action(action_id="a", text="购物袋", role="button")
    proposed = _action(action_id="a", text="购物袋按钮改写措辞", role="button")
    assert has_target_evidence_conflict(previous, proposed) is False


# --- T011: evaluate_target_consistency() AND semantics (US2, safety issue B) ---


def test_declared_purpose_intent_and_risk_all_satisfied_is_legitimate() -> None:
    previous = _action(action_id="bag", text="レジ袋", role="button")
    proposed = _action(
        action_id="dismiss",
        text="閉じる",
        role="button",
        action_type="click",
        micro_action_purpose="dismiss_overlay",
        risk_level="low",
    )
    assert (
        evaluate_target_consistency("点击レジ袋加入购物车", previous, proposed)
        == "legitimate_micro_action"
    )


def test_declared_purpose_but_risk_exceeds_threshold_is_not_legitimate() -> None:
    previous = _action(action_id="bag", text="レジ袋", role="button")
    proposed = _action(
        action_id="dismiss",
        text="閉じる",
        role="button",
        micro_action_purpose="dismiss_overlay",
        risk_level="high",
    )
    outcome = evaluate_target_consistency("点击レジ袋加入购物车", previous, proposed)
    assert outcome != "legitimate_micro_action"


def test_action_type_change_alone_without_declared_purpose_is_not_automatic_drift() -> None:
    """Safety issue B: an action_type change is a risk SIGNAL, not a verdict."""
    previous = _action(action_id="shared", text="レジ袋", role="button")
    proposed = _action(
        action_id="shared",
        text="レジ袋",
        role="button",
        action_type="type_text",
    )
    outcome = evaluate_target_consistency("点击レジ袋", previous, proposed)
    assert outcome != "dangerous_drift"
    assert outcome == "ambiguous"


def test_button_to_result_row_drift() -> None:
    previous = _action(action_id="bag", text="ジ袋", role="button", description="购物袋按钮")
    proposed = _action(
        action_id="other",
        text="ジ袋",
        role="text",
        description="商品列表中已添加的购物袋商品行",
    )
    assert (
        evaluate_target_consistency("点击购物袋按钮", previous, proposed)
        == "dangerous_drift"
    )
    prior_iteration = ActionIteration(
        iteration_index=0,
        semantic_action=previous,
        action_effect=ActionEffect(
            status="expected_effect",
            evidence=ActionEffectEvidence(),
            reason="changed",
        ),
    )
    decision = RepeatGuard(micro_action_risk_thresholds={}).check(
        "add-bag", "点击购物袋按钮", proposed, prior_iteration
    )
    assert decision.allowed is False
    assert decision.reason == "dangerous_drift"


def test_control_to_unrelated_control_drift() -> None:
    previous = _action(action_id="bag", text="购物袋", role="button")
    proposed = _action(action_id="delete", text="删除", role="button")
    assert (
        evaluate_target_consistency("点击购物袋按钮", previous, proposed)
        == "dangerous_drift"
    )


def test_normal_wording_variation_is_not_dangerous() -> None:
    previous = _action(action_id="old", text="レジ袋", role="button")
    proposed = _action(
        action_id="new",
        text="レジ袋ボタン",
        role="control",
        description="购物袋を追加するボタン",
    )
    assert (
        evaluate_target_consistency("点击レジ袋加入购物车", previous, proposed)
        != "dangerous_drift"
    )


def test_drift_is_blocked_before_action_policy_or_execution() -> None:
    previous = _action(action_id="bag", text="购物袋", role="button")
    proposed = _action(
        action_id="row",
        text="已添加商品行",
        role="list row",
        description="已添加的结果展示行",
    )
    prior_iteration = ActionIteration(
        iteration_index=0,
        semantic_action=previous,
        action_effect=ActionEffect(
            status="expected_effect",
            evidence=ActionEffectEvidence(),
            reason="already changed",
        ),
    )
    decision = RepeatGuard(micro_action_risk_thresholds={}).check(
        "add-bag", "点击购物袋按钮", proposed, prior_iteration
    )
    assert decision.allowed is False
    assert decision.reason == "dangerous_drift"
    assert prior_iteration.executable_action is None


def test_ambiguous_when_signals_insufficient_to_classify() -> None:
    """/speckit-analyze HIGH-finding fix: the '"ambiguous"' branch must be reachable."""
    previous = _action(action_id="a", text="未知目标", role=None)
    proposed = _action(action_id="b", text="也不明确", role=None)
    outcome = evaluate_target_consistency("步骤意图未知", previous, proposed)
    assert outcome == "ambiguous"


def test_ambiguous_outcome_routes_through_repeat_guard_no_effect_or_fail_safe() -> None:
    previous = _action(action_id="a", text="未知目标", role=None)
    proposed = _action(action_id="b", text="也不明确", role=None)

    no_effect_iteration = ActionIteration(
        iteration_index=0,
        semantic_action=previous,
        action_effect=ActionEffect(
            status="no_effect", evidence=ActionEffectEvidence(), reason="no_effect"
        ),
    )
    decision = RepeatGuard(micro_action_risk_thresholds={}).check(
        "step-x", "步骤意图未知", proposed, no_effect_iteration
    )
    assert decision.allowed is True
    assert decision.reason == "no_effect_confirmed"

    pending_iteration = ActionIteration(
        iteration_index=0,
        semantic_action=previous,
        action_effect=ActionEffect(
            status="effect_uncertain",
            evidence=ActionEffectEvidence(),
            reason="pending",
        ),
    )
    decision2 = RepeatGuard(micro_action_risk_thresholds={}).check(
        "step-x", "步骤意图未知", proposed, pending_iteration
    )
    assert decision2.allowed is False
    assert decision2.reason == "ambiguous_fail_safe"
