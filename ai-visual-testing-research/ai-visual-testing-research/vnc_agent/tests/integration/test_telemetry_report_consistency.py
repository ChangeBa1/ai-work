"""Phase 7 (T068): the same TestRun/event set must produce consistent
structured JSON Lines log events, `report.json`, and `report.html` — stage
status/duration, dedup counts, cache hits, and model-call counts are
cross-checked item by item against each other, never independently
recomputed per output (telemetry-contract.md "Stable structured-log
events"; report-contract.md "Report build boundary").
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import pytest
import structlog

from tests.support.frame_dedup_spies import SpyOCR, SpyTemplateAnalyzer
from vnc_agent.domain.run import TestRun
from vnc_agent.perception import structured_screen as ss_mod
from vnc_agent.perception.cache import AnalysisResultCache
from vnc_agent.perception.pipeline import ObservationPipeline
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.reporting.report_builder import ReportBuilder
from vnc_agent.runtime.telemetry import CounterEvent, ModelCallAudit, log_event
from vnc_agent.storage.artifact_store import ArtifactStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "images" / "frame_dedup"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


class SequenceDriver:
    def __init__(self, names: list[str]):
        self._bytes = [(FIXTURES / MANIFEST[n]["file"]).read_bytes() for n in names]
        self._i = 0
        meta = MANIFEST[names[0]]
        self._resolution = (meta["width"], meta["height"])

    @property
    def resolution(self):
        return self._resolution

    async def capture_screen(self) -> bytes:
        data = self._bytes[min(self._i, len(self._bytes) - 1)]
        self._i += 1
        return data

    async def capture_region(self, x, y, w, h) -> bytes:
        return await self.capture_screen()


def _html_cell(html: str, label: str) -> str:
    match = re.search(rf"<th>{re.escape(label)}</th><td[^>]*>([^<]*)</td>", html)
    assert match, f"could not find performance row for label {label!r} in HTML"
    return match.group(1)


@pytest.mark.asyncio
async def test_json_lines_json_and_html_agree_on_the_same_event_set(
    tmp_path: Path, monkeypatch
):
    spy_ocr = SpyOCR(results=[])
    spy_template = SpyTemplateAnalyzer(results=[])
    monkeypatch.setattr(ss_mod, "run_ocr_array", spy_ocr)
    monkeypatch.setattr(
        ss_mod,
        "match_templates_in_dir_array",
        lambda pixels, d, threshold=0.8: spy_template(pixels),
    )

    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    run = TestRun(run_id="consist-r1", test_case_id="tc")
    store = ArtifactStore(tmp_path)
    svc = FrameCaptureService(
        SequenceDriver(["baseline_full"] * 10 + ["single_pixel_changed"]),
        run_id="consist-r1", vnc_session_id="s1", test_run=run, artifact_store=store,
    )
    cache = AnalysisResultCache(max_frames=5)
    pipeline = ObservationPipeline(
        svc, templates_dir=templates_dir, ocr_enabled=True, template_enabled=True,
        vision_fallback=False, cache=cache,
    )

    with structlog.testing.capture_logs() as logs:
        for _ in range(11):
            await pipeline.observe(step_id="s1", capture_source="observation")

        # One actual + one skipped model call, mirroring
        # runtime/agent_runtime.py's own audit+counter+log_event pairing
        # (`_record_model_call_audit`) — kept manual here to isolate the
        # telemetry consistency contract from the full agent runtime loop.
        run.model_call_audits.append(
            ModelCallAudit(
                audit_id="audit-1", run_id="consist-r1", step_id="s1",
                frame_id=run.frames[0].id, iteration_index=0, model_role="planner",
                request_identity="req-1", context_identity="ctx-1",
                sanitized_request={"step_intent": "click"},
                sanitized_response={"action_type": "click"}, outcome="actual",
            )
        )
        actual_payload = {"model_role": "planner", "invocation_id": "inv-1", "status": "completed"}
        run.counter_events.append(
            CounterEvent(kind="model_call", occurred_at=datetime.now(UTC), payload=actual_payload)
        )
        log_event("model_call_event", **actual_payload)

        run.model_call_audits.append(
            ModelCallAudit(
                audit_id="audit-2", run_id="consist-r1", step_id="s1",
                frame_id=run.frames[0].id, iteration_index=0, model_role="grounder",
                request_identity="req-2", context_identity="ctx-2",
                sanitized_request={}, sanitized_response={}, outcome="skipped",
                reason="no_new_context",
            )
        )
        skipped_payload = {
            "model_role": "grounder", "reason": "no_new_context", "request_identity": "req-2",
        }
        run.counter_events.append(
            CounterEvent(
                kind="model_call_skipped", occurred_at=datetime.now(UTC), payload=skipped_payload
            )
        )
        log_event("model_call_event", **skipped_payload)

        builder = ReportBuilder(store, locale="zh-CN")
        builder.build(run, formats=("json", "html"))

    # ---- ground truth straight from the TestRun/spies ----
    assert len(run.frames) == 11
    unique = sum(1 for f in run.frames if not f.deduplicated)
    duplicate = sum(1 for f in run.frames if f.deduplicated)
    assert unique == 2
    assert duplicate == 9
    assert spy_ocr.call_count == 2
    assert spy_template.call_count == 2

    report_dict = json.loads(Path(run.report_json_path).read_text(encoding="utf-8"))
    html_text = Path(run.report_html_path).read_text(encoding="utf-8")

    # ---- report.json performance_summary must equal run.performance_summary
    # (same object, never independently recomputed for the JSON output) ----
    assert run.performance_summary is not None
    assert report_dict["performance_summary"] == run.performance_summary.model_dump(mode="json")
    ps = report_dict["performance_summary"]
    assert ps["total_capture_count"] == 11
    assert ps["unique_frame_count"] == unique
    assert ps["duplicate_frame_count"] == duplicate
    assert ps["cache_hits"]["ocr"] == 9
    assert ps["cache_hits"]["template"] == 9
    assert ps["analysis_invocations"]["ocr"] == 2
    assert ps["analysis_invocations"]["template"] == 2
    assert ps["actual_model_call_count"] == 1
    assert ps["skipped_model_call_count"] == 1
    assert len(report_dict["frames"]) == 11

    # ---- JSON Lines log events must agree with report.json item by item ----
    dedup_log_events = [e for e in logs if e["event"] == "frame_dedup_decision"]
    assert len(dedup_log_events) == 11
    assert sum(1 for e in dedup_log_events if e["deduplicated"]) == ps["duplicate_frame_count"]
    assert sum(1 for e in dedup_log_events if not e["deduplicated"]) == ps["unique_frame_count"]

    ocr_hit_logs = [
        e for e in logs
        if e["event"] == "analysis_cache_event" and e.get("component") == "ocr" and e["hit"]
    ]
    ocr_miss_logs = [
        e for e in logs
        if e["event"] == "analysis_cache_event" and e.get("component") == "ocr" and not e["hit"]
    ]
    assert len(ocr_hit_logs) == ps["cache_hits"]["ocr"]
    assert len(ocr_miss_logs) == ps["analysis_invocations"]["ocr"]

    template_hit_logs = [
        e for e in logs
        if e["event"] == "analysis_cache_event" and e.get("component") == "template" and e["hit"]
    ]
    template_miss_logs = [
        e for e in logs
        if e["event"] == "analysis_cache_event"
        and e.get("component") == "template"
        and not e["hit"]
    ]
    assert len(template_hit_logs) == ps["cache_hits"]["template"]
    assert len(template_miss_logs) == ps["analysis_invocations"]["template"]

    model_call_logs = [e for e in logs if e["event"] == "model_call_event"]
    actual_model_logs = [e for e in model_call_logs if e.get("status") == "completed"]
    skipped_model_logs = [e for e in model_call_logs if "reason" in e]
    assert len(actual_model_logs) == ps["actual_model_call_count"] == 1
    assert len(skipped_model_logs) == ps["skipped_model_call_count"] == 1

    # ---- stage_measurements: same (stage, status) multiset in the log
    # stream and in run.stage_measurements, including report_build/
    # report_output (only appended once ReportBuilder.build() returns) ----
    stage_log_events = [e for e in logs if e["event"] == "stage_measurement"]
    assert len(stage_log_events) == len(run.stage_measurements)
    log_stage_status_counts = Counter((e["stage"], e["status"]) for e in stage_log_events)
    run_stage_status_counts = Counter((m.stage, m.status) for m in run.stage_measurements)
    assert log_stage_status_counts == run_stage_status_counts
    assert run_stage_status_counts[("report_build", "completed")] == 1
    assert run_stage_status_counts[("report_output", "completed")] == 1

    # ---- report.json's frozen stage_measurements snapshot is taken from
    # inside the report_build/report_output measure_stage blocks, so it
    # never self-references its own two entries (report-contract.md
    # "Report build boundary") — everything else must still match ----
    json_stage_status_counts = Counter(
        (m["stage"], m["status"]) for m in report_dict["stage_measurements"]
    )
    assert ("report_build", "completed") not in json_stage_status_counts
    assert ("report_output", "completed") not in json_stage_status_counts
    non_report_run_counts = Counter(
        (m.stage, m.status)
        for m in run.stage_measurements
        if m.stage not in ("report_build", "report_output")
    )
    assert json_stage_status_counts == non_report_run_counts

    # ---- report.html renders the exact same performance_summary numbers
    # (rendered from the already-built report_dict, not recomputed) ----
    assert _html_cell(html_text, "总采集次数") == "11"
    assert _html_cell(html_text, "唯一帧数") == str(unique)
    assert _html_cell(html_text, "重复帧数") == str(duplicate)
    assert _html_cell(html_text, "实际模型调用次数") == "1"
    assert _html_cell(html_text, "跳过模型调用次数") == "1"
