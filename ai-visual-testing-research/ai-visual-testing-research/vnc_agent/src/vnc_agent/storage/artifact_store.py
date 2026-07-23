"""Artifact store with sensitive-region masking for local persistence (FR-049).

Feature 004 adds transactional `FrameArtifactBundle` staging/publish
(data-model.md §3 "FrameArtifactBundle", frame-capture-contract.md "Artifact
safety"): every unique frame's safe/private files + manifest are written into
a staging directory on the same filesystem as the final bundle root, synced,
then published via exactly one directory rename. No final file is ever
visible before that rename, and no logical frame/report ever references a
bundle that has not completed this transaction.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2

from vnc_agent.domain.observation import PhysicalImageRef

_MANIFEST_FILENAME = "manifest.json"


class ArtifactPersistenceError(Exception):
    """Raised when staging, syncing, or publishing a FrameArtifactBundle fails."""


@dataclass(frozen=True)
class PublishedBundle:
    bundle_id: str
    refs: dict[str, PhysicalImageRef]
    manifest_path: str


def _fsync_file(path: Path) -> None:
    # Windows requires a writable handle for fsync; O_RDONLY raises EBADF there.
    flags = os.O_RDWR if os.name == "nt" else os.O_RDONLY
    fd = os.open(str(path), flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_dir(path: Path) -> None:
    # Windows has no directory fsync; POSIX does. Best-effort only.
    if os.name == "nt":
        return
    fd = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class ArtifactStore:
    def __init__(
        self,
        root: str | Path,
        *,
        mask_regions: list[list[int]] | None = None,
    ) -> None:
        self.root = Path(root)
        self.mask_regions = mask_regions or []
        self.root.mkdir(parents=True, exist_ok=True)

    def run_dir(self, run_id: str) -> Path:
        d = self.root / "runs" / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _bundles_dir(self, run_id: str) -> Path:
        d = self.run_dir(run_id) / "bundles"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _staging_root(self, run_id: str) -> Path:
        d = self.run_dir(run_id) / ".staging"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _quarantine_dir(self, run_id: str) -> Path:
        d = self.run_dir(run_id) / ".quarantine"
        d.mkdir(parents=True, exist_ok=True)
        return d

    # --- FrameArtifactBundle: staging → single-rename publish -----------------

    def stage_and_publish_bundle(
        self,
        *,
        run_id: str,
        owner_frame_id: str,
        mask_identity: str,
        content_hash: str | None,
        files: dict[str, bytes],
    ) -> PublishedBundle:
        """Write ``files`` (purpose -> encoded bytes) + manifest into a staging
        bundle, sync, then publish via exactly one same-filesystem directory
        rename. Any failure removes staging and raises
        :class:`ArtifactPersistenceError`; no partial final bundle is ever
        visible (frame-capture-contract.md "Artifact safety")."""
        allowed_purposes = {"safe_evidence", "private_model"}
        unknown = set(files) - allowed_purposes
        if unknown:
            raise ArtifactPersistenceError(f"unsupported bundle purposes: {unknown}")
        if "safe_evidence" not in files:
            raise ArtifactPersistenceError("bundle must always include safe_evidence")

        bundle_id = str(uuid.uuid4())
        staging = self._staging_root(run_id) / bundle_id
        try:
            staging.mkdir(parents=True, exist_ok=False)
            manifest_files: dict[str, dict[str, Any]] = {}
            for purpose, data in files.items():
                filename = f"{purpose}.png"
                path = staging / filename
                path.write_bytes(data)
                _fsync_file(path)
                manifest_files[purpose] = {
                    "relative_path": filename,
                    "byte_size": len(data),
                    "artifact_sha256": hashlib.sha256(data).hexdigest(),
                    "mask_identity": mask_identity,
                }
            manifest = {
                "artifact_bundle_id": bundle_id,
                "run_id": run_id,
                "owner_frame_id": owner_frame_id,
                "purposes": sorted(files.keys()),
                "content_hash": content_hash,
                "files": manifest_files,
            }
            manifest_path = staging / _MANIFEST_FILENAME
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            _fsync_file(manifest_path)
            _fsync_dir(staging)

            final_dir = self._bundles_dir(run_id) / bundle_id
            os.rename(str(staging), str(final_dir))
            _fsync_dir(self._bundles_dir(run_id))
        except Exception as exc:
            shutil.rmtree(staging, ignore_errors=True)
            raise ArtifactPersistenceError(f"bundle publish failed: {exc}") from exc

        created_at = datetime.now(UTC)
        refs: dict[str, PhysicalImageRef] = {}
        for purpose, meta in manifest_files.items():
            refs[purpose] = PhysicalImageRef(
                physical_image_id=str(uuid.uuid4()),
                owner_frame_id=owner_frame_id,
                artifact_bundle_id=bundle_id,
                purpose=purpose,  # type: ignore[arg-type]
                path=str(final_dir / meta["relative_path"]),
                byte_size=meta["byte_size"],
                artifact_sha256=meta["artifact_sha256"],
                content_hash=content_hash,
                mask_identity=mask_identity,
                created_at=created_at,
            )
        return PublishedBundle(
            bundle_id=bundle_id, refs=refs, manifest_path=str(final_dir / _MANIFEST_FILENAME)
        )

    def avoided_write_descriptor(self, ref: PhysicalImageRef) -> dict[str, Any]:
        """Byte basis for a `physical_write_avoided` CounterEvent — always the
        actual reused file's recorded size, never estimated."""
        return {
            "purpose": ref.purpose,
            "source_physical_id": ref.physical_image_id,
            "byte_basis": ref.byte_size,
        }

    def validate_reusable_refs(self, refs: list[PhysicalImageRef]) -> bool:
        """Cheap reuse-eligibility check for a duplicate frame: the file must
        still exist at its published bundle path with the manifest's byte
        size. Does not re-hash on every duplicate — full integrity
        (artifact_sha256 + decodability) is the report resolver's job."""
        for ref in refs:
            path = Path(ref.path)
            if not path.is_file():
                return False
            if path.stat().st_size != ref.byte_size:
                return False
        return True

    def read_manifest(self, bundle_dir: str | Path) -> dict[str, Any]:
        manifest_path = Path(bundle_dir) / _MANIFEST_FILENAME
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    def recover_orphans(self, run_id: str, referenced_bundle_ids: set[str]) -> list[str]:
        """Startup/reconnect reconciliation (frame-capture-contract.md
        "startup/reconnect recovery"): remove leftover staging directories
        and quarantine any published bundle with no `TestRun.frames`
        reference. Returns the quarantined bundle ids."""
        from vnc_agent.runtime.telemetry import log_event

        staging_root = self._staging_root(run_id)
        removed_staging = [child.name for child in staging_root.iterdir()]
        for child in list(staging_root.iterdir()):
            shutil.rmtree(child, ignore_errors=True)

        quarantined: list[str] = []
        bundles_dir = self._bundles_dir(run_id)
        for child in list(bundles_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name not in referenced_bundle_ids:
                dest = self._quarantine_dir(run_id) / child.name
                shutil.move(str(child), str(dest))
                quarantined.append(child.name)

        if removed_staging or quarantined:
            log_event(
                "artifact_bundle_recovery",
                run_id=run_id,
                removed_staging_bundle_ids=removed_staging,
                quarantined_bundle_ids=quarantined,
                status="completed",
            )
        return quarantined

    def save_bytes(self, run_id: str, relative: str, data: bytes) -> str:
        path = self.run_dir(run_id) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def save_json(self, run_id: str, relative: str, obj: Any) -> str:
        path = self.run_dir(run_id) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(path)

    def mask_image_file(self, image_path: str | Path, out_path: str | Path | None = None) -> str:
        """Apply mask_regions blackout for local/report use only (not model API)."""
        src = Path(image_path)
        img = cv2.imread(str(src), cv2.IMREAD_COLOR)
        if img is None:
            return str(src)
        for r in self.mask_regions:
            if len(r) != 4:
                continue
            x1, y1, x2, y2 = r
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), thickness=-1)
        dest = Path(out_path) if out_path else src.with_name(src.stem + "_masked" + src.suffix)
        dest.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(dest), img)
        return str(dest)

    def mask_png_bytes(self, raw_png: bytes) -> bytes:
        """Mask PNG bytes in-memory (used by screenshot capture for frames/)."""
        from vnc_agent.perception.screenshot import apply_mask_to_png_bytes

        return apply_mask_to_png_bytes(raw_png, self.mask_regions)

    def copy_masked_for_report(self, image_path: str | Path, run_id: str, name: str) -> str:
        """
        Copy frame into report_frames/. If the source is already under frames/
        (already masked at capture time per FR-049), just copy; otherwise mask.
        """
        dest = self.run_dir(run_id) / "report_frames" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        src = Path(image_path)
        # frames/ is the local-persistence path and is already masked when
        # mask_regions is configured; avoid double-masking.
        if "frames" in src.parts and "frames_model" not in src.parts and self.mask_regions:
            import shutil

            shutil.copy2(src, dest)
            return str(dest)
        return self.mask_image_file(image_path, dest)
