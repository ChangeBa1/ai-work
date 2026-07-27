"""Page fingerprint construction + similarity scoring (feature 015, design §13).

Pure, deterministic functions: no I/O, no randomness, no global state —
identical inputs always produce identical outputs (Constitution I). Business
agnostic (Constitution VI): generic pixels, text tokens and geometry only.

Fingerprint components (spec FR-001):

- perceptual hash (pHash): 32x32 grayscale → DCT → top-left 8x8 low-frequency
  block, mean-thresholded excluding the DC term → 64-bit hex string;
- OCR keyword set: normalized token set with dynamic-looking tokens (clock /
  date / serial-number shapes) filtered out (spec Clarification 2);
- OCR layout distribution: occupied cells of an 8x8 grid over the frame;
- resolution.

Similarity (spec FR-002, Clarification 1): design §13 assigns
0.30 pHash + 0.30 OCR text + 0.20 OCR layout + 0.20 stable-template-set.
This MVP has no page-level stable-template facility, so the 0.20 template
weight is redistributed proportionally: 0.375 / 0.375 / 0.25.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

import cv2
import numpy as np

from vnc_agent.domain.memory import PageFingerprint
from vnc_agent.domain.observation import OCRItem

#: Similarity weights (spec Clarification 1 — §13 weights with the
#: stable-template component folded in proportionally).
WEIGHT_PHASH = 0.375
WEIGHT_TEXT = 0.375
WEIGHT_LAYOUT = 0.25

#: Layout-grid granularity per axis (coarse quantization, spec FR-001).
GRID_SIZE = 8

# Characters that, together with digits, make up "dynamic" tokens: clock /
# date separators, decimal and thousands punctuation, currency and ordinal
# markers commonly attached to changing numeric readouts. Generic shapes,
# never application vocabulary (Constitution VI).
_DYNAMIC_EXTRA_CHARS = set(":/-.,;·¥￥$€%#№no. 年月日時分秒时分点")


def is_dynamic_token(token: str) -> bool:
    """True when the token is a digits-plus-separators shape (clock, date,
    amount, serial number) — the dominant dynamic-region noise source.

    A token is dynamic iff it contains at least one digit and every character
    is a digit or a separator/marker character. Pure-text tokens (labels,
    button captions, kana/kanji words) are never dynamic.
    """
    if not token:
        return False
    has_digit = False
    for ch in token:
        if ch.isdigit():
            has_digit = True
        elif ch.lower() not in _DYNAMIC_EXTRA_CHARS:
            return False
    return has_digit


def _normalized_tokens(ocr_items: Sequence[OCRItem]) -> list[tuple[str, OCRItem]]:
    out: list[tuple[str, OCRItem]] = []
    for item in ocr_items:
        token = (item.normalized_text or item.text).strip().lower()
        if not token or is_dynamic_token(token):
            continue
        out.append((token, item))
    return out


def compute_phash(image: np.ndarray) -> str:
    """64-bit DCT mean hash of ``image`` (BGR or grayscale), as 16 hex chars."""
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(small))
    block = dct[:8, :8].flatten()
    # Exclude the DC term from the mean so overall brightness shifts do not
    # flip every bit.
    mean = block[1:].mean()
    bits = 0
    for value in block:
        bits = (bits << 1) | int(value > mean)
    return f"{bits & (2**64 - 1):016x}"


def hamming_distance(a_hex: str, b_hex: str) -> int:
    """Bit distance between two 64-bit hex hashes."""
    return bin(int(a_hex, 16) ^ int(b_hex, 16)).count("1")


def build_page_fingerprint(
    image: np.ndarray | None,
    ocr_items: Sequence[OCRItem],
    resolution: tuple[int, int],
) -> PageFingerprint:
    """Build the deterministic page fingerprint (spec FR-001).

    ``image`` is the decoded masked-safe frame (spec Clarification 3); None
    leaves the pHash component empty (score contribution degrades, never
    crashes). Public 016 extension point (spec "016 扩展点").
    """
    width, height = resolution
    phash = compute_phash(image) if image is not None and image.size else ""

    tokens: set[str] = set()
    cells: set[str] = set()
    for token, item in _normalized_tokens(ocr_items):
        tokens.add(token)
        x1, y1, x2, y2 = item.bbox
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        if width > 0 and height > 0:
            col = min(GRID_SIZE - 1, max(0, cx * GRID_SIZE // width))
            row = min(GRID_SIZE - 1, max(0, cy * GRID_SIZE // height))
            cells.add(f"{col},{row}")

    return PageFingerprint(
        phash=phash,
        ocr_tokens=sorted(tokens),
        layout_cells=sorted(cells),
        resolution=resolution,
    )


def _jaccard(a: Sequence[str], b: Sequence[str]) -> float:
    """Set similarity with the both-empty convention (spec FR-002): two empty
    sets carry no distinguishing evidence => 1.0; one-sided emptiness is a
    real mismatch => 0.0."""
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def page_similarity(a: PageFingerprint, b: PageFingerprint) -> float:
    """Weighted similarity in [0, 1] (spec FR-002). Pure 016 extension point."""
    if a.phash and b.phash:
        phash_sim = 1.0 - hamming_distance(a.phash, b.phash) / 64.0
    elif not a.phash and not b.phash:
        phash_sim = 1.0
    else:
        phash_sim = 0.0
    text_sim = _jaccard(a.ocr_tokens, b.ocr_tokens)
    layout_sim = _jaccard(a.layout_cells, b.layout_cells)
    return WEIGHT_PHASH * phash_sim + WEIGHT_TEXT * text_sim + WEIGHT_LAYOUT * layout_sim


def classify_page_match(
    score: float,
    *,
    same_resolution: bool,
    high: float,
    medium: float,
    low: float,
) -> Literal["high", "medium", "low", "none"]:
    """Three-tier classification (design §13). Resolution mismatch caps the
    tier at "low" — remembered bboxes/templates are resolution-dependent, so
    neither direct clicks nor grounder hints may cross resolutions
    (spec FR-002)."""
    if score >= high:
        level: Literal["high", "medium", "low", "none"] = "high"
    elif score >= medium:
        level = "medium"
    elif score >= low:
        level = "low"
    else:
        level = "none"
    if not same_resolution and level in ("high", "medium"):
        level = "low"
    return level
