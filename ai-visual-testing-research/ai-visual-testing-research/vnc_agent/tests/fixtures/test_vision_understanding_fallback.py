"""US2: vision fallback when OCR/template insufficient."""

from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.models.provider import VisionUnderstandingResponse
from vnc_agent.perception.pipeline import ObservationPipeline


class FakeDriver:
    def __init__(self, img):
        self._img = img
        self._w, self._h = img.shape[1], img.shape[0]

    @property
    def resolution(self):
        return (self._w, self._h)

    async def capture_screen(self):
        ok, buf = cv2.imencode(".png", self._img)
        return buf.tobytes()

    async def capture_region(self, x, y, w, h):
        return await self.capture_screen()


@pytest.mark.asyncio
async def test_vision_fallback(tmp_path: Path):
    planner = StubPlanner(
        describe=VisionUnderstandingResponse(
            mode="describe",
            description="blank desktop",
            confidence=0.7,
            model_name="stub",
        )
    )
    img = np.zeros((80, 80, 3), dtype=np.uint8)
    pipe = ObservationPipeline(
        FakeDriver(img),
        artifacts_dir=tmp_path,
        planner=planner,
        ocr_enabled=False,
        template_enabled=False,
        vision_fallback=True,
    )
    screen = await pipe.observe(run_id="r", step_id="s")
    assert screen.vision_understanding is not None
    assert screen.vision_understanding.description == "blank desktop"
    assert planner.describe_calls == 1
