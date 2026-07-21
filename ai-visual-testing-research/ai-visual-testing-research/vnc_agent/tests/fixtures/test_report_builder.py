"""US9 + US7: JSON/HTML report labels for trusted / effect-only / weak assertion."""

from datetime import datetime, timezone
from pathlib import Path

from vnc_agent.domain.run import ActionIteration, StepRecord, TestRun
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.reporting.html_report import write_html_report
from vnc_agent.reporting.json_report import build_report_dict, write_json_report
from vnc_agent.reporting.report_builder import ReportBuilder
from vnc_agent.storage.artifact_store import ArtifactStore


def _run_with_vr(vr: VerificationResult, step_id: str = "s1") -> TestRun:
    return TestRun(
        run_id="report-test-1",
        test_case_id="c1",
        status="passed" if vr.status == "passed" else "failed",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        steps=[
            StepRecord(
                step_id=step_id,
                final_status="passed" if vr.status == "passed" else "failed",
                iterations=[
                    ActionIteration(iteration_index=0, verification_result=vr)
                ],
            )
        ],
    )


def test_json_html_same_status(tmp_path: Path):
    run = _run_with_vr(
        VerificationResult(
            status="passed",
            reason="ok",
            evidence_refs=[],
            basis="business_assertion",
        )
    )
    store = ArtifactStore(tmp_path)
    builder = ReportBuilder(store)
    builder.build(run, formats=("json", "html"))
    assert Path(run.report_json_path).exists()
    assert Path(run.report_html_path).exists()
    text = Path(run.report_json_path).read_text(encoding="utf-8")
    assert '"status": "passed"' in text
    html = Path(run.report_html_path).read_text(encoding="utf-8")
    assert "passed" in html


def test_trusted_pass_report_markers(tmp_path: Path):
    """T058: business-assertion-backed passed is distinct."""
    run = _run_with_vr(
        VerificationResult(
            status="passed",
            reason="text ok",
            basis="business_assertion",
            weak_assertion_warning=False,
        ),
        step_id="trusted",
    )
    data = build_report_dict(run)
    step = data["steps"][0]
    assert step["verification_label"] == "trusted_pass"
    assert step["weak_assertion_warning"] is False
    html = write_html_report(run, tmp_path / "t.html")
    text = Path(html).read_text(encoding="utf-8")
    assert "trusted_pass" in text or "Trusted pass" in text
    assert "weak_assertion_warning" not in text or 'data-marker="weak_assertion_warning"' not in text


def test_effect_only_pass_report_markers(tmp_path: Path):
    """T058: effect_only passed is distinct from trusted and weak warning."""
    run = _run_with_vr(
        VerificationResult(
            status="passed",
            reason="action effect only, not a verified business result",
            basis="action_effect_only",
            weak_assertion_warning=False,
        ),
        step_id="effect",
    )
    data = build_report_dict(run)
    step = data["steps"][0]
    assert step["verification_label"] == "effect_only_pass"
    assert step["weak_assertion_warning"] is False
    html_path = write_html_report(run, tmp_path / "e.html")
    text = Path(html_path).read_text(encoding="utf-8")
    assert "effect_only" in text or "Action effect only" in text
    assert 'data-marker="weak_assertion_warning"' not in text


def test_weak_assertion_warning_report_markers(tmp_path: Path):
    """T058 / FR-027: weak assertion uncertain is visibly marked."""
    run = _run_with_vr(
        VerificationResult(
            status="uncertain",
            reason="仅凭 screen_changed 证据判定",
            basis="action_effect_only",
            weak_assertion_warning=True,
        ),
        step_id="weak",
    )
    data = build_report_dict(run)
    step = data["steps"][0]
    assert step["weak_assertion_warning"] is True
    assert step["verification_label"] == "weak_assertion_warning"
    json_path = write_json_report(run, tmp_path / "w.json")
    jtext = Path(json_path).read_text(encoding="utf-8")
    assert "weak_assertion_warning" in jtext
    html_path = write_html_report(run, tmp_path / "w.html")
    htext = Path(html_path).read_text(encoding="utf-8")
    assert "weak_assertion_warning" in htext
    assert "Weak assertion" in htext or "weak assertion" in htext
