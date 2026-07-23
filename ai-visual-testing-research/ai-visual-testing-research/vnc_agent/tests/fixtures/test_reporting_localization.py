"""Phase 6 (T051): full HTML localization — DOM structure, autoescape,
stable machine CSS/data markers, and absence of the pre-004 English UI
strings (report-contract.md "Compatibility tests").

Diagnostic `<code>{{ dict }}</code>` dumps of raw structured audit data
(grounding candidates, executable actions, recovery attempts) are treated
like raw error code/detail — legitimately machine-shaped, not "static UI
text" — so this test targets the *known pre-004 English UI phrases*
(headings/labels that used to be hardcoded English) rather than a blanket
Latin-character scan, which would over-flag inherently technical content
(UUIDs, file paths, dict keys) that report-contract.md's own whitelist
already permits.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.support.report_assertions import extract_visible_text
from vnc_agent.domain.run import ActionIteration, StepRecord, TestRun
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.reporting.report_builder import ReportBuilder
from vnc_agent.storage.artifact_store import ArtifactStore

# Every one of these hardcoded English strings existed in the pre-004
# template (html_report.py, feature 001-003) and must be fully gone now.
_OLD_ENGLISH_UI_STRINGS = [
    "Test Run",
    "Case:",
    "Status:",
    "Started:",
    "Ended:",
    "Precondition / Executed Action Audit",
    "Human confirmed facts:",
    "Declared tag counts:",
    "Executed actions:",
    "Weak assertion warning",
    "Action effect only, not a verified business result",
    "Trusted pass",
    "Failure:",
    "Iteration ",
    "Action Identity / Coordinate Space",
    "Canonical identity:",
    "Coordinate audit:",
    "Before:",
    "After:",
    "Action:",
    "ActionEffect:",
    "Grounding:",
    "Executable:",
    "Wait:",
    "Recovery:",
]


def _run() -> TestRun:
    run = TestRun(
        run_id="loc-r1", test_case_id="loc-tc", status="passed",
        started_at=datetime.now(UTC), ended_at=datetime.now(UTC),
    )
    step = StepRecord(step_id="s1", final_status="passed")
    step.iterations.append(
        ActionIteration(
            iteration_index=0,
            verification_result=VerificationResult(status="passed"),
        )
    )
    run.steps.append(step)
    return run


def test_html_lang_and_charset(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    builder = ReportBuilder(store)
    run = _run()
    builder.build(run, formats=("html",))
    html = Path(run.report_html_path).read_text(encoding="utf-8")
    assert '<html lang="zh-CN">' in html
    assert '<meta charset="utf-8"/>' in html


def test_no_leftover_pre_004_english_ui_strings(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    builder = ReportBuilder(store)
    run = _run()
    builder.build(run, formats=("html",))
    html = Path(run.report_html_path).read_text(encoding="utf-8")
    leaked = [s for s in _OLD_ENGLISH_UI_STRINGS if s in html]
    assert not leaked, f"pre-004 English UI strings leaked into zh-CN report: {leaked}"


def test_stable_machine_css_and_data_markers_present(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    builder = ReportBuilder(store)
    run = _run()
    builder.build(run, formats=("html",))
    html = Path(run.report_html_path).read_text(encoding="utf-8")
    assert 'data-status="passed"' in html
    assert 'class="status status-passed"' in html


def test_autoescape_neutralizes_injected_markup(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    builder = ReportBuilder(store)
    run = _run()
    run.steps[0].failure_reason = "<script>alert(1)</script>"
    run.status = "failed"
    run.steps[0].final_status = "failed"
    builder.build(run, formats=("html",))
    html = Path(run.report_html_path).read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_visible_chinese_text_present_for_core_ui_sections(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    builder = ReportBuilder(store)
    run = _run()
    builder.build(run, formats=("html",))
    html = Path(run.report_html_path).read_text(encoding="utf-8")
    visible = "\n".join(extract_visible_text(html))
    expected_labels = [
        "测试运行报告", "测试用例", "状态", "开始时间", "结束时间", "性能摘要", "步骤", "迭代",
    ]
    for expected in expected_labels:
        assert expected in visible


def test_snapshot_round_trip_stable_across_two_runs(tmp_path: Path):
    """Deterministic snapshot proof: rebuilding from the same TestRun twice
    (with stabilized ids/timestamps) produces byte-identical zh-CN output."""
    from tests.support.report_assertions import normalize_report_snapshot

    store1 = ArtifactStore(tmp_path / "a")
    run1 = _run()
    ReportBuilder(store1).build(run1, formats=("html",))
    html1 = Path(run1.report_html_path).read_text(encoding="utf-8")

    store2 = ArtifactStore(tmp_path / "b")
    run2 = _run()
    ReportBuilder(store2).build(run2, formats=("html",))
    html2 = Path(run2.report_html_path).read_text(encoding="utf-8")

    norm1 = normalize_report_snapshot(html1, run_root=tmp_path / "a")
    norm2 = normalize_report_snapshot(html2, run_root=tmp_path / "b")
    assert norm1 == norm2


_GOLDEN_PATH = Path(__file__).resolve().parents[1] / "snapshots" / "report_zh_cn.html"


def _golden_run() -> TestRun:
    """A single fixed, representative run covering: passed/failed steps,
    a weak-assertion iteration, a failure reason, and no evidence (offline,
    no captured frames) — stable across regenerations."""
    from vnc_agent.domain.action_effect import ActionEffect
    from vnc_agent.domain.recovery import FailureType, RecoveryAttempt

    run = TestRun(
        run_id="golden-run", test_case_id="golden-case", status="failed",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        ended_at=datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC),
    )
    passed_step = StepRecord(step_id="s1-passed", final_status="passed")
    passed_step.iterations.append(
        ActionIteration(
            iteration_index=0,
            verification_result=VerificationResult(status="passed", basis="business_assertion"),
            action_effect=ActionEffect(status="expected_effect"),
        )
    )
    weak_step = StepRecord(step_id="s2-weak", final_status="passed")
    weak_step.iterations.append(
        ActionIteration(
            iteration_index=0,
            verification_result=VerificationResult(
                status="uncertain", reason="仅凭 screen_changed 证据判定",
                basis="action_effect_only", weak_assertion_warning=True,
            ),
            action_effect=ActionEffect(status="no_effect"),
            recovery_attempts=[
                RecoveryAttempt(
                    failure_type=FailureType.TARGET_NOT_FOUND, strategy="re_ground",
                    attempt_index=0, max_retries=2, resolved=False,
                )
            ],
        )
    )
    failed_step = StepRecord(
        step_id="s3-failed", final_status="failed", failure_reason="target_not_found"
    )
    failed_step.iterations.append(
        ActionIteration(
            iteration_index=0,
            verification_result=VerificationResult(status="failed", reason="target_not_found"),
            action_effect=ActionEffect(status="effect_uncertain"),
        )
    )
    run.steps = [passed_step, weak_step, failed_step]
    return run


def test_golden_snapshot_stable(tmp_path: Path):
    """Regenerating the golden run twice must produce identical normalized
    HTML — and it must match the committed golden file if one exists,
    catching accidental localization/markup regressions."""
    from tests.support.report_assertions import normalize_report_snapshot

    store = ArtifactStore(tmp_path)
    run = _golden_run()
    ReportBuilder(store).build(run, formats=("html",))
    html = Path(run.report_html_path).read_text(encoding="utf-8")
    normalized = normalize_report_snapshot(html, run_root=tmp_path)

    if not _GOLDEN_PATH.exists():
        _GOLDEN_PATH.write_text(normalized, encoding="utf-8")
        pytest.skip("golden snapshot did not exist — created it for review")

    golden = _GOLDEN_PATH.read_text(encoding="utf-8")
    assert normalized == golden, (
        "report_zh_cn.html golden snapshot drifted — review the diff and, if "
        "the change is intentional, delete tests/snapshots/report_zh_cn.html "
        "and rerun to regenerate it"
    )
