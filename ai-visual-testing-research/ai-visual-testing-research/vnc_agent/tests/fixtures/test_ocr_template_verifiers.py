"""US7: OCR/template verifiers."""

from datetime import datetime, timezone

from vnc_agent.domain.observation import OCRItem, StructuredScreen, TemplateMatch
from vnc_agent.domain.verification import VerificationCondition
from vnc_agent.verification.ocr_verifier import verify_text
from vnc_agent.verification.template_verifier import verify_template


def _screen(**kwargs) -> StructuredScreen:
    return StructuredScreen(
        frame_id="f",
        resolution=(100, 100),
        captured_at=datetime.now(timezone.utc),
        **kwargs,
    )


def test_text_appears():
    s = _screen(ocr_items=[OCRItem(text="欢迎", bbox=(0, 0, 10, 10), confidence=0.9)])
    assert verify_text(VerificationCondition(type="text_appears", value="欢迎"), s) == "passed"
    assert verify_text(VerificationCondition(type="text_appears", value="登录"), s) == "failed"


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
