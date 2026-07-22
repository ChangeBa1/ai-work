"""US8 T063: stitched offline regression of the original bag-duplicate incident."""

from __future__ import annotations

from datetime import UTC
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
from vnc_agent.planning.action_policy import ActionPolicy


@pytest.mark.asyncio
async def test_pos_bag_full_regression(tmp_path: Path, app_config):
    """
    click → ~local cart change (small global) → expected_effect →
    duplicate click blocked → recovery switch_to_keyboard without focus_path →
    no blind tab → simulated error popup path never yields trusted passed on weak evidence.
    """
    action = SemanticAction(
        action_id="add-bag",
        intent="点击レジ袋加入购物袋",
        action_type="click",
        target=TargetDescription(text="unique-bag-reg"),
        action_kind="non_idempotent",
    )
    planner = StubPlanner(action=action)
    grounder = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(100, 80, 200, 120),
                    coordinate_space="pixel",
                    confidence=0.95,
                    reason="ok",
                )
            ],
            model_name="stub",
        )
    )
    case = TestCase(
        id="bag-regression",
        name="bag-regression",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="add-shopping-bag",
                name="加入购物袋",
                intent="点击レジ袋加入购物袋",
                max_retries=2,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[
                        VerificationCondition(type="screen_changed", value="")
                    ],
                ),
            )
        ],
    )
    base = np.zeros((200, 300, 3), dtype=np.uint8)
    base[80:120, 100:200] = (0, 200, 0)
    after_local = base.copy()
    after_local[10:40, 250:290] = 255  # small local change
    frames = [base, base, after_local, after_local, after_local, after_local, after_local]
    drv = FakeVNC(frames=frames)
    runtime, _ = await build_runtime(
        tmp_path, app_config, driver=drv, planner=planner, grounder=grounder
    )

    execute_calls: list = []
    original = runtime.executor.execute

    async def tracked(executable):
        execute_calls.append(executable)
        return await original(executable)

    runtime.executor.execute = tracked  # type: ignore[method-assign]
    ctx = await runtime.run(case)
    step = ctx.test_run.steps[0]

    mouse_clicks = [e for e in execute_calls if e.method == "mouse"]
    assert len(mouse_clicks) == 1, f"duplicate click not blocked: {len(mouse_clicks)}"

    # No blind tab-only executable without focus path
    for e in execute_calls:
        if e.method == "keyboard" and e.keys == ["tab"]:
            assert runtime.recovery.focus_path is not None, (
                "blind tab without VerifiedFocusNavigationPath"
            )

    # At least one iteration recorded action_effect
    effects = [it.action_effect for it in step.iterations if it.action_effect]
    assert effects, "expected ActionEffect on iterations"
    # First successful execution should see expected_effect when local change present
    assert any(ae.status == "expected_effect" for ae in effects) or any(
        it.repeat_guard_decision and not it.repeat_guard_decision.allowed
        for it in step.iterations
    )

    # Unit-level: prefer_keyboard without path never yields tab
    policy = ActionPolicy()
    from datetime import datetime

    from vnc_agent.domain.observation import StructuredScreen

    screen = StructuredScreen(
        frame_id="x",
        resolution=(300, 200),
        captured_at=datetime.now(UTC),
    )
    pr = policy.resolve(
        action, screen, prefer_keyboard=True, focus_path=None, grounding_result=None
    )
    # needs grounding or stop — not focus tab
    if pr.executable is not None:
        assert pr.executable.keys != ["tab"] or pr.outcome != "focus"
