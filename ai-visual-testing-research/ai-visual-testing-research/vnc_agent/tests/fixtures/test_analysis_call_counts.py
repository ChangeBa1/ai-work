"""Phase 4 (T029 RED / T038 GREEN, T040 final): independent Spy-based
invocation counting for OCR/template across a 10-identical + 1-changed
sequence, and A→B→A re-invocation on the third (non-adjacent) occurrence.

Call counts are the oracle — never duration or report-side counting
(telemetry-contract.md "Test oracle").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.support.frame_dedup_spies import SpyOCR, SpyTemplateAnalyzer
from vnc_agent.domain.run import TestRun
from vnc_agent.perception import structured_screen as ss_mod
from vnc_agent.perception.cache import AnalysisResultCache
from vnc_agent.perception.pipeline import ObservationPipeline
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.storage.artifact_store import ArtifactStore

FIXTURES = Path(__file__).resolve().parent / "images" / "frame_dedup"
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


def _pipeline(driver, tmp_path: Path, templates_dir: Path) -> ObservationPipeline:
    svc = FrameCaptureService(
        driver, run_id="r1", vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    cache = AnalysisResultCache(max_frames=5)
    return ObservationPipeline(
        svc, templates_dir=templates_dir, ocr_enabled=True, template_enabled=True,
        vision_fallback=False, cache=cache,
    )


@pytest.mark.asyncio
async def test_ten_identical_plus_one_changed_analyzes_twice(tmp_path: Path, monkeypatch):
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
    names = ["baseline_full"] * 10 + ["single_pixel_changed"]
    pipeline = _pipeline(SequenceDriver(names), tmp_path, templates_dir)

    for _ in range(11):
        await pipeline.observe(step_id="s1", capture_source="observation")

    assert spy_ocr.call_count == 2, "OCR must run exactly twice: first unique + the 11th"
    assert spy_template.call_count == 2, "template must run exactly twice"


@pytest.mark.asyncio
async def test_a_b_a_reinvokes_on_third_non_adjacent_occurrence(tmp_path: Path, monkeypatch):
    spy_ocr = SpyOCR(results=[])
    monkeypatch.setattr(ss_mod, "run_ocr_array", spy_ocr)

    names = ["baseline_full", "single_pixel_changed", "baseline_full"]
    pipeline = _pipeline(SequenceDriver(names), tmp_path, tmp_path / "empty-templates")
    pipeline.template_enabled = False

    for _ in range(3):
        await pipeline.observe(step_id="s1", capture_source="observation")

    assert spy_ocr.call_count == 3, "A->B->A: each is a fresh full analysis, none reused"


@pytest.mark.asyncio
async def test_nine_duplicates_hit_and_tenth_change_misses(tmp_path: Path, monkeypatch):
    spy_ocr = SpyOCR(results=[])
    monkeypatch.setattr(ss_mod, "run_ocr_array", spy_ocr)

    names = ["baseline_full"] * 10 + ["single_pixel_changed"]
    pipeline = _pipeline(SequenceDriver(names), tmp_path, tmp_path / "empty-templates")
    pipeline.template_enabled = False

    screens = []
    for _ in range(11):
        screens.append(await pipeline.observe(step_id="s1", capture_source="observation"))

    for i in range(1, 10):
        assert "ocr" in screens[i].analysis_source_refs, f"screen {i} should be a cache hit"
    assert "ocr" not in screens[10].analysis_source_refs, (
        "the changed 11th must be a fresh analysis"
    )
    assert spy_ocr.call_count == 2
