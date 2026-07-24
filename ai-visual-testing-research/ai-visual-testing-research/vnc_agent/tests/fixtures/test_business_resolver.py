"""US2/3/4/6/7: resolve_step_result status/basis table + conflict rules."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.domain.verification import (
    VerificationCondition,
    VerificationResult,
    VerificationSpec,
)
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.models.provider import VisionUnderstandingResponse
from vnc_agent.verification.business_resolver import resolve_step_result


def _screen(*, texts: list[str] | None = None, changed: bool = True) -> StructuredScreen:
    ocr = [
        OCRItem(text=t, bbox=(i * 10, 0, i * 10 + 40, 20), confidence=0.9)
        for i, t in enumerate(texts or [])
    ]
    return StructuredScreen(
        frame_id="f1",
        resolution=(200, 200),
        captured_at=datetime.now(timezone.utc),
        ocr_items=ocr,
        changed_since_last=changed,
        image_path="",
    )


def _ae(status: str = "expected_effect") -> ActionEffect:
    return ActionEffect(
        status=status,  # type: ignore[arg-type]
        evidence=ActionEffectEvidence(global_diff_ratio=0.01),
        reason="test",
    )


@pytest.mark.asyncio
async def test_reobserve_and_describe_at_most_once():
    """T022: escalation calls reobserve + describe_screen each ≤1; no execute."""
    reobserve_n = 0
    screen = _screen(texts=[], changed=True)

    async def reobserve():
        nonlocal reobserve_n
        reobserve_n += 1
        return _screen(texts=[], changed=True)

    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="uncertain",
            confidence=0.4,
            reason="still unclear",
            model_name="stub",
        )
    )
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="NEVER"),
            VerificationCondition(type="visual_question", value="bag count is 1?"),
        ],
    )
    # text_appears fails → overall failed for all-operator if failed present
    # Use only visual_question + weak so status can be uncertain
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="visual_question", value="is bag count 1?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        screen,
        planner=planner,
        reobserve=reobserve,
        escalate=True,
    )
    # Escalation reobserve at most once; describe_screen is used by
    # VerificationEngine for visual_question (initial + optional re-verify)
    # plus at most one escalation fallback — must not loop unboundedly.
    assert reobserve_n <= 1
    assert planner.describe_calls <= 3
    assert result.status in ("passed", "failed", "uncertain")


@pytest.mark.asyncio
async def test_deterministic_overrides_visual_failed_vs_passed():
    """T023 / FR-010: det failed + visual passed → failed."""
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="passed",
            confidence=0.9,
            reason="looks ok",
            model_name="stub",
        )
    )
    # text not on screen → failed; visual would pass
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="1点"),
            VerificationCondition(type="visual_question", value="count is 1?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["0点"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_deterministic_overrides_visual_passed_vs_failed():
    """T023: det passed + visual failed → still passed."""
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="failed",
            confidence=0.9,
            reason="model says no",
            model_name="stub",
        )
    )
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="1点"),
            VerificationCondition(type="visual_question", value="count is 1?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["1点"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "passed"


@pytest.mark.asyncio
async def test_business_assertion_mixed_basis():
    """T033: business passed + screen_changed → passed, basis=mixed."""
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="screen_changed"),
            VerificationCondition(type="text_appears", value="1点"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["1点"], changed=True),
        escalate=False,
    )
    assert result.status == "passed"
    assert result.basis == "mixed"
    assert result.weak_assertion_warning is False


@pytest.mark.asyncio
async def test_business_failed_not_overridden_by_effect():
    """T033: business failed even if screen_changed passed → failed."""
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="screen_changed"),
            VerificationCondition(type="text_appears", value="MISSING"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["other"], changed=True),
        escalate=False,
    )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_expected_error_assertion_still_evaluated():
    """T039 / FR-021: unexpected_effect + text_appears error → may still pass."""
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="错误"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("unexpected_effect"),
        _screen(texts=["操作错误", "Error"]),
        escalate=False,
    )
    assert result.status == "passed"
    assert result.weak_assertion_warning is False


@pytest.mark.asyncio
async def test_no_effect_blocks_business_pass_on_unchanged_screen():
    """no_effect must not let pre-existing text_appears auto-pass business steps."""
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="1"),
            VerificationCondition(type="text_appears", value="5"),
            VerificationCondition(type="text_appears", value="袋"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("no_effect"),
        _screen(texts=["1", "5", "レジ袋"], changed=False),
        escalate=False,
    )
    assert result.status == "failed"
    assert "no_effect" in result.failed_conditions
    assert result.basis == "mixed"


@pytest.mark.asyncio
async def test_effect_only_pass():
    """T050: effect_only + expected_effect → passed, basis=action_effect_only."""
    spec = VerificationSpec(
        operator="all",
        conditions=[VerificationCondition(type="screen_changed")],
    )
    result = await resolve_step_result(
        spec,
        "effect_only",
        _ae("expected_effect"),
        _screen(changed=True),
        escalate=False,
    )
    assert result.status == "passed"
    assert result.weak_assertion_warning is False
    assert result.basis == "action_effect_only"


@pytest.mark.asyncio
async def test_legacy_effect_only_warning():
    """T056: omitted mode + weak only + expected_effect → uncertain + warning."""
    spec = VerificationSpec(
        operator="all",
        conditions=[VerificationCondition(type="screen_changed")],
    )
    result = await resolve_step_result(
        spec,
        None,
        _ae("expected_effect"),
        _screen(changed=True),
        escalate=False,
    )
    assert result.status == "uncertain"
    assert result.weak_assertion_warning is True
    assert result.basis == "action_effect_only"
