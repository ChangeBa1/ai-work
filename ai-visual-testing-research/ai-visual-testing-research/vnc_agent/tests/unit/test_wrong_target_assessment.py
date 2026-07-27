"""Feature 022 (wrong-click-detection): pure wrong-target assessment
(perception/action_effect.py::assess_wrong_target) — FR-B01/FR-B02.

All tests are pure-function tests: no VNC, no models, no files.
"""

from __future__ import annotations

import math

from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.observation import Region
from vnc_agent.perception.action_effect import (
    assess_wrong_target,
    direction_8,
    expand_target_region,
    region_iou,
)

RES = (1000, 800)
# w=100 h=50, center (450, 325); x0.5 neighborhood = (350, 275, 550, 375)
TARGET = Region(x1=400, y1=300, x2=500, y2=350)


def _effect(
    status: str = "expected_effect",
    blobs: list[Region] | None = None,
    ratio: float = 0.01,
) -> ActionEffect:
    return ActionEffect(
        status=status,  # type: ignore[arg-type]
        evidence=ActionEffectEvidence(
            global_diff_ratio=ratio, local_blobs=list(blobs or [])
        ),
        reason="test",
    )


def _assess(effect: ActionEffect, **kw):
    kw.setdefault("target_region", TARGET)
    kw.setdefault("resolution", RES)
    return assess_wrong_target(effect, **kw)


# ---------------------------------------------------------------- suspected


def test_far_blob_expected_effect_small_global_ratio_is_suspected():
    blob = Region(x1=700, y1=600, x2=740, y2=630)  # center (720, 615)
    out = _assess(_effect(blobs=[blob]), click_point=(450, 325))
    assert out.suspected is True
    assert out.blob_count == 1
    assert out.blobs_intersecting_neighborhood == 0
    assert out.max_blob_target_iou == 0.0
    assert out.nearest_blob_bbox == (700, 600, 740, 630)
    assert out.nearest_blob_offset == (270, 290)
    assert out.nearest_blob_distance_px == math.hypot(270, 290)
    assert out.nearest_blob_direction == "down_right"
    assert out.click_point == (450, 325)
    assert out.target_region == (400, 300, 500, 350)


def test_blob_inside_neighborhood_not_suspected():
    blob = Region(x1=360, y1=280, x2=380, y2=290)  # inside expanded region
    out = _assess(_effect(blobs=[blob]))
    assert out.suspected is False
    assert out.blobs_intersecting_neighborhood == 1


def test_any_blob_inside_neighborhood_vetoes_suspicion():
    far = Region(x1=700, y1=600, x2=740, y2=630)
    near = Region(x1=410, y1=310, x2=430, y2=330)  # overlaps the target itself
    out = _assess(_effect(blobs=[far, near]))
    assert out.suspected is False
    assert out.blobs_intersecting_neighborhood == 1
    assert out.max_blob_target_iou > 0.0


def test_blob_just_outside_expanded_boundary_is_suspected():
    # Expanded neighborhood ends at x2=550 (exclusive edge): a blob starting
    # exactly at 550 does not intersect it.
    blob = Region(x1=550, y1=300, x2=570, y2=320)
    out = _assess(_effect(blobs=[blob]))
    assert out.suspected is True


def test_blob_overlapping_expansion_band_not_suspected():
    # Starts inside the expansion band (549 < 550) even though it is fully
    # outside the raw target region.
    blob = Region(x1=549, y1=300, x2=570, y2=320)
    out = _assess(_effect(blobs=[blob]))
    assert out.suspected is False
    assert out.blobs_intersecting_neighborhood == 1


def test_custom_expand_ratio_changes_verdict():
    blob = Region(x1=560, y1=310, x2=580, y2=330)
    strict = _assess(_effect(blobs=[blob]), neighborhood_expand_ratio=0.5)
    loose = _assess(_effect(blobs=[blob]), neighborhood_expand_ratio=1.0)
    assert strict.suspected is True
    assert loose.suspected is False


# ------------------------------------------------- screen-scale exemption


def test_global_ratio_at_threshold_is_exempt():
    blob = Region(x1=700, y1=600, x2=740, y2=630)
    out = _assess(_effect(blobs=[blob], ratio=0.10))
    assert out.suspected is False
    assert "exempt" in out.reason


def test_global_ratio_below_threshold_still_suspected():
    blob = Region(x1=700, y1=600, x2=740, y2=630)
    out = _assess(_effect(blobs=[blob], ratio=0.099))
    assert out.suspected is True


def test_custom_global_max_threshold_applied():
    blob = Region(x1=700, y1=600, x2=740, y2=630)
    out = _assess(_effect(blobs=[blob], ratio=0.05), global_diff_ratio_max=0.05)
    assert out.suspected is False
    assert out.global_diff_ratio_max == 0.05


# -------------------------------------------------------- non-assessable


def test_non_expected_effect_statuses_never_suspected():
    blob = Region(x1=700, y1=600, x2=740, y2=630)
    for status in ("no_effect", "unexpected_effect", "effect_uncertain"):
        out = _assess(_effect(status=status, blobs=[blob]))
        assert out.suspected is False, status
        # Nearest-blob geometry is still recorded for telemetry/023.
        assert out.nearest_blob_distance_px is not None


def test_no_target_region_not_assessable():
    out = assess_wrong_target(
        _effect(blobs=[Region(x1=1, y1=1, x2=5, y2=5)]),
        target_region=None,
        resolution=RES,
    )
    assert out.suspected is False
    assert out.target_region is None
    assert out.nearest_blob_bbox is None


def test_no_blobs_not_assessable():
    out = _assess(_effect(blobs=[]))
    assert out.suspected is False
    assert out.blob_count == 0
    assert out.nearest_blob_distance_px is None


def test_nearest_blob_is_the_closest_one():
    near = Region(x1=560, y1=330, x2=580, y2=350)  # center (570, 340)
    far = Region(x1=900, y1=700, x2=940, y2=740)
    out = _assess(_effect(blobs=[far, near]))
    assert out.suspected is True
    assert out.nearest_blob_bbox == (560, 330, 580, 350)
    assert out.nearest_blob_offset == (120, 15)
    assert out.nearest_blob_direction == "right"


# ------------------------------------------------------- geometry helpers


def test_expand_target_region_clamps_to_resolution():
    r = Region(x1=10, y1=10, x2=110, y2=60)
    expanded = expand_target_region(r, expand_ratio=0.5, resolution=(120, 40))
    assert expanded.x1 == 0  # 10 - 50 clamped
    assert expanded.y1 == 0
    assert expanded.x2 == 120  # 160 clamped to width
    assert expanded.y2 == 40  # clamped to height (< y2 of the raw box is fine)


def test_expand_target_region_zero_ratio_is_identity():
    r = Region(x1=10, y1=10, x2=110, y2=60)
    assert expand_target_region(r, expand_ratio=0.0, resolution=RES).as_tuple() == (
        10,
        10,
        110,
        60,
    )


def test_region_iou_identity_and_disjoint():
    a = Region(x1=0, y1=0, x2=10, y2=10)
    assert region_iou(a, a) == 1.0
    assert region_iou(a, Region(x1=20, y1=20, x2=30, y2=30)) == 0.0
    # Half overlap: inter 50, union 150.
    b = Region(x1=5, y1=0, x2=15, y2=10)
    assert abs(region_iou(a, b) - (50 / 150)) < 1e-9


def test_direction_8_sectors():
    assert direction_8(0, 0) == "center"
    assert direction_8(10, 0) == "right"
    assert direction_8(0, -10) == "up"
    assert direction_8(-10, 0) == "left"
    assert direction_8(0, 10) == "down"
    assert direction_8(10, -10) == "up_right"
    assert direction_8(-10, -10) == "up_left"
    assert direction_8(-10, 10) == "down_left"
    assert direction_8(10, 10) == "down_right"
