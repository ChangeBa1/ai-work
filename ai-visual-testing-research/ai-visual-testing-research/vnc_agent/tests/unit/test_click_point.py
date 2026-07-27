"""Feature 013 (safe-click-point): pure-function unit tests (T007/T010/T013).

Covers: center hit inside the safe zone, edge inset, degenerate tiny bbox,
sibling push-away, minimal-overlap fallback, screen clamp, determinism.
"""

import pytest

from vnc_agent.planning.click_point import SafeClickPoint, safe_click_point

BBOX = (100, 80, 200, 120)  # w=100, h=40, center (150, 100)


def _safe_zone(bbox, ratio):
    x1, y1, x2, y2 = bbox
    ix, iy = round((x2 - x1) * ratio), round((y2 - y1) * ratio)
    return (x1 + ix, y1 + iy, x2 - ix, y2 - iy)


def _inside(pt, rect):
    return rect[0] <= pt[0] <= rect[2] and rect[1] <= pt[1] <= rect[3]


# --- US1: edge inset / center / degenerate ---


def test_no_siblings_returns_geometric_center():
    pt = safe_click_point(BBOX)
    assert pt == SafeClickPoint(150, 100, False)


@pytest.mark.parametrize("ratio", [0.0, 0.15, 0.3])
def test_point_falls_in_inset_safe_zone(ratio):
    pt = safe_click_point(BBOX, edge_inset_ratio=ratio)
    assert _inside((pt.x, pt.y), _safe_zone(BBOX, ratio))


def test_point_always_inside_original_bbox_fr012():
    boxes = [(0, 0, 3, 3), (10, 10, 11, 11), (5, 5, 500, 8), (0, 0, 1920, 1080)]
    for bbox in boxes:
        for ratio in (0.0, 0.15, 0.45):
            pt = safe_click_point(bbox, edge_inset_ratio=ratio)
            assert _inside((pt.x, pt.y), bbox), (bbox, ratio, pt)


def test_tiny_bbox_degrades_to_center():
    pt = safe_click_point((10, 10, 12, 12))
    assert pt == SafeClickPoint(11, 11, False)


def test_zero_size_bbox_degrades_to_center():
    pt = safe_click_point((50, 50, 50, 50))
    assert pt == SafeClickPoint(50, 50, False)


def test_empty_safe_zone_degrades_to_center_axis():
    # ratio > 0.5 is rejected at config level but the pure function stays
    # robust: an empty per-axis zone degrades to the center coordinate.
    pt = safe_click_point(BBOX, edge_inset_ratio=0.6)
    assert (pt.x, pt.y) == (150, 100)


def test_thin_strip_single_axis_degradation():
    # h=1 -> y inset rounds to 0, x still inset; both stay inside the bbox.
    bbox = (0, 10, 100, 11)
    pt = safe_click_point(bbox, edge_inset_ratio=0.15)
    zone = _safe_zone(bbox, 0.15)
    assert zone[0] <= pt.x <= zone[2]
    assert 10 <= pt.y <= 11


# --- US2: sibling overlap avoidance ---


def test_sibling_covering_center_pushes_point_out():
    sibling = (140, 70, 260, 130)  # covers the center (150, 100)
    pt = safe_click_point(BBOX, siblings=[sibling])
    assert not _inside((pt.x, pt.y), sibling)
    assert _inside((pt.x, pt.y), _safe_zone(BBOX, 0.15))
    assert pt.residual_overlap is False
    # Deterministic expectation: closest zero-overlap grid point to center.
    assert pt == SafeClickPoint(133, 100, False)


def test_non_covering_sibling_keeps_center():
    # Sibling intersects the bbox but not the center: center stays optimal.
    pt = safe_click_point(BBOX, siblings=[(180, 80, 260, 120)])
    assert pt == SafeClickPoint(150, 100, False)


def test_far_sibling_behaves_like_no_siblings():
    assert safe_click_point(BBOX, siblings=[(500, 500, 600, 600)]) == safe_click_point(
        BBOX
    )


def test_degenerate_sibling_is_ignored():
    assert safe_click_point(BBOX, siblings=[(150, 90, 150, 110)]) == safe_click_point(
        BBOX
    )


def test_full_cover_returns_minimal_overlap_with_flag():
    pt = safe_click_point(BBOX, siblings=[BBOX])  # sibling identical to bbox
    assert pt.residual_overlap is True
    assert _inside((pt.x, pt.y), _safe_zone(BBOX, 0.15))


def test_two_siblings_prefers_single_overlap_free_region():
    # Left and right thirds covered; only a middle band is free.
    left = (100, 80, 140, 120)
    right = (160, 80, 200, 120)
    pt = safe_click_point(BBOX, siblings=[left, right])
    assert not _inside((pt.x, pt.y), left) and not _inside((pt.x, pt.y), right)
    assert pt.residual_overlap is False


# --- US3: clamp + determinism ---


def test_clamp_to_screen_resolution():
    pt = safe_click_point((790, 590, 810, 610), screen_resolution=(800, 600))
    assert 0 <= pt.x <= 799 and 0 <= pt.y <= 599


def test_no_resolution_means_no_clamp():
    pt = safe_click_point((790, 590, 810, 610))
    assert (pt.x, pt.y) == (800, 600)


def test_residual_overlap_judged_before_clamp():
    bbox = (790, 590, 810, 610)
    # Sibling fully covers the bbox: residual stays True even after the clamp
    # moves the point (metadata reflects the sibling geometry, not the clamp).
    pt = safe_click_point(bbox, siblings=[bbox], screen_resolution=(800, 600))
    assert pt.residual_overlap is True
    assert pt.x <= 799 and pt.y <= 599


def test_determinism_same_input_same_output():
    kwargs = dict(
        siblings=[(140, 70, 260, 130), (100, 80, 140, 120)],
        screen_resolution=(800, 600),
        edge_inset_ratio=0.15,
    )
    assert safe_click_point(BBOX, **kwargs) == safe_click_point(BBOX, **kwargs)
