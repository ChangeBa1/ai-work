"""US2: screenshot metadata / crop offset (mock driver)."""

import asyncio
from pathlib import Path

import pytest

from vnc_agent.perception.screenshot import capture_full_screen, capture_region


class FakeDriver:
    def __init__(self):
        import cv2
        import numpy as np

        self._img = np.zeros((120, 200, 3), dtype=np.uint8)
        self._img[10:50, 10:80] = (0, 255, 0)
        self._width, self._height = 200, 120

    @property
    def resolution(self):
        return (self._width, self._height)

    async def capture_screen(self) -> bytes:
        import cv2

        ok, buf = cv2.imencode(".png", self._img)
        return buf.tobytes()

    async def capture_region(self, x, y, w, h) -> bytes:
        import cv2

        crop = self._img[y : y + h, x : x + w]
        ok, buf = cv2.imencode(".png", crop)
        return buf.tobytes()


@pytest.mark.asyncio
async def test_full_screen_persists(tmp_path: Path):
    d = FakeDriver()
    frame = await capture_full_screen(
        d, run_id="r", step_id="s", artifacts_dir=tmp_path
    )
    assert Path(frame.image_path).exists()
    assert frame.width == 200
    assert frame.height == 120
    assert frame.crop_offset == (0, 0)


@pytest.mark.asyncio
async def test_region_offset(tmp_path: Path):
    d = FakeDriver()
    frame = await capture_region(
        d, x=10, y=10, w=70, h=40, run_id="r", step_id="s", artifacts_dir=tmp_path
    )
    assert frame.crop_offset == (10, 10)
    assert Path(frame.image_path).exists()
