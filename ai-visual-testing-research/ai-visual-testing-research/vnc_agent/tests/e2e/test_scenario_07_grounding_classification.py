"""E2E scenario 7: grounding classification paths, no OOB clicks."""

from pathlib import Path

import pytest

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner
from tests.e2e.conftest import build_runtime


@pytest.mark.asyncio
async def test_no_oob_click_when_all_out_of_bounds(tmp_path: Path, app_config, simple_case):
    planner = StubPlanner(
        action=SemanticAction(
            action_id="c",
            intent="click",
            action_type="click",
            target=TargetDescription(description="x", text="x"),
        )
    )
    grounder = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(bbox=(5000, 5000, 5100, 5100), confidence=0.99)
            ],
            model_name="stub",
        )
    )
    runtime, drv = await build_runtime(
        tmp_path, app_config, planner=planner, grounder=grounder
    )
    await runtime.run(simple_case)
    for x, y in drv.clicks:
        assert 0 <= x < 300 and 0 <= y < 200
