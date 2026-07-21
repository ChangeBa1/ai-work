"""US2 T030: bag count 0→1; identical re-proposal blocked — execute once only."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import cv2
import numpy as np
import pytest

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner
from tests.e2e.conftest import FakeVNC, build_runtime


def _frames_bag_0_to_1() -> list[np.ndarray]:
    """Before: blank-ish; after first click: local badge region white."""
    base = np.zeros((200, 300, 3), dtype=np.uint8)
    base[80:120, 100:200] = (0, 200, 0)  # button region for OCR/grounding bbox
    after = base.copy()
    after[10:50, 240:290] = 255  # cart badge local change
    # Sequence: observe before, wait frames, after observe, re-observe, next before...
    return [base, base, after, after, after, after, after]


@pytest.mark.asyncio
async def test_no_duplicate_add_bag_click(tmp_path: Path, app_config):
    action = SemanticAction(
        action_id="add-bag",
        intent="点击レジ袋加入购物袋",
        action_type="click",
        target=TargetDescription(text="unique-bag-btn-xyz"),
        action_kind="non_idempotent",
    )
    planner = StubPlanner(action=action)
    grounder = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(100, 80, 200, 120), confidence=0.95, reason="ok"
                )
            ],
            model_name="stub",
        )
    )
    case = TestCase(
        id="no-dup",
        name="no-dup",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="add-shopping-bag",
                name="加入购物袋",
                intent="点击レジ袋加入购物袋",
                max_retries=2,
                # Omitted verification_mode + screen_changed only → uncertain (weak),
                # so RepeatGuard blocks the second semantically identical non-idempotent click
                expected=VerificationSpec(
                    operator="all",
                    conditions=[
                        VerificationCondition(type="screen_changed", value="")
                    ],
                ),
            )
        ],
    )
    drv = FakeVNC(frames=_frames_bag_0_to_1())
    runtime, _ = await build_runtime(
        tmp_path, app_config, driver=drv, planner=planner, grounder=grounder
    )

    execute_calls: list = []
    original = runtime.executor.execute

    async def tracked_execute(executable):
        execute_calls.append(executable)
        return await original(executable)

    runtime.executor.execute = tracked_execute  # type: ignore[method-assign]

    ctx = await runtime.run(case)
    step = ctx.test_run.steps[0]
    # Count only click-like executes for the bag action
    bag_execs = [
        e
        for e in execute_calls
        if e.operation in ("click", "double_click", "right_click")
        or (e.method == "mouse")
    ]
    assert len(bag_execs) == 1, (
        f"expected exactly one execute for add-bag, got {len(bag_execs)}; "
        f"iterations={len(step.iterations)}; "
        f"guards={[it.repeat_guard_decision for it in step.iterations]}"
    )
