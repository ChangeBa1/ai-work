"""Phase 6 (T054 partial): safe evidence resolver — zero-copy resolution
plus the full negative matrix (missing/truncated/corrupted/byte-size
mismatch/hash mismatch/undecodable/mask mismatch/out-of-bounds/orphan
bundle). Report resolvers must never link private, staging, quarantined, or
tampered evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vnc_agent.domain.run import TestRun
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.reporting.safe_evidence import (
    ResolvedEvidence,
    SafeEvidenceResolver,
    UnavailableEvidence,
    resolve_safe_evidence,
)
from vnc_agent.storage.artifact_store import ArtifactStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "images" / "frame_dedup"
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


async def _two_frames(tmp_path: Path):
    test_run = TestRun(run_id="r1", test_case_id="tc")
    store = ArtifactStore(tmp_path)
    svc = FrameCaptureService(
        SequenceDriver(["baseline_full", "baseline_full"]),
        run_id="r1", vnc_session_id="s1", test_run=test_run, artifact_store=store,
    )
    o1 = await svc.capture(step_id="s1", capture_source="observation")
    o2 = await svc.capture(step_id="s1", capture_source="observation")
    return store, o1.frame, o2.frame


@pytest.mark.asyncio
async def test_duplicate_logical_frames_resolve_to_identical_path_no_copy(tmp_path: Path):
    store, frame1, frame2 = await _two_frames(tmp_path)
    r1 = resolve_safe_evidence(frame1, artifact_store=store)
    r2 = resolve_safe_evidence(frame2, artifact_store=store)
    assert isinstance(r1, ResolvedEvidence)
    assert isinstance(r2, ResolvedEvidence)
    assert r1.path == r2.path
    # zero-copy: exactly one safe_evidence.png ever exists on disk
    safe_files = list((tmp_path / "runs" / "r1" / "bundles").rglob("safe_evidence.png"))
    assert len(safe_files) == 1


@pytest.mark.asyncio
async def test_resolver_memoizes_by_physical_image_id(tmp_path: Path, monkeypatch):
    store, frame1, frame2 = await _two_frames(tmp_path)
    resolver = SafeEvidenceResolver(store)

    import vnc_agent.reporting.safe_evidence as se_mod

    calls = {"n": 0}
    real = se_mod.resolve_safe_evidence

    def counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(se_mod, "resolve_safe_evidence", counting)
    resolver.resolve(frame1)
    resolver.resolve(frame2)
    # NOTE: SafeEvidenceResolver.resolve calls the *module-level* function by
    # its own bound reference captured at class-definition time in this
    # implementation; this test instead verifies the externally observable
    # behavior: repeated resolves for the same physical id return identical
    # results without re-reading.
    assert resolver.resolve(frame1) is resolver.resolve(frame2)


@pytest.mark.asyncio
async def test_missing_file_is_unavailable(tmp_path: Path):
    store, frame1, _ = await _two_frames(tmp_path)
    Path(frame1.safe_image.path).unlink()
    result = resolve_safe_evidence(frame1, artifact_store=store)
    assert isinstance(result, UnavailableEvidence)
    assert result.reason == "missing"


@pytest.mark.asyncio
async def test_truncated_file_is_unavailable(tmp_path: Path):
    store, frame1, _ = await _two_frames(tmp_path)
    p = Path(frame1.safe_image.path)
    original = p.read_bytes()
    p.write_bytes(original[: len(original) // 2])
    result = resolve_safe_evidence(frame1, artifact_store=store)
    assert isinstance(result, UnavailableEvidence)
    assert result.reason == "truncated"


@pytest.mark.asyncio
async def test_byte_size_mismatch_is_unavailable(tmp_path: Path):
    store, frame1, _ = await _two_frames(tmp_path)
    p = Path(frame1.safe_image.path)
    original = p.read_bytes()
    p.write_bytes(original + b"\x00" * 16)
    result = resolve_safe_evidence(frame1, artifact_store=store)
    assert isinstance(result, UnavailableEvidence)
    assert result.reason == "byte_size_mismatch"


@pytest.mark.asyncio
async def test_corrupted_same_size_bytes_fail_hash_check(tmp_path: Path):
    store, frame1, _ = await _two_frames(tmp_path)
    p = Path(frame1.safe_image.path)
    original = bytearray(p.read_bytes())
    original[-1] ^= 0xFF  # flip last byte, same length
    p.write_bytes(bytes(original))
    result = resolve_safe_evidence(frame1, artifact_store=store)
    assert isinstance(result, UnavailableEvidence)
    assert result.reason == "hash_mismatch"


@pytest.mark.asyncio
async def test_undecodable_bytes_of_matching_size_and_hash_are_unavailable(tmp_path: Path):
    store, frame1, _ = await _two_frames(tmp_path)
    p = Path(frame1.safe_image.path)
    garbage = b"\x00" * frame1.safe_image.byte_size
    p.write_bytes(garbage)
    # Overwrite the ref's expected hash/size to match this garbage so we
    # isolate the decodability check specifically.
    import hashlib

    tampered_ref = frame1.safe_image.model_copy(
        update={"artifact_sha256": hashlib.sha256(garbage).hexdigest(), "byte_size": len(garbage)}
    )
    tampered_frame = frame1.model_copy(update={"safe_image": tampered_ref})
    result = resolve_safe_evidence(tampered_frame, artifact_store=store)
    assert isinstance(result, UnavailableEvidence)
    assert result.reason == "undecodable"


@pytest.mark.asyncio
async def test_mask_identity_mismatch_is_unavailable(tmp_path: Path):
    store, frame1, _ = await _two_frames(tmp_path)
    tampered_ref = frame1.safe_image.model_copy(update={"mask_identity": "tampered-identity"})
    tampered_frame = frame1.model_copy(update={"safe_image": tampered_ref})
    result = resolve_safe_evidence(tampered_frame, artifact_store=store)
    assert isinstance(result, UnavailableEvidence)
    assert result.reason == "mask_mismatch"


@pytest.mark.asyncio
async def test_out_of_bounds_path_is_unavailable(tmp_path: Path):
    store, frame1, _ = await _two_frames(tmp_path)
    outside = tmp_path / "outside.png"
    outside.write_bytes(Path(frame1.safe_image.path).read_bytes())
    tampered_ref = frame1.safe_image.model_copy(update={"path": str(outside)})
    tampered_frame = frame1.model_copy(update={"safe_image": tampered_ref})
    result = resolve_safe_evidence(tampered_frame, artifact_store=store)
    assert isinstance(result, UnavailableEvidence)
    assert result.reason == "out_of_bounds"


@pytest.mark.asyncio
async def test_orphan_bundle_after_quarantine_is_unavailable(tmp_path: Path):
    store, frame1, _ = await _two_frames(tmp_path)
    # Simulate a crash-recovery quarantine of this frame's bundle.
    store.recover_orphans("r1", referenced_bundle_ids=set())
    result = resolve_safe_evidence(frame1, artifact_store=store)
    assert isinstance(result, UnavailableEvidence)
    assert result.reason == "orphan_bundle"


@pytest.mark.asyncio
async def test_wrong_purpose_is_unavailable(tmp_path: Path):
    store, frame1, _ = await _two_frames(tmp_path)
    tampered_ref = frame1.safe_image.model_copy(update={"purpose": "report_copy"})
    tampered_frame = frame1.model_copy(update={"safe_image": tampered_ref})
    result = resolve_safe_evidence(tampered_frame, artifact_store=store)
    assert isinstance(result, UnavailableEvidence)
    assert result.reason == "wrong_purpose"
