"""Feature 024 (FR-017/FR-018): coordinate projection + anchor constraints.

The `enforce` semantics are the point: a strong prior may reject a candidate,
a weak hint must never kill one (spec Q3 as decided).
"""

from __future__ import annotations

import pytest

from vnc_agent.domain.app_perception import AnchorConstraint, AnchorHit
from vnc_agent.models.coordinate_space import restore_original_bbox
from vnc_agent.perception.app_plugins.geometry import (
    area_ratio,
    evaluate_constraints,
    in_edge_band,
    is_inside,
    project_to_zoom_space,
    satisfies,
)

CROP = (100, 80)
SCALE = 2.5
ZOOM_RES = (1000, 1300)


def anchor(text, bbox, confidence=0.9):
    return AnchorHit(anchor_text=text, matched_text=text, bbox=bbox, confidence=confidence)


# --- projection ------------------------------------------------------------


def test_projection_round_trips_with_the_restoration_chain():
    """Projection is the inverse of the click-restoration formula, so hints
    and the image they accompany always share one coordinate space."""
    original = (200, 180, 260, 220)
    projected = project_to_zoom_space(
        original, crop_offset=CROP, scale_factor=SCALE, zoom_resolution=ZOOM_RES
    )
    assert projected is not None
    restored = restore_original_bbox(projected, scale_factor=SCALE, crop_offset=CROP)
    assert restored == original


def test_projection_rejects_boxes_outside_the_crop():
    assert project_to_zoom_space((10, 10, 20, 20), crop_offset=CROP, scale_factor=SCALE) is None


def test_projection_rejects_boxes_past_the_zoom_bounds():
    assert (
        project_to_zoom_space(
            (100, 80, 900, 800), crop_offset=CROP, scale_factor=SCALE, zoom_resolution=ZOOM_RES
        )
        is None
    )


@pytest.mark.parametrize("scale", [0.0, -1.0])
def test_projection_rejects_non_positive_scale(scale):
    assert project_to_zoom_space((200, 180, 260, 220), crop_offset=CROP, scale_factor=scale) is None


def test_projection_rejects_degenerate_result():
    assert (
        project_to_zoom_space((200, 180, 200, 220), crop_offset=CROP, scale_factor=SCALE)
        is None
    )


# --- containment / edge band ----------------------------------------------


def test_is_inside_uses_the_box_centre():
    region = (100, 100, 200, 200)
    assert is_inside(region, (140, 140, 160, 160))
    assert not is_inside(region, (300, 300, 320, 320))


def test_edge_band_flags_boxes_hugging_the_crop_border():
    region = (0, 0, 1000, 1000)
    assert in_edge_band(region, (0, 400, 10, 460), 0.02)
    assert not in_edge_band(region, (400, 400, 460, 460), 0.02)
    assert not in_edge_band(region, (0, 400, 10, 460), 0.0)


def test_area_ratio():
    assert area_ratio((0, 0, 512, 384), (1024, 768)) == pytest.approx(0.25)
    assert area_ratio((0, 0, 10, 10), (0, 0)) == 0.0


# --- relations -------------------------------------------------------------

ANCHORS = [
    anchor("TopMost", (245, 530, 313, 546)),
    anchor("Barcode:", (10, 6, 59, 18)),
    anchor("Favorite:", (12, 56, 61, 68)),
]


def test_same_row_and_right_of():
    scan = (331, 526, 406, 549)
    same_row = AnchorConstraint(subject="Scan", relation="same_row", anchors=["TopMost"])
    right_of = AnchorConstraint(subject="Scan", relation="right_of", anchors=["TopMost"])
    assert satisfies(same_row, scan, ANCHORS)
    assert satisfies(right_of, scan, ANCHORS)


def test_same_row_rejects_a_box_in_the_table_below():
    wrong = (331, 300, 406, 320)
    assert not satisfies(
        AnchorConstraint(subject="Scan", relation="same_row", anchors=["TopMost"]), wrong, ANCHORS
    )


@pytest.mark.parametrize(
    "relation, candidate, expected",
    [
        ("left_of", (10, 530, 60, 546), True),
        ("left_of", (400, 530, 460, 546), False),
        ("above", (245, 100, 313, 120), True),
        ("below", (245, 700, 313, 720), True),
        ("below", (245, 100, 313, 120), False),
        ("same_column", (250, 100, 310, 120), True),
        ("same_column", (900, 100, 950, 120), False),
    ],
)
def test_relations(relation, candidate, expected):
    constraint = AnchorConstraint(subject="x", relation=relation, anchors=["TopMost"])
    assert satisfies(constraint, candidate, ANCHORS) is expected


def test_between_relation_uses_the_dominant_axis():
    constraint = AnchorConstraint(
        subject="input", relation="between", anchors=["Barcode:", "Favorite:"]
    )
    assert satisfies(constraint, (20, 25, 300, 45), ANCHORS) is True
    assert satisfies(constraint, (20, 200, 300, 220), ANCHORS) is False


def test_unevaluable_constraint_is_not_a_violation():
    """An anchor that is not on screen cannot condemn a candidate."""
    constraint = AnchorConstraint(subject="x", relation="same_row", anchors=["Missing"])
    assert satisfies(constraint, (0, 0, 10, 10), ANCHORS) is None


# --- enforce semantics (spec Q3) ------------------------------------------

GOOD = (331, 526, 406, 549)   # same row as TopMost, to its right
BAD = (331, 300, 406, 320)    # down in the table


def test_strong_constraint_rejects_the_violating_candidate():
    constraint = AnchorConstraint(
        subject="Scan", relation="same_row", anchors=["TopMost"], enforce=True
    )
    kept, violations = evaluate_constraints([constraint], [GOOD, BAD], ANCHORS)
    assert kept == [GOOD], "the strong prior must drop the bad candidate"
    assert len(violations) == 1
    assert violations[0].mode == "enforced"
    assert violations[0].candidate_bbox == BAD


def test_weak_constraint_never_kills_a_candidate():
    constraint = AnchorConstraint(
        subject="Scan", relation="same_row", anchors=["TopMost"], enforce=False
    )
    kept, violations = evaluate_constraints([constraint], [GOOD, BAD], ANCHORS)
    assert kept == [GOOD, BAD], "a weak hint must only record"
    assert len(violations) == 1
    assert violations[0].mode == "record_only"


def test_record_only_mode_downgrades_strong_constraints():
    constraint = AnchorConstraint(
        subject="Scan", relation="same_row", anchors=["TopMost"], enforce=True
    )
    kept, violations = evaluate_constraints(
        [constraint], [GOOD, BAD], ANCHORS, mode="record_only"
    )
    assert kept == [GOOD, BAD]
    assert violations[0].mode == "record_only"


def test_strong_constraint_may_empty_the_candidate_list():
    """A legitimate outcome: the caller falls back to the existing
    target_not_found path; no new failure type is invented."""
    constraint = AnchorConstraint(
        subject="Scan", relation="same_row", anchors=["TopMost"], enforce=True
    )
    kept, violations = evaluate_constraints([constraint], [BAD], ANCHORS)
    assert kept == []
    assert len(violations) == 1


def test_no_constraints_is_a_passthrough():
    kept, violations = evaluate_constraints([], [GOOD, BAD], ANCHORS)
    assert kept == [GOOD, BAD]
    assert violations == []


def test_unevaluable_constraints_keep_every_candidate():
    constraint = AnchorConstraint(
        subject="x", relation="same_row", anchors=["Missing"], enforce=True
    )
    kept, violations = evaluate_constraints([constraint], [GOOD, BAD], ANCHORS)
    assert kept == [GOOD, BAD]
    assert violations == []


def test_mixed_strengths_only_the_strong_one_rejects():
    strong = AnchorConstraint(
        subject="Scan", relation="same_row", anchors=["TopMost"], enforce=True
    )
    weak = AnchorConstraint(
        subject="Scan", relation="above", anchors=["TopMost"], enforce=False
    )
    kept, violations = evaluate_constraints([strong, weak], [GOOD, BAD], ANCHORS)
    assert kept == [GOOD]
    modes = {v.mode for v in violations}
    assert modes == {"enforced", "record_only"}
