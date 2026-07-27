"""Feature 009 E2E (T005/T009/T011/T014/T016): planner short-circuit on
duplicate frame + repeat-guard-blocked action.

Two unrelated GUI scenarios (Constitution Principle VI two-scenario rule):
mouse click flow (shopping-style button, scenario-10 fixtures) and a
keyboard flow (non-idempotent enter keypress) — both business-agnostic in
core; scenario semantics live only here.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from tests.e2e.conftest import FakeVNC, build_runtime
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.runtime.telemetry import derive_performance_summary

SKIP = "duplicate_frame_blocked_action"
TRIGGER_REASONS = {
    "blocked_effect_pending",
    "blocked_effect_pending_normalized_target",
    "ambiguous_fail_safe",
}


def _frames_change_once_then_freeze() -> list[np.ndarray]:
    """Before: base; after first action: one local change; then frozen."""
    base = np.zeros((200, 300, 3), dtype=np.uint8)
    base[80:120, 100:200] = (0, 200, 0)  # button region for OCR/grounding bbox
    after = base.copy()
    after[10:50, 240:290] = 255  # local badge-like change
    return [base, base, after, after, after, after, after, after, after]


def _click_planner() -> StubPlanner:
    return StubPlanner(
        action=SemanticAction(
            action_id="add-item",
            intent="click the add button",
            action_type="click",
            target=TargetDescription(text="unique-add-btn-xyz"),
            action_kind="non_idempotent",
        )
    )


def _grounder() -> StubGrounder:
    return StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(100, 80, 200, 120),
                    confidence=0.95,
                    reason="ok",
                    coordinate_space="pixel",
                )
            ],
            model_name="stub",
        )
    )


def _click_case(*, max_retries: int = 3, timeout_seconds: int | None = None) -> TestCase:
    return TestCase(
        id="skip-replan",
        name="skip-replan",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="click-add",
                name="click add",
                intent="click the add button",
                max_retries=max_retries,
                # Weak screen_changed-only assertion -> uncertain, so
                # RepeatGuard blocks the identical non-idempotent re-proposal
                expected=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="screen_changed", value="")],
                    timeout_seconds=timeout_seconds,
                ),
            )
        ],
    )


async def _run_click_scenario(tmp_path, app_config, **case_kwargs):
    planner = _click_planner()
    drv = FakeVNC(frames=_frames_change_once_then_freeze())
    runtime, _ = await build_runtime(
        tmp_path, app_config, driver=drv, planner=planner, grounder=_grounder()
    )
    ctx = await runtime.run(_click_case(**case_kwargs))
    return ctx, planner


# --- US1: skip fires; US2: budget-safe termination --------------------------


@pytest.mark.asyncio
async def test_skip_replan_on_frozen_screen(tmp_path: Path, app_config):
    ctx, planner = await _run_click_scenario(tmp_path, app_config, max_retries=3)
    step = ctx.test_run.steps[0]

    assert len(step.iterations) == 4  # first + max_retries, unchanged budget
    assert step.final_status == "failed"
    assert ctx.test_run.status == "failed"

    it0, it1, it2, it3 = step.iterations
    # it0 planned + executed; it1 planned but blocked by RepeatGuard
    assert it0.planner_skipped_reason is None
    assert it1.planner_skipped_reason is None
    assert it1.repeat_guard_decision is not None
    assert it1.repeat_guard_decision.allowed is False
    assert it1.repeat_guard_decision.reason in TRIGGER_REASONS

    # it2/it3: identical frame + blocked previous action -> planner skipped
    for it in (it2, it3):
        assert it.planner_skipped_reason == SKIP
        assert it.semantic_action is None
        assert it.executable_action is None
        assert it.execution_result is None
        # carried copy of the blocking decision (contract §4)
        assert it.repeat_guard_decision is not None
        assert it.repeat_guard_decision.allowed is False
        assert it.repeat_guard_decision.reason == it1.repeat_guard_decision.reason

    # duplicate-frame precondition actually held (auditable via FR-009 field)
    assert it1.before_content_hash is not None
    assert it2.before_content_hash == it1.before_content_hash
    assert it3.before_content_hash == it1.before_content_hash

    # planner called exactly twice: initial plan + the blocked re-plan
    assert planner.plan_calls == 2


@pytest.mark.asyncio
async def test_skip_iterations_consume_budget_and_step_fails(tmp_path: Path, app_config):
    ctx, planner = await _run_click_scenario(tmp_path, app_config, max_retries=2)
    step = ctx.test_run.steps[0]
    # Exactly max_retries + 1 iterations — a skipped round consumes budget
    # like any other round; no extra rounds, no new terminal state.
    assert len(step.iterations) == 3
    assert step.final_status == "failed"
    assert step.failure_reason is not None
    assert planner.plan_calls == 2
    assert step.iterations[2].planner_skipped_reason == SKIP


# --- US3: observability -----------------------------------------------------


@pytest.mark.asyncio
async def test_skip_telemetry_and_report(tmp_path: Path, app_config):
    ctx, planner = await _run_click_scenario(tmp_path, app_config, max_retries=3)
    run = ctx.test_run
    step = run.steps[0]
    skipped = [it for it in step.iterations if it.planner_skipped_reason == SKIP]
    assert len(skipped) == 2

    # model_call counter events: planner count equals actual plan calls
    planner_calls = [
        e
        for e in run.counter_events
        if e.kind == "model_call" and e.payload.get("model_role") == "planner"
    ]
    assert len(planner_calls) == planner.plan_calls == 2

    # one model_call_skipped event per skipped round, with required payload
    skipped_events = [e for e in run.counter_events if e.kind == "model_call_skipped"]
    assert len(skipped_events) == len(skipped)
    for e in skipped_events:
        assert e.payload["model_role"] == "planner"
        assert e.payload["reason"] == SKIP
        assert e.payload["request_identity"]

    # one outcome="skipped" planner audit per skipped round
    skipped_audits = [
        a
        for a in run.model_call_audits
        if a.model_role == "planner" and a.outcome == "skipped"
    ]
    assert len(skipped_audits) == len(skipped)
    assert all(a.reason == SKIP for a in skipped_audits)
    actual_planner_audits = [
        a
        for a in run.model_call_audits
        if a.model_role == "planner" and a.outcome == "actual"
    ]
    assert len(actual_planner_audits) == 2

    # no planner StageMeasurement for skipped iteration indexes
    skipped_indexes = {it.iteration_index for it in skipped}
    planner_stages = [m for m in run.stage_measurements if m.stage == "planner"]
    assert all(m.iteration_index not in skipped_indexes for m in planner_stages)
    assert len(planner_stages) == 2

    # derived summary: conservation, planner count did not grow
    summary = derive_performance_summary(run)
    assert summary.model_calls.get("planner", 0) == 2
    assert summary.skipped_model_call_count == len(skipped)

    # JSON report carries the marker (FR-007, additive key)
    assert run.report_json_path is not None
    report = json.loads(Path(run.report_json_path).read_text(encoding="utf-8"))
    report_iters = report["steps"][0]["iterations"]
    markers = [it["planner_skipped_reason"] for it in report_iters]
    assert markers == [None, None, SKIP, SKIP]


# --- US4: time-dependent exception protection -------------------------------


@pytest.mark.asyncio
async def test_no_skip_when_verification_declares_timeout(tmp_path: Path, app_config):
    ctx, planner = await _run_click_scenario(
        tmp_path, app_config, max_retries=3, timeout_seconds=5
    )
    step = ctx.test_run.steps[0]
    assert all(it.planner_skipped_reason is None for it in step.iterations)
    # planner consulted on every iteration — SC-005: zero behavior change
    assert planner.plan_calls == len(step.iterations)
    assert not [e for e in ctx.test_run.counter_events if e.kind == "model_call_skipped"]


# --- Second unrelated scenario: keyboard flow (Principle VI) ----------------


@pytest.mark.asyncio
async def test_skip_replan_keyboard_flow(tmp_path: Path, app_config):
    """Non-idempotent keypress flow: screen changes once after the first
    enter, then freezes; the identical re-proposal is blocked and further
    identical-frame rounds skip the planner. No mouse involved."""
    planner = StubPlanner(
        action=SemanticAction(
            action_id="confirm",
            intent="press enter to confirm",
            action_type="press_key",
            keys=["enter"],
            action_kind="non_idempotent",
        )
    )
    drv = FakeVNC(frames=_frames_change_once_then_freeze())
    runtime, _ = await build_runtime(tmp_path, app_config, driver=drv, planner=planner)
    case = TestCase(
        id="skip-replan-kbd",
        name="skip-replan-kbd",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="confirm-dialog",
                name="confirm dialog",
                intent="press enter to confirm",
                max_retries=3,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="screen_changed", value="")],
                ),
            )
        ],
    )
    ctx = await runtime.run(case)
    step = ctx.test_run.steps[0]

    assert len(step.iterations) == 4
    assert step.final_status == "failed"
    skipped = [it for it in step.iterations if it.planner_skipped_reason == SKIP]
    assert len(skipped) == 2
    assert planner.plan_calls == 2
    # only one enter was ever sent — skip path never executes anything
    assert drv.keys.count("enter") == 1
    summary = derive_performance_summary(ctx.test_run)
    assert summary.model_calls.get("planner", 0) == 2
    assert summary.skipped_model_call_count == 2
