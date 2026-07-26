"""US7: OCR/template verifiers."""

from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

from vnc_agent.domain.observation import OCRItem, StructuredScreen, TemplateMatch
from vnc_agent.domain.verification import VerificationCondition
from vnc_agent.perception.ocr import engine as ocr_engine
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


# ---------------------------------------------------------------------------
# Feature 010 (FR-008/009): failed-needle ROI 2x upscale re-OCR retry.
# Cross-scenario coverage (Principle VI): the retry is exercised with two
# unrelated generic GUI scenarios — a form-dialog label and an icon-menu
# caption — neither tied to any business domain.
# ---------------------------------------------------------------------------


class _RetrySpyEngine:
    """Stub engine emitting `text` for every call, counting invocations."""

    def __init__(self, text: str | None):
        self.text = text
        self.calls = 0

    def __call__(self, img):
        self.calls += 1
        if self.text is None:
            return None, None
        box = [[4, 4], [60, 4], [60, 24], [4, 24]]
        return [[box, self.text, 0.9]], None


@pytest.fixture(autouse=True)
def _clean_engine_state():
    yield
    ocr_engine.configure_ocr()
    ocr_engine.reset_engine()


def _frame(tmp_path: Path) -> str:
    p = tmp_path / "frame.png"
    cv2.imwrite(str(p), np.zeros((100, 100, 3), dtype=np.uint8))
    return str(p)


@pytest.mark.parametrize("needle", ["Submit", "設定一覧"])  # two unrelated scenarios
def test_regioned_text_appears_rescued_by_single_upscale_retry(tmp_path: Path, needle: str):
    spy = _RetrySpyEngine(needle)
    ocr_engine.set_engine(spy)
    s = _screen(
        ocr_items=[OCRItem(text="unrelated", bbox=(0, 0, 10, 10), confidence=0.9)],
        image_path=_frame(tmp_path),
    )
    cond = VerificationCondition(
        type="text_appears", value=needle, region=[10, 10, 90, 40]
    )
    assert verify_text(cond, s) == "passed"
    assert spy.calls == 1, "exactly one bounded retry OCR pass"
    # retry items must stay local — screen ocr_items untouched
    assert [i.text for i in s.ocr_items] == ["unrelated"]


def test_text_appears_without_region_never_retries(tmp_path: Path):
    spy = _RetrySpyEngine("Submit")
    ocr_engine.set_engine(spy)
    s = _screen(ocr_items=[], image_path=_frame(tmp_path))
    cond = VerificationCondition(type="text_appears", value="Submit")
    assert verify_text(cond, s) == "failed"
    assert spy.calls == 0


def test_text_appears_without_image_path_never_retries():
    spy = _RetrySpyEngine("Submit")
    ocr_engine.set_engine(spy)
    s = _screen(ocr_items=[])
    cond = VerificationCondition(
        type="text_appears", value="Submit", region=[10, 10, 90, 40]
    )
    assert verify_text(cond, s) == "failed"
    assert spy.calls == 0


def test_text_disappears_never_uses_the_retry(tmp_path: Path):
    """Finding more text via retry may only rescue text_appears — it must
    never flip a text_disappears pass into a fail."""
    spy = _RetrySpyEngine("Ghost")
    ocr_engine.set_engine(spy)
    s = _screen(ocr_items=[], image_path=_frame(tmp_path))
    cond = VerificationCondition(
        type="text_disappears", value="Ghost", region=[10, 10, 90, 40]
    )
    assert verify_text(cond, s) == "passed"
    assert spy.calls == 0


def test_empty_retry_result_still_fails(tmp_path: Path):
    spy = _RetrySpyEngine(None)  # retry OCR finds nothing
    ocr_engine.set_engine(spy)
    s = _screen(ocr_items=[], image_path=_frame(tmp_path))
    cond = VerificationCondition(
        type="text_appears", value="Options", region=[10, 10, 90, 40]
    )
    assert verify_text(cond, s) == "failed"
    assert spy.calls == 1


def test_retry_wrong_text_still_fails(tmp_path: Path):
    spy = _RetrySpyEngine("Other")
    ocr_engine.set_engine(spy)
    s = _screen(ocr_items=[], image_path=_frame(tmp_path))
    cond = VerificationCondition(
        type="text_appears", value="Options", region=[10, 10, 90, 40]
    )
    assert verify_text(cond, s) == "failed"
    assert spy.calls == 1
