"""Assemble StructuredScreen from perception primitives (FR-011).

Feature 004: component computation is separated from assembly
(perception-cache-contract.md). The array-native entry point
(`assemble_structured_screen_from_pixels`) consumes the already-decoded
pixel array a `FrameCaptureService` capture produced; a strictly-adjacent
exact-duplicate frame reuses OCR/template pure results from the bounded
`AnalysisResultCache`, but a *new* `StructuredScreen` is always built —
current frame identity/time/path are never overwritten by the cached
source's identity. `diff` is a deterministic short-circuit for duplicates
(never a cache lookup) and a fresh computation for unique frames (also
never a lookup — only strictly-adjacent duplicates are cache-eligible).

The legacy path-based `assemble_structured_screen` is kept as an
offline-compatible wrapper with no caching.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from vnc_agent.domain.observation import (
    ScreenFrame,
    StructuredScreen,
    VisionUnderstanding,
    scope_identity,
)
from vnc_agent.perception.cache import AnalysisCacheKey, AnalysisResultCache
from vnc_agent.perception.ocr.engine import (
    ocr_component_identity,
    run_ocr,
    run_ocr_array,
)
from vnc_agent.perception.screen_diff import compute_diff, compute_diff_arrays
from vnc_agent.perception.template.matcher import (
    match_templates_in_dir,
    match_templates_in_dir_array,
    template_set_fingerprint,
)

AnalysisEventFn = Callable[[dict[str, Any]], None]

# Fallback identity shape; at call time the engine's live
# `ocr_component_identity()` is preferred so the analysis-cache key reflects
# the configured recognition language (feature 010, FR-011).
_DEFAULT_OCR_IDENTITY = {
    "backend": "rapidocr-onnxruntime",
    "version": "1.0",
    "language": "auto",
    "preprocess": "none",
}

_COMPONENT_STAGE = {"ocr": "OCR", "template": "template", "vision_describe": "vision"}


def _lookup_or_compute(
    *,
    cache: AnalysisResultCache | None,
    component: str,
    algorithm_revision: str,
    frame: ScreenFrame,
    scope_id: str,
    perception_config_fingerprint: str,
    component_identity: dict[str, Any],
    compute_fn: Callable[[], Any],
    on_event: AnalysisEventFn | None,
    test_run: Any = None,
    clock: Any = None,
) -> tuple[Any, str | None]:
    """Returns ``(result, source_frame_id)``; ``source_frame_id`` is None on
    a miss/uncached path — only set when a cache hit actually reused it."""
    from vnc_agent.runtime.telemetry import measure_stage

    stage = _COMPONENT_STAGE.get(component, component)

    def _measure(**kwargs: Any):
        from contextlib import nullcontext

        if test_run is None:
            return nullcontext()
        return measure_stage(
            test_run, stage=stage, run_id=frame.run_id, step_id=frame.step_id,
            frame_id=frame.id, clock=clock, **kwargs,
        )

    if cache is None or frame.content_hash is None:
        with _measure(actual_call=True, cache_hit=False):
            result = compute_fn()
        if on_event:
            on_event(
                {"component": component, "outcome": "miss", "invocation_id": str(uuid.uuid4())}
            )
        return result, None

    key = AnalysisCacheKey(
        component=component,  # type: ignore[arg-type]
        algorithm_revision=algorithm_revision,
        content_hash=frame.content_hash,
        scope_identity=scope_id,
        pixel_format=frame.scope.pixel_format,
        mask_identity=frame.scope.mask_identity,
        perception_config_fingerprint=perception_config_fingerprint,
        component_identity=component_identity,
    )

    entry = None
    try:
        entry = cache.lookup(
            key,
            frame_deduplicated=frame.deduplicated,
            duplicate_of_frame_id=frame.duplicate_of_frame_id,
            current_sequence=frame.capture_sequence,
        )
    except Exception:
        # cache get failure -> miss + full analysis (perception-cache-
        # contract.md "Error behavior"); never blocks the current frame.
        entry = None

    if entry is not None:
        with _measure(actual_call=False, cache_hit=True, source_ref=entry.source_frame_id):
            pass
        if on_event:
            on_event(
                {
                    "component": component,
                    "outcome": "hit",
                    "source_ref": entry.source_frame_id,
                }
            )
        return entry.result, entry.source_frame_id

    with _measure(actual_call=True, cache_hit=False):
        result = compute_fn()
    invocation_id = str(uuid.uuid4())
    try:
        cache.store(
            key,
            result,
            source_frame_id=frame.id,
            sequence=frame.capture_sequence,
            invocation_id=invocation_id,
        )
    except Exception:
        pass  # cache put failure -> result still usable, just not cached
    if on_event:
        on_event({"component": component, "outcome": "miss", "invocation_id": invocation_id})
    return result, None


def assemble_structured_screen_from_pixels(
    frame: ScreenFrame,
    pixels: np.ndarray,
    *,
    previous_pixels: np.ndarray | None = None,
    cache: AnalysisResultCache | None = None,
    ocr_enabled: bool = True,
    template_enabled: bool = True,
    templates_dir: str | Path | None = None,
    vision: VisionUnderstanding | None = None,
    diff_threshold: float = 0.02,
    perception_config_fingerprint: str = "default-v1",
    ocr_identity: dict[str, Any] | None = None,
    template_threshold: float = 0.8,
    on_analysis_event: AnalysisEventFn | None = None,
    test_run: Any = None,
    clock: Any = None,
) -> StructuredScreen:
    scope_id = scope_identity(frame.scope)
    analysis_source_refs: dict[str, str] = {}

    if ocr_enabled:
        identity = dict(ocr_identity or ocr_component_identity())
        ocr_items, source = _lookup_or_compute(
            cache=cache,
            component="ocr",
            algorithm_revision="ocr-v1",
            frame=frame,
            scope_id=scope_id,
            perception_config_fingerprint=perception_config_fingerprint,
            component_identity=identity,
            compute_fn=lambda: run_ocr_array(pixels),
            on_event=on_analysis_event,
            test_run=test_run,
            clock=clock,
        )
        if source:
            analysis_source_refs["ocr"] = source
    else:
        ocr_items = []

    if template_enabled and templates_dir is not None:
        fingerprint = template_set_fingerprint(templates_dir)
        identity = {
            "matcher_revision": "template-v1",
            "threshold": template_threshold,
            "template_set_fingerprint": fingerprint,
        }
        template_matches, source = _lookup_or_compute(
            cache=cache,
            component="template",
            algorithm_revision="template-v1",
            frame=frame,
            scope_id=scope_id,
            perception_config_fingerprint=perception_config_fingerprint,
            component_identity=identity,
            compute_fn=lambda: match_templates_in_dir_array(
                pixels, templates_dir, threshold=template_threshold
            ),
            on_event=on_analysis_event,
            test_run=test_run,
            clock=clock,
        )
        if source:
            analysis_source_refs["template"] = source
    else:
        template_matches = []

    if frame.deduplicated:
        # perception-cache-contract.md "Diff special case": deterministic
        # short-circuit, never a path read, never an OpenCV diff.
        changed, regions, ratio, local_blobs = False, [], 0.0, []
        if on_analysis_event:
            on_analysis_event(
                {"component": "diff", "outcome": "hit", "source_ref": frame.duplicate_of_frame_id}
            )
        if frame.duplicate_of_frame_id:
            analysis_source_refs["diff"] = frame.duplicate_of_frame_id
    else:
        changed, regions, ratio, local_blobs = compute_diff_arrays(
            previous_pixels, pixels, threshold=diff_threshold
        )
        if on_analysis_event:
            on_analysis_event(
                {"component": "diff", "outcome": "miss", "invocation_id": str(uuid.uuid4())}
            )

    return StructuredScreen(
        frame_id=frame.id,
        resolution=(frame.width, frame.height),
        captured_at=frame.timestamp,
        ocr_items=ocr_items,
        template_matches=template_matches,
        changed_since_last=changed,
        changed_regions=regions,
        local_blobs=local_blobs,
        global_diff_ratio=ratio,
        vision_understanding=vision,
        image_path=frame.image_path,
        crop_offset=frame.crop_offset,
        model_image_path=frame.model_image_path,
        content_hash=frame.content_hash,
        deduplicated=frame.deduplicated,
        duplicate_of_frame_id=frame.duplicate_of_frame_id,
        comparison_available=frame.comparison_available,
        capture_sequence=frame.capture_sequence,
        scope_key=scope_id,
        analysis_source_refs=analysis_source_refs,
    )


def assemble_structured_screen(
    frame: ScreenFrame,
    *,
    prev_frame_path: str | None = None,
    ocr_enabled: bool = True,
    template_enabled: bool = True,
    templates_dir: str | Path | None = None,
    vision: VisionUnderstanding | None = None,
    diff_threshold: float = 0.02,
) -> StructuredScreen:
    """Offline-compatible path-based wrapper — see
    :func:`assemble_structured_screen_from_pixels`. No caching."""
    ocr_items = run_ocr(frame.image_path) if ocr_enabled else []
    template_matches = []
    if template_enabled and templates_dir is not None:
        template_matches = match_templates_in_dir(frame.image_path, templates_dir)

    changed, regions, ratio, local_blobs = compute_diff(
        prev_frame_path, frame.image_path, threshold=diff_threshold
    )

    return StructuredScreen(
        frame_id=frame.id,
        resolution=(frame.width, frame.height),
        captured_at=frame.timestamp,
        ocr_items=ocr_items,
        template_matches=template_matches,
        changed_since_last=changed,
        changed_regions=regions,
        local_blobs=local_blobs,
        global_diff_ratio=ratio,
        vision_understanding=vision,
        image_path=frame.image_path,
        crop_offset=frame.crop_offset,
        model_image_path=frame.model_image_path or frame.image_path,
        capture_sequence=frame.capture_sequence,
        scope_key=scope_identity(frame.scope),
    )
