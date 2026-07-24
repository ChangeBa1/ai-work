"""Feature 006: ExecutionRouter error propagation for type_text driver failures."""

from unittest.mock import AsyncMock

import pytest

from vnc_agent.domain.action import ExecutableAction
from vnc_agent.execution.router import ExecutionRouter


def _router() -> ExecutionRouter:
    return ExecutionRouter(AsyncMock())


@pytest.mark.asyncio
async def test_type_text_driver_failure_reports_failure_with_diagnosable_message():
    router = _router()
    router.driver.send_text = AsyncMock(side_effect=RuntimeError("driver keyPress failed"))
    action = ExecutableAction(method="keyboard", operation="type_text", text="45127366")

    result = await router.execute(action)

    assert result.success is False
    assert result.error_code == "error"
    assert "driver keyPress failed" in result.error_message


@pytest.mark.asyncio
async def test_type_text_success_reports_success():
    router = _router()
    router.driver.send_text = AsyncMock(return_value=None)
    action = ExecutableAction(method="keyboard", operation="type_text", text="45127366")

    result = await router.execute(action)

    assert result.success is True
    router.driver.send_text.assert_awaited_once_with("45127366")
