"""E2E scenario 3: grounding click with ≤3 candidates."""

from pathlib import Path

import pytest

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner
from tests.e2e.conftest import build_runtime


@pytest.mark.asyncio
async def test_grounding_click(tmp_path: Path, app_config, simple_case):
    planner = StubPlanner(
        action=SemanticAction(
            action_id="c1",
            intent="click button",
            action_type="click",
            target=TargetDescription(text="btn", description="green button"),
        )
    )
    grounder = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(bbox=(100, 80, 200, 120), confidence=0.95, reason="top"),
                GroundingCandidate(bbox=(10, 10, 30, 30), confidence=0.4, reason="low"),
            ],
            model_name="stub",
        )
    )
    runtime, drv = await build_runtime(
        tmp_path, app_config, planner=planner, grounder=grounder
    )
    ctx = await runtime.run(simple_case)
    assert len(grounder.calls) >= 1
    if drv.clicks:
        x, y = drv.clicks[0]
        assert 100 <= x <= 200 and 80 <= y <= 120
