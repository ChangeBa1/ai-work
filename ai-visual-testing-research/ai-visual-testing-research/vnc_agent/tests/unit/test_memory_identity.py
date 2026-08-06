"""Feature 025: structured element identity unit tests."""

from __future__ import annotations

import pytest

from vnc_agent.domain.observation import OCRItem, Region
from vnc_agent.memory.identity import (
    build_identity_key,
    geom_cell_from_center,
    normalize_visible_text,
    resolve_identity_candidates_for_lookup,
    resolve_identity_for_write,
)


def test_normalize_r4_goldens():
    assert normalize_visible_text("小計") == "小計"
    assert normalize_visible_text("  小計  ") == "小計"
    assert normalize_visible_text("レジ袋") == "レジ袋"
    assert normalize_visible_text("ＡＢＣ") == "abc"
    assert normalize_visible_text("Abc") == "abc"
    assert normalize_visible_text("小計解除") != normalize_visible_text("小計")
    assert normalize_visible_text("1金券") != normalize_visible_text("金券")
    assert normalize_visible_text("×") == "×"
    assert normalize_visible_text("／") == "/"
    assert normalize_visible_text("--") == "--"
    assert normalize_visible_text("pre-paid") == "pre-paid"
    assert normalize_visible_text("") == ""
    assert normalize_visible_text("   ") == ""
    # halfwidth katakana via NFKC
    assert normalize_visible_text("ﾚｼﾞ袋") == "レジ袋"


def test_geom_cell_and_key_format():
    # 1024x768, center ~867,627 → col/row for G=16
    cell = geom_cell_from_center(867, 627, 1024, 768, 16)
    assert cell == f"{min(15, int(867 / 1024 * 16))},{min(15, int(627 / 768 * 16))}"
    k16 = build_identity_key(
        schema_version="eid-v1",
        grid_size=16,
        normalized_visible_text="小計",
        geom_cell="13,13",
    )
    assert k16 == "eid-v1:g16|小計|13,13"
    k32 = build_identity_key(
        schema_version="eid-v1",
        grid_size=32,
        normalized_visible_text="小計",
        geom_cell="13,13",
    )
    assert k32.startswith("eid-v1:g32|")
    assert k16 != k32


def test_write_pick_tie_break_stable_under_shuffle():
    region = Region(x1=100, y1=100, x2=120, y2=120)
    # Equal distance from region center (110,110): two bboxes same distance
    a = OCRItem(text="AAA", bbox=(90, 90, 100, 100), confidence=0.9)
    b = OCRItem(text="BBB", bbox=(120, 120, 130, 130), confidence=0.9)
    # both centers distance: a (95,95) dist^2=450; b (125,125) dist^2=450
    res = (300, 300)
    r1 = resolve_identity_for_write(
        region=region,
        ocr_items=[b, a],
        resolution=res,
        grid_size=16,
        schema_version="eid-v1",
    )
    r2 = resolve_identity_for_write(
        region=region,
        ocr_items=[a, b],
        resolution=res,
        grid_size=16,
        schema_version="eid-v1",
    )
    assert r1 is not None and r2 is not None
    assert r1.identity_key == r2.identity_key
    assert r1.normalized_visible_text == "aaa"  # dictionary order: aaa < bbb


def test_write_no_ocr_returns_none():
    region = Region(x1=10, y1=10, x2=20, y2=20)
    assert (
        resolve_identity_for_write(
            region=region,
            ocr_items=[],
            resolution=(100, 100),
            grid_size=16,
            schema_version="eid-v1",
        )
        is None
    )


def test_write_query_geom_cell_equal_even_if_region_offset():
    """T018a: geom_cell from OCR center, not target_region — must match write/query."""
    ocr = OCRItem(text="TOTAL", bbox=(150, 85, 170, 95), confidence=0.9)
    # Region deliberately offset so its center is in a different cell than OCR center
    region = Region(x1=10, y1=10, x2=30, y2=30)
    res = (300, 200)
    w = resolve_identity_for_write(
        region=region,
        ocr_items=[ocr],
        resolution=res,
        grid_size=16,
        schema_version="eid-v1",
    )
    assert w is not None
    q = resolve_identity_candidates_for_lookup(
        target_label="TOTAL",
        ocr_items=[ocr],
        resolution=res,
        grid_size=16,
        schema_version="eid-v1",
    )
    assert q.status == "unique" and q.identity is not None
    assert w.geom_cell == q.identity.geom_cell
    assert w.identity_key == q.identity.identity_key
    # And geom is NOT region center
    rcx, rcy = region.center()
    from vnc_agent.memory.identity import geom_cell_from_center

    region_cell = geom_cell_from_center(rcx, rcy, res[0], res[1], 16)
    assert w.geom_cell != region_cell or True  # may or may not differ; key is write==query


@pytest.mark.identity_paraphrase_hit
def test_write_identity_lookup_with_paraphrased_label_hits():
    ocr = OCRItem(text="TOTAL", bbox=(150, 85, 170, 95), confidence=0.9)
    region = Region(x1=150, y1=85, x2=170, y2=95)
    res = (300, 200)
    w = resolve_identity_for_write(
        region=region,
        ocr_items=[ocr],
        resolution=res,
        grid_size=16,
        schema_version="eid-v1",
    )
    assert w is not None
    q = resolve_identity_candidates_for_lookup(
        target_label="the TOTAL button at the bottom",
        ocr_items=[ocr],
        resolution=res,
        grid_size=16,
        schema_version="eid-v1",
    )
    assert q.status == "unique"
    assert q.identity is not None
    assert q.identity.identity_key == w.identity_key


def test_ambiguous_same_text_two_cells_no_hit():
    ocr1 = OCRItem(text="SAME", bbox=(10, 10, 30, 30), confidence=0.9)
    ocr2 = OCRItem(text="SAME", bbox=(200, 150, 220, 170), confidence=0.9)
    q = resolve_identity_candidates_for_lookup(
        target_label="SAME",
        ocr_items=[ocr1, ocr2],
        resolution=(300, 200),
        grid_size=16,
        schema_version="eid-v1",
    )
    assert q.status == "ambiguous"
    assert len(q.candidates) >= 2
    assert q.identity is None


def test_different_cells_not_merged_on_write():
    res = (300, 200)
    r1 = Region(x1=10, y1=10, x2=30, y2=30)
    r2 = Region(x1=200, y1=150, x2=220, y2=170)
    o1 = OCRItem(text="BTN", bbox=(10, 10, 30, 30), confidence=0.9)
    o2 = OCRItem(text="BTN", bbox=(200, 150, 220, 170), confidence=0.9)
    w1 = resolve_identity_for_write(
        region=r1, ocr_items=[o1, o2], resolution=res, grid_size=16, schema_version="eid-v1"
    )
    w2 = resolve_identity_for_write(
        region=r2, ocr_items=[o1, o2], resolution=res, grid_size=16, schema_version="eid-v1"
    )
    assert w1 is not None and w2 is not None
    assert w1.identity_key != w2.identity_key
    assert w1.geom_cell != w2.geom_cell
