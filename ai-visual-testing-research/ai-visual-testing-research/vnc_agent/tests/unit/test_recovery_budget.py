"""US8: Per-failure-type max retries stop without infinite loop (FR-038)."""


import pytest

from vnc_agent.config import AgentConfig, AppConfig, ModelsConfig, RecoveryPolicy, VNCTargetsConfig
from vnc_agent.domain.recovery import FailureType
from vnc_agent.recovery.classifier import Classification
from vnc_agent.recovery.engine import RecoveryEngine
from vnc_agent.recovery.strategies import StrategyContext


def _cfg() -> AppConfig:
    agent = AgentConfig(
        recovery={
            "target_not_found": RecoveryPolicy(
                max_retries=2,
                cooldown_ms=0,
                consumes_global_retry_budget=True,
                allows_action_path_change=True,
                requires_strong_model=False,
                requires_human_confirmation=False,
            ),
        }
    )
    return AppConfig(
        agent=agent,
        models=ModelsConfig(),
        vnc_targets=VNCTargetsConfig(),
        config_dir="config",
    )


@pytest.mark.asyncio
async def test_tier2_budget_stops():
    engine = RecoveryEngine(_cfg())
    ctx = StrategyContext()
    for _i in range(3):
        attempt = await engine.handle(
            Classification(failure_type=FailureType.TARGET_NOT_FOUND),
            step_controller=None,
            ctx=ctx,
        )
    assert engine.tier2_exhausted(FailureType.TARGET_NOT_FOUND)
    assert attempt.resolved is False
    assert attempt.attempt_index >= 1 or attempt.max_retries == 2
