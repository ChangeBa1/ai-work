"""Phase 5 (T042) RED->GREEN: DeterministicClock-driven StageMeasurement
append-only recording (telemetry-contract.md "Measurement semantics").

completed/failed must keep the actually observed (deterministic, injected)
duration; unavailable stages are never recorded with a fabricated 0ms.
"""

from __future__ import annotations

import pytest

from tests.support.frame_dedup_spies import DeterministicClock
from vnc_agent.domain.run import TestRun
from vnc_agent.runtime.telemetry import measure_stage


def test_measure_stage_completed_appends_real_duration():
    test_run = TestRun(run_id="r1", test_case_id="tc")
    clock = DeterministicClock(step_ns=2_000_000)  # 2ms per read
    with measure_stage(test_run, stage="capture", run_id="r1", clock=clock):
        pass
    assert len(test_run.stage_measurements) == 1
    m = test_run.stage_measurements[0]
    assert m.stage == "capture"
    assert m.status == "completed"
    assert m.duration_ms == pytest.approx(2.0)
    assert m.actual_call is True
    assert m.cache_hit is False


def test_measure_stage_failed_keeps_real_duration_and_reraises():
    test_run = TestRun(run_id="r1", test_case_id="tc")
    clock = DeterministicClock(step_ns=3_000_000)
    with pytest.raises(ValueError):
        with measure_stage(test_run, stage="persistence", run_id="r1", clock=clock):
            raise ValueError("simulated failure")
    m = test_run.stage_measurements[0]
    assert m.status == "failed"
    assert m.duration_ms == pytest.approx(3.0)
    assert m.error_type == "ValueError"


def test_measure_stage_cache_hit_marks_actual_call_false():
    test_run = TestRun(run_id="r1", test_case_id="tc")
    clock = DeterministicClock(step_ns=1_000_000)
    with measure_stage(
        test_run, stage="OCR", run_id="r1", clock=clock, actual_call=False, cache_hit=True,
        source_ref="frame-1",
    ):
        pass
    m = test_run.stage_measurements[0]
    assert m.actual_call is False
    assert m.cache_hit is True
    assert m.source_ref == "frame-1"
    assert m.duration_ms is not None  # still a real observed duration


def test_measure_stage_appends_not_overwrites_across_many_stages():
    test_run = TestRun(run_id="r1", test_case_id="tc")
    clock = DeterministicClock(step_ns=1_000_000)
    for stage in ("capture", "OCR", "template", "vision", "planner"):
        with measure_stage(test_run, stage=stage, run_id="r1", clock=clock):
            pass
    assert [m.stage for m in test_run.stage_measurements] == [
        "capture", "OCR", "template", "vision", "planner",
    ]


def test_record_unavailable_stage_has_null_duration():
    from vnc_agent.runtime.telemetry import record_unavailable_stage

    test_run = TestRun(run_id="r1", test_case_id="tc")
    record_unavailable_stage(test_run, stage="report_output", run_id="r1")
    m = test_run.stage_measurements[0]
    assert m.status == "unavailable"
    assert m.duration_ms is None
