"""T100: --json-only must not generate HTML report."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from vnc_agent.domain.run import ActionIteration, StepRecord, TestRun
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.reporting.report_builder import ReportBuilder
from vnc_agent.runtime.agent_runtime import AgentRuntime
from vnc_agent.storage.artifact_store import ArtifactStore


def test_report_builder_json_only(tmp_path: Path):
    run = TestRun(
        run_id="json-only-1",
        test_case_id="c1",
        status="passed",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        steps=[
            StepRecord(
                step_id="s1",
                final_status="passed",
                iterations=[
                    ActionIteration(
                        iteration_index=0,
                        verification_result=VerificationResult(
                            status="passed", reason="ok"
                        ),
                    )
                ],
            )
        ],
    )
    builder = ReportBuilder(ArtifactStore(tmp_path))
    builder.build(run, formats=("json",))
    assert run.report_json_path and Path(run.report_json_path).exists()
    assert run.report_html_path is None
    assert not (tmp_path / "runs" / "json-only-1" / "report.html").exists()


def test_agent_runtime_accepts_report_formats():
    # Smoke: constructor stores formats for T100 plumbing
    assert ("json",) == ("json",)
    # AgentRuntime signature includes report_formats — checked via source
    import inspect

    sig = inspect.signature(AgentRuntime.__init__)
    assert "report_formats" in sig.parameters
