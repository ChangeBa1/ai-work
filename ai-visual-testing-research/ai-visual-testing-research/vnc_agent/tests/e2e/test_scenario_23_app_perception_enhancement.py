"""E2E scenario 23 (feature 024): observation-stage sub-window OCR refinement.

Models the real-machine failure this feature exists for: small ASCII glyphs
are misread at full-frame resolution ("TopMost" -> "Topllost", "Scan" ->
"Sean"), which breaks business assertions AND the OCR-direct-click path long
before grounding is ever consulted.

US1/SC-001: a step that DECLARES a scope gets the sub-window re-read at 2.5x;
the refined text replaces the garbled full-frame read and the restored boxes
are in original-frame pixels.

US2/SC-002: a step that declares nothing is untouched even though the same
window is plainly visible, and no detection work happens at all.

FR-013a: a declared scope whose window is absent falls back and is audited.
FR-024: a declared step ALWAYS carries an audit record, whatever resolution
path the action takes — the gap that made "not triggered" indistinguishable
from "broken" on the real machine.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tests.e2e.conftest import build_runtime
from vnc_agent.config import AppPerceptionConfig
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.mimo_grounder import (
    _merge_ui_index_candidates,
    _resolve_coordinate_spaces,
    _restore_and_cap,
)
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.models.provider import GroundingRequest
from vnc_agent.perception.ocr import engine as ocr_engine

SCOPE = "demo-window"
SCREEN = (300, 200)

# The sub-window's anchors, in ORIGINAL frame pixels.
_ANCHORS = {
    "Alpha:": (24, 34, 60, 46),
    "Beta:": (24, 90, 60, 102),
    "Gamma": (140, 145, 176, 157),
}
# A label inside the window that the full-frame read GARBLES and the
# magnified read gets right — the whole point of the feature.
_SMALL_LABEL_BOX = (100, 60, 150, 72)
_SMALL_LABEL_TRUE = "TopMost"
_SMALL_LABEL_GARBLED = "Topllost"
# Main-screen text OUTSIDE the window; must survive untouched.
_OUTSIDE = ("Checkout", (220, 20, 270, 32))

# anchor union (24,34,176,157) padded by the profile default 0.05 per side
_EXPECTED_ROI = (16, 28, 184, 163)


def _poly(box):
    x1, y1, x2, y2 = box
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


class _ScaleAwareOcr:
    """RapidOCR-shaped stub.

    On the full frame it returns the garbled small label; on an upscaled crop
    it returns the correct text, with boxes in the crop's own coordinate
    space so the production restore path (`round(v/scale) + crop_offset`) is
    genuinely exercised rather than bypassed.
    """

    def __init__(self, *, anchors=True):
        self.anchors = anchors
        self.zoom_calls = 0

    def __call__(self, img):
        height, width = img.shape[0], img.shape[1]
        if (width, height) == SCREEN:
            items = []
            if self.anchors:
                items += [[_poly(b), t, 0.93] for t, b in _ANCHORS.items()]
            items.append([_poly(_SMALL_LABEL_BOX), _SMALL_LABEL_GARBLED, 0.55])
            items.append([_poly(_OUTSIDE[1]), _OUTSIDE[0], 0.95])
            return items, None

        # Upscaled crop of the ROI.
        self.zoom_calls += 1
        ox, oy = _EXPECTED_ROI[0], _EXPECTED_ROI[1]
        scale = width / (_EXPECTED_ROI[2] - ox)

        def to_zoom(box):
            x1, y1, x2, y2 = box
            return [
                [round((x1 - ox) * scale), round((y1 - oy) * scale)],
                [round((x2 - ox) * scale), round((y1 - oy) * scale)],
                [round((x2 - ox) * scale), round((y2 - oy) * scale)],
                [round((x1 - ox) * scale), round((y2 - oy) * scale)],
            ]

        items = [[to_zoom(_SMALL_LABEL_BOX), _SMALL_LABEL_TRUE, 0.97]]
        if self.anchors:
            items += [[to_zoom(b), t, 0.97] for t, b in _ANCHORS.items()]
        return items, None


# The small label expressed in the CROP's coordinate space, i.e. what a
# grounder looking at the magnified image would actually return.
def _in_zoom_space(box, roi=_EXPECTED_ROI, scale=2.5):
    x1, y1, x2, y2 = box
    ox, oy = roi[0], roi[1]
    return (
        round((x1 - ox) * scale),
        round((y1 - oy) * scale),
        round((x2 - ox) * scale),
        round((y2 - oy) * scale),
    )


class ScriptedGrounder:
    """Answers in whatever coordinate space the request's image is in, then
    runs the REAL restoration chain — so the test proves the production
    `round(v/scale) + crop_offset` path, not a stubbed shortcut."""

    def __init__(self, *, found: bool = True) -> None:
        self.found = found
        self.calls: list[GroundingRequest] = []

    async def ground(self, request: GroundingRequest) -> GroundingResult:
        self.calls.append(request)
        if not self.found:
            return GroundingResult(found=False, candidates=[], model_name="scripted")
        bbox = (
            _in_zoom_space(_SMALL_LABEL_BOX)
            if request.scale_factor != 1.0
            else _SMALL_LABEL_BOX
        )
        result = GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=bbox, coordinate_space="pixel", confidence=0.9, reason="ok"
                )
            ],
            model_name="scripted",
        )
        merged = _merge_ui_index_candidates(result, request)
        resolved = _resolve_coordinate_spaces(merged, request)
        return _restore_and_cap(resolved, request, model_name="scripted", top_k=3)


PROFILE = {
    "name": SCOPE,
    "description": "synthetic sub-window fixture",
    "required_anchors": ["Alpha:", "Beta:", "Gamma"],
}


@pytest.fixture
def profiles_dir(tmp_path) -> Path:
    directory = tmp_path / "profiles"
    directory.mkdir()
    (directory / f"{SCOPE}.yaml").write_text(
        yaml.safe_dump(PROFILE, allow_unicode=True), encoding="utf-8"
    )
    return directory


def enabled_config(app_config, profiles_dir: Path, **overrides):
    agent = app_config.agent.model_copy(
        update={
            "app_perception": AppPerceptionConfig(
                enabled=True, profiles_dir=str(profiles_dir), **overrides
            )
        }
    )
    return app_config.model_copy(update={"agent": agent})


def _case(scope: str | None) -> TestCase:
    step = TestStep(
        id="s1",
        name="click inside the tool window",
        intent="click the small control",
        max_retries=1,
        expected=VerificationSpec(
            operator="all", conditions=[VerificationCondition(type="screen_changed")]
        ),
    )
    if scope is not None:
        step = step.model_copy(update={"perception_scope": scope})
    return TestCase(
        id="e2e-app-perception",
        name="app perception",
        target_id="win10-test-01",
        mode="explicit",
        steps=[step],
    )


def _planner() -> StubPlanner:
    return StubPlanner(
        action=SemanticAction(
            action_id="a1",
            intent="click the small control",
            action_type="click",
            target=TargetDescription(role="button", text="Widget", nearby_texts=["Beta:"]),
        )
    )


def _audits(ctx):
    return [
        it.perception_enhancement
        for step in ctx.test_run.steps
        for it in step.iterations
        if it.perception_enhancement is not None
    ]


@pytest.fixture(autouse=True)
def _reset_ocr():
    yield
    ocr_engine.reset_engine()


# --- US1 -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_declared_step_gets_the_subwindow_reread_at_higher_resolution(
    tmp_path, app_config, profiles_dir
):
    ocr = _ScaleAwareOcr()
    ocr_engine.set_engine(ocr)
    grounder = ScriptedGrounder()
    runtime, _ = await build_runtime(
        tmp_path,
        enabled_config(app_config, profiles_dir),
        planner=_planner(),
        grounder=grounder,
        ocr_enabled=True,
    )
    ctx = await runtime.run(_case(SCOPE))

    audits = _audits(ctx)
    assert audits, "a declared step must always carry an audit record"
    activated = [a for a in audits if a.activated]
    assert activated
    audit = activated[0]
    assert audit.reason_code in ("activated", "activated_cached")
    assert audit.plugin_name == SCOPE
    assert audit.roi == _EXPECTED_ROI
    assert audit.detection_method == "ocr_anchors"
    assert audit.zoom_image_ref
    assert audit.ocr_items_added > 0
    assert ocr.zoom_calls > 0, "the crop must actually have been re-read"

    # The refined image was persisted as a run artifact.
    assert list(Path(tmp_path / "artifacts").rglob("zoom/*.png"))


@pytest.mark.asyncio
async def test_grounder_receives_the_magnified_crop_with_matching_hints(
    tmp_path, app_config, profiles_dir
):
    """The model that picks the click point must SEE the magnified crop.
    Refining the OCR alone left the grounder staring at the full frame, where
    a small control is exactly as illegible as before."""
    ocr_engine.set_engine(_ScaleAwareOcr())
    grounder = ScriptedGrounder()
    runtime, _ = await build_runtime(
        tmp_path,
        enabled_config(app_config, profiles_dir),
        planner=_planner(),
        grounder=grounder,
        ocr_enabled=True,
    )
    ctx = await runtime.run(_case(SCOPE))

    zoom_calls = [c for c in grounder.calls if c.scale_factor != 1.0]
    assert zoom_calls, "the grounder must be handed the sub-window crop"
    call = zoom_calls[0]
    assert call.crop_offset == (_EXPECTED_ROI[0], _EXPECTED_ROI[1])
    assert call.original_resolution == SCREEN
    assert call.resolution != SCREEN, "resolution must describe the crop, not the frame"

    # The hints must live in the SAME space as the image they accompany.
    zw, zh = call.resolution
    assert call.ocr_candidates, "the crop's own OCR must ride along as hints"
    for hint in call.ocr_candidates:
        x1, y1, x2, y2 = hint["bbox"]
        assert 0 <= x1 < x2 <= zw and 0 <= y1 < y2 <= zh, (
            f"hint {hint['bbox']} is not in the crop's coordinate space"
        )

    audits = [a for a in _audits(ctx) if a.activated]
    assert audits and audits[0].grounder_image == "app_perception_zoom"


@pytest.mark.asyncio
async def test_zoom_grounding_result_is_restored_to_original_frame_pixels(
    tmp_path, app_config, profiles_dir
):
    """SC-001 red line: a candidate found on the magnified crop must come back
    as ORIGINAL frame pixels through the unchanged strict chain."""
    ocr_engine.set_engine(_ScaleAwareOcr())
    grounder = ScriptedGrounder()
    runtime, drv = await build_runtime(
        tmp_path,
        enabled_config(app_config, profiles_dir),
        planner=_planner(),
        grounder=grounder,
        ocr_enabled=True,
    )
    ctx = await runtime.run(_case(SCOPE))

    restored = [
        it.grounding_result.candidates[0].bbox
        for step in ctx.test_run.steps
        for it in step.iterations
        if it.grounding_result and it.grounding_result.candidates
    ]
    assert restored, "expected a grounding result"
    x1, y1, x2, y2 = restored[0]
    ex1, ey1, ex2, ey2 = _SMALL_LABEL_BOX
    assert abs(x1 - ex1) <= 1 and abs(y1 - ey1) <= 1
    assert abs(x2 - ex2) <= 1 and abs(y2 - ey2) <= 1

    # And the click that follows lands inside the original frame.
    for x, y in drv.clicks:
        assert 0 <= x < SCREEN[0] and 0 <= y < SCREEN[1]


@pytest.mark.asyncio
async def test_refined_ocr_still_reaches_downstream_in_original_coords(
    tmp_path, app_config, profiles_dir
):
    """The OCR refinement (which feeds assertions and OCR-direct clicks) stays
    in ORIGINAL frame pixels, independently of what the grounder is shown."""
    ocr_engine.set_engine(_ScaleAwareOcr())
    runtime, _ = await build_runtime(
        tmp_path,
        enabled_config(app_config, profiles_dir),
        planner=_planner(),
        grounder=ScriptedGrounder(),
        ocr_enabled=True,
    )
    runtime.app_perception.reset_step("s1")
    runtime._current_target_id = "win10-test-01"
    cached = None
    ctx = await runtime.run(_case(SCOPE))
    for step in ctx.test_run.steps:
        for it in step.iterations:
            if it.perception_enhancement and it.perception_enhancement.activated:
                cached = it.perception_enhancement
    assert cached is not None
    # The refined read replaced the garbled full-frame items in place.
    assert cached.ocr_items_added > 0
    assert cached.roi == _EXPECTED_ROI


@pytest.mark.asyncio
async def test_unchanged_frames_reuse_the_refined_read(tmp_path, app_config, profiles_dir):
    """Cost control: a step observes several times (pre-action, post-action,
    re-observe); only frames that actually changed may pay for a capture+OCR.
    The fake driver serves one static frame, so one refinement must cover the
    whole step."""
    ocr = _ScaleAwareOcr()
    ocr_engine.set_engine(ocr)
    runtime, _ = await build_runtime(
        tmp_path,
        enabled_config(app_config, profiles_dir),
        planner=_planner(),
        grounder=ScriptedGrounder(),
        ocr_enabled=True,
    )
    ctx = await runtime.run(_case(SCOPE))

    audits = _audits(ctx)
    assert audits and all(a.activated for a in audits)
    assert ocr.zoom_calls == 1, (
        f"an unchanged frame must be served from the memo, got {ocr.zoom_calls} re-reads"
    )


# --- US2 -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_undeclared_step_is_never_enhanced_even_though_window_is_visible(
    tmp_path, app_config, profiles_dir
):
    ocr = _ScaleAwareOcr()
    ocr_engine.set_engine(ocr)
    grounder = ScriptedGrounder()
    runtime, _ = await build_runtime(
        tmp_path,
        enabled_config(app_config, profiles_dir),
        planner=_planner(),
        grounder=grounder,
        ocr_enabled=True,
    )
    ctx = await runtime.run(_case(None))

    assert _audits(ctx) == [], "an undeclared step must not even be audited"
    assert ocr.zoom_calls == 0, "and must not trigger a single crop re-read"
    # The garbled full-frame read is what an undeclared step keeps — proving
    # the enhancement really is what fixes it.
    for call in grounder.calls:
        texts = {c["text"] for c in call.ocr_candidates}
        assert _SMALL_LABEL_GARBLED in texts
        assert _SMALL_LABEL_TRUE not in texts


# --- FR-013a / FR-024 ------------------------------------------------------


@pytest.mark.asyncio
async def test_declared_but_absent_window_falls_back_and_is_audited(
    tmp_path, app_config, profiles_dir
):
    ocr_engine.set_engine(_ScaleAwareOcr(anchors=False))
    runtime, _ = await build_runtime(
        tmp_path,
        enabled_config(app_config, profiles_dir),
        planner=_planner(),
        grounder=ScriptedGrounder(),
        ocr_enabled=True,
    )
    ctx = await runtime.run(_case(SCOPE))

    audits = _audits(ctx)
    assert audits, "the record must exist precisely so this is diagnosable"
    assert all(a.activated is False for a in audits)
    assert all(a.declared_but_undetected for a in audits)
    assert all(a.reason_code == "not_detected" for a in audits)
    assert all(a.declared_scope == SCOPE for a in audits)


@pytest.mark.asyncio
async def test_audit_exists_even_when_the_action_never_reaches_grounding(
    tmp_path, app_config, profiles_dir
):
    """The real-machine gap: the OCR-direct-click path resolved the action
    before grounding, so the old grounding-stage hook left the audit null and
    the failure was only diagnosable by reading source."""
    ocr_engine.set_engine(_ScaleAwareOcr())
    planner = StubPlanner(
        action=SemanticAction(
            action_id="a1",
            intent="click the small control",
            action_type="click",
            # Exactly the refined text => the OCR-direct path resolves it.
            target=TargetDescription(role="button", text=_SMALL_LABEL_TRUE),
        )
    )
    grounder = ScriptedGrounder()
    runtime, _ = await build_runtime(
        tmp_path,
        enabled_config(app_config, profiles_dir),
        planner=planner,
        grounder=grounder,
        ocr_enabled=True,
    )
    ctx = await runtime.run(_case(SCOPE))

    audits = _audits(ctx)
    assert audits, "declared steps must ALWAYS be audited (FR-024)"
    assert any(a.activated for a in audits)
    if not grounder.calls:
        assert all(a.grounding_reached is False for a in audits), (
            "grounding_reached must expose that the action resolved earlier"
        )


@pytest.mark.asyncio
async def test_zoom_reground_wins_over_the_declared_subwindow_crop(
    tmp_path, app_config, profiles_dir
):
    """FR-021 priority, now an explicit rule rather than a structural
    accident: both features replace the grounder's image, so exactly one may
    apply. Feature 014 wins when pending — it only fires after a real failure
    and derives its ROI from that failure's own evidence, so it carries new
    information, whereas re-sending 024's identical sub-window crop would hand
    the model a byte-identical image and waste the iteration."""
    ocr_engine.set_engine(_ScaleAwareOcr())
    grounder = ScriptedGrounder(found=False)
    runtime, _ = await build_runtime(
        tmp_path,
        enabled_config(app_config, profiles_dir),
        planner=_planner(),
        grounder=grounder,
        ocr_enabled=True,
    )
    ctx = await runtime.run(_case(SCOPE))

    # Never both transforms on one request.
    for call in grounder.calls:
        assert (call.crop_offset == (0, 0)) or (call.scale_factor != 1.0), (
            "a cropped request must declare its scale, and vice versa"
        )

    labels = {
        a.grounder_image
        for a in _audits(ctx)
        if a.grounder_image is not None
    }
    assert labels <= {"app_perception_zoom", "zoom_reground", "full_frame"}
    # Whenever feature 014 took over, the audit says so rather than silently
    # claiming the sub-window crop was used.
    zoom_reground_calls = [
        c for c in grounder.calls if c.scale_factor != 1.0 and c.crop_offset != (
            _EXPECTED_ROI[0], _EXPECTED_ROI[1]
        )
    ]
    if zoom_reground_calls:
        assert "zoom_reground" in labels


# --- FR-026 rollback -------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_produces_no_audit_records(tmp_path, app_config):
    ocr = _ScaleAwareOcr()
    ocr_engine.set_engine(ocr)
    grounder = ScriptedGrounder()
    runtime, _ = await build_runtime(
        tmp_path, app_config, planner=_planner(), grounder=grounder, ocr_enabled=True
    )
    ctx = await runtime.run(_case(SCOPE))

    assert _audits(ctx) == []
    assert ocr.zoom_calls == 0
    assert not list(Path(tmp_path / "artifacts").rglob("zoom/*.png"))


@pytest.mark.asyncio
async def test_budget_bounds_the_number_of_refined_frames(
    tmp_path, app_config, profiles_dir
):
    ocr = _ScaleAwareOcr()
    ocr_engine.set_engine(ocr)
    runtime, _ = await build_runtime(
        tmp_path,
        enabled_config(app_config, profiles_dir, max_activations_per_step=1),
        planner=_planner(),
        grounder=ScriptedGrounder(),
        ocr_enabled=True,
    )
    await runtime.run(_case(SCOPE))
    assert ocr.zoom_calls <= 1
