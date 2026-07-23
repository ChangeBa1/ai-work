"""Phase 3 (T016 RED / T022 GREEN): StabilityEngine consumes recorder-issued
ScreenFrames; duplicate fast-path counts as an unchanged sample without
re-reading any file; foreign-source captures never pollute this wait's local
stable count or early_exit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vnc_agent.domain.run import TestRun
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.perception.stability import StabilityEngine
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
async def test_stable_frame_count_three_reached_on_third_logical_sample(tmp_path: Path):
    names = ["baseline_full"] * 6
    driver = SequenceDriver(names)
    svc = FrameCaptureService(
        driver, run_id="r1", vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    eng = StabilityEngine(
        svc, min_delay_ms=1, max_delay_ms=5000, capture_interval_ms=1, stable_frame_count=3,
    )
    result = await eng.wait_stable(step_id="s1")
    assert result.stable is True
    assert result.end_reason == "stable"
    # 3 logical samples needed: sample1 (no comparison), sample2 (dup->1 stable),
    # sample3 (dup->2 stable == stable_frame_count-1) => stop
    assert svc._sequence == 3


@pytest.mark.asyncio
async def test_duplicate_fast_path_does_not_reread_files(tmp_path: Path, monkeypatch):
    names = ["baseline_full"] * 4
    driver = SequenceDriver(names)
    svc = FrameCaptureService(
        driver, run_id="r1", vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    eng = StabilityEngine(
        svc, min_delay_ms=1, max_delay_ms=5000, capture_interval_ms=1, stable_frame_count=3,
    )

    from vnc_agent.perception import screen_diff as sd

    calls = {"n": 0}
    real = sd.compute_diff_arrays

    def counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(sd, "compute_diff_arrays", counting)
    await eng.wait_stable(step_id="s1")
    # duplicate frames must short-circuit via ScreenFrame.deduplicated, never
    # calling compute_diff_arrays at all (unique-vs-unique comparison unused
    # here since every sample after the first is an exact duplicate)
    assert calls["n"] == 0


@pytest.mark.asyncio
async def test_foreign_source_captures_do_not_affect_wait_local_state(tmp_path: Path):
    names = ["baseline_full"] * 3
    driver = SequenceDriver(names)
    svc = FrameCaptureService(
        driver, run_id="r1", vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    # A capture from an unrelated source before the wait starts must not
    # seed the wait's local previous-sample state.
    await svc.capture(step_id="s1", capture_source="observation")

    eng = StabilityEngine(
        svc, min_delay_ms=1, max_delay_ms=5000, capture_interval_ms=1, stable_frame_count=3,
    )
    result = await eng.wait_stable(step_id="s1")
    assert result.stable is True
    # global trace has the 1 foreign frame + this wait's own samples
    sources = [f.capture_source for f in svc.test_run.frames]
    assert sources[0] == "observation"
    assert all(s == "stability_wait" for s in sources[1:])


@pytest.mark.asyncio
async def test_unique_threshold_diff_still_applies_when_not_deduplicated(tmp_path: Path):
    names = [
        "baseline_full", "single_pixel_changed", "single_pixel_changed", "single_pixel_changed",
    ]
    driver = SequenceDriver(names)
    svc = FrameCaptureService(
        driver, run_id="r1", vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    eng = StabilityEngine(
        svc, min_delay_ms=1, max_delay_ms=5000, capture_interval_ms=1, stable_frame_count=3,
        pixel_diff_threshold=0.5,  # a single pixel change must NOT cross this ratio threshold
    )
    result = await eng.wait_stable(step_id="s1")
    assert result.stable is True
    assert result.end_reason == "stable"
