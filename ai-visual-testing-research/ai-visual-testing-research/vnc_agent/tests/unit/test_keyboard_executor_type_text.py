"""Feature 006: KeyboardExecutor.type_text() pass-through contract."""

from unittest.mock import AsyncMock

import pytest

from vnc_agent.execution.keyboard_executor import KeyboardExecutor


def _executor() -> tuple[KeyboardExecutor, AsyncMock]:
    driver = AsyncMock()
    return KeyboardExecutor(driver), driver


@pytest.mark.asyncio
async def test_type_text_empty_string_calls_driver_once_and_does_not_raise():
    executor, driver = _executor()

    await executor.type_text("")

    driver.send_text.assert_awaited_once_with("")


@pytest.mark.asyncio
async def test_type_text_propagates_driver_exception_unmodified():
    executor, driver = _executor()
    driver.send_text = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(RuntimeError, match="boom"):
        await executor.type_text("x")
