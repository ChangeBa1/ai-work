"""Wait / stability engine (FR-025~030, SC-009 frame buffer)."""

from __future__ import annotations

import asyncio
import time
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable, Sequence

from vnc_agent.domain.observation import Region
from vnc_agent.domain.verification import WaitResult
from vnc_agent.perception.screen_diff import compute_diff
from vnc_agent.perception import screenshot as shot
from vnc_agent.runtime.exceptions import VNCDisconnectedError

if TYPE_CHECKING:
    from vnc_agent.drivers.base import VNCDriver

EarlyExitFn = Callable[[str], Awaitable[bool]]  # image_path -> should stop


class StabilityEngine:
    def __init__(
        self,
        driver: VNCDriver,
        *,
        artifacts_dir: str | Path,
        min_delay_ms: int = 300,
        max_delay_ms: int = 20000,
        capture_interval_ms: int = 500,
        stable_frame_count: int = 3,
        pixel_diff_threshold: float = 0.02,
        mask_regions: list[Region] | None = None,
        security_mask_regions: Sequence[Sequence[int]] | None = None,
        max_buffer: int = 5,
    ) -> None:
        self.driver = driver
        self.artifacts_dir = Path(artifacts_dir)
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self.capture_interval_ms = capture_interval_ms
        self.stable_frame_count = max(2, stable_frame_count)
        self.pixel_diff_threshold = pixel_diff_threshold
        # Dynamic UI regions excluded from stability pixel-diff
        self.mask_regions = mask_regions or []
        # FR-049 sensitive regions applied to local frames/ persistence
        self.security_mask_regions = list(security_mask_regions) if security_mask_regions else []
        self._buffer: deque[str] = deque(maxlen=max_buffer)

    async def wait_stable(
        self,
        *,
        run_id: str,
        step_id: str | None = None,
        roi: Region | None = None,
        early_exit: EarlyExitFn | None = None,
    ) -> WaitResult:
        t0 = time.monotonic()
        await asyncio.sleep(self.min_delay_ms / 1000.0)
        consecutive_stable = 0
        prev_path: str | None = None

        while True:
            elapsed_ms = int((time.monotonic() - t0) * 1000)
            if elapsed_ms >= self.max_delay_ms:
                return WaitResult(
                    waited_ms=elapsed_ms, stable=False, end_reason="timeout"
                )

            try:
                sec = self.security_mask_regions or None
                if roi is not None:
                    frame = await shot.capture_region(
                        self.driver,
                        x=roi.x1,
                        y=roi.y1,
                        w=roi.x2 - roi.x1,
                        h=roi.y2 - roi.y1,
                        run_id=run_id,
                        step_id=step_id,
                        artifacts_dir=self.artifacts_dir,
                        mask_regions=sec,
                    )
                else:
                    frame = await shot.capture_full_screen(
                        self.driver,
                        run_id=run_id,
                        step_id=step_id,
                        artifacts_dir=self.artifacts_dir,
                        mask_regions=sec,
                    )
            except VNCDisconnectedError:
                return WaitResult(
                    waited_ms=int((time.monotonic() - t0) * 1000),
                    stable=False,
                    end_reason="vnc_error",
                )
            except Exception:
                return WaitResult(
                    waited_ms=int((time.monotonic() - t0) * 1000),
                    stable=False,
                    end_reason="vnc_error",
                )

            path = frame.image_path
            self._buffer.append(path)

            if early_exit is not None:
                try:
                    if await early_exit(path):
                        return WaitResult(
                            waited_ms=int((time.monotonic() - t0) * 1000),
                            stable=True,
                            end_reason="expected_condition",
                        )
                except Exception:
                    pass

            if prev_path is not None:
                changed, _, ratio, _ = compute_diff(
                    prev_path,
                    path,
                    threshold=self.pixel_diff_threshold,
                    mask_regions=self.mask_regions,
                )
                if not changed:
                    consecutive_stable += 1
                else:
                    consecutive_stable = 0
                # Need stable_frame_count frames → (count-1) consecutive stable diffs
                if consecutive_stable >= self.stable_frame_count - 1:
                    return WaitResult(
                        waited_ms=int((time.monotonic() - t0) * 1000),
                        stable=True,
                        end_reason="stable",
                    )

            prev_path = path
            await asyncio.sleep(self.capture_interval_ms / 1000.0)

    def buffer_paths(self) -> list[str]:
        return list(self._buffer)
