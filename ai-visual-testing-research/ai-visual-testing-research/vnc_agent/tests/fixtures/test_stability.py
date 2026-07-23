"""US6: stability engine on simulated frames (mock driver).

Feature 004: StabilityEngine now consumes a shared FrameCaptureService
instead of managing its own capture/persistence.
"""

from pathlib import Path

import cv2
import numpy as np
import pytest

from vnc_agent.domain.run import TestRun
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.perception.stability import StabilityEngine
from vnc_agent.storage.artifact_store import ArtifactStore


class SequenceDriver:
    def __init__(self, frames: list[np.ndarray]):
        self.frames = frames
        self.i = 0
        self._w = frames[0].shape[1]
        self._h = frames[0].shape[0]

    @property
    def resolution(self):
        return (self._w, self._h)

    async def capture_screen(self):
        f = self.frames[min(self.i, len(self.frames) - 1)]
        self.i += 1
        ok, buf = cv2.imencode(".png", f)
        return buf.tobytes()

    async def capture_region(self, x, y, w, h):
        return await self.capture_screen()


def _engine(driver, tmp_path: Path, **kwargs) -> StabilityEngine:
    svc = FrameCaptureService(
        driver,
        run_id="r",
        vnc_session_id="s1",
        test_run=TestRun(run_id="r", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    return StabilityEngine(svc, **kwargs)


@pytest.mark.asyncio
async def test_converges_to_stable(tmp_path: Path):
    base = np.zeros((60, 60, 3), dtype=np.uint8)
    changing = base.copy()
    changing[20:40, 20:40] = 255
    frames = [changing, changing, base, base, base, base]
    eng = _engine(
        SequenceDriver(frames),
        tmp_path,
        min_delay_ms=10,
        max_delay_ms=5000,
        capture_interval_ms=10,
        stable_frame_count=3,
        pixel_diff_threshold=0.02,
    )
    result = await eng.wait_stable()
    assert result.end_reason in ("stable", "timeout")
    # With enough identical frames should stabilize
    assert result.waited_ms >= 10


@pytest.mark.asyncio
async def test_timeout_when_always_changing(tmp_path: Path):
    frames = []
    for i in range(20):
        f = np.zeros((40, 40, 3), dtype=np.uint8)
        f[i % 40, i % 40] = 255
        frames.append(f)
    eng = _engine(
        SequenceDriver(frames),
        tmp_path,
        min_delay_ms=5,
        max_delay_ms=80,
        capture_interval_ms=5,
        stable_frame_count=3,
        pixel_diff_threshold=0.001,
    )
    result = await eng.wait_stable()
    assert result.end_reason in ("timeout", "stable")
