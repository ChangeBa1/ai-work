"""Phase 5 (T043) RED->GREEN: the same event object enters both
`TestRun` and structured JSON Lines logs — never independently recomputed
per output (telemetry-contract.md "Stable structured-log events").
"""

from __future__ import annotations

from pathlib import Path

import pytest
import structlog

from vnc_agent.domain.run import TestRun
from vnc_agent.perception.screenshot import FrameCaptureFailedError, FrameCaptureService
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
        import numpy as np

        img = np.zeros((10, 10, 3), dtype=np.uint8)
        ok, buf = cv2.imencode(".png", img)
        self._bytes = buf.tobytes()

    @property
    def resolution(self):
        return (10, 10)

    async def capture_screen(self) -> bytes:
        return self._bytes

    async def capture_region(self, x, y, w, h) -> bytes:
        return self._bytes


@pytest.mark.asyncio
async def test_frame_dedup_and_physical_events_appear_in_both_test_run_and_logs(
    tmp_path: Path,
):
    test_run = TestRun(run_id="r1", test_case_id="tc")
    svc = FrameCaptureService(
        GoodDriver(), run_id="r1", vnc_session_id="s1",
        test_run=test_run, artifact_store=ArtifactStore(tmp_path),
    )
    with structlog.testing.capture_logs() as logs:
        await svc.capture(step_id="s1", capture_source="observation")
        await svc.capture(step_id="s1", capture_source="observation")

    log_events = {entry["event"] for entry in logs}
    assert "frame_dedup_decision" in log_events
    assert "physical_image_event" in log_events
    assert "stage_measurement" in log_events

    dedup_run_events = [e for e in test_run.counter_events if e.kind == "frame_dedup_decision"]
    dedup_log_events = [e for e in logs if e["event"] == "frame_dedup_decision"]
    assert len(dedup_run_events) == len(dedup_log_events) == 2
    for run_event, log_entry in zip(dedup_run_events, dedup_log_events, strict=True):
        assert run_event.payload["frame_id"] == log_entry["frame_id"]
        assert run_event.payload["deduplicated"] == log_entry["deduplicated"]


@pytest.mark.asyncio
async def test_failed_capture_attempt_log_has_full_attribution(tmp_path: Path):
    test_run = TestRun(run_id="r1", test_case_id="tc")
    svc = FrameCaptureService(
        GarbageDriver(), run_id="r1", vnc_session_id="s1",
        test_run=test_run, artifact_store=ArtifactStore(tmp_path),
    )
    with structlog.testing.capture_logs() as logs:
        with pytest.raises(FrameCaptureFailedError):
            await svc.capture(step_id="step-x", capture_source="observation")

    failed_logs = [e for e in logs if e["event"] == "capture_attempt_failed"]
    assert len(failed_logs) == 1
    entry = failed_logs[0]
    assert entry["run_id"] == "r1"
    assert entry["step_id"] == "step-x"
    assert entry["capture_source"] == "observation"
    assert entry["attempt_sequence"] == 1
    assert entry["error_type"] == "decode_error"
    assert entry["measurement_id"]

    # same shape as the TestRun-side event
    run_event = test_run.counter_events[0]
    assert run_event.kind == "capture_attempt_failed"
    assert run_event.payload["measurement_id"] == entry["measurement_id"]


@pytest.mark.asyncio
async def test_artifact_bundle_recovery_logged_with_run_and_bundle_ids(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    bundle = store.stage_and_publish_bundle(
        run_id="r1", owner_frame_id="f1", mask_identity="m1", content_hash="c" * 64,
        files={"safe_evidence": b"safe-bytes"},
    )
    with structlog.testing.capture_logs() as logs:
        quarantined = store.recover_orphans("r1", referenced_bundle_ids=set())

    assert quarantined == [bundle.bundle_id]
    recovery_logs = [e for e in logs if e["event"] == "artifact_bundle_recovery"]
    assert len(recovery_logs) == 1
    assert recovery_logs[0]["run_id"] == "r1"
    assert bundle.bundle_id in recovery_logs[0]["quarantined_bundle_ids"]


def test_model_call_audit_log_never_leaks_bytes_or_credentials():
    """Structural guarantee shared with ModelCallAudit's own validator: the
    JSON Lines encoding of a sanitized payload must never contain raw bytes
    (they are not JSON-serializable in the first place, and the
    sanitization scan already rejects them before this point)."""
    from pydantic import ValidationError

    from vnc_agent.runtime.telemetry import ModelCallAudit

    with pytest.raises(ValidationError):
        ModelCallAudit(
            audit_id="a1", run_id="r1", step_id=None, frame_id=None, iteration_index=None,
            model_role="planner", request_identity="x", context_identity="y",
            sanitized_request={"api_key": "sk-secret"}, sanitized_response={},
            outcome="actual", source_ref=None, reason=None,
        )
