"""Wait / stability engine (FR-025~030, SC-009 frame buffer).

Feature 004: consumes `ScreenFrame`s from the shared `FrameCaptureService`
recorder instead of managing its own capture/persistence. A duplicate
(`deduplicated=True`) logical sample deterministically counts as an
unchanged comparison without re-reading any file; only captures issued by
*this* wait's own loop ever touch its local `consecutive_stable`/`prev`
state — foreign-source captures (observation, retry, recovery, post-action
verification, or any other concurrent caller) enter the shared global trace
but never this wait's local decision.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from vnc_agent.domain.observation import Region
from vnc_agent.domain.verification import WaitResult
from vnc_agent.perception.screen_diff import compute_diff_arrays
from vnc_agent.perception.screenshot import FrameCaptureFailedError
from vnc_agent.runtime.exceptions import VNCDisconnectedError

if TYPE_CHECKING:
    from vnc_agent.perception.screenshot import DecodedCapture, FrameCaptureService

EarlyExitFn = Callable[[str], Awaitable[bool]]  # image_path -> should stop


class StabilityEngine:
    def __init__(
        self,
        capture_service: FrameCaptureService,
        *,
        min_delay_ms: int = 300,
        max_delay_ms: int = 20000,
        capture_interval_ms: int = 500,
        stable_frame_count: int = 3,
        pixel_diff_threshold: float = 0.02,
        mask_regions: list[Region] | None = None,
        max_buffer: int = 5,
    ) -> None:
        self.capture_service = capture_service
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self.capture_interval_ms = capture_interval_ms
        self.stable_frame_count = max(2, stable_frame_count)
        self.pixel_diff_threshold = pixel_diff_threshold
        # Dynamic UI regions excluded from stability pixel-diff (not the
        # security mask — that lives on the shared FrameCaptureService).
        self.mask_regions = mask_regions or []
        self._buffer: deque[str] = deque(maxlen=max_buffer)

    async def wait_stable(
        self,
        *,
        step_id: str | None = None,
        roi: Region | None = None,
        early_exit: EarlyExitFn | None = None,
    ) -> WaitResult:
        t0 = time.monotonic()
        await asyncio.sleep(self.min_delay_ms / 1000.0)
        consecutive_stable = 0
        prev_decoded: DecodedCapture | None = None

        while True:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            if elapsed_ms >= self.max_delay_ms:
                return WaitResult(waited_ms=elapsed_ms, stable=False, end_reason="timeout")

            try:
                outcome = await self.capture_service.capture(
                    step_id=step_id, capture_source="stability_wait", roi=roi
                )
            except VNCDisconnectedError:
                return WaitResult(
                    waited_ms=int((time.monotonic() - t0) * 1000),
                    stable=False,
                    end_reason="vnc_error",
                )
            except (FrameCaptureFailedError, Exception):
                return WaitResult(
                    waited_ms=int((time.monotonic() - t0) * 1000),
                    stable=False,
                    end_reason="vnc_error",
                )

            frame = outcome.frame
            self._buffer.append(frame.image_path)

            if early_exit is not None:
                try:
                    if await early_exit(frame.image_path):
                        return WaitResult(
                            waited_ms=int((time.monotonic() - t0) * 1000),
                            stable=True,
                            end_reason="expected_condition",
                        )
                except Exception:
                    pass

            if frame.deduplicated:
                # Exact duplicate of the immediately preceding logical frame
                # (whoever captured it) — deterministically unchanged; never
                # re-read a file to "confirm" this.
                consecutive_stable += 1
            elif prev_decoded is not None:
                changed, _, _ratio, _ = compute_diff_arrays(
                    prev_decoded.pixels,
                    outcome.decoded.pixels,
                    threshold=self.pixel_diff_threshold,
                    mask_regions=self.mask_regions,
                )
                if not changed:
                    consecutive_stable += 1
                else:
                    consecutive_stable = 0
            # else: first sample this wait has itself captured — no local
            # comparison basis yet, consecutive_stable stays at 0.

            if consecutive_stable >= self.stable_frame_count - 1:
                return WaitResult(
                    waited_ms=int((time.monotonic() - t0) * 1000),
                    stable=True,
                    end_reason="stable",
                )

            prev_decoded = outcome.decoded
            await asyncio.sleep(self.capture_interval_ms / 1000.0)

    def buffer_paths(self) -> list[str]:
        return list(self._buffer)
