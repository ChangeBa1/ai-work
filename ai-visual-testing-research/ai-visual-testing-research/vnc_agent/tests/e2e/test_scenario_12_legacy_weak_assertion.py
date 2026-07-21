"""US7 T062: legacy pos-buy-bag-checkout offline → uncertain + weak_assertion_warning."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.testcase import load_test_case
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner
from tests.e2e.conftest import FakeVNC, build_runtime

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
async def test_legacy_weak_assertion_uncertain(tmp_path: Path, app_config):
    path = ROOT / "testcases" / "pos-buy-bag-checkout.yaml"
    if not path.exists():
        # Minimal legacy-shaped case if sample missing
        data = {
            "id": "legacy-bag",
            "name": "legacy",
            "target_id": "win10-test-01",
            "mode": "explicit",
            "steps": [
                {
                    "id": "add-shopping-bag",
                    "name": "加入购物袋商品",
                    "intent": "点击レジ袋",
                    "max_retries": 0,
                    "expected": {
                        "operator": "all",
                        "conditions": [{"type": "screen_changed", "value": ""}],
                    },
                }
            ],
        }
        p = tmp_path / "legacy.yaml"
        p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        case = load_test_case(p)
    else:
        case = load_test_case(path)
        # Run only the first weak-only step to keep offline run short
        case = case.model_copy(update={"steps": case.steps[:1]})
        case.steps[0] = case.steps[0].model_copy(update={"max_retries": 0})

    step_id = case.steps[0].id
    planner = StubPlanner(
        action=SemanticAction(
            action_id="a1",
            intent=case.steps[0].intent,
            action_type="click",
            target=TargetDescription(text="unique-bag-legacy"),
            action_kind="non_idempotent",
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
    base = np.zeros((200, 300, 3), dtype=np.uint8)
    base[80:120, 100:200] = (0, 200, 0)
    after = base.copy()
    after[10:50, 240:290] = 255
    drv = FakeVNC(frames=[base, base, after, after, after])
    runtime, _ = await build_runtime(
        tmp_path, app_config, driver=drv, planner=planner, grounder=grounder
    )
    ctx = await runtime.run(case)
    step = next(s for s in ctx.test_run.steps if s.step_id == step_id)
    assert step.iterations
    last = step.iterations[-1]
    assert last.verification_result is not None
    assert last.verification_result.status == "uncertain"
    assert last.verification_result.weak_assertion_warning is True
    assert last.verification_result.status != "passed"
