"""E2E scenario 4: verify gate — failed step stops run (FR-035)."""

from pathlib import Path

import pytest

from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from tests.e2e.conftest import build_runtime


@pytest.mark.asyncio
async def test_failed_step_stops_remaining(tmp_path: Path, app_config):
    case = TestCase(
        id="gate",
        name="gate",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="fail-step",
                name="fail",
                intent="press escape",
                max_retries=0,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[
                        VerificationCondition(type="text_appears", value="NEVER_MATCH_ZZZ")
                    ],
                ),
            ),
            TestStep(
                id="second",
                name="second",
                intent="should not run",
                max_retries=0,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="screen_changed")],
                ),
            ),
        ],
    )
    runtime, _ = await build_runtime(tmp_path, app_config)
    ctx = await runtime.run(case)
    assert ctx.test_run.status == "failed"
    assert len(ctx.test_run.steps) == 1  # second never scheduled
    assert case.steps[1].status == "pending"
