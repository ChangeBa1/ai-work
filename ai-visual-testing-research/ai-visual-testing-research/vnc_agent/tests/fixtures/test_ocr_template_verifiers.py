"""US7: OCR/template verifiers."""

from datetime import UTC, datetime

from vnc_agent.domain.observation import OCRItem, StructuredScreen, TemplateMatch
from vnc_agent.domain.verification import VerificationCondition
from vnc_agent.verification.ocr_verifier import verify_text
from vnc_agent.verification.template_verifier import verify_template


def _screen(**kwargs) -> StructuredScreen:
    return StructuredScreen(
        frame_id="f",
        resolution=(100, 100),
        captured_at=datetime.now(UTC),
        **kwargs,
    )


def test_text_appears():
    s = _screen(ocr_items=[OCRItem(text="欢迎", bbox=(0, 0, 10, 10), confidence=0.9)])
    assert verify_text(VerificationCondition(type="text_appears", value="欢迎"), s) == "passed"
    assert verify_text(VerificationCondition(type="text_appears", value="登录"), s) == "failed"


def test_text_appears_normalizes_cjk_ocr_confusables():
    """RapidOCR often emits simplified CN forms for JP UI glyphs (单/价 vs 単/価)."""
    s = _screen(ocr_items=[OCRItem(text="单价", bbox=(0, 0, 10, 10), confidence=0.9)])
    assert verify_text(VerificationCondition(type="text_appears", value="単価"), s) == "passed"
    s2 = _screen(ocr_items=[OCRItem(text="单！", bbox=(0, 0, 10, 10), confidence=0.76)])
    # Degraded single-glyph read of the 単価 header must not invent the missing 価.
    assert verify_text(VerificationCondition(type="text_appears", value="単価"), s2) == "failed"


def test_text_appears_matches_across_adjacent_ocr_fragments():
    """Join same-line fragments so split labels still match multi-char needles."""
    s = _screen(
        ocr_items=[
            OCRItem(text="内", bbox=(10, 100, 30, 120), confidence=0.9),
            OCRItem(text="税10%", bbox=(32, 100, 90, 120), confidence=0.9),
        ]
    )
    assert verify_text(VerificationCondition(type="text_appears", value="内税"), s) == "passed"


def test_text_appears_tolerates_amount_thousand_separators():
    """RapidOCR often reads JP ',' thousands as '.' (10,000 -> 10.000)."""
    s = _screen(
        ocr_items=[
            OCRItem(text="10.000", bbox=(0, 0, 40, 20), confidence=0.9),
            OCRItem(text="9.995", bbox=(0, 30, 40, 50), confidence=0.9),
            OCRItem(text="確定", bbox=(0, 60, 40, 80), confidence=0.9),
        ]
    )
    assert verify_text(VerificationCondition(type="text_appears", value="10,000"), s) == "passed"
    assert verify_text(VerificationCondition(type="text_appears", value="9,995"), s) == "passed"
    # Bare single digit must not match via digit compaction alone.
    assert verify_text(VerificationCondition(type="text_appears", value="8"), s) == "failed"
    s_miss = _screen(ocr_items=[OCRItem(text="預り金", bbox=(0, 0, 40, 20), confidence=0.9)])
    miss = verify_text(VerificationCondition(type="text_appears", value="10,000"), s_miss)
    assert miss == "failed"


def test_text_disappears():
    s = _screen(ocr_items=[OCRItem(text="密码", bbox=(0, 0, 10, 10), confidence=0.9)])
    assert verify_text(VerificationCondition(type="text_disappears", value="密码"), s) == "failed"
    assert verify_text(VerificationCondition(type="text_disappears", value="欢迎"), s) == "passed"


def test_template_appears():
    s = _screen(
        template_matches=[TemplateMatch(template_id="logo", bbox=(0, 0, 5, 5), confidence=0.9)]
    )
    assert (
        verify_template(VerificationCondition(type="template_appears", value="logo"), s)
        == "passed"
    )
