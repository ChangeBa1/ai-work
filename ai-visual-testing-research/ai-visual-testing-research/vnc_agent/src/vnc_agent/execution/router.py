"""Execution router with per-action timeout and modifier release (FR-021/022/024)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from vnc_agent.domain.action import ExecutableAction, ExecutionResult
from vnc_agent.execution.keyboard_executor import KeyboardExecutor
from vnc_agent.execution.mouse_executor import MouseExecutor
from vnc_agent.runtime.exceptions import ActionTimeoutError, KeyRepeatSendError

if TYPE_CHECKING:
    from vnc_agent.drivers.base import VNCDriver

# Feature 005 remediation (analysis finding F1): a spec-legal worst-case
# batch (repeat_count=50, repeat_interval_ms=500 -> 24.5s) can exceed the
# configured default per-action timeout (10s), which would otherwise drop
# requested_count/completed_count via the generic timeout path below.
BATCH_REPEAT_TIMEOUT_MARGIN_SECONDS = 5.0


def compute_batch_repeat_timeout_seconds(
    repeat_count: int, repeat_interval_ms: int, default_timeout_seconds: float
) -> float:
    """Timeout large enough for a whole press_key_repeat batch; never below
    `default_timeout_seconds`."""
    batch_duration_seconds = (repeat_count - 1) * (repeat_interval_ms / 1000.0)
    return max(
        default_timeout_seconds, batch_duration_seconds + BATCH_REPEAT_TIMEOUT_MARGIN_SECONDS
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionRouter:
    def __init__(
        self,
        driver: VNCDriver,
        *,
        default_timeout_seconds: float = 10.0,
    ) -> None:
        self.driver = driver
        self.default_timeout_seconds = default_timeout_seconds
        self.keyboard = KeyboardExecutor(driver)
        self.mouse = MouseExecutor(driver)

    async def execute(
        self,
        action: ExecutableAction,
        *,
        timeout_seconds: float | None = None,
    ) -> ExecutionResult:
        timeout = timeout_seconds if timeout_seconds is not None else self.default_timeout_seconds
        started = _utcnow()
        click_point = None
        try:
            dispatch_result = await asyncio.wait_for(self._dispatch(action), timeout=timeout)
            ended = _utcnow()
            if action.coordinates:
                click_point = action.coordinates
            requested_count = None
            completed_count = None
            if action.operation == "press_key_repeat":
                requested_count = action.repeat_count
                completed_count = dispatch_result
            return ExecutionResult(
                success=True,
                started_at=started,
                ended_at=ended,
                timed_out=False,
                target_region=action.target_region,
                actual_click_point=click_point,
                requested_count=requested_count,
                completed_count=completed_count,
            )
        except asyncio.TimeoutError:
            await self._safe_release()
            return ExecutionResult(
                success=False,
                started_at=started,
                ended_at=_utcnow(),
                timed_out=True,
                target_region=action.target_region,
                actual_click_point=action.coordinates,
                error_code="timeout",
                error_message=f"action timed out after {timeout}s",
            )
        except KeyRepeatSendError as e:
            await self._safe_release()
            return ExecutionResult(
                success=False,
                started_at=started,
                ended_at=_utcnow(),
                timed_out=False,
                target_region=action.target_region,
                actual_click_point=action.coordinates,
                error_code="key_repeat_partial",
                error_message=str(e),
                requested_count=e.requested_count,
                completed_count=e.completed_count,
            )
        except Exception as e:
            await self._safe_release()
            return ExecutionResult(
                success=False,
                started_at=started,
                ended_at=_utcnow(),
                timed_out=False,
                target_region=action.target_region,
                actual_click_point=action.coordinates,
                error_code="error",
                error_message=str(e),
            )

    async def _dispatch(self, action: ExecutableAction) -> int | None:
        if action.operation == "wait" or action.operation == "finish":
            return None
        if action.method == "keyboard":
            if action.operation == "type_text":
                await self.keyboard.type_text(action.text or "")
            elif action.operation == "hotkey":
                await self.keyboard.hotkey(action.keys)
            elif action.operation == "press_key_repeat":
                return await self.keyboard.press_key_repeat(
                    action.keys[0], action.repeat_count, action.repeat_interval_ms
                )
            else:
                if len(action.keys) > 1:
                    await self.keyboard.hotkey(action.keys)
                elif action.keys:
                    await self.keyboard.press_key(action.keys[0])
            return None

        # mouse
        if action.coordinates is None:
            raise ValueError("mouse action requires coordinates")
        x, y = action.coordinates
        op = action.operation
        if op == "click":
            await self.mouse.click(x, y)
        elif op == "double_click":
            await self.mouse.double_click(x, y)
        elif op == "right_click":
            await self.mouse.right_click(x, y)
        elif op == "scroll":
            await self.mouse.scroll(x, y)
        elif op == "drag":
            # simple drag offset
            await self.mouse.drag(x, y, x + 50, y)
        else:
            await self.mouse.click(x, y)

    async def _safe_release(self) -> None:
        try:
            await self.keyboard.release_modifiers()
        except Exception:
            pass
