"""US9: Report status matches last verification (SC-007)."""

from datetime import datetime, timezone

from vnc_agent.domain.run import ActionIteration, StepRecord, TestRun
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.reporting.json_report import build_report_dict


def test_failed_not_reported_as_passed():
    run = TestRun(
        run_id="r1",
        test_case_id="c1",
        status="failed",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        steps=[
            StepRecord(
                step_id="s1",
                final_status="failed",
                failure_reason="no login",
                iterations=[
                    ActionIteration(
                        iteration_index=0,
                        verification_result=VerificationResult(
                            status="failed", reason="text missing"
                        ),
                    )
                ],
            )
        ],
    )
    report = build_report_dict(run)
    assert report["status"] == "failed"
    assert report["steps"][0]["status"] == "failed"
    assert report["steps"][0]["iterations"][-1]["verification_result"]["status"] == "failed"


def test_uncertain_exhausted_is_failed_on_step():
    run = TestRun(
        run_id="r2",
        test_case_id="c1",
        status="failed",
        steps=[
            StepRecord(
                step_id="s1",
                final_status="failed",  # uncertain → failed when budget exhausted
                iterations=[
                    ActionIteration(
                        iteration_index=0,
                        verification_result=VerificationResult(
                            status="uncertain", reason="?"
                        ),
                    )
                ],
            )
        ],
    )
    report = build_report_dict(run)
    assert report["status"] == "failed"
    assert report["steps"][0]["status"] == "failed"
