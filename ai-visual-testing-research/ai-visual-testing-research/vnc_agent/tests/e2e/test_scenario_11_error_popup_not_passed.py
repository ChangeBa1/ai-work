"""US4 T043: error popup after action → StepVerificationResult never passed on weak evidence."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner
from tests.e2e.conftest import FakeVNC, build_runtime


@pytest.mark.asyncio
async def test_error_popup_never_passed_on_weak_evidence(tmp_path: Path, app_config):
    before = np.zeros((200, 300, 3), dtype=np.uint8)
    before[80:120, 100:200] = (0, 200, 0)
    after = before.copy()
    after[20:180, 30:270] = 200  # large dialog-like change

    planner = StubPlanner(
        action=SemanticAction(
            action_id="c1",
            intent="click submit",
            action_type="click",
            target=TargetDescription(text="unique-submit-xyz"),
        )
    )
    grounder = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(bbox=(100, 80, 200, 120), confidence=0.95, reason="ok")
            ],
            model_name="stub",
        )
    )
    # Inject OCR error keyword on after-frame by patching pipeline is heavy;
    # use weak-only step + manually force ActionEffect via error path:
    # Prefer business-less screen_changed step so weak path applies.
    case = TestCase(
        id="err-popup",
        name="err-popup",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="s1",
                name="submit",
                intent="click submit",
                max_retries=0,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="screen_changed")],
                ),
            )
        ],
    )
    drv = FakeVNC(frames=[before, before, after, after, after])
    runtime, _ = await build_runtime(
        tmp_path, app_config, driver=drv, planner=planner, grounder=grounder
    )

    # Force error keyword detection by monkeypatching classify on runtime path
    from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
    from vnc_agent.domain.observation import OCRItem
    import vnc_agent.runtime.agent_runtime as ar

    real_classify = ar.classify_action_effect

    def classify_with_error(before_s, after_s, **kwargs):
        # Attach error OCR to after
        after_s = after_s.model_copy(
            update={
                "ocr_items": [
                    OCRItem(
                        text="Error: failed",
                        bbox=(40, 40, 200, 70),
                        confidence=0.99,
                    )
                ]
            }
        )
        return real_classify(before_s, after_s, **kwargs)

    ar.classify_action_effect = classify_with_error  # type: ignore[assignment]
    try:
        ctx = await runtime.run(case)
    finally:
        ar.classify_action_effect = real_classify  # type: ignore[assignment]

    step = ctx.test_run.steps[0]
    assert step.iterations
    last = step.iterations[-1]
    assert last.verification_result is not None
    assert last.verification_result.status in ("failed", "uncertain")
    assert last.verification_result.status != "passed"
    if last.action_effect is not None:
        assert last.action_effect.status == "unexpected_effect"
