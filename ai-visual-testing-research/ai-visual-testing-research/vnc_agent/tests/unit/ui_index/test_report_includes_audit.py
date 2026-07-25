"""T072: JSON/HTML report must surface ActionIteration.ui_index_audit (FR-013, SC-006)."""

from __future__ import annotations

from vnc_agent.domain.run import ActionIteration, StepRecord, TestRun
from vnc_agent.reporting.json_report import build_report_dict
from vnc_agent.ui_index.audit import IndexUsageAuditRecord


def _run_with_iteration(iteration: ActionIteration) -> dict:
    run = TestRun(
        run_id="audit-report-r1",
        test_case_id="audit-report-tc",
        status="passed",
        steps=[
            StepRecord(
                step_id="s1",
                final_status="passed",
                iterations=[iteration],
            )
        ],
    )
    return build_report_dict(run)


def test_report_includes_hit_ui_index_audit():
    audit = IndexUsageAuditRecord(
        bundle_id="bundle-form-input",
        schema_version="1.0",
        outcome="hit",
        matched_screen_id="screen.form_edit",
        hint_element_ids=["el.form.submit_btn"],
        candidate_transition_ids=["tr.form.submit"],
        grounder_outcome="succeeded",
    )
    report = _run_with_iteration(
        ActionIteration(iteration_index=0, ui_index_audit=audit)
    )
    it = report["steps"][0]["iterations"][0]
    assert "ui_index_audit" in it
    assert it["ui_index_audit"] == audit.model_dump(mode="json")


def test_report_includes_explicit_null_when_audit_absent():
    """Index not enabled / never recorded: key present as null, not omitted."""
    report = _run_with_iteration(ActionIteration(iteration_index=0, ui_index_audit=None))
    it = report["steps"][0]["iterations"][0]
    assert "ui_index_audit" in it
    assert it["ui_index_audit"] is None


def test_report_includes_not_configured_audit_record():
    audit = IndexUsageAuditRecord(outcome="not_configured")
    report = _run_with_iteration(
        ActionIteration(iteration_index=0, ui_index_audit=audit)
    )
    it = report["steps"][0]["iterations"][0]
    assert "ui_index_audit" in it
    assert it["ui_index_audit"]["outcome"] == "not_configured"
    assert it["ui_index_audit"] == audit.model_dump(mode="json")
