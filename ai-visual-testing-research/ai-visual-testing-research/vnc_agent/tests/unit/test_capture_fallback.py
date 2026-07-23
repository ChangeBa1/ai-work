"""Phase 3 (T017 RED / T019-T020 GREEN part 1): capture failure matrix.

decode/mask-encode failures abort the capture — no ScreenFrame, no
downstream analysis/verification, no fabricated content hash/pixel format.
Hash/candidate-compare failures degrade to unique + full analysis without
raising and without producing dedup/cache-hit/avoided/skipped accounting.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from vnc_agent.domain.run import TestRun
from vnc_agent.perception.screenshot import (
    CaptureDecodeError,
    FrameCaptureFailedError,
    FrameCaptureService,
)
from vnc_agent.storage.artifact_store import ArtifactStore


class GarbageDriver:
    resolution = (10, 10)

    async def capture_screen(self) -> bytes:
        return b"not a real png"

    async def capture_region(self, x, y, w, h) -> bytes:
        return await self.capture_screen()


class GoodDriver:
    def __init__(self):
        import cv2

        self._img = np.zeros((10, 10, 3), dtype=np.uint8)
        ok, buf = cv2.imencode(".png", self._img)
        self._bytes = buf.tobytes()

    @property
    def resolution(self):
        return (10, 10)

    async def capture_screen(self) -> bytes:
        return self._bytes

    async def capture_region(self, x, y, w, h) -> bytes:
        return self._bytes


@pytest.mark.asyncio
async def test_decode_failure_raises_and_produces_no_screen_frame(tmp_path: Path):
    test_run = TestRun(run_id="r1", test_case_id="tc")
    svc = FrameCaptureService(
        GarbageDriver(), run_id="r1", vnc_session_id="s1",
        test_run=test_run, artifact_store=ArtifactStore(tmp_path),
    )
    with pytest.raises(FrameCaptureFailedError):
        await svc.capture(step_id="s1", capture_source="observation")
    assert test_run.frames == []


@pytest.mark.asyncio
async def test_decode_failure_records_capture_attempt_failed_counter(tmp_path: Path):
    test_run = TestRun(run_id="r1", test_case_id="tc")
    svc = FrameCaptureService(
        GarbageDriver(), run_id="r1", vnc_session_id="s1",
        test_run=test_run, artifact_store=ArtifactStore(tmp_path),
    )
    with pytest.raises(FrameCaptureFailedError):
        await svc.capture(step_id="step-x", capture_source="observation")
    assert len(test_run.counter_events) == 1
    event = test_run.counter_events[0]
    assert event.kind == "capture_attempt_failed"
    assert event.payload["run_id"] == "r1"
    assert event.payload["step_id"] == "step-x"
    assert event.payload["capture_source"] == "observation"
    assert event.payload["error_type"] == "decode_error"
    assert event.payload["attempt_sequence"] == 1


@pytest.mark.asyncio
async def test_decode_failure_underlying_cause_is_capture_decode_error(tmp_path: Path):
    test_run = TestRun(run_id="r1", test_case_id="tc")
    svc = FrameCaptureService(
        GarbageDriver(), run_id="r1", vnc_session_id="s1",
        test_run=test_run, artifact_store=ArtifactStore(tmp_path),
    )
    with pytest.raises(FrameCaptureFailedError) as excinfo:
        await svc.capture(step_id="s1", capture_source="observation")
    assert isinstance(excinfo.value.cause, CaptureDecodeError)


@pytest.mark.asyncio
async def test_hash_optimization_failure_degrades_to_unique_without_raising(
    tmp_path: Path, monkeypatch
):
    """Simulated hash-optimization failure (content_hash=None) must never
    prevent a successful unique capture, and must never be reported as a
    dedup/cache-hit/avoided event."""
    from vnc_agent.perception import screenshot as shot

    test_run = TestRun(run_id="r1", test_case_id="tc")
    svc = FrameCaptureService(
        GoodDriver(), run_id="r1", vnc_session_id="s1",
        test_run=test_run, artifact_store=ArtifactStore(tmp_path),
    )

    real_decode = shot.decode_capture

    def failing_hash_decode(raw_png: bytes):
        dc = real_decode(raw_png)
        return shot.DecodedCapture(
            pixels=dc.pixels, pixel_format=dc.pixel_format,
            content_hash=None, width=dc.width, height=dc.height,
        )

    monkeypatch.setattr(shot, "decode_capture", failing_hash_decode)
    outcome1 = await svc.capture(step_id="s1", capture_source="observation")
    outcome2 = await svc.capture(step_id="s1", capture_source="observation")
    assert outcome1.frame.deduplicated is False
    assert outcome2.frame.deduplicated is False  # can't prove duplicate without a hash
    assert outcome1.frame.content_hash is None
    assert not any(e.kind == "analysis_cache_hit" for e in test_run.counter_events)


@pytest.mark.asyncio
async def test_candidate_compare_exception_degrades_to_unique(tmp_path: Path, monkeypatch):
    from vnc_agent.perception import screenshot as shot

    test_run = TestRun(run_id="r1", test_case_id="tc")
    svc = FrameCaptureService(
        GoodDriver(), run_id="r1", vnc_session_id="s1",
        test_run=test_run, artifact_store=ArtifactStore(tmp_path),
    )
    await svc.capture(step_id="s1", capture_source="observation")

    def boom(*args, **kwargs):
        raise RuntimeError("simulated pixel-compare failure")

    monkeypatch.setattr(shot, "pixels_strictly_equal", boom)
    outcome2 = await svc.capture(step_id="s1", capture_source="observation")
    assert outcome2.frame.deduplicated is False
