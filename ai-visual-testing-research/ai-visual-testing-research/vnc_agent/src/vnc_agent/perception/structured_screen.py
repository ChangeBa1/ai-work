"""Assemble StructuredScreen from perception primitives (FR-011).

Feature 004: the array-native entry point (`assemble_structured_screen_from_pixels`)
consumes the already-decoded pixel array a `FrameCaptureService` capture
produced — never re-reads the just-written file. The legacy path-based
`assemble_structured_screen` is kept as an offline-compatible wrapper.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from vnc_agent.domain.observation import (
    ScreenFrame,
    StructuredScreen,
    VisionUnderstanding,
)
from vnc_agent.perception.ocr.engine import run_ocr, run_ocr_array
from vnc_agent.perception.screen_diff import compute_diff, compute_diff_arrays
from vnc_agent.perception.template.matcher import (
    match_templates_in_dir,
    match_templates_in_dir_array,
)


def assemble_structured_screen_from_pixels(
    frame: ScreenFrame,
    pixels: np.ndarray,
    *,
    previous_pixels: np.ndarray | None = None,
    ocr_enabled: bool = True,
    template_enabled: bool = True,
    templates_dir: str | Path | None = None,
    vision: VisionUnderstanding | None = None,
    diff_threshold: float = 0.02,
) -> StructuredScreen:
    ocr_items = run_ocr_array(pixels) if ocr_enabled else []
    template_matches = (
        match_templates_in_dir_array(pixels, templates_dir)
        if template_enabled and templates_dir is not None
        else []
    )

    if frame.deduplicated:
        # data-model.md §7: duplicate diff is a deterministic short-circuit —
        # never re-read/re-diff a pixel-identical predecessor.
        changed, regions, ratio, local_blobs = False, [], 0.0, []
    else:
        changed, regions, ratio, local_blobs = compute_diff_arrays(
            previous_pixels, pixels, threshold=diff_threshold
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
    :func:`assemble_structured_screen_from_pixels`."""
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
    )
