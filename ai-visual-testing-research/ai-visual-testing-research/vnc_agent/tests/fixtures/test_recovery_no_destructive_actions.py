"""Feature 003 recovery-policy safety tests (T034/T053)."""

import pytest

from vnc_agent.config import (
    AgentConfig,
    AppConfig,
    ModelsConfig,
    RecoveryPolicy,
    VNCTargetsConfig,
)
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.recovery import FailureType
from vnc_agent.execution.target_consistency import evaluate_target_consistency
from vnc_agent.recovery.classifier import Classification
from vnc_agent.recovery.engine import RecoveryEngine
from vnc_agent.recovery.strategies import StrategyContext
from vnc_agent.runtime.step_controller import StepController


def _config(*, allows_action_path_change: bool = False) -> AppConfig:
    policy = RecoveryPolicy(
        max_retries=2,
        cooldown_ms=0,
        consumes_global_retry_budget=True,
        allows_action_path_change=allows_action_path_change,
        requires_strong_model=False,
        requires_human_confirmation=False,
    )
    return AppConfig(
        agent=AgentConfig(recovery={"target_not_found": policy}),
        models=ModelsConfig(),
        vnc_targets=VNCTargetsConfig(),
        config_dir="config",
    )


@pytest.mark.asyncio
async def test_recovery_consumes_shared_budget_and_stops_when_exhausted() -> None:
    engine = RecoveryEngine(_config())
    controller = StepController(max_retries=1)
    controller.start_iteration()
    first = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND, detail="dangerous_drift"),
        step_controller=controller,
        ctx=StrategyContext(),
    )
    second = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND, detail="ambiguous_fail_safe"),
        step_controller=controller,
        ctx=StrategyContext(),
    )
    assert first.resolved is True
    assert controller.remaining_budget() == 0
    assert second.resolved is False


@pytest.mark.asyncio
async def test_policy_forbids_unconfigured_action_path_change() -> None:
    engine = RecoveryEngine(_config(allows_action_path_change=False))
    engine._step_strategy_index[FailureType.TARGET_NOT_FOUND.value] = 1
    attempt = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND, detail="coordinate_space_rejected"),
        step_controller=StepController(max_retries=2),
        ctx=StrategyContext(),
    )
    assert attempt.strategy == "re_ground"
    assert attempt.resolved is False
    assert engine.need_reground is False


@pytest.mark.asyncio
async def test_ambiguous_high_risk_outcome_routes_through_requires_human_confirmation() -> None:
    """Feature 003 T034 (FR-013/034): a declared micro-action purpose whose
    risk_level exceeds its threshold yields "ambiguous" — this MUST be
    resolvable only via the existing RecoveryPolicy.requires_human_
    confirmation field, not a new independent risk-veto branch."""
    previous = SemanticAction(
        action_id="a",
        intent="do something",
        action_type="click",
        target=TargetDescription(role="button", text="x"),
        action_kind="non_idempotent",
    )
    proposed = SemanticAction(
        action_id="b",
        intent="do something else",
        action_type="click",
        target=TargetDescription(role="button", text="x"),
        action_kind="non_idempotent",
        micro_action_purpose="dismiss_overlay",
        risk_level="high",
    )
    outcome = evaluate_target_consistency(
        "step intent",
        previous,
        proposed,
        micro_action_risk_thresholds={"dismiss_overlay": "medium"},
    )
    assert outcome == "ambiguous"

    # The recovery contract's requires_human_confirmation is the ONLY gate —
    # not satisfied here → MUST stay unresolved, not silently proceed.
    policy = RecoveryPolicy(
        max_retries=1,
        cooldown_ms=0,
        consumes_global_retry_budget=True,
        allows_action_path_change=False,
        requires_strong_model=False,
        requires_human_confirmation=True,
    )
    config = AppConfig(
        agent=AgentConfig(recovery={"target_not_found": policy}),
        models=ModelsConfig(),
        vnc_targets=VNCTargetsConfig(),
        config_dir="config",
    )
    engine = RecoveryEngine(config)

    no_confirmation = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND, detail="ambiguous_fail_safe"),
        step_controller=StepController(max_retries=1),
        ctx=StrategyContext(human_confirmation_granted=False),
    )
    assert no_confirmation.resolved is False

    with_confirmation = await engine.handle(
        Classification(FailureType.TARGET_NOT_FOUND, detail="ambiguous_fail_safe"),
        step_controller=StepController(max_retries=1),
        ctx=StrategyContext(human_confirmation_granted=True),
    )
    assert with_confirmation.resolved is True
