"""Feature 005: KeyboardExecutor.press_key_repeat() — happy path (T006) and
fail-fast partial-failure behavior (T016)."""

from unittest.mock import AsyncMock, patch

import pytest

from vnc_agent.execution.keyboard_executor import KeyboardExecutor
from vnc_agent.runtime.exceptions import KeyRepeatSendError


def _executor() -> tuple[KeyboardExecutor, AsyncMock]:
    driver = AsyncMock()
    return KeyboardExecutor(driver), driver


# --- Happy path (T006) ----------------------------------------------------


@pytest.mark.asyncio
async def test_press_key_repeat_sends_key_exact_count_times():
    executor, driver = _executor()
    result = await executor.press_key_repeat("backspace", 5, 50)
    assert driver.send_key.await_count == 5
    for call in driver.send_key.await_args_list:
        assert call.args == ("backspace",)
    assert result == 5


@pytest.mark.asyncio
async def test_press_key_repeat_each_send_is_a_single_call():
    executor, driver = _executor()
    await executor.press_key_repeat("delete", 3, 10)
    # A discrete press-and-release per send — never a separate "down"/"up"
    # pair — is inherently satisfied since KeyboardExecutor only ever calls
    # driver.send_key(), never any key-down/key-up primitive (the VNCDriver
    # Protocol doesn't even expose one). Assert no other driver method was
    # touched during the batch.
    driver.send_hotkey.assert_not_awaited()
    driver.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_press_key_repeat_sleeps_between_sends_not_after_last():
    executor, driver = _executor()
    with patch("vnc_agent.execution.keyboard_executor.asyncio.sleep", new=AsyncMock()) as sleep:
        await executor.press_key_repeat("backspace", 5, 50)
    assert sleep.await_count == 4  # count - 1
    for call in sleep.await_args_list:
        assert call.args == (0.05,)


@pytest.mark.asyncio
async def test_press_key_repeat_single_count_no_sleep():
    executor, driver = _executor()
    with patch("vnc_agent.execution.keyboard_executor.asyncio.sleep", new=AsyncMock()) as sleep:
        result = await executor.press_key_repeat("backspace", 1, 50)
    assert driver.send_key.await_count == 1
    sleep.assert_not_awaited()
    assert result == 1


# --- Fail-fast partial failure (T016) --------------------------------------


@pytest.mark.asyncio
async def test_press_key_repeat_fails_fast_stops_and_reports_completed_count():
    executor, driver = _executor()
    calls = {"n": 0}

    async def flaky_send_key(key: str) -> None:
        calls["n"] += 1
        if calls["n"] == 8:
            raise RuntimeError("simulated VNC send failure")

    driver.send_key = AsyncMock(side_effect=flaky_send_key)

    with pytest.raises(KeyRepeatSendError) as exc_info:
        await executor.press_key_repeat("backspace", 20, 10)

    err = exc_info.value
    assert err.key == "backspace"
    assert err.requested_count == 20
    assert err.completed_count == 7
    assert isinstance(err.cause, RuntimeError)
    # Fail-fast: no further sends attempted after the failure.
    assert driver.send_key.await_count == 8


@pytest.mark.asyncio
async def test_press_key_repeat_fails_on_first_send_reports_zero_completed():
    executor, driver = _executor()
    driver.send_key = AsyncMock(side_effect=RuntimeError("boom"))

    with pytest.raises(KeyRepeatSendError) as exc_info:
        await executor.press_key_repeat("backspace", 20, 10)

    err = exc_info.value
    assert err.completed_count == 0
    assert err.requested_count == 20
    assert driver.send_key.await_count == 1
