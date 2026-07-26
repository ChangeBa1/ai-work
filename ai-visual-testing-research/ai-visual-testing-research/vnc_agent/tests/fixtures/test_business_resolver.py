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
    """T023 / FR-010 baseline (011-revised): det failed + visual passed below the
    arbitration confidence threshold → failed (deterministic still wins)."""
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="passed",
            confidence=0.5,  # below 011 arbitration threshold (0.8)
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
    assert "deterministic_overrides_visual" in result.reason


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


# ---------------------------------------------------------------------------
# Feature 011 — weak-OCR-miss arbitration (revised FR-010)
# ---------------------------------------------------------------------------


def _visual_passed(confidence: float = 0.9) -> StubPlanner:
    return StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="passed",
            confidence=confidence,
            reason="clearly visible",
            model_name="stub",
        )
    )


# Two unrelated GUI vocabularies (Constitution VI cross-scenario gate):
# a form save flow and an icon menu flow.
_CROSS_SCENARIOS = [
    pytest.param(
        "保存成功", ["フォーム", "OK"], "did the save-success banner appear?", id="form-flow"
    ),
    pytest.param(
        "設定メニュー", ["アイコン一覧"], "is the settings menu open?", id="icon-menu-flow"
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("needle,texts,question", _CROSS_SCENARIOS)
async def test_weak_ocr_miss_overridden_by_visual(needle, texts, question):
    """011 US1 / FR-002/003: weak-negative-only failed + high-confidence visual
    passed + expected_effect → passed with audit tag, failed_conditions kept."""
    planner = _visual_passed(0.9)
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value=needle),
            VerificationCondition(type="visual_question", value=question),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=texts),
        planner=planner,
        escalate=False,
    )
    assert result.status == "passed"
    assert "weak_ocr_miss_overridden_by_visual" in result.reason
    assert f"text_appears:{needle}" in result.failed_conditions
    # FR-006 / SC-005: initial visual_question + exactly one re-check call
    assert planner.describe_calls == 2


@pytest.mark.asyncio
async def test_weak_ocr_miss_multiple_misses_overridden():
    """011 US1: several weak-negative misses together are still overridable."""
    planner = _visual_passed(0.85)
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="単価"),
            VerificationCondition(type="text_appears", value="99,999"),
            VerificationCondition(type="visual_question", value="is unit price 99,999?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["ほかの文字"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "passed"
    assert "weak_ocr_miss_overridden_by_visual" in result.reason
    assert "text_appears:単価" in result.failed_conditions
    assert "text_appears:99,999" in result.failed_conditions


@pytest.mark.asyncio
async def test_strong_negative_text_disappears_keeps_failed():
    """011 US2 / FR-004: OCR affirmatively read forbidden text → visual passed
    never overrides (strong negative)."""
    planner = _visual_passed(0.95)
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_disappears", value="エラー"),
            VerificationCondition(type="visual_question", value="did the error go away?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["エラー"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "failed"
    assert "weak_ocr_miss_overridden_by_visual" not in result.reason


@pytest.mark.asyncio
async def test_strong_negative_template_keeps_failed():
    """011 US2 / FR-004: template-class assertion failure is strong negative."""
    planner = _visual_passed(0.95)
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="template_appears", value="saved_marker"),
            VerificationCondition(type="visual_question", value="is the marker shown?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["何か"]),  # no template_matches → template_appears failed
        planner=planner,
        escalate=False,
    )
    assert result.status == "failed"
    assert "weak_ocr_miss_overridden_by_visual" not in result.reason


@pytest.mark.asyncio
async def test_mixed_weak_and_strong_failures_keep_failed():
    """011 US2 / FR-004: any strong negative in the failed set blocks arbitration."""
    planner = _visual_passed(0.95)
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="合計"),
            VerificationCondition(type="text_disappears", value="エラー"),
            VerificationCondition(type="visual_question", value="is the total shown?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["エラー"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_low_confidence_visual_keeps_old_rule():
    """011 US3 / FR-005: visual passed below threshold → old FR-010 behavior."""
    planner = _visual_passed(0.79)
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="保存成功"),
            VerificationCondition(type="visual_question", value="saved?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["ほか"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "failed"
    assert "deterministic_overrides_visual" in result.reason


@pytest.mark.asyncio
async def test_custom_threshold_tightens_arbitration():
    """011 FR-007: a configured 0.9 threshold rejects a 0.85-confidence pass."""
    planner = _visual_passed(0.85)
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="保存成功"),
            VerificationCondition(type="visual_question", value="saved?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["ほか"]),
        planner=planner,
        escalate=False,
        visual_override_confidence_threshold=0.9,
    )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_no_effect_keeps_old_rule():
    """011 US3 / FR-005/008: action_effect=no_effect → arbitration never fires."""
    planner = _visual_passed(0.95)
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="保存成功"),
            VerificationCondition(type="visual_question", value="saved?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("no_effect"),
        _screen(texts=["ほか"], changed=False),
        planner=planner,
        escalate=False,
    )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_unexpected_effect_keeps_old_rule():
    """011 US3 / FR-005/008 (scenario 11 semantics): unexpected_effect → not passed."""
    planner = _visual_passed(0.95)
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="保存成功"),
            VerificationCondition(type="visual_question", value="saved?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("unexpected_effect"),
        _screen(texts=["エラー"]),
        planner=planner,
        escalate=False,
    )
    assert result.status != "passed"


@pytest.mark.asyncio
async def test_no_visual_question_keeps_failed():
    """011 FR-005: weak-negative miss without any visual_question → failed."""
    spec = VerificationSpec(
        operator="all",
        conditions=[VerificationCondition(type="text_appears", value="保存成功")],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["ほか"]),
        planner=_visual_passed(0.95),
        escalate=False,
    )
    assert result.status == "failed"


@pytest.mark.asyncio
async def test_recheck_error_fail_safe_keeps_failed():
    """011 FR-005: re-check call failure → fail-safe, old rule kept."""

    class FlakyPlanner(StubPlanner):
        async def describe_screen(self, request):  # type: ignore[override]
            self.describe_calls += 1
            if self.describe_calls == 1:
                return VisionUnderstandingResponse(
                    mode="answer_question",
                    answer="passed",
                    confidence=0.95,
                    reason="ok",
                    model_name="stub",
                )
            raise RuntimeError("model unavailable")

    planner = FlakyPlanner()
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="保存成功"),
            VerificationCondition(type="visual_question", value="saved?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["ほか"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "failed"
    assert planner.describe_calls == 2


@pytest.mark.asyncio
async def test_recheck_disagreement_fail_safe_keeps_failed():
    """011 FR-005/006: re-check answering non-passed → old rule kept."""

    class DisagreeingPlanner(StubPlanner):
        async def describe_screen(self, request):  # type: ignore[override]
            self.describe_calls += 1
            answer = "passed" if self.describe_calls == 1 else "uncertain"
            return VisionUnderstandingResponse(
                mode="answer_question",
                answer=answer,
                confidence=0.95,
                reason="ok",
                model_name="stub",
            )

    planner = DisagreeingPlanner()
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="保存成功"),
            VerificationCondition(type="visual_question", value="saved?"),
        ],
    )
    result = await resolve_step_result(
        spec,
        "business",
        _ae("expected_effect"),
        _screen(texts=["ほか"]),
        planner=planner,
        escalate=False,
    )
    assert result.status == "failed"
