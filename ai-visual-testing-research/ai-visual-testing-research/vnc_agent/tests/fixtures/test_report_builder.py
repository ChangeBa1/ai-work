"""US9 + US7: JSON/HTML report labels for trusted / effect-only / weak assertion."""

from datetime import UTC, datetime
from pathlib import Path

from vnc_agent.domain.action import (
    ExecutableAction,
    ExecutionResult,
    SemanticAction,
    TargetDescription,
)
from vnc_agent.domain.action_identity import CanonicalActionIdentity
from vnc_agent.domain.grounding import GroundingResult
from vnc_agent.domain.repeat_guard import RepeatGuardDecision
from vnc_agent.domain.reporting_tags import ActionMatcher, ActionTagRule
from vnc_agent.domain.run import (
    ActionIteration,
    FactEvaluation,
    HumanConfirmedFact,
    PreconditionEvaluation,
    StepRecord,
    TestRun,
)
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
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
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
    assert (
        "weak_assertion_warning" not in text
        or 'data-marker="weak_assertion_warning"' not in text
    )


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
    # Feature 004: HTML is fully localized to zh-CN — the machine data
    # marker stays stable, but the visible label is now Chinese.
    assert "弱断言警告" in htext


_PRIMARY_TAG_RULES = [
    ActionTagRule(tag="primary_submit", matcher=ActionMatcher(target_role="button")),
    ActionTagRule(
        tag="navigation", matcher=ActionMatcher(intent_contains="navigate")
    ),
]


def _audited_run() -> TestRun:
    now = datetime.now(UTC)
    executed = ActionIteration(
        iteration_index=0,
        semantic_action=SemanticAction(
            action_id="target",
            intent="点击目标按钮",
            action_type="click",
            target=TargetDescription(role="button", text="目标"),
            action_kind="non_idempotent",
        ),
        canonical_identity=CanonicalActionIdentity(
            step_id="generic-step",
            action_type="click",
            action_id="target",
            normalized_target="目标",
        ),
        grounding_result=GroundingResult(
            found=True,
            candidates=[],
            coordinate_space_audit=[
                {
                    "coordinate_space": "normalized_1000",
                    "raw_bbox": [251, 402, 405, 459],
                    "resolved_bbox": [257, 630, 415, 720],
                    "accepted": True,
                }
            ],
        ),
        executable_action=ExecutableAction(
            method="mouse", operation="click", coordinates=(336, 675)
        ),
        execution_result=ExecutionResult(success=True, started_at=now, ended_at=now),
    )
    blocked = ActionIteration(
        iteration_index=1,
        semantic_action=SemanticAction(
            action_id="target",
            intent="点击非交互结果展示元素",
            action_type="click",
            action_kind="non_idempotent",
        ),
        canonical_identity=CanonicalActionIdentity(
            step_id="generic-step",
            action_type="click",
            action_id="target",
            normalized_target="结果展示元素",
        ),
        repeat_guard_decision=RepeatGuardDecision(
            allowed=False, reason="dangerous_drift"
        ),
    )
    untagged = ActionIteration(
        iteration_index=2,
        semantic_action=SemanticAction(
            action_id="other",
            intent="执行其它安全动作",
            action_type="press_key",
            keys=["escape"],
        ),
        executable_action=ExecutableAction(
            method="keyboard", operation="press_key", keys=["escape"]
        ),
        execution_result=ExecutionResult(success=True, started_at=now, ended_at=now),
    )
    return TestRun(
        run_id="audit",
        test_case_id="case",
        precondition_evaluation=PreconditionEvaluation(
            status="passed",
            fact_evaluations=[
                FactEvaluation(
                    key="example_state",
                    result=VerificationResult(status="passed", reason="matched"),
                )
            ],
            checked_at=now,
        ),
        human_confirmed_facts=[
            HumanConfirmedFact(
                key="example_state", confirmed_value="0", confirmed_at=now
            )
        ],
        steps=[StepRecord(step_id="generic-step", iterations=[executed, blocked, untagged])],
    )


def test_action_identity_and_coordinate_audit(tmp_path: Path) -> None:
    run = _audited_run()
    data = build_report_dict(run)
    iteration = data["steps"][0]["iterations"][0]
    assert iteration["canonical_action_identity"]["action_id"] == "target"
    assert iteration["coordinate_space_audit"][0]["accepted"] is True

    html_path = write_html_report(run, tmp_path / "audit.html")
    html = Path(html_path).read_text(encoding="utf-8")
    # Feature 004: localized to zh-CN — assert the Chinese section labels
    # instead of the old English heading.
    assert "规范动作身份" in html
    assert "坐标空间审计" in html


def test_run_level_precondition_and_tag_audit() -> None:
    """Feature 003 T037: precondition_evaluation/human_confirmed_facts/
    declared_tag_counts replace the old fixed cart/category fields; tag
    counting only includes actions with a proven-sent execution result."""
    data = build_report_dict(_audited_run(), action_tags=_PRIMARY_TAG_RULES)
    assert data["precondition_evaluation"]["status"] == "passed"
    assert data["precondition_evaluation"]["fact_evaluations"][0]["key"] == "example_state"
    assert data["human_confirmed_facts"][0]["key"] == "example_state"
    assert len(data["executed_action_log"]) == 2
    # "target" (role=button) sent action matches primary_submit; the blocked
    # dangerous_drift proposal (never sent) MUST NOT count.
    assert data["declared_tag_counts"]["primary_submit"] == 1
    assert data["declared_tag_counts"]["navigation"] == 0
    # An executed action matching no declared rule stays in the log with no
    # tag, and no "unclassified" catch-all bucket is introduced.
    assert data["executed_action_log"][1]["tags"] == []
