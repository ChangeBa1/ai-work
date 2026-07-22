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
    result = await resolve_step_result(
        step.expected,
        step.verification_mode,
        _effect(),
        _screen(["1", "5", "袋"]),
        escalate=False,
    )
    assert result.status == "passed"
    assert result.weak_assertion_warning is False
    assert result.basis in {"business_assertion", "mixed"}


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
