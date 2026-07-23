"""Phase 4 (T032) RED->GREEN: cache get/put/eviction exceptions degrade to a
full analysis for the current component, never a fabricated hit/skip/avoided
outcome, and never block the current frame's result
(perception-cache-contract.md "Error behavior").
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vnc_agent.domain.run import TestRun
from vnc_agent.perception.cache import AnalysisResultCache
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.perception.structured_screen import assemble_structured_screen_from_pixels
from vnc_agent.storage.artifact_store import ArtifactStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "images" / "frame_dedup"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


class OneShotDriver:
    def __init__(self, name: str):
        self._bytes = (FIXTURES / MANIFEST[name]["file"]).read_bytes()
        meta = MANIFEST[name]
        self._resolution = (meta["width"], meta["height"])

    @property
    def resolution(self):
        return self._resolution

    async def capture_screen(self) -> bytes:
        return self._bytes

    async def capture_region(self, x, y, w, h) -> bytes:
        return self._bytes


@pytest.mark.asyncio
async def test_cache_get_exception_falls_back_to_full_analysis(tmp_path: Path, monkeypatch):
    driver = OneShotDriver("baseline_full")
    svc = FrameCaptureService(
        driver, run_id="r1", vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    cache = AnalysisResultCache(max_frames=5)
    outcome1 = await svc.capture(step_id="s1", capture_source="observation")
    assemble_structured_screen_from_pixels(
        outcome1.frame, outcome1.decoded.pixels, cache=cache,
        ocr_enabled=True, template_enabled=False,
    )

    def boom(*args, **kwargs):
        raise RuntimeError("simulated cache get failure")

    monkeypatch.setattr(cache, "lookup", boom)

    outcome2 = await svc.capture(step_id="s1", capture_source="observation")
    assert outcome2.frame.deduplicated is True  # eligible for lookup, but lookup is broken

    events: list[dict] = []
    screen2 = assemble_structured_screen_from_pixels(
        outcome2.frame, outcome2.decoded.pixels, cache=cache,
        ocr_enabled=True, template_enabled=False,
        on_analysis_event=events.append,
    )
    # still produces a usable result despite the cache being broken
    assert isinstance(screen2.ocr_items, list)
    ocr_events = [e for e in events if e["component"] == "ocr"]
    assert ocr_events and ocr_events[0]["outcome"] == "miss"
    assert "ocr" not in screen2.analysis_source_refs, (
        "a broken cache get must never masquerade as a hit"
    )


@pytest.mark.asyncio
async def test_cache_put_exception_still_returns_usable_result(tmp_path: Path, monkeypatch):
    driver = OneShotDriver("baseline_full")
    svc = FrameCaptureService(
        driver, run_id="r1", vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    cache = AnalysisResultCache(max_frames=5)

    def boom(*args, **kwargs):
        raise RuntimeError("simulated cache put failure")

    monkeypatch.setattr(cache, "store", boom)

    outcome1 = await svc.capture(step_id="s1", capture_source="observation")
    events: list[dict] = []
    screen1 = assemble_structured_screen_from_pixels(
        outcome1.frame, outcome1.decoded.pixels, cache=cache,
        ocr_enabled=True, template_enabled=False,
        on_analysis_event=events.append,
    )
    assert isinstance(screen1.ocr_items, list)
    ocr_events = [e for e in events if e["component"] == "ocr"]
    assert ocr_events and ocr_events[0]["outcome"] == "miss"
    # entry was never actually stored (put raised), so len(cache) stays 0 —
    # proving the failure was not silently swallowed into a false success
    assert len(cache) == 0
