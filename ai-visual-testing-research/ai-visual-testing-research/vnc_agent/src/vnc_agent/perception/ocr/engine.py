"""Lightweight OCR via RapidOCR / ONNX Runtime (FR-006).

Feature 010 (ocr-japanese-model): the recognition-stage model is
configurable. ``configure_ocr`` is called once at the composition root
(api/cli.py) with the perception config; the engine itself is still built
lazily on first use (constitution: load OCR models on demand, never more
than one at a time) and rebuilt only when the effective settings change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from vnc_agent.domain.observation import OCRItem, Region

# Feature 010: language identifier -> (rec model, rec character dict),
# project-relative to the vnc_agent working directory (same convention as
# artifacts.root_dir / artifacts.db_path). Provenance: models/ocr/README.md.
OCR_LANG_ASSETS: dict[str, tuple[str, str]] = {
    "japan": (
        "models/ocr/japan_PP-OCRv4_rec_mobile.onnx",
        "models/ocr/japan_dict.txt",
    ),
}


@dataclass(frozen=True)
class OCREngineSettings:
    """Effective recognition-engine settings resolved at composition time."""

    lang: str | None = None
    rec_model_path: str | None = None
    rec_keys_path: str | None = None


_engine: Any = None
_settings: OCREngineSettings | None = None


def configure_ocr(
    *,
    lang: str | None = None,
    rec_model_path: str | Path | None = None,
    rec_keys_path: str | Path | None = None,
    base_dir: str | Path | None = None,
) -> None:
    """Resolve and validate OCR engine settings (feature 010, FR-002/004/005).

    - All-``None`` clears settings: behavior identical to the pre-feature
      default (bundled recognition model).
    - ``lang`` with a known :data:`OCR_LANG_ASSETS` mapping resolves to the
      project-provided model files; an explicit ``rec_model_path`` overrides
      the mapping.
    - Unknown ``lang`` without an explicit model path raises ``ValueError``.
    - A resolved model/dict path missing on disk raises ``FileNotFoundError``
      naming the offending path (fail fast at composition, before any VNC
      connection).
    - The cached engine instance is dropped only when the effective settings
      actually change (rebuild-on-change, never per-invocation).
    """
    global _engine, _settings

    base = Path(base_dir) if base_dir is not None else Path.cwd()

    model = Path(rec_model_path) if rec_model_path is not None else None
    keys = Path(rec_keys_path) if rec_keys_path is not None else None

    if model is None and lang is not None:
        try:
            mapped_model, mapped_keys = OCR_LANG_ASSETS[lang]
        except KeyError:
            raise ValueError(
                f"unknown perception.ocr_lang {lang!r} with no explicit "
                f"ocr_rec_model_path; known languages: {sorted(OCR_LANG_ASSETS)}"
            ) from None
        model = Path(mapped_model)
        if keys is None:
            keys = Path(mapped_keys)

    def _resolve(p: Path | None) -> str | None:
        if p is None:
            return None
        resolved = p if p.is_absolute() else base / p
        if not resolved.exists():
            raise FileNotFoundError(
                f"configured OCR model asset not found: {resolved}"
            )
        return str(resolved)

    new_settings = OCREngineSettings(
        lang=lang,
        rec_model_path=_resolve(model),
        rec_keys_path=_resolve(keys),
    )
    if _settings is not None:
        if new_settings == _settings:
            return  # unchanged: keep the cached engine (FR-004)
        _settings = new_settings
        _engine = None  # rebuild lazily with the new settings
        return
    _settings = new_settings
    if new_settings != OCREngineSettings():
        _engine = None  # first non-default configuration: rebuild lazily


def get_ocr_settings() -> OCREngineSettings | None:
    """Introspection for tests/probes — the currently effective settings."""
    return _settings


def ocr_component_identity() -> dict[str, Any]:
    """OCR component identity for the analysis cache (feature 010, FR-011)."""
    lang = _settings.lang if _settings is not None else None
    return {
        "backend": "rapidocr-onnxruntime",
        "version": "1.0",
        "language": lang or "default",
        "preprocess": "none",
    }


def _get_engine() -> Any:
    global _engine
    if _engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR

            kwargs: dict[str, Any] = {}
            if _settings is not None:
                if _settings.rec_model_path:
                    kwargs["rec_model_path"] = _settings.rec_model_path
                if _settings.rec_keys_path:
                    kwargs["rec_keys_path"] = _settings.rec_keys_path
            _engine = RapidOCR(**kwargs)
        except Exception:
            # Fallback stub when rapidocr is unavailable (tests can inject)
            _engine = _StubOCR()
    return _engine


class _StubOCR:
    def __call__(self, img: Any) -> tuple[list | None, None]:
        return None, None


def reset_engine() -> None:
    """Drop the cached engine instance (test seam); settings persist."""
    global _engine
    _engine = None


def set_engine(engine: Any) -> None:
    """Inject an engine (test seam); always wins over configured settings."""
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


def run_ocr_region_scaled(
    image_path: str | Path,
    region: Region,
    *,
    scale: float = 2.0,
) -> list[OCRItem]:
    """Single bounded re-OCR of ``region`` at ``scale`` x magnification
    (feature 010, FR-008 — small-glyph rescue for regioned assertions).

    Reads the persisted frame image (independent evidence), crops the region
    clamped to frame bounds, upscales, runs the configured engine, and maps
    bboxes back to original frame coordinates. Unreadable image or empty
    clamped crop returns ``[]``.
    """
    import cv2

    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        return []

    h, w = img.shape[:2]
    x1 = max(0, min(int(region.x1), w))
    y1 = max(0, min(int(region.y1), h))
    x2 = max(0, min(int(region.x2), w))
    y2 = max(0, min(int(region.y2), h))
    if x2 <= x1 or y2 <= y1:
        return []

    crop = img[y1:y2, x1:x2]
    upscaled = cv2.resize(
        crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC
    )

    items = run_ocr_array(upscaled)
    mapped: list[OCRItem] = []
    for it in items:
        bx1, by1, bx2, by2 = it.bbox
        mapped.append(
            it.model_copy(
                update={
                    "bbox": (
                        int(bx1 / scale) + x1,
                        int(by1 / scale) + y1,
                        int(bx2 / scale) + x1,
                        int(by2 / scale) + y1,
                    )
                }
            )
        )
    return mapped
