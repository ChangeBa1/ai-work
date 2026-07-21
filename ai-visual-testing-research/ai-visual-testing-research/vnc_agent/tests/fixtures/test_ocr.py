"""US2: OCR engine smoke (may use stub if RapidOCR unavailable)."""

from pathlib import Path

import cv2
import numpy as np

from vnc_agent.perception.ocr import engine as ocr_engine


class FakeOCR:
    def __call__(self, img):
        # Simulate one text box
        box = [[10, 10], [80, 10], [80, 40], [10, 40]]
        return [[box, "Hello", 0.95]], None


def test_ocr_returns_items(tmp_path: Path):
    ocr_engine.set_engine(FakeOCR())
    try:
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        p = tmp_path / "t.png"
        cv2.imwrite(str(p), img)
        items = ocr_engine.run_ocr(p)
        assert len(items) == 1
        assert items[0].text == "Hello"
        assert items[0].bbox[0] == 10
    finally:
        ocr_engine.reset_engine()
