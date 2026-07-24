"""Business assertions for the formal POS bag checkout case (T037/T038)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.domain.testcase import load_test_case
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.models.provider import VisionUnderstandingResponse
from vnc_agent.verification.business_resolver import resolve_step_result

ROOT = Path(__file__).resolve().parents[2]


def _screen(texts: list[str], *, changed: bool = True) -> StructuredScreen:
    return StructuredScreen(
        frame_id="business",
        resolution=(1024, 1568),
        captured_at=datetime.now(UTC),
        ocr_items=[
            OCRItem(text=text, bbox=(10, i * 30, 100, i * 30 + 20), confidence=0.9)
            for i, text in enumerate(texts)
        ],
        changed_since_last=changed,
    )


def _effect() -> ActionEffect:
    return ActionEffect(
        status="expected_effect",
        evidence=ActionEffectEvidence(global_diff_ratio=0.004669),
        reason="fixed local cart change",
    )


@pytest.mark.asyncio
async def test_noisy_bag_business_assertions_pass() -> None:
    case = load_test_case(ROOT / "testcases" / "pos-buy-bag-checkout.yaml")
    step = case.steps[0]
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="passed",
            confidence=1.0,
            reason="cart shows 1 bag item totaling 5",
            model_name="stub",
        )
    )
    result = await resolve_step_result(
        step.expected,
        step.verification_mode,
        _effect(),
        # Post-register chrome only — bare "1"/"5"/"袋" alone must NOT be enough.
        _screen(["レジ袋", "5", "点数", "1", "内税10%", "1個"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "passed"
    assert result.weak_assertion_warning is False
    assert result.basis in {"business_assertion", "mixed"}


@pytest.mark.asyncio
async def test_rapidocr_degraded_pos_bag_chrome_still_passes() -> None:
    """Regression: real RapidOCR never emits 単価 (reads 单/单！); case must still pass."""
    case = load_test_case(ROOT / "testcases" / "pos-buy-bag-checkout.yaml")
    step = case.steps[0]
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="passed",
            confidence=1.0,
            reason="cart shows レジ袋 1点 total 5",
            model_name="stub",
        )
    )
    # Tokens captured from run bb9f039e after-click safe_evidence OCR.
    result = await resolve_step_result(
        step.expected,
        step.verification_mode,
        _effect(),
        _screen(
            [
                "ジ袋",
                "单！",
                "5",
                "合計",
                "1",
                "個",
                "内税10%",
                "点数值下合計",
                "1Lジ袋",
                "小計",
                "袋",
            ]
        ),
        planner=planner,
        escalate=False,
    )
    assert result.status == "passed"
    assert result.weak_assertion_warning is False


@pytest.mark.asyncio
async def test_empty_pos_keypad_chrome_does_not_pass_add_bag() -> None:
    """Empty POS has keypad 1/5 and レジ袋 button text — must not pass add-bag."""
    case = load_test_case(ROOT / "testcases" / "pos-buy-bag-checkout.yaml")
    step = case.steps[0]
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="failed",
            confidence=1.0,
            reason="cart total is still 0",
            model_name="stub",
        )
    )
    result = await resolve_step_result(
        step.expected,
        step.verification_mode,
        _effect(),
        _screen(["1", "2", "3", "4", "5", "レジ袋", "小計", "0個"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_no_effect_rejects_business_match_on_unchanged_screen() -> None:
    """no_effect + matching chrome must not pass (triggers retry/recovery)."""
    case = load_test_case(ROOT / "testcases" / "pos-buy-bag-checkout.yaml")
    step = case.steps[0]
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="passed",
            confidence=1.0,
            reason="model hallucinates pass on static chrome",
            model_name="stub",
        )
    )
    no_effect = ActionEffect(
        status="no_effect",
        evidence=ActionEffectEvidence(global_diff_ratio=0.0),
        reason="identical frames",
    )
    result = await resolve_step_result(
        step.expected,
        step.verification_mode,
        no_effect,
        _screen(["点数", "内税10%", "レジ袋", "1", "5"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "failed"
    assert "no_effect" in result.failed_conditions


@pytest.mark.asyncio
async def test_subtotal_deterministic_assertion_passes_without_visual_model() -> None:
    case = load_test_case(ROOT / "testcases" / "pos-buy-bag-checkout.yaml")
    step = case.steps[1]
    assert all(condition.type != "visual_question" for condition in step.expected.conditions)
    result = await resolve_step_result(
        step.expected,
        step.verification_mode,
        _effect(),
        _screen(["不足額"]),
        escalate=False,
    )
    assert result.status == "passed"
    assert result.weak_assertion_warning is False


@pytest.mark.asyncio
async def test_cash_amount_assertions_pass_with_visual_confirmation() -> None:
    case = load_test_case(ROOT / "testcases" / "pos-buy-bag-checkout.yaml")
    step = case.steps[2]
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="passed",
            confidence=1.0,
            reason="automatic deposit and change are visible in the POS dialog",
            model_name="stub",
        )
    )
    result = await resolve_step_result(
        step.expected,
        step.verification_mode,
        _effect(),
        _screen(["預り金", "10,000", "お釣り", "9,995", "確定"]),
        planner=planner,
    )
    assert result.status == "passed"
    assert result.weak_assertion_warning is False


@pytest.mark.asyncio
async def test_cash_amount_assertions_pass_with_rapidocr_dot_thousands() -> None:
    """Regression: OCR emits 10.000/9.995 while case asserts 10,000/9,995."""
    case = load_test_case(ROOT / "testcases" / "pos-buy-bag-checkout.yaml")
    step = case.steps[2]
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="passed",
            confidence=1.0,
            reason="dialog shows deposit 10000 change 9995 and 確定",
            model_name="stub",
        )
    )
    result = await resolve_step_result(
        step.expected,
        step.verification_mode,
        _effect(),
        _screen(["預り金", "10.000", "お釣り", "9.995", "確定"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "passed"


@pytest.mark.asyncio
async def test_completed_transaction_visual_assertion_passes() -> None:
    case = load_test_case(ROOT / "testcases" / "pos-buy-bag-checkout.yaml")
    step = case.steps[3]
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="passed",
            confidence=1.0,
            reason="the large red 済 completion mark is visible",
            model_name="stub",
        )
    )
    result = await resolve_step_result(
        step.expected,
        step.verification_mode,
        _effect(),
        _screen(["済"]),
        planner=planner,
    )
    assert result.status == "passed"
    assert result.weak_assertion_warning is False
