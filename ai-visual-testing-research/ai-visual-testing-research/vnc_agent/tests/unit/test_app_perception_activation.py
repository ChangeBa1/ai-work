"""Feature 024 (FR-011/FR-012, SC-002): the activation ladder.

The central property under test: activation has exactly ONE source — the
step's explicit `perception_scope`. Seeing a known window on screen is never
a reason, and an undeclared step must not even run a detection.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from vnc_agent.config import AppPerceptionConfig
from vnc_agent.domain.app_perception import SubWindowDetection
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.perception.app_plugins.activation import (
    decide_detection,
    decide_precondition,
    scope_hint_mismatch,
)
from vnc_agent.perception.app_plugins.coordinator import (
    AppPerceptionCoordinator,
    DeclaredWindowMissingError,
)
from vnc_agent.perception.app_plugins.detector import DeclarativeSubWindowPlugin
from vnc_agent.perception.app_plugins.profile import PluginProfile
from vnc_agent.perception.app_plugins.registry import PluginRegistry

RESOLUTION = (1024, 768)
SCOPE = "demo-window"

PROFILE = {"name": SCOPE, "required_anchors": ["Alpha:", "Beta:", "Gamma"]}


def ocr(text, bbox, confidence=0.95):
    return OCRItem(text=text, bbox=bbox, confidence=confidence)


def window_anchors(x1=100, y1=80, x2=500, y2=600):
    return [
        ocr("Alpha:", (x1 + 4, y1 + 4, x1 + 40, y1 + 16)),
        ocr("Beta:", (x1 + 4, (y1 + y2) // 2, x1 + 40, (y1 + y2) // 2 + 12)),
        ocr("Gamma", (x2 - 44, y2 - 18, x2 - 4, y2 - 4)),
    ]


def screen(items=None):
    return StructuredScreen(
        frame_id="f1",
        resolution=RESOLUTION,
        captured_at=datetime.now(UTC),
        ocr_items=window_anchors() if items is None else items,
    )


class CountingPlugin(DeclarativeSubWindowPlugin):
    """Wraps the real detector so we can count detect() calls."""

    def __init__(self, profile, fail: bool = False):
        super().__init__(profile)
        self.calls = 0
        self.fail = fail

    def detect(self, frame):
        self.calls += 1
        return None if self.fail else super().detect(frame)


class FakeZoom:
    """Stands in for observe_zoom: its ocr_items are ALREADY restored to
    original-frame pixels, exactly as the real one returns them."""

    def __init__(self, path="zoom.png"):
        self.image_path = path
        self.crop_offset = (100, 80)
        self.scale_factor = 2.5
        self.resolution = (1000, 1300)
        self.ocr_items = [ocr("Alpha:", (104, 84, 140, 96), 0.99)]
        self.ocr_items_zoom_space = []


class FakePipeline:
    def __init__(self, observation="default"):
        self.observation = FakeZoom() if observation == "default" else observation
        self.calls = 0

    async def observe_zoom(self, **kwargs):
        self.calls += 1
        return self.observation


def build(config_overrides=None, fail_detect=False, pipeline=None):
    profile = PluginProfile.model_validate(PROFILE)
    plugin = CountingPlugin(profile, fail=fail_detect)
    registry = PluginRegistry()
    registry.register(plugin)
    config = AppPerceptionConfig(enabled=True, **(config_overrides or {}))
    return AppPerceptionCoordinator(config, registry), plugin, pipeline or FakePipeline()


class Outcome:
    """Adapter so the existing assertions keep reading naturally."""

    def __init__(self, enhanced, audit, original):
        self.screen = enhanced
        self.audit = audit
        # "observation" == "the screen was actually refined this round".
        self.observation = enhanced if enhanced is not original else None


def run(coordinator, pipeline, *, scope=SCOPE, target=None, step="s1", frame=None):
    original = frame if frame is not None else screen()
    enhanced, audit = asyncio.run(
        coordinator.enhance_screen(
            original,
            step_id=step,
            declared_scope=scope,
            target=target,
            target_id="win10-test-01",
            pipeline=pipeline,
        )
    )
    return Outcome(enhanced, audit, original)


# --- reason codes ----------------------------------------------------------


def test_undeclared_step_is_not_activated_and_runs_no_detection():
    """SC-002: the default path must be free — no detection, no geometry."""
    coordinator, plugin, pipeline = build()
    outcome = run(coordinator, pipeline, scope=None)
    assert outcome.observation is None
    assert outcome.audit.reason_code == "not_declared"
    assert outcome.audit.activated is False
    assert plugin.calls == 0, "an undeclared step must never trigger detection"
    assert pipeline.calls == 0


def test_explicit_none_is_equivalent_to_undeclared():
    coordinator, plugin, pipeline = build()
    outcome = run(coordinator, pipeline, scope="none")
    assert outcome.audit.reason_code == "declared_off"
    assert plugin.calls == 0


def test_seeing_the_window_never_activates_an_undeclared_step():
    """The whole point of the design: the window IS on screen and perfectly
    detectable, yet a step that did not ask for it is untouched."""
    coordinator, plugin, _ = build()
    assert plugin.detect(screen()) is not None, "precondition: window is visible"
    outcome = run(coordinator, FakePipeline(), scope=None)
    assert outcome.audit.activated is False
    assert outcome.audit.reason_code == "not_declared"


def test_disabled_globally():
    profile = PluginProfile.model_validate(PROFILE)
    registry = PluginRegistry()
    registry.register(DeclarativeSubWindowPlugin(profile))
    coordinator = AppPerceptionCoordinator(AppPerceptionConfig(enabled=False), registry)
    outcome = run(coordinator, FakePipeline())
    assert outcome.audit.reason_code == "disabled"


def test_unknown_plugin_name():
    coordinator, _, pipeline = build()
    outcome = run(coordinator, pipeline, scope="not-registered")
    assert outcome.audit.reason_code == "plugin_not_registered"


def test_plugin_not_allowed_for_this_target():
    coordinator, _, pipeline = build({"allowed_plugins": {"win10-test-01": []}})
    outcome = run(coordinator, pipeline)
    assert outcome.audit.reason_code == "plugin_not_allowed"


def test_target_absent_from_allow_list_permits_every_plugin():
    coordinator, _, pipeline = build({"allowed_plugins": {"other-machine": ["x"]}})
    outcome = run(coordinator, pipeline)
    assert outcome.audit.activated is True


def _other_frame():
    """A different frame (different content hash) so the memo does not hit."""
    return StructuredScreen(
        frame_id="f2",
        resolution=RESOLUTION,
        captured_at=datetime.now(UTC),
        ocr_items=window_anchors(),
        content_hash="other",
    )


def test_budget_exhausted_after_the_configured_number_of_refined_frames():
    coordinator, _, pipeline = build({"max_activations_per_step": 1})
    assert run(coordinator, pipeline).audit.activated is True
    second = run(coordinator, pipeline, frame=_other_frame())
    assert second.audit.reason_code == "budget_exhausted"
    assert second.observation is None
    # A different step gets its own budget.
    assert run(coordinator, pipeline, step="s2").audit.activated is True


def test_unchanged_frame_is_served_from_the_memo_without_spending_budget():
    """Re-observing the same screen (pre-action, post-action, re-observe) must
    not pay for another capture + OCR pass."""
    coordinator, plugin, pipeline = build({"max_activations_per_step": 1})
    first = run(coordinator, pipeline)
    assert first.audit.reason_code == "activated"
    second = run(coordinator, pipeline)
    assert second.audit.reason_code == "activated_cached"
    assert second.audit.activated is True
    assert pipeline.calls == 1, "the memo must avoid a second zoom capture"
    assert plugin.calls == 1, "and a second detection"


def test_budget_and_memo_reset_per_step():
    coordinator, _, pipeline = build({"max_activations_per_step": 1})
    run(coordinator, pipeline)
    coordinator.reset_step("s1")
    outcome = run(coordinator, pipeline)
    assert outcome.audit.activated is True
    assert outcome.audit.reason_code == "activated", "memo must be cleared too"


def test_zero_budget_disables_enhancement():
    coordinator, _, pipeline = build({"max_activations_per_step": 0})
    assert run(coordinator, pipeline).audit.reason_code == "budget_exhausted"


def test_enhancement_is_not_gated_on_the_action_type():
    """The refinement now feeds assertions and OCR-direct clicks too, so a
    keyboard step's verification benefits from it just as much as a click
    does. Gating on "this action produces a coordinate" would withhold it
    from exactly the cases that motivated moving it to the OCR stage."""
    coordinator, _, pipeline = build()
    assert run(coordinator, pipeline).audit.activated is True


def test_not_detected_marks_declared_but_undetected():
    coordinator, _, pipeline = build(fail_detect=True)
    outcome = run(coordinator, pipeline)
    assert outcome.audit.reason_code == "not_detected"
    assert outcome.audit.declared_but_undetected is True
    assert outcome.audit.declared_scope == SCOPE
    assert outcome.observation is None


def test_low_detection_confidence():
    coordinator, _, pipeline = build({"min_detection_confidence": 0.99})
    outcome = run(coordinator, pipeline)
    assert outcome.audit.reason_code == "low_detection_confidence"
    assert outcome.audit.declared_but_undetected is True


def test_roi_not_subwindow_when_detection_covers_the_screen():
    coordinator, _, pipeline = build({"roi_area_ratio_max": 0.05})
    outcome = run(coordinator, pipeline)
    assert outcome.audit.reason_code == "roi_not_subwindow"


def test_roi_not_subwindow_when_region_is_tiny():
    coordinator, _, pipeline = build({"min_roi_size_px": 5000})
    assert run(coordinator, pipeline).audit.reason_code == "roi_not_subwindow"


def test_scale_not_beneficial():
    coordinator, _, pipeline = build({"max_upscaled_megapixels": 0.01})
    assert run(coordinator, pipeline).audit.reason_code == "scale_not_beneficial"


def test_observation_failure_falls_open():
    coordinator, _, _ = build()
    outcome = run(coordinator, FakePipeline(observation=None))
    assert outcome.audit.reason_code == "observation_failed"
    assert outcome.observation is None


def test_observation_exception_falls_open():
    class Exploding:
        async def observe_zoom(self, **kwargs):
            raise RuntimeError("capture died")

    coordinator, _, _ = build()
    outcome = run(coordinator, Exploding())
    assert outcome.audit.reason_code == "observation_failed"


def test_activated_populates_the_full_audit():
    coordinator, _, pipeline = build()
    outcome = run(coordinator, pipeline)
    audit = outcome.audit
    assert audit.activated is True
    assert audit.reason_code == "activated"
    assert audit.plugin_name == SCOPE
    assert audit.roi is not None
    assert audit.detection_method == "ocr_anchors"
    assert audit.detection_confidence is not None
    assert audit.scale_factor == 2.5
    assert audit.zoom_image_ref == "zoom.png"
    assert audit.upscaled_resolution == (1000, 1300)
    assert len(audit.matched_anchors) == 3
    # The refined read replaced the full-frame items inside the window.
    assert audit.ocr_items_replaced == 3
    assert audit.ocr_items_added == 1


def test_every_reason_code_maps_activated_consistently():
    """activated is true iff reason_code == "activated"."""
    coordinator, _, pipeline = build()
    for outcome in (run(coordinator, pipeline, scope=None), run(coordinator, pipeline)):
        assert outcome.audit.activated == (
            outcome.audit.reason_code in ("activated", "activated_cached")
        )


# --- FR-013a: declared-but-missing behaviour -------------------------------


def test_fallback_mode_is_silent_but_audited():
    coordinator, _, pipeline = build({"on_declared_window_missing": "fallback"}, fail_detect=True)
    outcome = run(coordinator, pipeline)
    assert outcome.observation is None
    assert outcome.audit.declared_but_undetected is True


def test_fail_mode_raises_a_diagnosable_error():
    coordinator, _, pipeline = build({"on_declared_window_missing": "fail"}, fail_detect=True)
    with pytest.raises(DeclaredWindowMissingError) as excinfo:
        run(coordinator, pipeline)
    assert SCOPE in str(excinfo.value)
    assert "s1" in str(excinfo.value)


# --- scope hint mismatch: records, never decides ---------------------------


def test_scope_hint_mismatch_records_targets_outside_the_window():
    region = (100, 80, 500, 600)
    items = window_anchors() + [ocr("Checkout", (800, 700, 900, 720))]
    mismatch = scope_hint_mismatch({"text": "Checkout"}, items, region)
    assert mismatch is not None
    assert mismatch.kind == "all_outside"
    assert mismatch.hits_outside == 1


def test_scope_hint_mismatch_detects_straddling():
    region = (100, 80, 500, 600)
    items = [ocr("Confirm", (200, 200, 260, 216)), ocr("Confirm", (800, 700, 860, 716))]
    mismatch = scope_hint_mismatch({"text": "Confirm"}, items, region)
    assert mismatch is not None
    assert mismatch.kind == "straddling"


def test_scope_hint_mismatch_silent_when_all_hits_are_inside():
    region = (100, 80, 500, 600)
    assert scope_hint_mismatch({"text": "Alpha:"}, window_anchors(), region) is None


def test_scope_hint_mismatch_ignores_step_intent_prose():
    """Only target.text / nearby_texts are clues. Intent prose routinely names
    both the window and the screen behind it, so matching it would create
    noise in exactly the wrong direction."""
    region = (100, 80, 500, 600)
    mismatch = scope_hint_mismatch(
        {"intent": "do not click inside Alpha:"}, window_anchors(), region
    )
    assert mismatch is None


def test_mismatch_never_changes_the_outcome():
    coordinator, _, pipeline = build()
    outcome = run(coordinator, pipeline, target={"text": "SomethingElse"})
    assert outcome.audit.activated is True, "a wrong-looking declaration is still honoured"


# --- ladder-order guards ---------------------------------------------------


def test_precondition_ladder_short_circuits_in_order():
    """Undeclared beats every other gate — even a disabled feature."""
    decision = decide_precondition(
        declared_scope=None,
        enabled=False,
        plugin_registered=False,
        plugin_allowed=False,
    )
    assert decision is not None and decision.reason_code == "not_declared"


def test_detection_ladder_accepts_a_good_detection():
    detection = SubWindowDetection(
        plugin_name=SCOPE,
        region=(100, 80, 500, 600),
        confidence=0.9,
        method="ocr_anchors",
        area_ratio=0.26,
    )
    assert (
        decide_detection(
            declared_scope=SCOPE,
            detection=detection,
            min_detection_confidence=0.7,
            roi_area_ratio_max=0.95,
            min_roi_size_px=24,
        )
        is None
    )


def test_empty_refined_read_keeps_the_original_ocr():
    """If the magnified pass reads nothing inside the window, the coarse read
    must survive: replacing it with an empty set would delete text the
    full-frame pass did catch and silently break assertions."""

    class EmptyZoom(FakeZoom):
        def __init__(self):
            super().__init__()
            self.ocr_items = []

    coordinator, _, _ = build()
    outcome = run(coordinator, FakePipeline(observation=EmptyZoom()))
    assert outcome.audit.activated is True
    assert outcome.audit.ocr_items_replaced == 0
    assert outcome.audit.ocr_items_added == 0
    assert [i.text for i in outcome.screen.ocr_items] == [
        i.text for i in window_anchors()
    ]


def test_refined_items_outside_the_roi_are_dropped_not_clamped():
    """A restored box that fell outside the crop is rejected outright."""

    class StrayZoom(FakeZoom):
        def __init__(self):
            super().__init__()
            self.ocr_items = [
                ocr("Inside", (110, 90, 150, 104), 0.99),
                ocr("Stray", (900, 700, 980, 720), 0.99),
            ]

    coordinator, _, _ = build()
    outcome = run(coordinator, FakePipeline(observation=StrayZoom()))
    texts = {i.text for i in outcome.screen.ocr_items}
    assert "Inside" in texts
    assert "Stray" not in texts
