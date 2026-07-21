"""E2E scenario 9: failure report completeness."""

from pathlib import Path

import pytest

from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from tests.e2e.conftest import build_runtime


@pytest.mark.asyncio
async def test_failure_report_has_reason_and_files(tmp_path: Path, app_config):
    case = TestCase(
        id="fail-report",
        name="fail-report",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="s1",
                name="s1",
                intent="escape",
                max_retries=0,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[
                        VerificationCondition(type="text_appears", value="MISSING")
                    ],
                ),
            )
        ],
    )
    runtime, _ = await build_runtime(tmp_path, app_config)
    ctx = await runtime.run(case)
    assert ctx.test_run.status == "failed"
    assert ctx.test_run.report_json_path
    assert Path(ctx.test_run.report_json_path).exists()
    assert ctx.test_run.report_html_path
    body = Path(ctx.test_run.report_json_path).read_text(encoding="utf-8")
    assert "failure_reason" in body or '"status": "failed"' in body
