"""Zero-copy safe evidence resolution (report-contract.md "Safe evidence contract").

Given a `ScreenFrame`, resolves its `safe_image` `PhysicalImageRef` to a
validated, already-published file path — never creates a copy, hardlink, or
symlink. Any failure returns a localized-unavailable reason instead of a
path; callers must never fall back to a private path or another frame's
evidence.

Multiple logical frames sharing one physical file (duplicates) resolve to
the exact same path — this function is pure and does no caching of its own
beyond what the filesystem already gives for free.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnc_agent.domain.observation import ScreenFrame
    from vnc_agent.storage.artifact_store import ArtifactStore


@dataclass(frozen=True)
class ResolvedEvidence:
    path: str
    artifact_sha256: str
    physical_image_id: str
    artifact_bundle_id: str


@dataclass(frozen=True)
class UnavailableEvidence:
    reason: str  # localization.py "evidence_error.<reason>" key suffix


EvidenceResult = "ResolvedEvidence | UnavailableEvidence"


def resolve_safe_evidence(
    frame: ScreenFrame, *, artifact_store: ArtifactStore
) -> ResolvedEvidence | UnavailableEvidence:
    ref = frame.safe_image
    if ref is None:
        return UnavailableEvidence("not_found")
    if ref.purpose != "safe_evidence":
        return UnavailableEvidence("wrong_purpose")

    run_root = artifact_store.bundles_dir(frame.run_id).resolve()
    try:
        path = Path(ref.path).resolve()
    except OSError:
        return UnavailableEvidence("missing")
    try:
        path.relative_to(run_root)
    except ValueError:
        # Not under the referenced-bundle root at all — includes staging/
        # quarantined/private paths, which must never be linked.
        return UnavailableEvidence("out_of_bounds")

    bundle_dir = path.parent
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        return UnavailableEvidence("orphan_bundle")
    try:
        manifest = artifact_store.read_manifest(bundle_dir)
    except Exception:
        return UnavailableEvidence("corrupted")

    if manifest.get("artifact_bundle_id") != ref.artifact_bundle_id:
        return UnavailableEvidence("orphan_bundle")

    file_meta = manifest.get("files", {}).get("safe_evidence")
    if not file_meta:
        return UnavailableEvidence("missing")
    if file_meta.get("mask_identity") != ref.mask_identity:
        return UnavailableEvidence("mask_mismatch")

    if not path.is_file():
        return UnavailableEvidence("missing")

    data = path.read_bytes()
    if len(data) < ref.byte_size:
        return UnavailableEvidence("truncated")
    if len(data) != ref.byte_size:
        return UnavailableEvidence("byte_size_mismatch")

    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != ref.artifact_sha256:
        return UnavailableEvidence("hash_mismatch")

    import cv2
    import numpy as np

    arr = np.frombuffer(data, dtype=np.uint8)
    decoded = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if decoded is None:
        return UnavailableEvidence("undecodable")

    return ResolvedEvidence(
        path=str(path),
        artifact_sha256=actual_sha,
        physical_image_id=ref.physical_image_id,
        artifact_bundle_id=ref.artifact_bundle_id,
    )


class SafeEvidenceResolver:
    """Stateful convenience wrapper: memoizes by physical_image_id within one
    report build (identical logical frames referencing the same physical
    file resolve/validate only once) — never caches across builds, never
    holds file bytes."""

    def __init__(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store
        self._cache: dict[str, ResolvedEvidence | UnavailableEvidence] = {}

    def resolve(self, frame: ScreenFrame) -> ResolvedEvidence | UnavailableEvidence:
        key = frame.safe_image.physical_image_id if frame.safe_image else f"none:{frame.id}"
        if key not in self._cache:
            self._cache[key] = resolve_safe_evidence(frame, artifact_store=self.artifact_store)
        return self._cache[key]
