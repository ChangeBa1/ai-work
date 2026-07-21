"""E2E scenario 5: multi-iteration + recovery upgrade persistence (T097/T098)."""

from pathlib import Path

import pytest

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.recovery import FailureType
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner
from tests.e2e.conftest import build_runtime


def _failing_case(*, max_retries: int = 2) -> TestCase:
    return TestCase(
        id="multi",
        name="multi",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="s1",
                name="s1",
                intent="click target",
                max_retries=max_retries,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[
                        VerificationCondition(type="text_appears", value="NOPE")
                    ],
                ),
            )
        ],
    )


@pytest.mark.asyncio
async def test_budget_exhaustion_keeps_iterations(tmp_path: Path, app_config):
    case = TestCase(
        id="multi",
        name="multi",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="s1",
                name="s1",
                intent="press escape",
                max_retries=2,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[
                        VerificationCondition(type="text_appears", value="NOPE")
                    ],
                ),
            )
        ],
    )
    runtime, _ = await build_runtime(tmp_path, app_config)
    ctx = await runtime.run(case)
    assert ctx.test_run.status == "failed"
    step = ctx.test_run.steps[0]
    assert step.final_status == "failed"
    assert len(step.iterations) >= 2  # first + retries


@pytest.mark.asyncio
async def test_second_candidate_upgrade_across_iterations(tmp_path: Path, app_config):
    """
    T098: grounding_low_confidence → second_candidate must raise candidate_index
    for the *next* ActionIteration (fails before T097 fix).
    """
    planner = StubPlanner(
        action=SemanticAction(
            action_id="c1",
            intent="click ambiguous target",
            action_type="click",
            target=TargetDescription(
                text="unique-non-ocr-target-xyz",
                description="ambiguous button",
            ),
        )
    )
    # Top-1 / Top-2 close → grounding_low_confidence / top1_top2_close
    c0 = GroundingCandidate(
        bbox=(100, 80, 140, 120), confidence=0.90, reason="top1"
    )
    c1 = GroundingCandidate(
        bbox=(160, 80, 200, 120), confidence=0.89, reason="top2"
    )
    grounder = StubGrounder(
        GroundingResult(found=True, candidates=[c0, c1], model_name="stub")
    )
    runtime, drv = await build_runtime(
        tmp_path, app_config, planner=planner, grounder=grounder
    )
    ctx = await runtime.run(_failing_case(max_retries=2))
    step = ctx.test_run.steps[0]
    assert len(step.iterations) >= 2

    it0 = step.iterations[0]
    assert it0.recovery_attempts, "iter0 should record recovery"
    assert any(
        a.strategy == "second_candidate"
        and a.failure_type == FailureType.GROUNDING_LOW_CONFIDENCE
        for a in it0.recovery_attempts
    ), f"expected second_candidate on iter0, got {it0.recovery_attempts}"

    # After T097 fix, recovery.candidate_index remains elevated for subsequent iters
    assert runtime.recovery.candidate_index >= 1

    # Iteration 1 must actually *use* the second candidate (not re-stop on top1)
    it1 = step.iterations[1]
    assert it1.executable_action is not None, (
        "iter1 should resolve an executable via second_candidate upgrade; "
        "if None, reset_iteration() is still wiping candidate_index each loop"
    )
    assert it1.executable_action.method == "mouse"
    assert it1.executable_action.coordinates == c1.center()
    # Click went to second candidate bbox, not the first
    if drv.clicks:
        assert drv.clicks[0] == c1.center()


@pytest.mark.asyncio
async def test_switch_to_keyboard_upgrade_across_iterations(
    tmp_path: Path, app_config
):
    """
    T098: action_no_effect recovery escalates second_candidate → switch_to_keyboard;
    prefer_keyboard must stick for a later ActionIteration (fails before T097 fix).
    """
    planner = StubPlanner(
        action=SemanticAction(
            action_id="c1",
            intent="click solid target",
            action_type="click",
            target=TargetDescription(
                text="unique-non-ocr-target-abc",
                description="solid button",
            ),
        )
    )
    # High confidence single candidate so first resolve executes a mouse click
    cand = GroundingCandidate(
        bbox=(100, 80, 200, 120), confidence=0.95, reason="ok"
    )
    grounder = StubGrounder(
        GroundingResult(found=True, candidates=[cand], model_name="stub")
    )
    runtime, drv = await build_runtime(
        tmp_path, app_config, planner=planner, grounder=grounder
    )
    # Need enough iterations for: execute → action_no_effect/second_candidate →
    # execute → action_no_effect/switch_to_keyboard → keyboard path
    ctx = await runtime.run(_failing_case(max_retries=3))
    step = ctx.test_run.steps[0]
    assert len(step.iterations) >= 2

    strategies = [
        a.strategy
        for it in step.iterations
        for a in it.recovery_attempts
        if a.failure_type == FailureType.ACTION_NO_EFFECT
    ]
    assert "switch_to_keyboard" in strategies or runtime.recovery.prefer_keyboard, (
        f"expected switch_to_keyboard escalation, strategies={strategies}, "
        f"prefer_keyboard={runtime.recovery.prefer_keyboard}"
    )

    # 002 US5: prefer_keyboard sticks, but without VerifiedFocusNavigationPath
    # ActionPolicy MUST NOT emit a blind keys=["tab"] focus action.
    assert runtime.recovery.prefer_keyboard is True
    blind_tabs = [
        it
        for it in step.iterations
        if it.executable_action is not None
        and it.executable_action.method == "keyboard"
        and it.executable_action.keys == ["tab"]
        and runtime.recovery.focus_path is None
    ]
    # When focus_path was never constructed, no iteration should be pure blind-tab
    if runtime.recovery.focus_path is None:
        assert not blind_tabs or all(
            it.executable_action.keys != ["tab"]  # type: ignore[union-attr]
            for it in step.iterations
            if it.executable_action is not None
            and it.executable_action.method == "keyboard"
            and it.semantic_action is not None
            and it.semantic_action.action_type in ("click", "double_click", "right_click")
        )
