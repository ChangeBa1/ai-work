"""Observation pipeline orchestration (FR-010/011, FR-049).

Feature 004: consumes ScreenFrames from the shared `FrameCaptureService`
recorder — no more per-call `capture_full_screen`, no more double
`assemble_structured_screen` for the masked case (the decoded pixel array is
already in memory once; masking only matters for the persisted safe file,
never for perception). OCR/template/diff reuse is delegated to
`structured_screen.py`; `vision_describe` (a cacheable content component,
distinct from the Planner/Verifier context-sensitive roles) is cached here
since it is issued through `planner.describe_screen(mode="describe")`.
Every hit/miss also lands as a `CounterEvent`/`StageMeasurement` on the
shared `TestRun` (telemetry-contract.md).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vnc_agent.domain.observation import (
    OCRItem,
    Region,
    ScreenFrame,
    StructuredScreen,
    VisionUnderstanding,
    scope_identity,
)
from vnc_agent.models.provider import PlannerProvider, VisionUnderstandingRequest
from vnc_agent.perception.cache import AnalysisCacheKey, AnalysisResultCache
from vnc_agent.perception.structured_screen import assemble_structured_screen_from_pixels
from vnc_agent.runtime.telemetry import CounterEvent, log_event, measure_stage

if TYPE_CHECKING:
    from vnc_agent.perception.screenshot import FrameCaptureService


def _config_fingerprint(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ZoomObservation:
    """Feature 014 (FR-003/FR-008): one bounded crop+upscale observation.

    ``image_path`` is the persisted upscaled image sent to the Grounder;
    ``resolution`` is that image's own (zoomed) dimensions; ``ocr_items``
    are already mapped back to original full-frame pixel coordinates."""

    image_path: str
    crop_offset: tuple[int, int]
    scale_factor: float
    resolution: tuple[int, int]
    frame_id: str
    ocr_items: list[OCRItem] = field(default_factory=list)


class ObservationPipeline:
    def __init__(
        self,
        capture_service: FrameCaptureService,
        *,
        templates_dir: str | Path | None = None,
        planner: PlannerProvider | None = None,
        ocr_enabled: bool = True,
        template_enabled: bool = True,
        vision_fallback: bool = True,
        diff_threshold: float = 0.02,
        cache: AnalysisResultCache | None = None,
        vision_provider_name: str = "planner-provider",
        vision_model: str = "default",
        clock: Any = None,
    ) -> None:
        self.capture_service = capture_service
        self.templates_dir = templates_dir
        self.planner = planner
        self.ocr_enabled = ocr_enabled
        self.template_enabled = template_enabled
        self.vision_fallback = vision_fallback
        self.diff_threshold = diff_threshold
        self.cache = cache
        self.vision_provider_name = vision_provider_name
        self.vision_model = vision_model
        self.clock = clock
        self.perception_config_fingerprint = _config_fingerprint(
            {
                "ocr_enabled": ocr_enabled,
                "template_enabled": template_enabled,
                "vision_fallback": vision_fallback,
                "diff_threshold": diff_threshold,
            }
        )

    async def observe(
        self,
        *,
        step_id: str | None = None,
        capture_source: str = "observation",
        roi: Region | None = None,
    ) -> StructuredScreen:
        outcome = await self.capture_service.capture(
            step_id=step_id, capture_source=capture_source, roi=roi
        )
        frame = outcome.frame
        decoded = outcome.decoded
        test_run = self.capture_service.test_run

        def _record_event(event: dict[str, Any]) -> None:
            if test_run is None or event["component"] == "diff":
                return  # diff has no canonical stage/analysis_invocation counter
            now = datetime.now(UTC)
            if event["outcome"] == "hit":
                payload = {
                    "component": event["component"],
                    "frame_id": frame.id,
                    "source_ref": event.get("source_ref"),
                }
                test_run.counter_events.append(
                    CounterEvent(kind="analysis_cache_hit", occurred_at=now, payload=payload)
                )
                log_event("analysis_cache_event", hit=True, **payload)
            else:
                payload = {
                    "component": event["component"],
                    "invocation_id": event.get("invocation_id", ""),
                    "status": "completed",
                }
                test_run.counter_events.append(
                    CounterEvent(kind="analysis_invocation", occurred_at=now, payload=payload)
                )
                log_event("analysis_cache_event", hit=False, **payload)

        screen = assemble_structured_screen_from_pixels(
            frame,
            decoded.pixels,
            previous_pixels=outcome.previous_decoded.pixels if outcome.previous_decoded else None,
            cache=self.cache,
            ocr_enabled=self.ocr_enabled,
            template_enabled=self.template_enabled,
            templates_dir=self.templates_dir,
            diff_threshold=self.diff_threshold,
            perception_config_fingerprint=self.perception_config_fingerprint,
            on_analysis_event=_record_event,
            test_run=test_run,
            clock=self.clock,
        )
        frame.analysis_source_refs = dict(screen.analysis_source_refs)

        if self.vision_fallback and self._needs_vision(screen) and self.planner:
            vision = await self._vision_describe_or_cache(frame, screen)
            if vision is not None:
                screen = screen.model_copy(update={"vision_understanding": vision})

        return screen

    async def observe_zoom(
        self,
        *,
        roi: Region,
        scale_factor: float,
        step_id: str | None = None,
        capture_source: str = "recovery",
    ) -> ZoomObservation | None:
        """Feature 014 (FR-003): one bounded ROI capture → upscale → re-OCR
        observation for the zoom_reground recovery escalation.

        Uses the shared FrameCaptureService (the ROI ScreenFrame lands in
        `TestRun.frames` per the normal capture contract); the upscaled image
        is persisted as a run artifact and is the image sent to the Grounder.
        Every failure returns None — the caller falls back to the normal
        full-screen grounding path (never a new fatal path).
        """
        import cv2
        import numpy as np

        from vnc_agent.perception.screenshot import (
            FrameCaptureFailedError,
            _apply_mask_to_pixels,
            _encode_png,
            _local_mask_regions,
        )

        if scale_factor <= 1.0:
            return None
        try:
            outcome = await self.capture_service.capture(
                step_id=step_id, capture_source=capture_source, roi=roi
            )
        except FrameCaptureFailedError:
            return None
        except Exception:
            return None
        decoded = outcome.decoded
        frame = outcome.frame
        roi_w, roi_h = roi.x2 - roi.x1, roi.y2 - roi.y1
        if (decoded.width, decoded.height) == (roi_w, roi_h):
            crop = decoded.pixels
        elif decoded.width >= roi.x2 and decoded.height >= roi.y2:
            # Driver returned a larger frame (e.g. full screen fallback):
            # crop the same ROI in memory — identical semantics.
            crop = decoded.pixels[roi.y1 : roi.y2, roi.x1 : roi.x2]
        else:
            return None
        if crop.size == 0:
            return None

        try:
            zoomed = cv2.resize(
                np.ascontiguousarray(crop),
                None,
                fx=scale_factor,
                fy=scale_factor,
                interpolation=cv2.INTER_CUBIC,
            )
        except Exception:
            return None
        zoom_h, zoom_w = zoomed.shape[0], zoomed.shape[1]

        ocr_items: list[OCRItem] = []
        if self.ocr_enabled:
            try:
                from vnc_agent.perception.ocr.engine import run_ocr_array

                for item in run_ocr_array(zoomed):
                    bx1, by1, bx2, by2 = item.bbox
                    ocr_items.append(
                        item.model_copy(
                            update={
                                "bbox": (
                                    int(bx1 / scale_factor) + roi.x1,
                                    int(by1 / scale_factor) + roi.y1,
                                    int(bx2 / scale_factor) + roi.x1,
                                    int(by2 / scale_factor) + roi.y1,
                                )
                            }
                        )
                    )
            except Exception:
                ocr_items = []

        # Masking: translate global mask rects into ROI-local space and scale
        # them up. The safe evidence copy is always masked; the model copy is
        # unmasked only when private persistence is allowed (FR-049 parity
        # with FrameCaptureService).
        local_masks = _local_mask_regions(
            self.capture_service.mask_regions, roi.x1, roi.y1, roi_w, roi_h
        )
        scaled_masks = [
            [int(v * scale_factor) for v in rect] for rect in local_masks
        ]
        store = self.capture_service.artifact_store
        run_id = self.capture_service.run_id
        try:
            if scaled_masks:
                safe_pixels = _apply_mask_to_pixels(zoomed, scaled_masks)
                safe_path = store.save_bytes(
                    run_id, f"zoom/{frame.id}-zoom-safe.png", _encode_png(safe_pixels)
                )
                if self.capture_service.private_persistence_allowed:
                    model_path = store.save_bytes(
                        run_id, f"zoom/{frame.id}-zoom-model.png", _encode_png(zoomed)
                    )
                else:
                    model_path = safe_path
            else:
                model_path = store.save_bytes(
                    run_id, f"zoom/{frame.id}-zoom.png", _encode_png(zoomed)
                )
        except Exception:
            return None

        log_event(
            "zoom_reground_observation",
            run_id=run_id,
            step_id=step_id,
            frame_id=frame.id,
            roi=roi.as_tuple(),
            scale_factor=scale_factor,
            zoom_image=model_path,
            ocr_item_count=len(ocr_items),
        )
        return ZoomObservation(
            image_path=model_path,
            crop_offset=(roi.x1, roi.y1),
            scale_factor=scale_factor,
            resolution=(zoom_w, zoom_h),
            frame_id=frame.id,
            ocr_items=ocr_items,
        )

    async def _vision_describe_or_cache(
        self, frame: ScreenFrame, screen: StructuredScreen
    ) -> VisionUnderstanding | None:
        """`vision_describe` is a cacheable content component (perception-
        cache-contract.md) — distinct from the Planner/Verifier
        context-sensitive roles, which are never cached."""
        test_run = self.capture_service.test_run
        component_identity = {
            "provider": self.vision_provider_name,
            "requested_model": self.vision_model,
            "mode": "describe",
            "prompt_revision": "vision-v1",
            "schema_revision": "vision-v1",
        }
        key: AnalysisCacheKey | None = None
        if self.cache is not None and frame.content_hash is not None:
            key = AnalysisCacheKey(
                component="vision_describe",
                algorithm_revision="vision-v1",
                content_hash=frame.content_hash,
                scope_identity=scope_identity(frame.scope),
                pixel_format=frame.scope.pixel_format,
                mask_identity=frame.scope.mask_identity,
                perception_config_fingerprint=self.perception_config_fingerprint,
                component_identity=component_identity,
            )
            try:
                entry = self.cache.lookup(
                    key,
                    frame_deduplicated=frame.deduplicated,
                    duplicate_of_frame_id=frame.duplicate_of_frame_id,
                    current_sequence=frame.capture_sequence,
                )
            except Exception:
                entry = None
            if entry is not None:
                if test_run is not None:
                    with measure_stage(
                        test_run, stage="vision", run_id=frame.run_id, step_id=frame.step_id,
                        frame_id=frame.id, clock=self.clock, actual_call=False, cache_hit=True,
                        source_ref=entry.source_frame_id,
                    ):
                        pass
                    vision_hit_payload = {
                        "component": "vision_describe",
                        "frame_id": frame.id,
                        "source_ref": entry.source_frame_id,
                    }
                    test_run.counter_events.append(
                        CounterEvent(
                            kind="analysis_cache_hit",
                            occurred_at=datetime.now(UTC),
                            payload=vision_hit_payload,
                        )
                    )
                    log_event("analysis_cache_event", hit=True, **vision_hit_payload)
                return entry.result

        try:
            if test_run is not None:
                with measure_stage(
                    test_run, stage="vision", run_id=frame.run_id, step_id=frame.step_id,
                    frame_id=frame.id, clock=self.clock,
                ):
                    resp = await self.planner.describe_screen(  # type: ignore[union-attr]
                        VisionUnderstandingRequest(
                            mode="describe",
                            # FR-049: model API MUST receive unmasked image
                            image_ref=frame.path_for_model(),
                            structured_screen_hint=screen.to_hint_dict(),
                            question=None,
                        )
                    )
                model_call_payload = {
                    "model_role": "vision",
                    "invocation_id": str(uuid.uuid4()),
                    "status": "completed",
                }
                test_run.counter_events.append(
                    CounterEvent(
                        kind="model_call", occurred_at=datetime.now(UTC), payload=model_call_payload
                    )
                )
                log_event("model_call_event", **model_call_payload)
            else:
                resp = await self.planner.describe_screen(  # type: ignore[union-attr]
                    VisionUnderstandingRequest(
                        mode="describe",
                        image_ref=frame.path_for_model(),
                        structured_screen_hint=screen.to_hint_dict(),
                        question=None,
                    )
                )
        except Exception:
            return None  # vision is best-effort supplement

        result = VisionUnderstanding(
            description=resp.description or "",
            confidence=resp.confidence,
            model_name=resp.model_name,
        )
        if self.cache is not None and key is not None:
            try:
                self.cache.store(
                    key,
                    result,
                    source_frame_id=frame.id,
                    sequence=frame.capture_sequence,
                    invocation_id=str(uuid.uuid4()),
                )
            except Exception:
                pass
        return result

    def _needs_vision(self, screen: StructuredScreen) -> bool:
        """True when hash/OCR/template insufficient to understand the page."""
        if screen.ocr_items or screen.template_matches:
            return False
        return True
