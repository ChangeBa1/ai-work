"""Feature 005 T009: cross-scenario, offline proof that a declared
batch_repeat_key step resolves to exactly one ActionIteration, with zero
Planner/Grounder calls and zero screenshots between the individual key
sends — using a generic, business-agnostic fixture (the ScannerSimulator
scenario is the second, unrelated scenario — see
testcases/pos-scan-magazine-checkout.yaml)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tests.e2e.conftest import FakeVNC, build_runtime
from vnc_agent.domain.testcase import TestCase, TestStep, load_test_case
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner

FIXTURE_CASE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "testcases"
    / "generic-batch-repeat-key-example.yaml"
)


def _frames_field_cleared() -> list[np.ndarray]:
    base = np.zeros((200, 300, 3), dtype=np.uint8)
    base[80:120, 100:200] = (0, 200, 0)
    after = base.copy()
    after[10:50, 240:290] = 255
    return [base, after]


@pytest.mark.asyncio
async def test_batch_repeat_key_runs_as_one_iteration_no_intermediate_calls(
    tmp_path: Path, app_config
):
    case = load_test_case(FIXTURE_CASE)
    assert case.steps[0].batch_repeat_key is not None
    assert case.steps[0].batch_repeat_key.count == 5

    drv = FakeVNC(frames=_frames_field_cleared())
    planner = StubPlanner()
    grounder = StubGrounder()
    runtime, _ = await build_runtime(
        tmp_path, app_config, driver=drv, planner=planner, grounder=grounder
    )

    ctx = await runtime.run(case)

    # No Planner or Grounder call at all for this step.
    assert planner.plan_calls == 0
    assert grounder.calls == []

    # Exactly one ActionIteration for the whole batch, not one per key.
    step = ctx.test_run.steps[0]
    assert len(step.iterations) == 1
    it = step.iterations[0]

    # The batch sent exactly 5 backspaces, consecutively.
    assert drv.keys == ["backspace"] * 5
    assert it.execution_result is not None
    assert it.execution_result.requested_count == 5
    assert it.execution_result.completed_count == 5

    # No capture happened *between* the individual key sends — the 5
    # "key:backspace" entries in the shared call log are contiguous, with
    # no "capture" entry interleaved (captures from the pre-action
    # observation and the post-action wait/verify are expected before and
    # after this contiguous block, just not inside it).
    key_indices = [i for i, entry in enumerate(drv.call_log) if entry == "key:backspace"]
    assert len(key_indices) == 5
    span = drv.call_log[key_indices[0] : key_indices[-1] + 1]
    assert all(entry == "key:backspace" for entry in span)

    # Exactly one post-action verification was recorded for the step.
    assert it.verification_result is not None


# --- T027 (converge finding F2): post-action wait/verify still run when the
# batch is interrupted (FR-004 "...or is interrupted" / Constitution IV) ---


class FaultyFakeVNC(FakeVNC):
    """FakeVNC whose send_key fails on a specific 1-indexed call number,
    matching KeyboardExecutor.press_key_repeat's fail-fast contract: the
    failing call itself is never recorded (it didn't succeed)."""

    def __init__(self, *, fail_at_call_number: int, frames=None):
        super().__init__(frames=frames)
        self.fail_at_call_number = fail_at_call_number
        self._send_key_call_count = 0

    async def send_key(self, key: str) -> None:
        self._send_key_call_count += 1
        if self._send_key_call_count == self.fail_at_call_number:
            raise RuntimeError("simulated VNC send failure")
        await super().send_key(key)


@pytest.mark.asyncio
async def test_interrupted_batch_still_runs_post_action_wait_and_verify(
    tmp_path: Path, app_config
):
    case = TestCase(
        id="batch-repeat-interrupted",
        name="batch-repeat-interrupted",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="clear-field-interrupted",
                name="clear field (interrupted)",
                intent="clear field via batch backspace",
                max_retries=1,
                batch_repeat_key={"key": "backspace", "count": 20},
                verification_mode="effect_only",
                expected=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="screen_changed", value="")],
                ),
            )
        ],
    )

    drv = FaultyFakeVNC(fail_at_call_number=8, frames=_frames_field_cleared())
    planner = StubPlanner()
    grounder = StubGrounder()
    runtime, _ = await build_runtime(
        tmp_path, app_config, driver=drv, planner=planner, grounder=grounder
    )

    ctx = await runtime.run(case)

    step = ctx.test_run.steps[0]
    assert len(step.iterations) == 1
    it = step.iterations[0]

    # The batch was interrupted after 7 successful sends (the 8th failed).
    assert it.execution_result is not None
    assert it.execution_result.success is False
    assert it.execution_result.requested_count == 20
    assert it.execution_result.completed_count == 7
    assert it.execution_result.error_code == "key_repeat_partial"

    # Post-action stability wait and verification still ran, on this same
    # single iteration, despite the interruption (FR-004 / Constitution IV —
    # verification is independent, evidence-based, and MUST NOT be skipped
    # just because the action reported failure).
    assert it.wait_result is not None
    assert it.verification_result is not None
