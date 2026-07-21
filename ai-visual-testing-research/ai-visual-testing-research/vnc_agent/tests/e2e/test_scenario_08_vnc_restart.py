"""E2E scenario 8: restart_step strategy recorded on disconnect recovery."""

from pathlib import Path

import pytest

from vnc_agent.domain.recovery import FailureType
from vnc_agent.recovery.classifier import Classification
from vnc_agent.recovery.engine import RecoveryEngine
from vnc_agent.recovery.strategies import StrategyContext
from vnc_agent.runtime.step_controller import StepController
from tests.e2e.conftest import FakeVNC


@pytest.mark.asyncio
async def test_restart_step_consumes_tier1(app_config):
    engine = RecoveryEngine(app_config)
    controller = StepController(max_retries=2)
    # consume first free iteration index advance
    controller.start_iteration()
    drv = FakeVNC()
    await drv.connect()
    attempt = await engine.handle(
        Classification(failure_type=FailureType.VNC_DISCONNECTED),
        step_controller=controller,
        ctx=StrategyContext(driver=drv),
    )
    assert attempt.strategy == "restart_step"
    assert attempt.resolved is True
    assert engine.need_restart_step is True


@pytest.mark.asyncio
async def test_no_restart_when_budget_zero(app_config):
    engine = RecoveryEngine(app_config)
    controller = StepController(max_retries=0)
    controller.start_iteration()
    controller.mark_exhausted()
    attempt = await engine.handle(
        Classification(failure_type=FailureType.VNC_DISCONNECTED),
        step_controller=controller,
        ctx=StrategyContext(driver=FakeVNC()),
    )
    assert attempt.resolved is False
