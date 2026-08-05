"""Feature 024 (FR-005c/d/e): source-derived relative geometry.

Covers the anchor-aware mapping (SC-010) and the red line that mapped
rectangles are hints/constraints only, never click coordinates (SC-011).
"""

from __future__ import annotations

import inspect

import pytest

from vnc_agent.perception.app_plugins.source_geometry import (
    ControlGeometry,
    SourceGeometry,
    derive_anchor_constraints,
    map_control_rect,
    predict_control_rect,
    solve_transform,
)

# A miniature form: 100x200 client area with one control per anchor style.
DESIGN = (100, 200)
TOP_LEFT = ControlGeometry(name="tl", text="TL", rect=(10, 20, 30, 40), anchors=["top", "left"])
BOTTOM_RIGHT = ControlGeometry(
    name="br", text="BR", rect=(70, 160, 90, 180), anchors=["bottom", "right"]
)
STRETCH = ControlGeometry(
    name="st", text="ST", rect=(10, 20, 90, 180), anchors=["top", "bottom", "left", "right"]
)
FLOAT = ControlGeometry(name="fl", text="FL", rect=(40, 90, 60, 110), anchors=[])

ALL_CONTROLS = [TOP_LEFT, BOTTOM_RIGHT, STRETCH, FLOAT]


@pytest.mark.parametrize("control", ALL_CONTROLS, ids=lambda c: c.name)
def test_identity_mapping_when_region_matches_design(control):
    """s == 1, no residual: the design rect lands verbatim at the origin."""
    region = (0, 0, 100, 200)
    assert map_control_rect(control, DESIGN, region) == control.rect


@pytest.mark.parametrize("control", ALL_CONTROLS, ids=lambda c: c.name)
@pytest.mark.parametrize("scale", [1.25, 2.0, 0.5])
def test_uniform_scale_collapses_all_anchor_styles(control, scale):
    """Under pure DPI scaling every anchor rule must agree with plain
    proportional scaling — the property that makes the model trustworthy."""
    ox, oy = 37, 11
    region = (ox, oy, ox + int(100 * scale), oy + int(200 * scale))
    mapped = map_control_rect(control, DESIGN, region)
    assert mapped is not None
    x1, y1, x2, y2 = control.rect
    expected = (
        round(ox + x1 * scale),
        round(oy + y1 * scale),
        round(ox + x2 * scale),
        round(oy + y2 * scale),
    )
    assert mapped == pytest.approx(expected, abs=1)


# NOTE on the resize cases below: the mapping takes s = min(AW/W, AH/H) so a
# *uniform* enlargement reads as DPI scaling, while widening one axis only
# gives s == 1 and pushes the whole difference into the residual — which is
# exactly the "user resized the window" case the anchors are meant to handle.
# The regions below are chosen so min(sx, sy) == 1.


def test_bottom_right_anchor_stays_pinned_when_window_widens():
    """The load-bearing case: a Bottom|Right control keeps its distance to the
    right/bottom edge instead of drifting with the top-left origin."""
    region = (0, 0, 300, 200)  # widened by 200, height unchanged => s == 1
    mapped = map_control_rect(BOTTOM_RIGHT, DESIGN, region)
    assert mapped is not None
    x1, y1, x2, y2 = mapped
    assert 300 - x2 == 100 - 90, "right gap must be preserved"
    assert (x2 - x1, y2 - y1) == (20, 20), "anchored size must not stretch"
    assert x1 > 200, "must follow the right edge, not stay near the origin"


def test_bottom_anchor_stays_pinned_when_window_heightens():
    region = (0, 0, 100, 500)  # heightened only => s == 1
    mapped = map_control_rect(BOTTOM_RIGHT, DESIGN, region)
    assert mapped is not None
    _, y1, _, y2 = mapped
    assert 500 - y2 == 200 - 180, "bottom gap must be preserved"
    assert y1 > 400


def test_top_left_anchor_stays_pinned_when_window_widens():
    assert map_control_rect(TOP_LEFT, DESIGN, (0, 0, 300, 200)) == (10, 20, 30, 40)


def test_both_edges_anchored_control_stretches():
    mapped = map_control_rect(STRETCH, DESIGN, (0, 0, 300, 200))
    assert mapped == (10, 20, 290, 180)


def test_unanchored_control_floats_with_half_the_delta():
    mapped = map_control_rect(FLOAT, DESIGN, (0, 0, 300, 200))
    assert mapped is not None
    x1, y1, x2, y2 = mapped
    assert (x1, y1) == (40 + 100, 90), "half of the 200px residual on x, none on y"
    assert (x2 - x1, y2 - y1) == (20, 20)


def test_anchor_styles_diverge_once_the_window_is_resized():
    """Sanity: the four styles must NOT agree under a non-uniform resize —
    otherwise the anchor semantics are not doing anything."""
    region = (0, 0, 300, 200)
    mapped = {c.name: map_control_rect(c, DESIGN, region) for c in ALL_CONTROLS}
    xs = {name: rect[0] for name, rect in mapped.items() if rect}
    assert len({xs["tl"], xs["br"], xs["fl"]}) == 3


@pytest.mark.parametrize(
    "region",
    [(0, 0, 0, 200), (0, 0, 100, 0), (50, 50, 40, 40)],
    ids=["degenerate-w", "degenerate-h", "inverted"],
)
def test_degenerate_region_returns_none(region):
    assert map_control_rect(TOP_LEFT, DESIGN, region) is None


def test_zero_design_size_returns_none():
    assert map_control_rect(TOP_LEFT, (0, 200), (0, 0, 100, 200)) is None


def test_result_outside_region_is_rejected_not_clamped():
    """A control whose design rect escapes the client area maps outside the
    measured bounds; it is dropped rather than clamped into range."""
    rogue = ControlGeometry(
        name="x", text="X", rect=(90, 190, 150, 260), anchors=["top", "left"]
    )
    assert map_control_rect(rogue, DESIGN, (0, 0, 100, 200)) is None


def test_derive_anchor_constraints_emits_weak_same_row_relations():
    geometry = SourceGeometry(
        client_size=DESIGN,
        controls=[
            ControlGeometry(name="a", text="A", rect=(0, 100, 20, 120)),
            ControlGeometry(name="b", text="B", rect=(50, 100, 70, 120)),
        ],
    )
    derived = derive_anchor_constraints(geometry)
    assert derived, "controls sharing a row should produce a relation"
    # Derived relations are always WEAK: promoting one to a hard reject stays
    # a deliberate human decision in the profile file.
    assert all(c.enforce is False for c in derived)
    assert derived[0].relation in ("left_of", "right_of", "same_row")


def test_controls_reject_degenerate_rect():
    with pytest.raises(ValueError):
        ControlGeometry(name="bad", rect=(10, 10, 10, 20))


def test_client_size_must_be_positive():
    with pytest.raises(ValueError):
        SourceGeometry(client_size=(0, 100))


# --- SC-011 red line -------------------------------------------------------


def test_source_geometry_never_reaches_click_coordinates():
    """Source geometry is a PRIOR, not a position.

    Guard against a future refactor quietly wiring mapped rectangles into the
    click path: the only consumer of `map_control_rect` in production code is
    the hint builder, whose output goes to the grounder's hint channel.
    """
    from vnc_agent.perception.app_plugins import coordinator as coord_mod

    module_level = [
        name
        for name, obj in vars(coord_mod).items()
        if inspect.isfunction(obj)
        and obj.__module__ == coord_mod.__name__
        and "map_control_rect" in inspect.getsource(obj)
    ]
    assert module_level == [], f"unexpected module-level use: {module_level}"

    # Exactly one method may call it, and it must be the hint builder.
    calling_methods = [
        name
        for name, obj in vars(coord_mod.AppPerceptionCoordinator).items()
        if inspect.isfunction(obj) and "map_control_rect" in inspect.getsource(obj)
    ]
    assert calling_methods == ["source_geometry_hints"], calling_methods


def test_runtime_feeds_source_hints_only_into_the_hint_channel():
    """In the runtime the mapped rects may reach exactly one place: the
    grounder request's candidate hint channel. Never an executable action."""
    from vnc_agent.runtime import agent_runtime as rt_mod

    lines = [
        line.strip()
        for line in inspect.getsource(rt_mod).splitlines()
        if "source_hints" in line and not line.strip().startswith("#")
    ]
    assert lines, "expected the runtime to use source_hints"
    allowed = (
        "source_hints = (",                    # building the hint list
        "self.app_perception.cached_hints(",
        "else []",
        ")",
        "+ source_hints",                      # appended to template_candidates
        "template_candidates=app_zoom.source_hints,",  # crop-space hints
    )
    for line in lines:
        assert line.startswith(allowed) or line == "source_hints = []", (
            f"source geometry leaked outside the hint channel: {line!r}"
        )
    joined = "\n".join(lines)
    assert "coordinates=" not in joined and "ExecutableAction" not in joined, (
        "source geometry must never feed an executable action"
    )


# --- runtime-measured design->screen transform ----------------------------
#
# The reference numbers below come from a real 1024x768 run: four anchors were
# measured by OCR and the fit recovered scale ~1.0 with an offset equal to the
# window chrome, with every residual under 1.5px.

_REAL_GEOMETRY = SourceGeometry(
    client_size=(423, 581),
    controls=[
        ControlGeometry(
            name="lblTop", text="Top:", rect=(10, 6, 59, 18), anchors=["top", "left"]
        ),
        ControlGeometry(
            name="lblMid", text="Mid:", rect=(12, 56, 61, 68), anchors=["top", "left"]
        ),
        ControlGeometry(
            name="chkOpt", text="Opt", rect=(245, 530, 313, 546), anchors=["top", "left"]
        ),
        ControlGeometry(
            name="btnGo", text="Go", rect=(331, 526, 406, 549), anchors=["bottom", "right"]
        ),
        # The control that matters: no text at all, so only geometry finds it.
        ControlGeometry(name="txtInput", rect=(11, 25, 367, 44), anchors=["top", "left"]),
    ],
)
_REAL_MEASURED = {
    "Top:": (20, 36, 64, 49),
    "Mid:": (22, 87, 66, 100),
    "Opt": (250, 562, 319, 577),
    "Go": (339, 560, 414, 575),
}
_REAL_WINDOW = (7, 31, 434, 612)


def test_transform_recovers_scale_and_chrome_offset():
    t = solve_transform(_REAL_GEOMETRY, _REAL_MEASURED)
    assert t is not None
    assert t.scale_x == pytest.approx(1.0, abs=0.01)
    assert t.scale_y == pytest.approx(1.0, abs=0.01)
    # The offset is the window border + title bar, not a fitted fudge factor.
    assert t.offset_x == pytest.approx(7.3, abs=1.0)
    assert t.offset_y == pytest.approx(31.0, abs=1.0)
    assert t.anchor_count == 4
    assert t.max_residual_px < 2.0


def test_predicts_a_textless_control_no_other_path_can_find():
    t = solve_transform(_REAL_GEOMETRY, _REAL_MEASURED)
    rect = predict_control_rect(_REAL_GEOMETRY, "txtInput", t, _REAL_WINDOW)
    assert rect is not None
    cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
    assert (cx, cy) == (196, 65)
    # The input box occupies y 57..73 on screen; the prediction is centred.
    assert 57 <= cy <= 73


def test_predicts_a_labelled_control_within_a_pixel_or_two_of_its_ocr_box():
    t = solve_transform(_REAL_GEOMETRY, _REAL_MEASURED)
    rect = predict_control_rect(_REAL_GEOMETRY, "btnGo", t, _REAL_WINDOW)
    assert rect is not None
    cx, cy = (rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2
    mx1, my1, mx2, my2 = _REAL_MEASURED["Go"]
    assert abs(cx - (mx1 + mx2) // 2) <= 2
    assert abs(cy - (my1 + my2) // 2) <= 2


# --- safety gates: every one refuses rather than guesses -------------------


def test_two_anchors_are_refused():
    """Two points fit exactly, leaving a zero residual that proves nothing."""
    two = {k: _REAL_MEASURED[k] for k in ("Top:", "Mid:")}
    assert solve_transform(_REAL_GEOMETRY, two) is None


def test_resized_window_is_refused_via_the_residual_gate():
    """THE anchor-semantics case: a resize moves Bottom|Right anchored
    controls relative to Top|Left ones, so no single transform fits both.
    The residual gate is what catches it — silence here would mean a
    confidently wrong click."""
    resized = dict(_REAL_MEASURED)
    resized["Go"] = (439, 560, 514, 575)  # window widened by 100px
    assert solve_transform(_REAL_GEOMETRY, resized) is None


def test_residual_threshold_is_configurable():
    resized = dict(_REAL_MEASURED)
    resized["Go"] = (349, 560, 424, 575)  # 10px off
    assert solve_transform(_REAL_GEOMETRY, resized, max_residual_px=2.0) is None
    assert solve_transform(_REAL_GEOMETRY, resized, max_residual_px=40.0) is not None


def test_degenerate_scale_is_refused():
    shrunk = {
        text: (round(x1 * 0.1), round(y1 * 0.1), round(x2 * 0.1) + 1, round(y2 * 0.1) + 1)
        for text, (x1, y1, x2, y2) in _REAL_MEASURED.items()
    }
    assert solve_transform(_REAL_GEOMETRY, shrunk, min_scale=0.5) is None


def test_anchors_crowded_in_one_corner_are_refused():
    """A fit validated only near the origin says nothing about the far
    corner, so it must not be extrapolated there."""
    corner = SourceGeometry(
        client_size=(423, 581),
        controls=[
            ControlGeometry(name="a", text="A", rect=(10, 6, 20, 16)),
            ControlGeometry(name="b", text="B", rect=(30, 8, 40, 18)),
            ControlGeometry(name="c", text="C", rect=(20, 20, 30, 30)),
            ControlGeometry(name="far", rect=(400, 560, 420, 575)),
        ],
    )
    measured = {"A": (17, 37, 27, 47), "B": (37, 39, 47, 49), "C": (27, 51, 37, 61)}
    assert solve_transform(corner, measured) is None


def test_prediction_outside_the_detected_window_is_refused_not_clamped():
    t = solve_transform(_REAL_GEOMETRY, _REAL_MEASURED)
    tiny_window = (7, 31, 100, 100)
    assert predict_control_rect(_REAL_GEOMETRY, "btnGo", t, tiny_window) is None


def test_unknown_control_name_is_refused():
    t = solve_transform(_REAL_GEOMETRY, _REAL_MEASURED)
    assert predict_control_rect(_REAL_GEOMETRY, "nope", t, _REAL_WINDOW) is None


def test_transform_follows_the_window_when_it_moves():
    """The whole point of solving at runtime: move the window and the fit
    tracks it, with no change to the profile."""
    shifted = {
        text: (x1 + 120, y1 + 45, x2 + 120, y2 + 45)
        for text, (x1, y1, x2, y2) in _REAL_MEASURED.items()
    }
    base = solve_transform(_REAL_GEOMETRY, _REAL_MEASURED)
    moved = solve_transform(_REAL_GEOMETRY, shifted)
    assert moved is not None
    assert moved.offset_x == pytest.approx(base.offset_x + 120, abs=0.5)
    assert moved.offset_y == pytest.approx(base.offset_y + 45, abs=0.5)
    assert moved.scale_x == pytest.approx(base.scale_x, abs=0.001)


def test_transform_follows_a_dpi_change():
    scaled = {
        text: (round(x1 * 1.5), round(y1 * 1.5), round(x2 * 1.5), round(y2 * 1.5))
        for text, (x1, y1, x2, y2) in _REAL_MEASURED.items()
    }
    t = solve_transform(_REAL_GEOMETRY, scaled)
    assert t is not None
    assert t.scale_x == pytest.approx(1.5, abs=0.02)
    assert t.scale_y == pytest.approx(1.5, abs=0.02)
