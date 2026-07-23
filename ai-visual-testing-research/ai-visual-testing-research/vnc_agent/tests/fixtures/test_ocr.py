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


def test_ocr_array_entry_ndarray(monkeypatch):
    """Feature 004 (T029/T034): OCR must accept an already-decoded ndarray
    directly — the analysis-component boundary the cache reuses — and never
    re-decode from a file (perception-cache-contract.md `ocr`)."""
    ocr_engine.set_engine(FakeOCR())
    decode_calls = {"n": 0}
    real_imread = cv2.imread

    def counting_imread(*args, **kwargs):
        decode_calls["n"] += 1
        return real_imread(*args, **kwargs)

    monkeypatch.setattr(cv2, "imread", counting_imread)
    try:
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        items = ocr_engine.run_ocr_array(img)
        assert len(items) == 1
        assert items[0].text == "Hello"
        assert decode_calls["n"] == 0, "run_ocr_array must never re-read/decode from disk"
    finally:
        ocr_engine.reset_engine()
