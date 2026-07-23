"""Lightweight OCR via RapidOCR / ONNX Runtime (FR-006)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from vnc_agent.domain.observation import OCRItem, Region

_engine: Any = None


def _get_engine() -> Any:
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR

            _engine = RapidOCR()
        except Exception:
            # Fallback stub when rapidocr is unavailable (tests can inject)
            _engine = _StubOCR()
    return _engine


class _StubOCR:
    def __call__(self, img: Any) -> tuple[list | None, None]:
        return None, None


def reset_engine() -> None:
    global _engine
    _engine = None


def set_engine(engine: Any) -> None:
    global _engine
    _engine = engine


def run_ocr_array(
    pixels: np.ndarray,
    *,
    roi: Region | None = None,
) -> list[OCRItem]:
    """Run OCR directly on an already-decoded array — never re-reads a file.

    Feature 004 (perception-cache-contract.md): the analysis-component
    boundary consumed by the analysis cache; ``run_ocr`` below is the
    offline-compatible path wrapper over this.
    """
    img = pixels

    offset_x, offset_y = 0, 0
    if roi is not None:
        offset_x, offset_y = roi.x1, roi.y1
        img = img[roi.y1 : roi.y2, roi.x1 : roi.x2]
        if img.size == 0:
            return []

    engine = _get_engine()
    result, _ = engine(img)
    items: list[OCRItem] = []
    if not result:
        return items

    for entry in result:
        # RapidOCR: [box_points, text, confidence]
        try:
            box, text, conf = entry[0], entry[1], float(entry[2])
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x1 = int(min(xs)) + offset_x
            y1 = int(min(ys)) + offset_y
            x2 = int(max(xs)) + offset_x
            y2 = int(max(ys)) + offset_y
            items.append(
                OCRItem(
                    text=str(text),
                    bbox=(x1, y1, x2, y2),
                    confidence=max(0.0, min(1.0, conf)),
                    normalized_text=str(text).strip().lower(),
                )
            )
        except Exception:
            continue
    return items


def run_ocr(
    image_path: str | Path,
    *,
    roi: Region | None = None,
) -> list[OCRItem]:
    """Offline-compatible path wrapper — see :func:`run_ocr_array`."""
    import cv2

    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        return []
    return run_ocr_array(img, roi=roi)
