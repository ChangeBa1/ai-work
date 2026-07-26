"""Feature 015: pure retrieval helpers (spec FR-006/FR-007, SC-004)."""

from __future__ import annotations

import numpy as np

from vnc_agent.domain.memory import PageFingerprint, PageMemory
from vnc_agent.memory.retrieval import (
    expand_bbox,
    find_best_page,
    match_element_template,
    region_intersects_any,
)

_THRESHOLDS = dict(high=0.88, medium=0.72, low=0.55)


def _frame(width: int = 300, height: int = 200) -> np.ndarray:
    xx, yy = np.meshgrid(np.arange(width), np.arange(height))
    channel = ((xx * 3 + yy * 11) % 199).astype(np.uint8)
    return np.stack([channel, channel[::-1], 255 - channel], axis=-1).astype(np.uint8)


def _stamp(frame: np.ndarray, bbox) -> np.ndarray:
    """Stamp a distinctive deterministic pattern into bbox."""
    x1, y1, x2, y2 = bbox
    xx, yy = np.meshgrid(np.arange(x2 - x1), np.arange(y2 - y1))
    pat = ((xx * 23 + yy * 57) % 256).astype(np.uint8)
    frame[y1:y2, x1:x2] = np.stack([pat, 255 - pat, pat // 2], axis=-1)
    return frame


class TestRegionIntersect:
    def test_overlap_and_disjoint(self):
        assert region_intersects_any((10, 10, 20, 20), [[15, 15, 30, 30]])
        assert not region_intersects_any((10, 10, 20, 20), [[20, 20, 30, 30]])  # touch only
        assert not region_intersects_any((10, 10, 20, 20), [])

    def test_degenerate_and_malformed_masks_ignored(self):
        assert not region_intersects_any((10, 10, 20, 20), [[15, 15, 15, 30], [1, 2, 3]])


class TestExpandBbox:
    def test_expand_and_clamp(self):
        assert expand_bbox((100, 100, 120, 110), expand_ratio=0.5, resolution=(300, 200)) == (
            90,
            95,
            130,
            115,
        )
        # clamped at frame edges
        assert expand_bbox((0, 0, 20, 10), expand_ratio=1.0, resolution=(300, 200)) == (
            0,
            0,
            40,
            20,
        )


class TestTemplateNeighborhood:
    def test_hit_at_remembered_position(self):
        bbox = (150, 85, 170, 95)
        frame = _stamp(_frame(), bbox)
        template = frame[85:95, 150:170].copy()
        got = match_element_template(
            frame, template, bbox, expand_ratio=0.5, threshold=0.85, resolution=(300, 200)
        )
        assert got is not None
        matched_bbox, score = got
        assert matched_bbox == bbox
        assert score >= 0.99

    def test_hit_when_shifted_within_neighborhood(self):
        old_bbox = (150, 85, 170, 95)
        new_bbox = (155, 87, 175, 97)
        frame = _stamp(_frame(), new_bbox)
        template = frame[87:97, 155:175].copy()
        got = match_element_template(
            frame, template, old_bbox, expand_ratio=0.5, threshold=0.85, resolution=(300, 200)
        )
        assert got is not None
        assert got[0] == new_bbox

    def test_miss_when_moved_outside_neighborhood(self):
        old_bbox = (150, 85, 170, 95)
        far_bbox = (20, 20, 40, 30)
        frame = _stamp(_frame(), far_bbox)
        template = frame[20:30, 20:40].copy()
        got = match_element_template(
            frame, template, old_bbox, expand_ratio=0.5, threshold=0.85, resolution=(300, 200)
        )
        assert got is None

    def test_miss_below_threshold(self):
        bbox = (150, 85, 170, 95)
        frame = _stamp(_frame(), bbox)
        # A template that never appears on this frame.
        template = np.full((10, 20, 3), 255, dtype=np.uint8)
        template[::2, ::2] = 0
        got = match_element_template(
            frame, template, bbox, expand_ratio=0.5, threshold=0.85, resolution=(300, 200)
        )
        assert got is None


class TestFindBestPage:
    def _page(self, page_id: str, tokens, resolution=(300, 200)) -> PageMemory:
        return PageMemory(
            page_id=page_id,
            fingerprint=PageFingerprint(
                phash="deadbeefdeadbeef",
                ocr_tokens=tokens,
                layout_cells=["1,1"],
                resolution=resolution,
            ),
            resolution=resolution,
        )

    def test_best_page_high(self):
        fp = self._page("q", ["a", "b"]).fingerprint
        pages = [self._page("p1", ["a", "b"]), self._page("p2", ["x", "y"])]
        page, score, level = find_best_page(fp, pages, **_THRESHOLDS)
        assert page is not None and page.page_id == "p1"
        assert level == "high"
        assert score >= 0.88

    def test_empty_pages(self):
        fp = self._page("q", ["a"]).fingerprint
        assert find_best_page(fp, [], **_THRESHOLDS) == (None, 0.0, "none")

    def test_resolution_mismatch_capped(self):
        fp = self._page("q", ["a", "b"]).fingerprint
        pages = [self._page("p1", ["a", "b"], resolution=(600, 400))]
        _, _, level = find_best_page(fp, pages, **_THRESHOLDS)
        assert level == "low"
