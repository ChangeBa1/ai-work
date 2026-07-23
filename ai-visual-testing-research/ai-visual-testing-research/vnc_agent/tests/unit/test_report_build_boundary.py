"""Phase 5 (T048) RED->GREEN: report_build has no self-reference and never
includes the final encode/write; report_output is a separate optional stage
that fails without corrupting existing run facts (telemetry-contract.md
"Report build boundary").
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from vnc_agent.domain.run import TestRun
from vnc_agent.reporting.report_builder import ReportBuilder
from vnc_agent.storage.artifact_store import ArtifactStore


def _run() -> TestRun:
    return TestRun(
        run_id="r1", test_case_id="tc", status="passed",
        started_at=datetime.now(UTC), ended_at=datetime.now(UTC),
    )


def test_report_build_and_report_output_are_separate_stage_measurements(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    builder = ReportBuilder(store)
    run = _run()

    builder.build(run, formats=("json", "html"))

    build_stages = [m for m in run.stage_measurements if m.stage == "report_build"]
    output_stages = [m for m in run.stage_measurements if m.stage == "report_output"]
    assert len(build_stages) == 1
    assert len(output_stages) == 1
    assert build_stages[0].status == "completed"
    assert output_stages[0].status == "completed"


def test_report_output_failure_does_not_corrupt_existing_run_facts(tmp_path: Path, monkeypatch):
    store = ArtifactStore(tmp_path)
    builder = ReportBuilder(store)
    run = _run()

    from pathlib import Path as PathCls

    real_write_text = PathCls.write_text

    def failing_write_text(self, *args, **kwargs):
        raise OSError("simulated disk full")

    monkeypatch.setattr(PathCls, "write_text", failing_write_text)
    with pytest.raises(OSError):
        builder.build(run, formats=("json",))

    output_stages = [m for m in run.stage_measurements if m.stage == "report_output"]
    assert len(output_stages) == 1
    assert output_stages[0].status == "failed"
    assert output_stages[0].duration_ms is not None
    # existing facts (status/timestamps) must be untouched by the failed write
    assert run.status == "passed"
    monkeypatch.setattr(PathCls, "write_text", real_write_text)


def test_report_build_measurement_precedes_report_output_and_excludes_write_time(
    tmp_path: Path, monkeypatch
):
    store = ArtifactStore(tmp_path)
    builder = ReportBuilder(store)
    run = _run()

    from pathlib import Path as PathCls

    real_write_text = PathCls.write_text

    def slow_write_text(self, *args, **kwargs):
        import time

        time.sleep(0.05)
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(PathCls, "write_text", slow_write_text)
    builder.build(run, formats=("json",))

    build_stage = next(m for m in run.stage_measurements if m.stage == "report_build")
    output_stage = next(m for m in run.stage_measurements if m.stage == "report_output")
    assert build_stage.duration_ms < output_stage.duration_ms
