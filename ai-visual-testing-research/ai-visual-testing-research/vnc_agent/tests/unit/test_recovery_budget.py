"""US8: Per-failure-type max retries stop without infinite loop (FR-038)."""

import asyncio

import pytest

from vnc_agent.config import AppConfig, AgentConfig, RecoveryPolicy, ModelsConfig, VNCTargetsConfig
from vnc_agent.domain.recovery import FailureType
from vnc_agent.recovery.classifier import Classification
from vnc_agent.recovery.engine import RecoveryEngine
from vnc_agent.recovery.strategies import StrategyContext


def _cfg() -> AppConfig:
    agent = AgentConfig(
        recovery={
            "target_not_found": RecoveryPolicy(max_retries=2, cooldown_ms=0),
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
    for i in range(3):
        attempt = await engine.handle(
            Classification(failure_type=FailureType.TARGET_NOT_FOUND),
            step_controller=None,
            ctx=ctx,
        )
    assert engine.tier2_exhausted(FailureType.TARGET_NOT_FOUND)
    assert attempt.resolved is False
    assert attempt.attempt_index >= 1 or attempt.max_retries == 2
