"""Text appears/disappears verifiers."""

from __future__ import annotations

import re
import unicodedata

from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.domain.verification import VerificationCondition, VerificationStatus

# RapidOCR (CN-biased rec) frequently emits simplified forms for JP POS glyphs.
_OCR_CONFUSABLES = str.maketrans(
    {
        "单": "単",
        "价": "価",
        "据": "拠",
        "门": "門",
        "关": "関",
        "预": "預",
        "现": "現",
        "计": "計",
        "点": "点",
        "税": "税",
        "个": "個",
        "金": "金",
        "额": "額",
    }
)

# Pure amount-like needles (digits + common thousand/decimal separators only).
_AMOUNT_LIKE = re.compile(r"^[\d,.\s]+$")
# Avoid matching bare short digits via amount-key compaction (keypad noise).
_MIN_AMOUNT_DIGITS = 3


def normalize_ocr_text(text: str) -> str:
    """Canonicalize OCR/needle text for tolerant CJK substring matching."""
    raw = (text or "").strip().lower()
    if not raw:
        return ""
    return unicodedata.normalize("NFKC", raw).translate(_OCR_CONFUSABLES)


def amount_digit_key(text: str) -> str | None:
    """Return digits-only key for amount-like strings, else None.

    Enables ``10,000`` (case) to match OCR ``10.000`` / ``10000`` without
    treating every short digit (e.g. keypad ``5``) as an amount key.
    """
    norm = normalize_ocr_text(text)
    if not norm or not _AMOUNT_LIKE.fullmatch(norm):
        return None
    digits = re.sub(r"\D", "", norm)
    if len(digits) < _MIN_AMOUNT_DIGITS:
        return None
    return digits


def _y_mid(item: OCRItem) -> float:
    y1, y2 = item.bbox[1], item.bbox[3]
    return (y1 + y2) / 2.0


def _height(item: OCRItem) -> float:
    return max(1.0, float(item.bbox[3] - item.bbox[1]))


def _line_joined_texts(items: list[OCRItem]) -> list[str]:
    """Join left-to-right fragments that share a horizontal band (same line)."""
    if not items:
        return []
    ordered = sorted(items, key=lambda it: (_y_mid(it), it.bbox[0]))
    lines: list[list[OCRItem]] = []
    for item in ordered:
        placed = False
        for line in lines:
            ref = line[0]
            if abs(_y_mid(item) - _y_mid(ref)) <= max(_height(item), _height(ref)) * 0.6:
                line.append(item)
                placed = True
                break
        if not placed:
            lines.append([item])
    joined: list[str] = []
    for line in lines:
        line.sort(key=lambda it: it.bbox[0])
        blob = "".join(normalize_ocr_text(it.text) for it in line)
        if blob:
            joined.append(blob)
    page = "".join(normalize_ocr_text(it.text) for it in ordered)
    if page:
        joined.append(page)
    return joined


def _haystacks(screen: StructuredScreen) -> list[str]:
    out: list[str] = []
    for item in screen.ocr_items:
        out.append(normalize_ocr_text(item.text))
        out.append(normalize_ocr_text(item.normalized_text))
    out.extend(_line_joined_texts(list(screen.ocr_items)))
    return [h for h in out if h]


def _text_found(needle: str, screen: StructuredScreen) -> bool:
    hays = _haystacks(screen)
    if any(needle in hay for hay in hays):
        return True
    needle_amt = amount_digit_key(needle)
    if needle_amt is None:
        return False
    for hay in hays:
        hay_amt = amount_digit_key(hay)
        if hay_amt is not None and needle_amt == hay_amt:
            return True
        # Also allow amount needle inside a longer amount-like OCR blob.
        hay_digits = re.sub(r"\D", "", hay)
        if hay_digits and needle_amt == hay_digits:
            return True
    return False


def _found_in_items(needle: str, items: list[OCRItem]) -> bool:
    """Needle match over a standalone OCR item list using the same
    normalization pipeline as the main haystack check."""
    hays: list[str] = []
    for item in items:
        hays.append(normalize_ocr_text(item.text))
        hays.append(normalize_ocr_text(item.normalized_text))
    hays.extend(_line_joined_texts(items))
    hays = [h for h in hays if h]
    if any(needle in hay for hay in hays):
        return True
    needle_amt = amount_digit_key(needle)
    if needle_amt is None:
        return False
    for hay in hays:
        hay_digits = re.sub(r"\D", "", hay)
        if hay_digits and needle_amt == hay_digits:
            return True
    return False


def _roi_retry_found(
    needle: str, condition: VerificationCondition, screen: StructuredScreen
) -> bool:
    """Feature 010 (FR-008): one bounded 2x-upscale re-OCR of the declared
    region when a regioned `text_appears` needle was not found. Retry items
    stay local to this decision — `screen.ocr_items` is never mutated."""
    if condition.region is None or not screen.image_path:
        return False
    from vnc_agent.perception.ocr.engine import run_ocr_region_scaled

    try:
        retry_items = run_ocr_region_scaled(screen.image_path, condition.region)
    except Exception:
        return False
    if not retry_items:
        return False
    return _found_in_items(needle, retry_items)


def verify_text(condition: VerificationCondition, screen: StructuredScreen) -> VerificationStatus:
    needle = normalize_ocr_text(condition.value or "")
    if not needle:
        return "uncertain"
    found = _text_found(needle, screen)
    if condition.type == "text_appears":
        if not found and _roi_retry_found(needle, condition, screen):
            found = True
        return "passed" if found else "failed"
    if condition.type == "text_disappears":
        # FR-008: the upscale retry never applies here — finding *more* text
        # could only flip a pass into a fail.
        return "passed" if not found else "failed"
    return "uncertain"
