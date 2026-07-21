"""E2E scenario 2: keyboard-first path, no grounder calls."""

from pathlib import Path

import pytest

from vnc_agent.domain.action import SemanticAction
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner
from tests.e2e.conftest import build_runtime


@pytest.mark.asyncio
async def test_keyboard_first_no_grounding(tmp_path: Path, app_config, simple_case):
    planner = StubPlanner(
        action=SemanticAction(
            action_id="k1", intent="hotkey", action_type="hotkey", keys=["ctrl", "s"]
        )
    )
    grounder = StubGrounder()
    runtime, drv = await build_runtime(
        tmp_path, app_config, planner=planner, grounder=grounder
    )
    ctx = await runtime.run(simple_case)
    assert grounder.calls == []
    # keyboard path should have been used if iterations ran
    if ctx.test_run.steps and ctx.test_run.steps[0].iterations:
        it = ctx.test_run.steps[0].iterations[0]
        if it.executable_action:
            assert it.executable_action.method == "keyboard"
