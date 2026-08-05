"""Feature 024 (FR-005b/FR-016): zoom factor selection.

Deliberately NOT derived from the window's size. Legibility is governed by
glyph height, which is ~constant across these windows (default UI fonts), not
by how large the window is; a size-derived scale would silently encode a
window-shape assumption and under-magnify wide, flat windows.

So: a fixed configured scale, clamped by [min_scale, max_scale] and then by a
total-pixel budget (weak-hardware guard). If the pixel budget forces the scale
below min_scale the enhancement is abandoned — magnifying by less than that
buys nothing for the extra OCR pass.
"""

from __future__ import annotations

_MEGA = 1_000_000.0


def compute_scale(
    region: tuple[int, int, int, int],
    *,
    default_scale: float,
    min_scale: float,
    max_scale: float,
    max_upscaled_megapixels: float,
    profile_override: float | None = None,
) -> float | None:
    """Return the scale to use, or None when zooming is not worthwhile."""
    x1, y1, x2, y2 = region
    w, h = x2 - x1, y2 - y1
    if w <= 0 or h <= 0:
        return None

    scale = profile_override if profile_override is not None else default_scale
    scale = max(min_scale, min(scale, max_scale))

    budget_px = max_upscaled_megapixels * _MEGA
    if w * h * scale * scale > budget_px:
        scale = (budget_px / (w * h)) ** 0.5

    if scale <= 1.0 or scale < min_scale:
        return None
    return scale
