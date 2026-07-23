"""Phase 3 (T014) RED: FrameArtifactBundle staging → single-rename publish.

Locks: safe/private files + manifest land in one staging bundle and are
published via exactly one same-filesystem directory rename; no-private
policy publishes safe-only with no private file/ref; per-file byte_size and
artifact_sha256 are computed from the actual encoded bytes; safe/private
share one ``artifact_bundle_id``; reuse-avoided accounting is derived from
the published ref, never a fabricated count.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from vnc_agent.storage.artifact_store import ArtifactPersistenceError, ArtifactStore


def _safe_bytes() -> bytes:
    return b"\x89PNG-fake-safe-bytes-0001"


def _private_bytes() -> bytes:
    return b"\x89PNG-fake-private-bytes-0002"


def test_publish_bundle_writes_manifest_and_computes_real_hashes(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    bundle = store.stage_and_publish_bundle(
        run_id="r1",
        owner_frame_id="f1",
        mask_identity="no-mask-v1",
        content_hash="c" * 64,
        files={"safe_evidence": _safe_bytes()},
    )
    ref = bundle.refs["safe_evidence"]
    assert ref.purpose == "safe_evidence"
    assert ref.artifact_bundle_id == bundle.bundle_id
    assert ref.byte_size == len(_safe_bytes())
    assert ref.artifact_sha256 == hashlib.sha256(_safe_bytes()).hexdigest()
    assert Path(ref.path).exists()
    assert Path(ref.path).read_bytes() == _safe_bytes()

    manifest = json.loads(Path(bundle.manifest_path).read_text(encoding="utf-8"))
    assert manifest["artifact_bundle_id"] == bundle.bundle_id
    assert manifest["run_id"] == "r1"
    assert manifest["owner_frame_id"] == "f1"
    assert manifest["files"]["safe_evidence"]["byte_size"] == len(_safe_bytes())
    assert manifest["files"]["safe_evidence"]["artifact_sha256"] == hashlib.sha256(
        _safe_bytes()
    ).hexdigest()


def test_publish_bundle_masked_private_allowed_shares_one_bundle_and_one_rename(
    tmp_path: Path, monkeypatch
):
    rename_calls = {"n": 0}
    import os

    real_rename = os.rename

    def counting_rename(src, dst):
        rename_calls["n"] += 1
        return real_rename(src, dst)

    monkeypatch.setattr(os, "rename", counting_rename)

    store = ArtifactStore(tmp_path)
    bundle = store.stage_and_publish_bundle(
        run_id="r1",
        owner_frame_id="f1",
        mask_identity="mask-v1",
        content_hash="c" * 64,
        files={"safe_evidence": _safe_bytes(), "private_model": _private_bytes()},
    )
    assert rename_calls["n"] == 1
    assert set(bundle.refs.keys()) == {"safe_evidence", "private_model"}
    assert bundle.refs["safe_evidence"].artifact_bundle_id == bundle.bundle_id
    assert bundle.refs["private_model"].artifact_bundle_id == bundle.bundle_id
    assert bundle.refs["safe_evidence"].path != bundle.refs["private_model"].path


def test_publish_bundle_no_private_persistence_writes_safe_only(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    bundle = store.stage_and_publish_bundle(
        run_id="r1",
        owner_frame_id="f1",
        mask_identity="mask-v1",
        content_hash="c" * 64,
        files={"safe_evidence": _safe_bytes()},  # caller never includes private bytes
    )
    assert set(bundle.refs.keys()) == {"safe_evidence"}
    bundle_dir = Path(bundle.manifest_path).parent
    written_files = {p.name for p in bundle_dir.iterdir() if p.name != "manifest.json"}
    assert written_files == {"safe_evidence.png"}


def test_publish_bundle_failure_cleans_up_staging_and_leaves_no_final_dir(
    tmp_path: Path, monkeypatch
):
    import os

    def failing_rename(src, dst):
        raise OSError("simulated rename failure")

    monkeypatch.setattr(os, "rename", failing_rename)

    store = ArtifactStore(tmp_path)
    with pytest.raises(ArtifactPersistenceError):
        store.stage_and_publish_bundle(
            run_id="r1",
            owner_frame_id="f1",
            mask_identity="no-mask-v1",
            content_hash="c" * 64,
            files={"safe_evidence": _safe_bytes()},
        )
    bundles_dir = tmp_path / "runs" / "r1" / "bundles"
    staging_dir = tmp_path / "runs" / "r1" / ".staging"
    assert not any(bundles_dir.iterdir()) if bundles_dir.exists() else True
    assert not any(staging_dir.rglob("*")) if staging_dir.exists() else True


def test_reuse_descriptor_reports_actual_byte_basis_not_fabricated(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    bundle = store.stage_and_publish_bundle(
        run_id="r1",
        owner_frame_id="f1",
        mask_identity="no-mask-v1",
        content_hash="c" * 64,
        files={"safe_evidence": _safe_bytes()},
    )
    ref = bundle.refs["safe_evidence"]
    descriptor = store.avoided_write_descriptor(ref)
    assert descriptor["byte_basis"] == ref.byte_size
    assert descriptor["source_physical_id"] == ref.physical_image_id
    assert descriptor["purpose"] == "safe_evidence"


def test_validate_reusable_refs_true_for_intact_published_bundle(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    bundle = store.stage_and_publish_bundle(
        run_id="r1",
        owner_frame_id="f1",
        mask_identity="no-mask-v1",
        content_hash="c" * 64,
        files={"safe_evidence": _safe_bytes()},
    )
    assert store.validate_reusable_refs(list(bundle.refs.values()))


def test_validate_reusable_refs_false_when_file_missing(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    bundle = store.stage_and_publish_bundle(
        run_id="r1",
        owner_frame_id="f1",
        mask_identity="no-mask-v1",
        content_hash="c" * 64,
        files={"safe_evidence": _safe_bytes()},
    )
    ref = bundle.refs["safe_evidence"]
    Path(ref.path).unlink()
    assert not store.validate_reusable_refs([ref])


def test_validate_reusable_refs_false_when_byte_size_mismatch(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    bundle = store.stage_and_publish_bundle(
        run_id="r1",
        owner_frame_id="f1",
        mask_identity="no-mask-v1",
        content_hash="c" * 64,
        files={"safe_evidence": _safe_bytes()},
    )
    ref = bundle.refs["safe_evidence"]
    tampered = ref.model_copy(update={"byte_size": ref.byte_size + 999})
    assert not store.validate_reusable_refs([tampered])
