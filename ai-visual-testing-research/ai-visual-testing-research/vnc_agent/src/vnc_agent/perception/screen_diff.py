"""Frame-to-frame difference detection (FR-007 + 002 local_blobs decoupling)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from vnc_agent.domain.observation import Region
from vnc_agent.perception.screenshot import load_image_array


def compute_diff(
    prev_path: str | Path | None,
    curr_path: str | Path,
    *,
    threshold: float = 0.02,
    mask_regions: list[Region] | None = None,
    min_blob_pixels: int = 16,
) -> tuple[bool, list[Region], float, list[Region]]:
    """
    Compare two frames.

    Returns (changed_since_last, changed_regions, diff_ratio, local_blobs).

    - ``changed_since_last`` / ``changed_regions``: gated by global ``threshold``
      (weak evidence for screen_changed).
    - ``local_blobs``: always extracted from connected components (subject only to
      ``min_blob_pixels`` and ``mask_regions``), independent of the global threshold
      (research.md §1 — root-cause fix for the 0.424% incident).
    """
    curr = load_image_array(curr_path)
    if prev_path is None:
        return True, [], 1.0, []

    prev = load_image_array(prev_path)
    if prev.shape != curr.shape:
        full = Region(x1=0, y1=0, x2=curr.shape[1], y2=curr.shape[0])
        return True, [full], 1.0, [full]

    gray_prev = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
    gray_curr = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(gray_prev, gray_curr)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)

    # Dynamic-noise mask applied before both ratio and contour extraction (FR-005)
    if mask_regions:
        for r in mask_regions:
            thresh[r.y1 : r.y2, r.x1 : r.x2] = 0

    total = thresh.size
    changed_px = int(np.count_nonzero(thresh))
    ratio = changed_px / total if total else 0.0
    changed = ratio >= threshold

    # Always extract local connected components (not gated by global threshold)
    local_blobs: list[Region] = []
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        if w * h < min_blob_pixels:
            continue
        local_blobs.append(Region(x1=x, y1=y, x2=x + w, y2=y + h))

    # Weak-signal regions still only when global threshold is met (001 compat)
    regions: list[Region] = list(local_blobs) if changed else []

    return changed, regions, ratio, local_blobs
