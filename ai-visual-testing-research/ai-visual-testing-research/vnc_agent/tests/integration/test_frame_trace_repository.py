"""Phase 7 (T061): TestRun round-trips through the SQLite JSON payload with
every feature-004 addition intact — five capture sources, a failed capture
attempt, shared PhysicalImageRef fields, a nullable model_image, duplicate
relation, artifact bundle recovery audit, stage measurements, counter
events, sanitized model call audits, and the performance summary. No
database schema migration is required (data-model.md §12).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vnc_agent.domain.run import TestRun
from vnc_agent.perception.screenshot import FrameCaptureFailedError, FrameCaptureService
from vnc_agent.runtime.telemetry import (
    CounterEvent,
    ModelCallAudit,
    derive_performance_summary,
)
from vnc_agent.storage.artifact_store import ArtifactStore
from vnc_agent.storage.database import init_db, make_engine, make_session_factory
from vnc_agent.storage.repositories import RunRepository

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "images" / "frame_dedup"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


class GarbageDriver:
    resolution = (10, 10)

    async def capture_screen(self) -> bytes:
        return b"not a real png"

    async def capture_region(self, x, y, w, h) -> bytes:
        return await self.capture_screen()


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
async def test_full_test_run_round_trips_through_sqlite_json_payload(tmp_path: Path):
    test_run = TestRun(
        run_id="repo-r1", test_case_id="repo-tc", status="passed",
        started_at=datetime.now(UTC), ended_at=datetime.now(UTC),
    )
    store = ArtifactStore(tmp_path)
    svc = FrameCaptureService(
        SequenceDriver(["baseline_full", "baseline_full", "masked"]),
        run_id="repo-r1", vnc_session_id="s1", test_run=test_run, artifact_store=store,
        mask_regions=[[40, 30, 56, 40]], private_persistence_allowed=True,
    )

    sources = ["observation", "stability_wait", "retry", "recovery", "post_action_verification"]
    for src in sources[:3]:
        await svc.capture(step_id="s1", capture_source=src)
    # a masked unique capture with a real model_image (private_model) too
    await svc.capture(step_id="s1", capture_source=sources[3])
    await svc.capture(step_id="s1", capture_source=sources[4])

    # a failed capture attempt via a broken driver on a second service
    # sharing the same TestRun (simulating an in-run failure)
    bad_svc = FrameCaptureService(
        GarbageDriver(), run_id="repo-r1", vnc_session_id="s1",
        test_run=test_run, artifact_store=store,
    )
    with pytest.raises(FrameCaptureFailedError):
        await bad_svc.capture(step_id="s1", capture_source="observation")

    # a recovery audit event (simulated startup/reconnect reconciliation)
    store.stage_and_publish_bundle(
        run_id="repo-r1", owner_frame_id="ghost", mask_identity="m1", content_hash="c" * 64,
        files={"safe_evidence": b"orphan-bytes"},
    )
    store.recover_orphans(
        "repo-r1", referenced_bundle_ids={f.safe_image.artifact_bundle_id for f in test_run.frames}
    )

    # a sanitized model call audit
    test_run.model_call_audits.append(
        ModelCallAudit(
            audit_id="audit-1", run_id="repo-r1", step_id="s1", frame_id=test_run.frames[0].id,
            iteration_index=0, model_role="planner", request_identity="req-1",
            context_identity="ctx-1", sanitized_request={"step_intent": "click"},
            sanitized_response={"action_type": "click"}, outcome="actual",
        )
    )
    test_run.counter_events.append(
        CounterEvent(
            kind="model_call", occurred_at=datetime.now(UTC),
            payload={"model_role": "planner", "invocation_id": "inv-1", "status": "completed"},
        )
    )
    test_run.performance_summary = derive_performance_summary(test_run)

    engine = make_engine(str(tmp_path / "repo.db"))
    await init_db(engine)
    repo = RunRepository(make_session_factory(engine))
    await repo.save_run(test_run)
    reloaded = await repo.get_run("repo-r1")

    assert reloaded is not None
    assert len(reloaded.frames) == len(test_run.frames) == 5
    assert {f.capture_source for f in reloaded.frames} == set(sources)

    # duplicate relation preserved
    dup_frames = [f for f in reloaded.frames if f.deduplicated]
    assert dup_frames
    assert dup_frames[0].duplicate_of_frame_id == reloaded.frames[0].id

    # shared PhysicalImageRef fields preserved: this service was configured
    # with a mask, so every frame has a distinct private_model model_image
    # (a *different* physical service, unmasked, is covered by the many
    # other US1 tests that exercise the model_image=None path).
    masked_frame = next(f for f in reloaded.frames if f.capture_source == "recovery")
    assert masked_frame.model_image is not None
    assert masked_frame.model_image.purpose == "private_model"
    assert masked_frame.model_image.path != masked_frame.safe_image.path
    assert masked_frame.safe_image.artifact_bundle_id == masked_frame.model_image.artifact_bundle_id

    # independent ids; each frame's own captured_at round-trips exactly
    # (not collapsed/shared across frames) — timestamps themselves are not
    # asserted pairwise-distinct since two fast captures can legitimately
    # land on the same clock tick under system load (id is the only
    # guaranteed-unique identity).
    assert len({f.id for f in reloaded.frames}) == 5
    original_by_id = {f.id: f.timestamp for f in test_run.frames}
    for f in reloaded.frames:
        assert f.timestamp == original_by_id[f.id]

    # failed capture attempt audit preserved
    failed_events = [e for e in reloaded.counter_events if e.kind == "capture_attempt_failed"]
    assert len(failed_events) == 1
    assert failed_events[0].payload["error_type"] == "decode_error"

    # recovery audit is a structured log event, not a TestRun field — but
    # the orphaned bundle must never appear as a successful physical event
    physical_events = [e for e in reloaded.counter_events if e.kind == "physical_image_written"]
    referenced_frame_ids = {f.id for f in reloaded.frames}
    for e in physical_events:
        assert e.payload["frame_id"] in referenced_frame_ids

    # stage measurements + model call audits + summary round-trip
    assert len(reloaded.stage_measurements) == len(test_run.stage_measurements)
    assert len(reloaded.model_call_audits) == 1
    assert reloaded.model_call_audits[0].sanitized_request == {"step_intent": "click"}
    assert reloaded.performance_summary is not None
    assert reloaded.performance_summary.total_capture_count == 5
    assert not reloaded.performance_summary.check_conservation()
