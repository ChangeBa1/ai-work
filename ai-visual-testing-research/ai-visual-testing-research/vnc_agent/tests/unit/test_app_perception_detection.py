"""Feature 024 (FR-006..FR-010, SC-009): declarative sub-window detection.

The shape-invariance parametrisation uses the REAL client sizes surveyed in
the target environment: aspect ratios span 0.73..5.34 and screen area spans
3.3%..77.1%, so any built-in shape prior in core would reject someone.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.perception.app_plugins.detector import (
    DeclarativeSubWindowPlugin,
    normalize,
)
from vnc_agent.perception.app_plugins.profile import PluginProfile
from vnc_agent.perception.app_plugins.scaling import compute_scale

RESOLUTION = (1024, 768)

# Real ClientSize values from the surveyed application (name, w, h).
REAL_WINDOW_SHAPES = [
    ("tall-narrow", 423, 581),      # aspect 0.73, 31.3% of screen
    ("wide", 634, 448),             # aspect 1.42, 36.1%
    ("very-wide-small", 235, 109),  # aspect 2.16, 3.3%
    ("ultra-wide", 854, 160),       # aspect 5.34, 17.4%
    ("near-fullscreen", 1028, 590), # aspect 1.74, 77.1% (clipped to frame)
]


def screen(items: list[OCRItem], resolution=RESOLUTION) -> StructuredScreen:
    return StructuredScreen(
        frame_id="f1",
        resolution=resolution,
        captured_at=datetime.now(UTC),
        ocr_items=items,
    )


def ocr(text: str, bbox, confidence: float = 0.95) -> OCRItem:
    return OCRItem(text=text, bbox=bbox, confidence=confidence)


def make_plugin(**overrides) -> DeclarativeSubWindowPlugin:
    payload = {"name": "demo-window", "required_anchors": ["Alpha:", "Beta:", "Gamma"]}
    payload.update(overrides)
    return DeclarativeSubWindowPlugin(PluginProfile.model_validate(payload))


def anchors_for(x1, y1, x2, y2) -> list[OCRItem]:
    """Three anchors spread over the top, middle and bottom of a window."""
    return [
        ocr("Alpha:", (x1 + 4, y1 + 4, x1 + 40, y1 + 16)),
        ocr("Beta:", (x1 + 4, (y1 + y2) // 2, x1 + 40, (y1 + y2) // 2 + 12)),
        ocr("Gamma", (x2 - 44, y2 - 18, x2 - 4, y2 - 4)),
    ]


def test_detects_window_from_anchor_union():
    plugin = make_plugin()
    detection = plugin.detect(screen(anchors_for(100, 80, 500, 600)))
    assert detection is not None
    assert detection.plugin_name == "demo-window"
    assert detection.method == "ocr_anchors"
    assert len(detection.matched_anchors) == 3
    x1, y1, x2, y2 = detection.region
    # The union of the anchors must be inside the derived region.
    assert x1 <= 104 and y1 <= 84 and x2 >= 496 and y2 >= 596


def test_detection_is_deterministic():
    plugin = make_plugin()
    frame = screen(anchors_for(100, 80, 500, 600))
    first = plugin.detect(frame)
    second = plugin.detect(frame)
    assert first == second


def test_missing_anchor_means_undetected():
    plugin = make_plugin()
    items = anchors_for(100, 80, 500, 600)[:2]
    assert plugin.detect(screen(items)) is None


def test_relaxed_anchor_threshold_allows_a_partial_read():
    plugin = make_plugin(min_required_anchor_hits=2)
    items = anchors_for(100, 80, 500, 600)[:2]
    assert plugin.detect(screen(items)) is not None


def test_highest_confidence_wins_when_an_anchor_matches_twice():
    plugin = make_plugin()
    items = anchors_for(100, 80, 500, 600)
    items.append(ocr("Alpha:", (900, 700, 950, 720), confidence=0.99))
    detection = plugin.detect(screen(items))
    assert detection is not None
    alpha = next(a for a in detection.matched_anchors if a.anchor_text == "Alpha:")
    assert alpha.bbox == (900, 700, 950, 720)


def test_truncated_text_still_matches():
    """Ellipsis-truncated labels are common in narrow renderings."""
    assert normalize("ScannerSi...") == "scannersi"
    assert normalize("Window…") == "window"
    plugin = make_plugin(required_anchors=["ScannerSimulator"])
    detection = plugin.detect(screen([ocr("ScannerSi...", (10, 10, 90, 24))]))
    assert detection is not None


def test_confidence_is_the_weakest_anchor():
    plugin = make_plugin()
    items = anchors_for(100, 80, 500, 600)
    items[1] = ocr("Beta:", items[1].bbox, confidence=0.42)
    detection = plugin.detect(screen(items))
    assert detection is not None
    assert detection.confidence == pytest.approx(0.42)


def test_detector_never_raises_on_a_broken_frame():
    """FR-010: any internal failure degrades to "undetected", never an
    exception escaping into the main loop."""

    class Exploding(list):
        def __iter__(self):
            raise RuntimeError("boom")

    frame = screen(anchors_for(100, 80, 500, 600))
    object.__setattr__(frame, "ocr_items", Exploding())
    assert make_plugin().detect(frame) is None


def test_profile_declared_shape_ranges_can_reject():
    plugin = make_plugin(aspect_ratio_range=[2.0, 4.0])
    # The synthetic window is roughly 0.7 aspect -> outside the declared range.
    assert plugin.detect(screen(anchors_for(100, 80, 500, 600))) is None


def test_profile_declared_min_size_can_reject():
    plugin = make_plugin(min_size_px=400)
    assert plugin.detect(screen(anchors_for(100, 80, 200, 180))) is None


# --- SC-009: shape invariance ---------------------------------------------


@pytest.mark.parametrize("label,w,h", REAL_WINDOW_SHAPES, ids=[s[0] for s in REAL_WINDOW_SHAPES])
def test_every_real_window_shape_is_detected(label, w, h):
    """A profile carrying no shape ranges must detect all of them: core holds
    no aspect/area prior of its own."""
    w = min(w, RESOLUTION[0])
    h = min(h, RESOLUTION[1])
    plugin = make_plugin()
    detection = plugin.detect(screen(anchors_for(0, 0, w, h)))
    assert detection is not None, f"{label} ({w}x{h}) was rejected"


@pytest.mark.parametrize("label,w,h", REAL_WINDOW_SHAPES, ids=[s[0] for s in REAL_WINDOW_SHAPES])
def test_scale_is_shape_independent(label, w, h):
    """The zoom factor must not depend on the window's shape or size (beyond
    the megapixel safety clamp)."""
    scale = compute_scale(
        (0, 0, w, h),
        default_scale=2.5,
        min_scale=1.2,
        max_scale=4.0,
        max_upscaled_megapixels=4.0,
    )
    assert scale is not None, f"{label} ({w}x{h}) produced no usable scale"
    assert 1.2 <= scale <= 2.5


def test_megapixel_budget_clamps_but_keeps_magnifying():
    scale = compute_scale(
        (0, 0, 1000, 1000),
        default_scale=4.0,
        min_scale=1.2,
        max_scale=4.0,
        max_upscaled_megapixels=4.0,
    )
    assert scale == pytest.approx(2.0)


def test_scale_abandoned_when_budget_forces_it_below_minimum():
    """A window so large that the pixel budget leaves no useful magnification
    must abandon enhancement rather than pay for a pointless OCR pass."""
    assert (
        compute_scale(
            (0, 0, 2000, 2000),
            default_scale=2.5,
            min_scale=1.2,
            max_scale=4.0,
            max_upscaled_megapixels=4.0,
        )
        is None
    )


def test_profile_scale_override_is_honoured():
    scale = compute_scale(
        (0, 0, 400, 400),
        default_scale=2.5,
        min_scale=1.2,
        max_scale=4.0,
        max_upscaled_megapixels=16.0,
        profile_override=3.5,
    )
    assert scale == pytest.approx(3.5)


def test_degenerate_region_has_no_scale():
    assert (
        compute_scale(
            (10, 10, 10, 40),
            default_scale=2.5,
            min_scale=1.2,
            max_scale=4.0,
            max_upscaled_megapixels=4.0,
        )
        is None
    )
