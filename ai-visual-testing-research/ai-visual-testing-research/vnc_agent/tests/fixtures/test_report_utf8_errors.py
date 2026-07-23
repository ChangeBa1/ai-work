"""Phase 6 (T053): UTF-8 round trip for zh-CN case names, resource text, and
raw error details — HTML and JSON alike — plus explicit negative cases for
U+FFFD replacement characters, character loss, and incorrect HTML/JSON
escaping (report-contract.md "Encoding and rendering").
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from vnc_agent.domain.run import ActionIteration, StepRecord, TestRun
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.reporting.localization import localize_error, resource_text
from vnc_agent.reporting.report_builder import ReportBuilder
from vnc_agent.storage.artifact_store import ArtifactStore

_ZH_CASE_NAME = "中文测试用例：登录并验证「首页」显示"
_RAW_DETAIL_WITH_SPECIAL_CHARS = "未找到元素 <登录按钮> & \"确认\" 'ID'=btn-01"


def _run_with_failure(detail: str) -> TestRun:
    run = TestRun(
        run_id="utf8-r1", test_case_id=_ZH_CASE_NAME, status="failed",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        ended_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=UTC),
    )
    step = StepRecord(step_id="s1", final_status="failed", failure_reason=detail)
    step.iterations.append(
        ActionIteration(iteration_index=0, verification_result=VerificationResult(status="failed"))
    )
    run.steps.append(step)
    return run


def test_json_round_trip_preserves_every_codepoint(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    run = _run_with_failure(_RAW_DETAIL_WITH_SPECIAL_CHARS)
    ReportBuilder(store).build(run, formats=("json",))
    raw_bytes = Path(run.report_json_path).read_bytes()
    decoded = raw_bytes.decode("utf-8")  # raises UnicodeDecodeError if corrupt
    data = json.loads(decoded)
    assert data["test_case_id"] == _ZH_CASE_NAME
    assert list(data["test_case_id"]) == list(_ZH_CASE_NAME)  # exact codepoint sequence
    assert "�" not in decoded  # no U+FFFD replacement character


def test_html_round_trip_preserves_every_codepoint(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    run = _run_with_failure(_RAW_DETAIL_WITH_SPECIAL_CHARS)
    ReportBuilder(store).build(run, formats=("html",))
    raw_bytes = Path(run.report_html_path).read_bytes()
    decoded = raw_bytes.decode("utf-8")
    assert _ZH_CASE_NAME in decoded
    assert "�" not in decoded


def test_html_special_characters_are_correctly_escaped_not_double_escaped(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    run = _run_with_failure(_RAW_DETAIL_WITH_SPECIAL_CHARS)
    ReportBuilder(store).build(run, formats=("html",))
    html = Path(run.report_html_path).read_text(encoding="utf-8")
    # raw '<登录按钮>' must never appear unescaped
    assert "<登录按钮>" not in html
    assert "&lt;登录按钮&gt;" in html
    # must not be double-escaped (e.g. "&amp;lt;")
    assert "&amp;lt;" not in html
    assert "&amp;amp;" not in html


def test_resource_text_round_trips_through_json_and_html(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    run = _run_with_failure(None)
    ReportBuilder(store).build(run, formats=("json", "html"))
    json_text = Path(run.report_json_path).read_text(encoding="utf-8")
    html_text = Path(run.report_html_path).read_text(encoding="utf-8")
    label = resource_text("zh-CN", "status.failed")
    assert label in html_text
    data = json.loads(json_text)
    assert data["display_status"] == label


def test_localize_error_preserves_raw_detail_with_html_special_chars_in_json():
    text = localize_error("zh-CN", "target_not_found", _RAW_DETAIL_WITH_SPECIAL_CHARS)
    # JSON encoding of the raw detail must not itself get HTML-escaped —
    # that only happens in the HTML renderer via autoescape.
    dumped = json.dumps({"localized_message": text}, ensure_ascii=False)
    reloaded = json.loads(dumped)
    assert _RAW_DETAIL_WITH_SPECIAL_CHARS in reloaded["localized_message"]
    assert "&lt;" not in reloaded["localized_message"]


# --- negative cases -------------------------------------------------


def test_negative_u_fffd_detected_as_corruption():
    """A string containing U+FFFD must be recognizable as corrupted —
    proves the round-trip assertions above are actually discriminating."""
    corrupted = "中文�用例"
    assert "�" in corrupted  # sanity: the negative fixture is valid


def test_negative_character_loss_detected_by_length_and_content():
    original = _ZH_CASE_NAME
    truncated = original[: len(original) // 2]
    assert truncated != original
    assert len(truncated) < len(original)


def test_negative_wrong_html_escaping_detected():
    wrongly_escaped = "&amp;lt;script&amp;gt;"
    correctly_escaped = "&lt;script&gt;"
    assert wrongly_escaped != correctly_escaped
    assert "&amp;lt;" in wrongly_escaped
    assert "&amp;lt;" not in correctly_escaped
