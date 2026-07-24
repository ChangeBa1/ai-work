"""Feature 005: ExecutionRouter press_key_repeat dispatch/result population
(T007 success case + timeout helper, T017 partial-failure case, T026
end-to-end timeout-path coverage)."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from vnc_agent.domain.action import ExecutableAction
from vnc_agent.execution.router import ExecutionRouter, compute_batch_repeat_timeout_seconds
from vnc_agent.runtime.exceptions import KeyRepeatSendError


def _router() -> ExecutionRouter:
    return ExecutionRouter(AsyncMock())


# --- Success case (T007) ---------------------------------------------------


@pytest.mark.asyncio
async def test_execute_press_key_repeat_success_populates_counts():
    router = _router()
    action = ExecutableAction(
        method="keyboard",
        operation="press_key_repeat",
        keys=["backspace"],
        repeat_count=20,
        repeat_interval_ms=50,
    )
    with patch.object(
        router.keyboard, "press_key_repeat", new=AsyncMock(return_value=20)
    ) as mocked:
        result = await router.execute(action)
    mocked.assert_awaited_once_with("backspace", 20, 50)
    assert result.success is True
    assert result.requested_count == 20
    assert result.completed_count == 20


@pytest.mark.asyncio
async def test_execute_press_key_leaves_counts_none():
    router = _router()
    action = ExecutableAction(method="keyboard", operation="press_key", keys=["escape"])
    with patch.object(router.keyboard, "press_key", new=AsyncMock()):
        result = await router.execute(action)
    assert result.requested_count is None
    assert result.completed_count is None


# --- compute_batch_repeat_timeout_seconds() (T007, remediation for F1) ----


def test_compute_batch_repeat_timeout_small_batch_uses_default():
    value = compute_batch_repeat_timeout_seconds(
        repeat_count=5, repeat_interval_ms=50, default_timeout_seconds=10.0
    )
    assert value == 10.0


def test_compute_batch_repeat_timeout_large_batch_scales_up():
    # (50 - 1) * 0.5 = 24.5s, both bounds individually legal per FR-006/FR-007.
    value = compute_batch_repeat_timeout_seconds(
        repeat_count=50, repeat_interval_ms=500, default_timeout_seconds=10.0
    )
    assert value >= 24.5 + 5.0
    assert value > 10.0


def test_compute_batch_repeat_timeout_never_below_default():
    value = compute_batch_repeat_timeout_seconds(
        repeat_count=1, repeat_interval_ms=0, default_timeout_seconds=10.0
    )
    assert value >= 10.0


# --- Partial failure (T017) -------------------------------------------------


@pytest.mark.asyncio
async def test_execute_press_key_repeat_partial_failure_populates_result():
    router = _router()
    action = ExecutableAction(
        method="keyboard",
        operation="press_key_repeat",
        keys=["backspace"],
        repeat_count=20,
        repeat_interval_ms=50,
    )
    err = KeyRepeatSendError(
        key="backspace", requested_count=20, completed_count=7, cause=RuntimeError("boom")
    )
    with patch.object(
        router.keyboard, "press_key_repeat", new=AsyncMock(side_effect=err)
    ):
        result = await router.execute(action)
    assert result.success is False
    assert result.requested_count == 20
    assert result.completed_count == 7
    assert result.error_code == "key_repeat_partial"
    assert result.error_message
    assert "backspace" in result.error_message or "boom" in result.error_message


# --- End-to-end timeout path through execute() (T026, converge finding F1) -
#
# Unlike the compute_batch_repeat_timeout_seconds() tests above (pure
# function, no ExecutionRouter involved), these exercise the actual
# asyncio.wait_for/except asyncio.TimeoutError path inside execute() for a
# press_key_repeat action, proving (a) the dynamic-timeout wiring genuinely
# prevents a timeout for the legal worst-case batch that the router's own
# static default would NOT have survived, and (b) a genuine hang past even
# the dynamically computed timeout still produces a sane, documented
# ExecutionResult.


@pytest.mark.asyncio
async def test_execute_press_key_repeat_static_default_times_out_for_slow_batch():
    # A small "static default" (analogous to the real 10s default in
    # config/agent.yaml) that a slower-than-expected batch send exceeds —
    # this is the failure mode F1 fixed by sizing the timeout dynamically.
    router = ExecutionRouter(AsyncMock(), default_timeout_seconds=0.05)
    action = ExecutableAction(
        method="keyboard",
        operation="press_key_repeat",
        keys=["backspace"],
        repeat_count=50,
        repeat_interval_ms=500,
    )

    async def slow_press_key_repeat(key, count, interval_ms):
        await asyncio.sleep(0.15)
        return count

    with patch.object(
        router.keyboard, "press_key_repeat", new=AsyncMock(side_effect=slow_press_key_repeat)
    ):
        result = await router.execute(action)  # no override -> uses the 0.05s default

    assert result.success is False
    assert result.timed_out is True
    assert result.error_code == "timeout"


@pytest.mark.asyncio
async def test_execute_press_key_repeat_dynamic_timeout_prevents_worst_case_timeout():
    # Same router (tiny 0.05s default) and same slow send as above, but this
    # time execute() is called the way agent_runtime.py actually calls it for
    # press_key_repeat: with timeout_seconds computed from the action's own
    # repeat_count/repeat_interval_ms. The legal worst case (count=50,
    # interval_ms=500) must not time out.
    router = ExecutionRouter(AsyncMock(), default_timeout_seconds=0.05)
    action = ExecutableAction(
        method="keyboard",
        operation="press_key_repeat",
        keys=["backspace"],
        repeat_count=50,
        repeat_interval_ms=500,
    )

    async def slow_press_key_repeat(key, count, interval_ms):
        await asyncio.sleep(0.15)
        return count

    computed_timeout = compute_batch_repeat_timeout_seconds(
        repeat_count=action.repeat_count,
        repeat_interval_ms=action.repeat_interval_ms,
        default_timeout_seconds=router.default_timeout_seconds,
    )
    with patch.object(
        router.keyboard, "press_key_repeat", new=AsyncMock(side_effect=slow_press_key_repeat)
    ):
        result = await router.execute(action, timeout_seconds=computed_timeout)

    assert result.success is True
    assert result.timed_out is False
    assert result.requested_count == 50
    assert result.completed_count == 50


@pytest.mark.asyncio
async def test_execute_press_key_repeat_genuine_timeout_reports_no_counts():
    # A hang that exceeds even the (explicitly small, here) sized timeout —
    # documents and verifies the current, accepted behavior: the generic
    # asyncio.TimeoutError path does not preserve partial-progress counts
    # (unlike the KeyRepeatSendError/fail-fast path, which does).
    router = ExecutionRouter(AsyncMock(), default_timeout_seconds=10.0)
    action = ExecutableAction(
        method="keyboard",
        operation="press_key_repeat",
        keys=["backspace"],
        repeat_count=50,
        repeat_interval_ms=500,
    )

    async def hanging_press_key_repeat(key, count, interval_ms):
        await asyncio.sleep(0.2)
        return count

    with patch.object(
        router.keyboard, "press_key_repeat", new=AsyncMock(side_effect=hanging_press_key_repeat)
    ):
        result = await router.execute(action, timeout_seconds=0.05)

    assert result.success is False
    assert result.timed_out is True
    assert result.error_code == "timeout"
    assert result.requested_count is None
    assert result.completed_count is None
