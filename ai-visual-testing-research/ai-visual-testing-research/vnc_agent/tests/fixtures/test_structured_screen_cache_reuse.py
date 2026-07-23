"""Phase 4 (T028 RED / T037 GREEN): only strictly-adjacent `deduplicated=true`
frames reuse component results, and a *new* StructuredScreen is always
created — current frame id/time/path are never overwritten by the cached
source's identity. Unique frames never even attempt a lookup.
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


@pytest.mark.asyncio
async def test_duplicate_frame_reuses_component_results_but_builds_fresh_screen(tmp_path: Path):
    driver = SequenceDriver(["baseline_full", "baseline_full"])
    svc = FrameCaptureService(
        driver, run_id="r1", vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    cache = AnalysisResultCache(max_frames=5)

    outcome1 = await svc.capture(step_id="s1", capture_source="observation")
    screen1 = assemble_structured_screen_from_pixels(
        outcome1.frame, outcome1.decoded.pixels, cache=cache, ocr_enabled=False,
        template_enabled=False,
    )

    outcome2 = await svc.capture(step_id="s1", capture_source="observation")
    assert outcome2.frame.deduplicated is True
    screen2 = assemble_structured_screen_from_pixels(
        outcome2.frame, outcome2.decoded.pixels,
        previous_pixels=outcome2.previous_decoded.pixels if outcome2.previous_decoded else None,
        cache=cache, ocr_enabled=False, template_enabled=False,
    )

    # Fresh object, distinct frame identity/time/path fields even on reuse
    assert screen2 is not screen1
    assert screen2.frame_id == outcome2.frame.id
    assert screen2.frame_id != screen1.frame_id
    assert screen2.captured_at == outcome2.frame.timestamp

    # Diff is the deterministic duplicate short-circuit
    assert screen2.changed_since_last is False
    assert screen2.global_diff_ratio == 0.0
    assert screen2.changed_regions == []
    assert screen2.local_blobs == []
    assert screen2.deduplicated is True
    assert screen2.duplicate_of_frame_id == outcome1.frame.id


@pytest.mark.asyncio
async def test_unique_frame_never_looks_up_cache(tmp_path: Path, monkeypatch):
    driver = SequenceDriver(["baseline_full", "single_pixel_changed"])
    svc = FrameCaptureService(
        driver, run_id="r1", vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    cache = AnalysisResultCache(max_frames=5)

    outcome1 = await svc.capture(step_id="s1", capture_source="observation")
    assemble_structured_screen_from_pixels(
        outcome1.frame, outcome1.decoded.pixels, cache=cache, ocr_enabled=False,
        template_enabled=False,
    )

    lookup_calls = {"n": 0}
    real_lookup = cache.lookup

    def counting_lookup(*args, **kwargs):
        lookup_calls["n"] += 1
        return real_lookup(*args, **kwargs)

    monkeypatch.setattr(cache, "lookup", counting_lookup)

    from vnc_agent.perception import structured_screen as ss_mod

    diff_calls = {"n": 0}
    real_diff = ss_mod.compute_diff_arrays

    def counting_diff(*args, **kwargs):
        diff_calls["n"] += 1
        return real_diff(*args, **kwargs)

    monkeypatch.setattr(ss_mod, "compute_diff_arrays", counting_diff)

    outcome2 = await svc.capture(step_id="s1", capture_source="observation")
    assert outcome2.frame.deduplicated is False
    screen2 = assemble_structured_screen_from_pixels(
        outcome2.frame, outcome2.decoded.pixels,
        previous_pixels=outcome2.previous_decoded.pixels if outcome2.previous_decoded else None,
        cache=cache, ocr_enabled=False, template_enabled=False,
    )
    assert screen2.deduplicated is False
    # unique frame: a real diff computation actually ran, not the
    # deterministic duplicate short-circuit
    assert diff_calls["n"] == 1
    assert lookup_calls["n"] == 0, "unique frames must never attempt a cache lookup"
