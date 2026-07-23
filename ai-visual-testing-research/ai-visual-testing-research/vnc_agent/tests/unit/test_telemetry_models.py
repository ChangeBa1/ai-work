"""Phase 2 (T007) RED: StageMeasurement / CounterEvent / ModelCallAudit /
PerformanceSummary (data-model.md §9-11, telemetry-contract.md).

Must fail before `vnc_agent.runtime.telemetry` exists.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vnc_agent.runtime.telemetry import (
    CANONICAL_STAGES,
    CounterEvent,
    ModelCallAudit,
    PerformanceSummary,
    StageMeasurement,
)


def _now():
    return datetime(2026, 1, 1, tzinfo=UTC)


# --- StageMeasurement -------------------------------------------------


def test_canonical_stages_are_stable_and_include_report_output_as_extra():
    required = {
        "capture", "pixel_hash", "persistence", "OCR", "template", "vision",
        "planner", "grounder", "verification", "report_build",
    }
    assert required.issubset(set(CANONICAL_STAGES))
    assert "report_output" in CANONICAL_STAGES


def test_stage_measurement_completed_requires_observed_duration():
    m = StageMeasurement(
        measurement_id="m1",
        run_id="r1",
        step_id=None,
        frame_id=None,
        iteration_index=None,
        stage="capture",
        started_at=_now(),
        duration_ms=12.5,
        status="completed",
        actual_call=True,
        cache_hit=False,
    )
    assert m.duration_ms == 12.5


def test_stage_measurement_unavailable_forbids_nonnull_duration():
    with pytest.raises(ValidationError):
        StageMeasurement(
            measurement_id="m2",
            run_id="r1",
            step_id=None,
            frame_id=None,
            iteration_index=None,
            stage="vision",
            started_at=_now(),
            duration_ms=0,
            status="unavailable",
            actual_call=False,
            cache_hit=False,
        )


def test_stage_measurement_unavailable_allows_null_duration():
    m = StageMeasurement(
        measurement_id="m3",
        run_id="r1",
        step_id=None,
        frame_id=None,
        iteration_index=None,
        stage="vision",
        started_at=_now(),
        duration_ms=None,
        status="unavailable",
        actual_call=False,
        cache_hit=False,
    )
    assert m.duration_ms is None


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
def test_stage_measurement_completed_failed_cancelled_require_nonnull_duration(status):
    with pytest.raises(ValidationError):
        StageMeasurement(
            measurement_id="m4",
            run_id="r1",
            step_id=None,
            frame_id=None,
            iteration_index=None,
            stage="capture",
            started_at=_now(),
            duration_ms=None,
            status=status,
            actual_call=True,
            cache_hit=False,
        )


def test_stage_measurement_actual_call_and_cache_hit_are_mutually_exclusive():
    with pytest.raises(ValidationError):
        StageMeasurement(
            measurement_id="m5",
            run_id="r1",
            step_id=None,
            frame_id=None,
            iteration_index=None,
            stage="OCR",
            started_at=_now(),
            duration_ms=1.0,
            status="completed",
            actual_call=True,
            cache_hit=True,
        )


def test_stage_measurement_rejects_unknown_stage():
    with pytest.raises(ValidationError):
        StageMeasurement(
            measurement_id="m6",
            run_id="r1",
            step_id=None,
            frame_id=None,
            iteration_index=None,
            stage="not_a_stage",
            started_at=_now(),
            duration_ms=1.0,
            status="completed",
            actual_call=True,
            cache_hit=False,
        )


# --- CounterEvent -------------------------------------------------


def test_counter_event_physical_image_written_requires_physical_ref_fields():
    with pytest.raises(ValidationError):
        CounterEvent(kind="physical_image_written", occurred_at=_now(), payload={})

    ok = CounterEvent(
        kind="physical_image_written",
        occurred_at=_now(),
        payload={
            "physical_image_id": "p1",
            "purpose": "safe_evidence",
            "byte_size": 100,
            "frame_id": "f1",
        },
    )
    assert ok.kind == "physical_image_written"


def test_counter_event_capture_attempt_failed_requires_full_attribution():
    with pytest.raises(ValidationError):
        CounterEvent(kind="capture_attempt_failed", occurred_at=_now(), payload={})

    ok = CounterEvent(
        kind="capture_attempt_failed",
        occurred_at=_now(),
        payload={
            "run_id": "r1",
            "step_id": "s1",
            "capture_source": "observation",
            "attempt_sequence": 1,
            "error_type": "decode_error",
            "measurement_id": "m1",
        },
    )
    assert ok.payload["capture_source"] == "observation"


def test_counter_event_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        CounterEvent(kind="not_a_kind", occurred_at=_now(), payload={})


# --- ModelCallAudit -------------------------------------------------


def test_model_call_audit_rejects_raw_bytes_in_sanitized_payload():
    with pytest.raises(ValidationError):
        ModelCallAudit(
            audit_id="a1",
            run_id="r1",
            step_id="s1",
            frame_id="f1",
            iteration_index=0,
            model_role="planner",
            request_identity="digest-1",
            context_identity="digest-2",
            sanitized_request={"raw": b"\x89PNG..."},
            sanitized_response={},
            outcome="actual",
            source_ref=None,
            reason=None,
        )


def test_model_call_audit_rejects_credential_like_keys():
    with pytest.raises(ValidationError):
        ModelCallAudit(
            audit_id="a2",
            run_id="r1",
            step_id="s1",
            frame_id="f1",
            iteration_index=0,
            model_role="planner",
            request_identity="digest-1",
            context_identity="digest-2",
            sanitized_request={"api_key": "sk-xxxx"},
            sanitized_response={},
            outcome="actual",
            source_ref=None,
            reason=None,
        )


def test_model_call_audit_rejects_private_path_markers():
    with pytest.raises(ValidationError):
        ModelCallAudit(
            audit_id="a3",
            run_id="r1",
            step_id="s1",
            frame_id="f1",
            iteration_index=0,
            model_role="verification",
            request_identity="digest-1",
            context_identity="digest-2",
            sanitized_request={"image_ref": "/runs/r1/frames_model/f1.png"},
            sanitized_response={},
            outcome="actual",
            source_ref=None,
            reason=None,
        )


def test_model_call_audit_skipped_requires_reason():
    with pytest.raises(ValidationError):
        ModelCallAudit(
            audit_id="a4",
            run_id="r1",
            step_id="s1",
            frame_id="f1",
            iteration_index=0,
            model_role="planner",
            request_identity="digest-1",
            context_identity="digest-2",
            sanitized_request={},
            sanitized_response={},
            outcome="skipped",
            source_ref="prior-audit-id",
            reason=None,
        )


def test_model_call_audit_actual_ok():
    audit = ModelCallAudit(
        audit_id="a5",
        run_id="r1",
        step_id="s1",
        frame_id="f1",
        iteration_index=0,
        model_role="grounder",
        request_identity="digest-1",
        context_identity="digest-2",
        sanitized_request={"target": "login button"},
        sanitized_response={"found": True},
        outcome="actual",
        source_ref=None,
        reason=None,
    )
    assert audit.outcome == "actual"


# --- PerformanceSummary -------------------------------------------------


def test_performance_summary_conservation_error_recorded_not_silently_fixed():
    summary = PerformanceSummary(
        total_capture_count=10,
        unique_frame_count=2,
        duplicate_frame_count=9,  # 2+9 != 10 on purpose
        dedup_ratio=0.9,
        physical_image_count=1,
        physical_images_by_purpose={"safe_evidence": 1, "private_model": 0, "report_copy": 0},
        avoided_write_count=9,
        avoided_write_bytes=900,
        cache_hits={"ocr": 9, "template": 9, "vision": 9},
        analysis_invocations={"ocr": 1, "template": 1, "vision": 1},
        model_calls={"vision": 1, "planner": 1, "grounder": 1, "verification": 1},
        actual_model_call_count=4,
        skipped_model_call_count=0,
        stage_totals_ms={"capture": 10.0},
        completeness="complete",
        consistency_errors=[],
    )
    errors = summary.check_conservation()
    assert errors, "2+9 != 10 must be flagged, not silently corrected"
    assert summary.unique_frame_count == 2  # not auto-fixed
    assert summary.duplicate_frame_count == 9


def test_performance_summary_dedup_ratio_null_when_total_zero():
    summary = PerformanceSummary(
        total_capture_count=0,
        unique_frame_count=0,
        duplicate_frame_count=0,
        dedup_ratio=None,
        physical_image_count=0,
        physical_images_by_purpose={},
        avoided_write_count=0,
        avoided_write_bytes=0,
        cache_hits={},
        analysis_invocations={},
        model_calls={},
        actual_model_call_count=0,
        skipped_model_call_count=0,
        stage_totals_ms={},
        completeness="complete",
        consistency_errors=[],
    )
    assert summary.dedup_ratio is None
    assert not summary.check_conservation()


def test_performance_summary_rejects_nonnull_ratio_when_total_zero():
    with pytest.raises(ValidationError):
        PerformanceSummary(
            total_capture_count=0,
            unique_frame_count=0,
            duplicate_frame_count=0,
            dedup_ratio=0.0,
            physical_image_count=0,
            physical_images_by_purpose={},
            avoided_write_count=0,
            avoided_write_bytes=0,
            cache_hits={},
            analysis_invocations={},
            model_calls={},
            actual_model_call_count=0,
            skipped_model_call_count=0,
            stage_totals_ms={},
            completeness="complete",
            consistency_errors=[],
        )


# --- append-only collection semantics -------------------------------------------------


def test_stage_measurements_are_appended_not_overwritten_by_run():
    from vnc_agent.domain.run import TestRun

    run = TestRun(run_id="r1", test_case_id="tc1")
    m1 = StageMeasurement(
        measurement_id="m1", run_id="r1", step_id=None, frame_id=None,
        iteration_index=None, stage="capture", started_at=_now(),
        duration_ms=1.0, status="completed", actual_call=True, cache_hit=False,
    )
    m2 = StageMeasurement(
        measurement_id="m2", run_id="r1", step_id=None, frame_id=None,
        iteration_index=None, stage="capture", started_at=_now(),
        duration_ms=2.0, status="completed", actual_call=True, cache_hit=False,
    )
    run.stage_measurements.append(m1)
    run.stage_measurements.append(m2)
    assert [m.measurement_id for m in run.stage_measurements] == ["m1", "m2"]
