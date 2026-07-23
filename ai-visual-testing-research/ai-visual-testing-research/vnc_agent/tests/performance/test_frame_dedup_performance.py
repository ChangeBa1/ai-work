"""Phase 5 (T049): fixed local-array performance gate — no network, no real
VNC. 100 identical captures must produce exactly 1 physical write and 1
actual analysis per component; conservation holds; report_build carries its
own real measurement.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.frame_dedup_spies import SpyOCR, SpyTemplateAnalyzer
from vnc_agent.domain.run import TestRun
from vnc_agent.perception.cache import AnalysisResultCache
from vnc_agent.perception.pipeline import ObservationPipeline
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.reporting.report_builder import ReportBuilder
from vnc_agent.runtime.telemetry import derive_performance_summary
from vnc_agent.storage.artifact_store import ArtifactStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "images" / "frame_dedup"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


class RepeatingDriver:
    def __init__(self, name: str, *, repeats: int):
        self._bytes = (FIXTURES / MANIFEST[name]["file"]).read_bytes()
        meta = MANIFEST[name]
        self._resolution = (meta["width"], meta["height"])
        self.repeats = repeats

    @property
    def resolution(self):
        return self._resolution

    async def capture_screen(self) -> bytes:
        return self._bytes

    async def capture_region(self, x, y, w, h) -> bytes:
        return self._bytes


@pytest.mark.performance
@pytest.mark.asyncio
async def test_hundred_identical_one_write_one_analysis_each(tmp_path: Path, monkeypatch):
    from vnc_agent.perception import structured_screen as ss_mod

    spy_ocr = SpyOCR(results=[])
    spy_template = SpyTemplateAnalyzer(results=[])
    monkeypatch.setattr(ss_mod, "run_ocr_array", spy_ocr)
    monkeypatch.setattr(
        ss_mod,
        "match_templates_in_dir_array",
        lambda pixels, d, threshold=0.8: spy_template(pixels),
    )

    test_run = TestRun(run_id="perf-r1", test_case_id="perf-tc")
    svc = FrameCaptureService(
        RepeatingDriver("baseline_full", repeats=100),
        run_id="perf-r1", vnc_session_id="perf-s1", test_run=test_run,
        artifact_store=ArtifactStore(tmp_path),
    )
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    cache = AnalysisResultCache(max_frames=5)
    pipeline = ObservationPipeline(
        svc, templates_dir=templates_dir, ocr_enabled=True, template_enabled=True,
        vision_fallback=False, cache=cache,
    )

    # warm-up (not measured) — the median run is what the gate checks
    for _ in range(3):
        await pipeline.observe(step_id="warmup", capture_source="observation")

    svc.clear()
    cache.clear()
    test_run.frames.clear()
    test_run.counter_events.clear()
    spy_ocr.reset()
    spy_template.reset()

    for _ in range(100):
        await pipeline.observe(step_id="s1", capture_source="observation")

    assert spy_ocr.call_count == 1, "100 identical captures must analyze OCR exactly once"
    assert spy_template.call_count == 1, "100 identical captures must analyze template exactly once"

    # summary.physical_image_count below is the source of truth for "wrote
    # exactly once" — it is derived only from events tied to frames in the
    # (warm-up-cleared) TestRun.frames, so it correctly ignores the warm-up
    # phase's own on-disk bundle.
    summary = derive_performance_summary(test_run)
    assert summary.total_capture_count == 100
    assert summary.unique_frame_count == 1
    assert summary.duplicate_frame_count == 99
    assert summary.physical_image_count == 1
    assert summary.avoided_write_count == 99
    assert not summary.check_conservation()
    assert summary.completeness == "complete"

    # report_build carries its own real measurement (not self-referential /
    # not re-derived) — telemetry-contract.md "Report build boundary"
    report_builder = ReportBuilder(ArtifactStore(tmp_path))
    report_builder.build(test_run, formats=("json",))
    build_stages = [m for m in test_run.stage_measurements if m.stage == "report_build"]
    assert len(build_stages) == 1
    assert build_stages[0].status == "completed"
