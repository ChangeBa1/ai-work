"""Screenshot capture — raw pixels written immediately to disk (SC-009, FR-049)."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from vnc_agent.domain.observation import ScreenFrame
from vnc_agent.perception.pixel_identity import canonical_pixel_format, pixel_content_hash

if TYPE_CHECKING:
    from vnc_agent.domain.observation import Region
    from vnc_agent.domain.run import TestRun
    from vnc_agent.drivers.base import VNCDriver
    from vnc_agent.storage.artifact_store import ArtifactStore


class CaptureDecodeError(Exception):
    """Raised when raw capture bytes cannot be decoded into a trusted pixel array."""


@dataclass(frozen=True)
class DecodedCapture:
    """One VNC capture, decoded exactly once (data-model.md §2).

    ``pixels`` is a read-only, C-contiguous ndarray shared by strict pixel
    comparison and every downstream analysis component — never re-decoded
    from a written file.
    """

    pixels: np.ndarray
    pixel_format: str
    content_hash: str | None
    width: int
    height: int


def decode_capture(raw_png: bytes) -> DecodedCapture:
    """Decode ``raw_png`` exactly once via ``cv2.imdecode(IMREAD_UNCHANGED)``.

    Raises :class:`CaptureDecodeError` when the bytes cannot be trusted as a
    pixel array; callers MUST treat this as a capture failure (no
    ScreenFrame, no analysis, no verification — frame-capture-contract.md
    "Failure matrix").
    """
    import cv2

    if not raw_png:
        raise CaptureDecodeError("empty capture bytes")
    arr = np.frombuffer(raw_png, dtype=np.uint8)
    decoded = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
    if decoded is None or decoded.size == 0:
        raise CaptureDecodeError("cv2.imdecode returned no image")
    if decoded.ndim not in (2, 3):
        raise CaptureDecodeError(f"unexpected decoded ndim={decoded.ndim}")

    normalized = decoded if decoded.flags["C_CONTIGUOUS"] else np.ascontiguousarray(decoded)
    normalized = normalized.copy()
    normalized.setflags(write=False)

    pixel_format = canonical_pixel_format(normalized)
    try:
        content_hash: str | None = pixel_content_hash(normalized, pixel_format=pixel_format)
    except Exception:
        content_hash = None

    height, width = normalized.shape[0], normalized.shape[1]
    return DecodedCapture(
        pixels=normalized,
        pixel_format=pixel_format,
        content_hash=content_hash,
        width=width,
        height=height,
    )


def pixels_strictly_equal(a: DecodedCapture, b: DecodedCapture) -> bool:
    """Shape/dtype check + ``np.array_equal`` — the final dedup verdict.

    ``content_hash`` equality (even a forced/injected collision) MUST NOT be
    trusted on its own; this is the authority (frame-capture-contract.md
    "Exact duplicate decision" item 9).
    """
    if a.pixels.shape != b.pixels.shape or a.pixels.dtype != b.pixels.dtype:
        return False
    return bool(np.array_equal(a.pixels, b.pixels))


def apply_mask_to_png_bytes(
    raw_png: bytes, mask_regions: Sequence[Sequence[int]] | None
) -> bytes:
    """Return PNG bytes with mask_regions blacked out. No-op if no regions."""
    if not mask_regions:
        return raw_png
    import cv2
    import numpy as np

    arr = np.frombuffer(raw_png, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return raw_png
    for r in mask_regions:
        if len(r) != 4:
            continue
        x1, y1, x2, y2 = int(r[0]), int(r[1]), int(r[2]), int(r[3])
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), thickness=-1)
    ok, encoded = cv2.imencode(".png", img)
    if not ok:
        return raw_png
    return encoded.tobytes()


def _local_mask_regions(
    mask_regions_global: Sequence[Sequence[int]],
    x: int,
    y: int,
    w: int,
    h: int,
) -> list[list[int]]:
    """Intersect+translate global mask rectangles into crop-local coordinates."""
    local: list[list[int]] = []
    for r in mask_regions_global or []:
        if len(r) != 4:
            continue
        x1, y1, x2, y2 = int(r[0]), int(r[1]), int(r[2]), int(r[3])
        ix1, iy1 = max(x1, x), max(y1, y)
        ix2, iy2 = min(x2, x + w), min(y2, y + h)
        if ix1 < ix2 and iy1 < iy2:
            local.append([ix1 - x, iy1 - y, ix2 - x, iy2 - y])
    return local


def _apply_mask_to_pixels(
    pixels: np.ndarray, mask_regions_local: Sequence[Sequence[int]]
) -> np.ndarray:
    if not mask_regions_local:
        return pixels
    masked = pixels.copy()
    for r in mask_regions_local:
        x1, y1, x2, y2 = r
        masked[y1:y2, x1:x2] = 0
    return masked


def _encode_png(pixels: np.ndarray) -> bytes:
    import cv2

    ok, buf = cv2.imencode(".png", pixels)
    if not ok:
        raise CaptureDecodeError("failed to encode pixels to PNG")
    return buf.tobytes()


def compute_mask_identity(mask_regions: Sequence[Sequence[int]] | None) -> str:
    """Stable identity for a *global* security-mask configuration
    (data-model.md §1 `mask_identity`) — config version + normalized rects."""
    import hashlib
    import json as _json

    regions = sorted(tuple(int(v) for v in r) for r in (mask_regions or []) if len(r) == 4)
    preimage = "mask-identity-v1|" + _json.dumps(regions)
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CaptureOutcome:
    frame: ScreenFrame
    decoded: DecodedCapture
    # The immediately preceding logical frame's decoded pixels (None for the
    # first capture in a run/session) — lets callers diff without re-reading
    # any file, and without duplicating FrameCaptureService's own bookkeeping.
    previous_decoded: DecodedCapture | None = None


class FrameCaptureFailedError(Exception):
    """Capture could not produce a trusted ScreenFrame; existing deterministic
    error/recovery flow owns what happens next (frame-capture-contract.md)."""

    def __init__(self, message: str, *, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class FrameCaptureService:
    """The one shared run/VNC-session-scoped capture + logical-frame recorder.

    `ObservationPipeline`, `StabilityEngine`, retries, recovery and
    post-action verification all call :meth:`capture` on the *same*
    instance so the global adjacent-frame sequence, dedup decision and
    `TestRun.frames` append are made in exactly one place
    (frame-capture-contract.md).
    """

    def __init__(
        self,
        driver: VNCDriver,
        *,
        run_id: str,
        vnc_session_id: str,
        test_run: TestRun | None,
        artifact_store: ArtifactStore,
        mask_regions: Sequence[Sequence[int]] = (),
        private_persistence_allowed: bool = True,
        clock: Any = None,
    ) -> None:
        self.driver = driver
        self.run_id = run_id
        self.vnc_session_id = vnc_session_id
        self.test_run = test_run
        self.artifact_store = artifact_store
        self.mask_regions = list(mask_regions)
        self.private_persistence_allowed = private_persistence_allowed
        self.clock = clock
        self._mask_identity = compute_mask_identity(self.mask_regions)
        self._sequence = 0
        self._attempt_sequence: dict[str, int] = {}
        self._last: tuple[ScreenFrame, DecodedCapture] | None = None

    def clear(self) -> None:
        """Run/session rotation clears `previous` (frame-capture-contract.md
        "Logical/physical invariants")."""
        self._last = None
        self._sequence = 0
        self._attempt_sequence.clear()

    def _measure(self, stage: str, **kwargs: Any):
        from contextlib import nullcontext

        from vnc_agent.runtime.telemetry import measure_stage

        if self.test_run is None:
            return nullcontext()
        return measure_stage(
            self.test_run, stage=stage, run_id=self.run_id, clock=self.clock, **kwargs
        )

    async def capture(
        self,
        *,
        step_id: str | None,
        capture_source: str,
        roi: Region | None = None,
    ) -> CaptureOutcome:
        from vnc_agent.domain.observation import CaptureScope, scope_identity
        from vnc_agent.storage.artifact_store import ArtifactPersistenceError

        self._attempt_sequence[capture_source] = self._attempt_sequence.get(capture_source, 0) + 1
        attempt_sequence = self._attempt_sequence[capture_source]

        with self._measure("capture", step_id=step_id):
            if roi is not None:
                capture_kind: str = "roi"
                x, y = roi.x1, roi.y1
                w, h = roi.x2 - roi.x1, roi.y2 - roi.y1
                raw = await self.driver.capture_region(x, y, w, h)
            else:
                capture_kind = "full_screen"
                x, y = 0, 0
                raw = await self.driver.capture_screen()

        try:
            with self._measure("pixel_hash", step_id=step_id):
                decoded = decode_capture(raw)
        except CaptureDecodeError as exc:
            self._record_capture_failure(
                step_id=step_id,
                capture_source=capture_source,
                attempt_sequence=attempt_sequence,
                error_type="decode_error",
            )
            raise FrameCaptureFailedError(f"capture decode failed: {exc}", cause=exc) from exc
        finally:
            del raw

        resolution = tuple(self.driver.resolution)
        scope = CaptureScope(
            capture_kind=capture_kind,  # type: ignore[arg-type]
            x=x,
            y=y,
            width=decoded.width,
            height=decoded.height,
            resolution=resolution,
            pixel_format=decoded.pixel_format,
            mask_identity=self._mask_identity,
            private_persistence_allowed=self.private_persistence_allowed,
        )

        dedup_ok = self._is_exact_duplicate(scope, decoded, scope_identity)
        if dedup_ok:
            assert self._last is not None
            prev_frame, _ = self._last
            refs_to_check = [prev_frame.safe_image]
            if prev_frame.model_image is not None:
                refs_to_check.append(prev_frame.model_image)
            if not self.artifact_store.validate_reusable_refs(refs_to_check):
                dedup_ok = False

        self._sequence += 1
        sequence = self._sequence
        frame_id = str(uuid.uuid4())
        timestamp = datetime.now(UTC)

        if dedup_ok:
            prev_frame, _ = self._last  # type: ignore[misc]
            frame = ScreenFrame(
                id=frame_id,
                run_id=self.run_id,
                vnc_session_id=self.vnc_session_id,
                step_id=step_id,
                capture_sequence=sequence,
                capture_source=capture_source,  # type: ignore[arg-type]
                timestamp=timestamp,
                scope=scope,
                content_hash=decoded.content_hash,
                deduplicated=True,
                duplicate_of_frame_id=prev_frame.id,
                comparison_available=True,
                changed_since_last=False,
                safe_image=prev_frame.safe_image,
                model_image=prev_frame.model_image,
                width=decoded.width,
                height=decoded.height,
                crop_offset=(x, y),
            )
        else:
            comparison_available = self._last is not None
            changed_since_last = True if comparison_available else None
            local_masks = _local_mask_regions(
                self.mask_regions, x, y, decoded.width, decoded.height
            )
            bundle_files: dict[str, bytes] = {}
            try:
                if local_masks:
                    safe_pixels = _apply_mask_to_pixels(decoded.pixels, local_masks)
                    bundle_files["safe_evidence"] = _encode_png(safe_pixels)
                    if self.private_persistence_allowed:
                        bundle_files["private_model"] = _encode_png(decoded.pixels)
                else:
                    bundle_files["safe_evidence"] = _encode_png(decoded.pixels)
            except CaptureDecodeError as exc:
                self._record_capture_failure(
                    step_id=step_id,
                    capture_source=capture_source,
                    attempt_sequence=attempt_sequence,
                    error_type="mask_encode_error",
                )
                raise FrameCaptureFailedError(f"mask encode failed: {exc}", cause=exc) from exc

            try:
                with self._measure("persistence", step_id=step_id, frame_id=frame_id):
                    bundle = self.artifact_store.stage_and_publish_bundle(
                        run_id=self.run_id,
                        owner_frame_id=frame_id,
                        mask_identity=self._mask_identity,
                        content_hash=decoded.content_hash,
                        files=bundle_files,
                    )
            except ArtifactPersistenceError as exc:
                self._record_capture_failure(
                    step_id=step_id,
                    capture_source=capture_source,
                    attempt_sequence=attempt_sequence,
                    error_type="persistence_error",
                )
                raise FrameCaptureFailedError(
                    f"artifact persistence failed: {exc}", cause=exc
                ) from exc

            safe_ref = bundle.refs["safe_evidence"]
            model_ref = bundle.refs.get("private_model") if local_masks else None

            try:
                frame = ScreenFrame(
                    id=frame_id,
                    run_id=self.run_id,
                    vnc_session_id=self.vnc_session_id,
                    step_id=step_id,
                    capture_sequence=sequence,
                    capture_source=capture_source,  # type: ignore[arg-type]
                    timestamp=timestamp,
                    scope=scope,
                    content_hash=decoded.content_hash,
                    deduplicated=False,
                    duplicate_of_frame_id=None,
                    comparison_available=comparison_available,
                    changed_since_last=changed_since_last,
                    safe_image=safe_ref,
                    model_image=model_ref,
                    width=decoded.width,
                    height=decoded.height,
                    crop_offset=(x, y),
                )
            except Exception as exc:
                # Bundle already published, but the immutable logical record
                # could not be committed: the bundle is now an orphan — it
                # stays on disk unreferenced until the next
                # startup/reconnect recover_orphans() quarantines it
                # (frame-capture-contract.md "Failure matrix"). No success
                # ScreenFrame/physical event is ever produced here.
                self._record_capture_failure(
                    step_id=step_id,
                    capture_source=capture_source,
                    attempt_sequence=attempt_sequence,
                    error_type="logical_commit_error",
                )
                raise FrameCaptureFailedError(
                    f"logical frame commit failed after bundle publish: {exc}", cause=exc
                ) from exc

        previous_decoded = self._last[1] if self._last is not None else None
        self.test_run.frames.append(frame)
        self._emit_capture_counters(frame, dedup_ok)
        self._last = (frame, decoded)
        return CaptureOutcome(frame=frame, decoded=decoded, previous_decoded=previous_decoded)

    def _emit_capture_counters(self, frame: ScreenFrame, dedup_ok: bool) -> None:
        """Same TestRun update as the successful logical frame commit
        (telemetry-contract.md "Counter definitions";
        frame-capture-contract.md "Capture response")."""
        from vnc_agent.runtime.telemetry import CounterEvent, log_event

        now = datetime.now(UTC)
        dedup_payload = {
            "frame_id": frame.id,
            "eligible": self._last is not None,
            "deduplicated": dedup_ok,
            "reason": "exact_pixel_duplicate" if dedup_ok else "unique",
        }
        self.test_run.counter_events.append(
            CounterEvent(kind="frame_dedup_decision", occurred_at=now, payload=dedup_payload)
        )
        log_event("frame_dedup_decision", **dedup_payload)
        if dedup_ok:
            for ref in (frame.safe_image, frame.model_image):
                if ref is None:
                    continue
                payload = self.artifact_store.avoided_write_descriptor(ref) | {
                    "frame_id": frame.id
                }
                self.test_run.counter_events.append(
                    CounterEvent(kind="physical_write_avoided", occurred_at=now, payload=payload)
                )
                log_event("physical_image_event", action="avoided", **payload)
        else:
            for ref in (frame.safe_image, frame.model_image):
                if ref is None:
                    continue
                payload = {
                    "physical_image_id": ref.physical_image_id,
                    "purpose": ref.purpose,
                    "byte_size": ref.byte_size,
                    "frame_id": frame.id,
                }
                self.test_run.counter_events.append(
                    CounterEvent(kind="physical_image_written", occurred_at=now, payload=payload)
                )
                log_event("physical_image_event", action="written", **payload)

    def _is_exact_duplicate(self, scope, decoded: DecodedCapture, scope_identity_fn) -> bool:
        if self._last is None:
            return False
        try:
            prev_frame, prev_decoded = self._last
            if prev_frame.run_id != self.run_id or prev_frame.vnc_session_id != self.vnc_session_id:
                return False
            if scope_identity_fn(prev_frame.scope) != scope_identity_fn(scope):
                return False
            if decoded.content_hash is None or prev_decoded.content_hash is None:
                return False
            if decoded.content_hash != prev_decoded.content_hash:
                return False
            return pixels_strictly_equal(prev_decoded, decoded)
        except Exception:
            # frame-capture-contract.md "Failure matrix": hash/candidate
            # compare failures degrade to unique + full analysis — never
            # raise, never fabricate a dedup/cache-hit/avoided/skipped event.
            return False

    def _record_capture_failure(
        self, *, step_id: str | None, capture_source: str, attempt_sequence: int, error_type: str
    ) -> None:
        from vnc_agent.runtime.telemetry import CounterEvent, log_event

        measurement_id = str(uuid.uuid4())
        payload = {
            "run_id": self.run_id,
            "step_id": step_id,
            "capture_source": capture_source,
            "attempt_sequence": attempt_sequence,
            "error_type": error_type,
            "measurement_id": measurement_id,
        }
        self.test_run.counter_events.append(
            CounterEvent(
                kind="capture_attempt_failed", occurred_at=datetime.now(UTC), payload=payload
            )
        )
        log_event("capture_attempt_failed", **payload)


async def capture_full_screen(
    driver: VNCDriver,
    *,
    run_id: str,
    step_id: str | None,
    artifacts_dir: str | Path,
    mask_regions: Sequence[Sequence[int]] | None = None,
) -> ScreenFrame:
    """Offline-compatible wrapper (frame-capture-contract.md "Compatibility").

    Builds a throwaway, unshared `FrameCaptureService` per call — no module
    global cache, no dedup across calls. Production assembly MUST use a
    shared `FrameCaptureService` instead (see `runtime/agent_runtime.py`).
    """
    from vnc_agent.domain.run import TestRun
    from vnc_agent.storage.artifact_store import ArtifactStore

    service = FrameCaptureService(
        driver,
        run_id=run_id,
        vnc_session_id=f"wrapper-{uuid.uuid4()}",
        test_run=TestRun(run_id=run_id, test_case_id="offline-wrapper"),
        artifact_store=ArtifactStore(artifacts_dir),
        mask_regions=mask_regions or (),
        private_persistence_allowed=True,
    )
    outcome = await service.capture(step_id=step_id, capture_source="observation")
    return outcome.frame


async def capture_region(
    driver: VNCDriver,
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    run_id: str,
    step_id: str | None,
    artifacts_dir: str | Path,
    mask_regions: Sequence[Sequence[int]] | None = None,
) -> ScreenFrame:
    """Offline-compatible wrapper — see :func:`capture_full_screen`."""
    from vnc_agent.domain.observation import Region
    from vnc_agent.domain.run import TestRun
    from vnc_agent.storage.artifact_store import ArtifactStore

    service = FrameCaptureService(
        driver,
        run_id=run_id,
        vnc_session_id=f"wrapper-{uuid.uuid4()}",
        test_run=TestRun(run_id=run_id, test_case_id="offline-wrapper"),
        artifact_store=ArtifactStore(artifacts_dir),
        mask_regions=mask_regions or (),
        private_persistence_allowed=True,
    )
    outcome = await service.capture(
        step_id=step_id,
        capture_source="observation",
        roi=Region(x1=x, y1=y, x2=x + w, y2=y + h),
    )
    return outcome.frame


def load_image_array(image_path: str | Path):
    """Load image from disk as numpy BGR array for OpenCV ops."""
    import cv2

    arr = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if arr is None:
        raise FileNotFoundError(f"cannot read image: {image_path}")
    return arr
