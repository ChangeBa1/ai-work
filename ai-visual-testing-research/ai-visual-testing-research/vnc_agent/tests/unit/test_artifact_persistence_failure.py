"""Phase 3 (T017 RED / T019-T020 GREEN part 2): bundle transaction failure
injection — second file write, fsync, rename, and post-publish logical
commit failures; startup/reconnect orphan recovery.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from vnc_agent.domain.run import TestRun
from vnc_agent.perception.screenshot import FrameCaptureFailedError, FrameCaptureService
from vnc_agent.storage.artifact_store import ArtifactPersistenceError, ArtifactStore


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


def test_second_file_write_failure_leaves_no_partial_bundle(tmp_path: Path, monkeypatch):
    store = ArtifactStore(tmp_path)
    real_write_bytes = Path.write_bytes
    calls = {"n": 0}

    def failing_write_bytes(self, data):
        calls["n"] += 1
        if calls["n"] == 2:  # second file (private_model.png) fails
            raise OSError("simulated disk full on second file")
        return real_write_bytes(self, data)

    monkeypatch.setattr(Path, "write_bytes", failing_write_bytes)
    with pytest.raises(ArtifactPersistenceError):
        store.stage_and_publish_bundle(
            run_id="r1", owner_frame_id="f1", mask_identity="m1", content_hash="c" * 64,
            files={"safe_evidence": b"safe-bytes", "private_model": b"private-bytes"},
        )
    bundles_dir = tmp_path / "runs" / "r1" / "bundles"
    staging_dir = tmp_path / "runs" / "r1" / ".staging"
    assert not any(bundles_dir.iterdir()) if bundles_dir.exists() else True
    assert not any(staging_dir.rglob("*")) if staging_dir.exists() else True


def test_sync_failure_cleans_up_staging(tmp_path: Path, monkeypatch):
    from vnc_agent.storage import artifact_store as store_mod

    def failing_fsync(path):
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(store_mod, "_fsync_file", failing_fsync)
    store = ArtifactStore(tmp_path)
    with pytest.raises(ArtifactPersistenceError):
        store.stage_and_publish_bundle(
            run_id="r1", owner_frame_id="f1", mask_identity="m1", content_hash="c" * 64,
            files={"safe_evidence": b"safe-bytes"},
        )
    bundles_dir = tmp_path / "runs" / "r1" / "bundles"
    assert not any(bundles_dir.iterdir()) if bundles_dir.exists() else True


def test_rename_failure_publishes_nothing(tmp_path: Path, monkeypatch):
    def failing_rename(src, dst):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(os, "rename", failing_rename)
    store = ArtifactStore(tmp_path)
    with pytest.raises(ArtifactPersistenceError):
        store.stage_and_publish_bundle(
            run_id="r1", owner_frame_id="f1", mask_identity="m1", content_hash="c" * 64,
            files={"safe_evidence": b"safe-bytes"},
        )
    bundles_dir = tmp_path / "runs" / "r1" / "bundles"
    assert not any(bundles_dir.iterdir()) if bundles_dir.exists() else True


@pytest.mark.asyncio
async def test_capture_failures_never_produce_partial_screen_frame(tmp_path: Path, monkeypatch):
    """Regardless of which staging step fails, FrameCaptureService must
    raise, must not append to TestRun.frames, and must not report a
    successful physical_image_written event."""
    test_run = TestRun(run_id="r1", test_case_id="tc")
    svc = FrameCaptureService(
        GoodDriver(), run_id="r1", vnc_session_id="s1",
        test_run=test_run, artifact_store=ArtifactStore(tmp_path),
    )

    def failing_rename(src, dst):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(os, "rename", failing_rename)
    with pytest.raises(FrameCaptureFailedError):
        await svc.capture(step_id="s1", capture_source="observation")
    assert test_run.frames == []
    assert not any(e.kind == "physical_image_written" for e in test_run.counter_events)


@pytest.mark.asyncio
async def test_published_bundle_with_failed_logical_commit_becomes_orphan_and_is_quarantined(
    tmp_path: Path, monkeypatch
):
    """Bundle publish succeeds, but constructing the immutable ScreenFrame
    fails: no success frame/physical event, and the unreferenced bundle sits
    on disk until the next recover_orphans() quarantines it."""
    test_run = TestRun(run_id="r1", test_case_id="tc")
    store = ArtifactStore(tmp_path)
    svc = FrameCaptureService(
        GoodDriver(), run_id="r1", vnc_session_id="s1",
        test_run=test_run, artifact_store=store,
    )

    from vnc_agent.perception import screenshot as shot

    def boom(*args, **kwargs):
        raise ValueError("simulated logical commit failure")

    monkeypatch.setattr(shot, "ScreenFrame", boom)
    with pytest.raises(FrameCaptureFailedError):
        await svc.capture(step_id="s1", capture_source="observation")
    assert test_run.frames == []

    bundles_dir = tmp_path / "runs" / "r1" / "bundles"
    published = list(bundles_dir.iterdir())
    assert len(published) == 1, "the bundle was published to disk despite the logical failure"

    quarantined = store.recover_orphans("r1", referenced_bundle_ids=set())
    assert quarantined == [published[0].name]
    assert not any(bundles_dir.iterdir())
    quarantine_dir = tmp_path / "runs" / "r1" / ".quarantine"
    assert (quarantine_dir / published[0].name).is_dir()


def test_recover_orphans_cleans_leftover_staging_on_startup(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    staging = store._staging_root("r1") / "leftover-bundle-id"
    staging.mkdir(parents=True)
    (staging / "safe_evidence.png").write_bytes(b"partial")

    store.recover_orphans("r1", referenced_bundle_ids=set())
    assert not any(store._staging_root("r1").iterdir())


def test_recover_orphans_keeps_referenced_bundles(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    bundle = store.stage_and_publish_bundle(
        run_id="r1", owner_frame_id="f1", mask_identity="m1", content_hash="c" * 64,
        files={"safe_evidence": b"safe-bytes"},
    )
    quarantined = store.recover_orphans("r1", referenced_bundle_ids={bundle.bundle_id})
    assert quarantined == []
    bundles_dir = tmp_path / "runs" / "r1" / "bundles"
    assert (bundles_dir / bundle.bundle_id).is_dir()
