"""Feature 014 (FR-002): deterministic zoom_reground ROI derivation order."""

from __future__ import annotations

from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.observation import OCRItem
from vnc_agent.recovery.zoom import determine_zoom_roi, expand_region

RESOLUTION = (1920, 1080)


def _grounding(*bboxes_conf) -> GroundingResult:
    return GroundingResult(
        found=True,
        candidates=[
            GroundingCandidate(bbox=b, confidence=c, coordinate_space="pixel")
            for b, c in bboxes_conf
        ],
        model_name="stub",
    )


class TestExpandRegion:
    def test_center_expansion_by_factor(self):
        roi = expand_region(
            (100, 100, 140, 120), factor=2.0, min_size_px=16, resolution=RESOLUTION
        )
        assert roi is not None
        # 40x20 bbox → 80x40 window centered on (120, 110)
        assert roi.as_tuple() == (80, 90, 160, 130)

    def test_min_size_enforced(self):
        roi = expand_region(
            (500, 500, 504, 504), factor=2.0, min_size_px=64, resolution=RESOLUTION
        )
        assert roi is not None
        assert roi.x2 - roi.x1 >= 64
        assert roi.y2 - roi.y1 >= 64

    def test_shifted_into_bounds_at_corner(self):
        # bbox near origin: expanded window would go negative → shifted inside
        roi = expand_region(
            (0, 0, 20, 20), factor=4.0, min_size_px=64, resolution=RESOLUTION
        )
        assert roi is not None
        assert roi.x1 >= 0 and roi.y1 >= 0
        assert roi.x2 <= RESOLUTION[0] and roi.y2 <= RESOLUTION[1]
        assert roi.x2 - roi.x1 >= 64

    def test_out_of_bounds_bbox_still_yields_in_bounds_window(self):
        # the classic target_not_found cause: candidate partially off-screen
        roi = expand_region(
            (1900, 1060, 1980, 1120), factor=2.0, min_size_px=64, resolution=RESOLUTION
        )
        assert roi is not None
        assert roi.x2 <= RESOLUTION[0] and roi.y2 <= RESOLUTION[1]

    def test_degenerate_screen_rejected(self):
        assert (
            expand_region((0, 0, 10, 10), factor=2.0, min_size_px=16, resolution=(0, 0))
            is None
        )


class TestDetermineZoomRoiOrder:
    def test_priority_a_highest_confidence_candidate(self):
        result = determine_zoom_roi(
            resolution=RESOLUTION,
            grounding_result=_grounding(
                ((100, 100, 140, 120), 0.4),
                ((800, 500, 840, 520), 0.7),  # highest confidence wins
            ),
            ocr_items=[
                OCRItem(text="anchor", bbox=(10, 10, 60, 30), confidence=0.9)
            ],
            target={"nearby_texts": ["anchor"]},
        )
        assert result is not None
        roi, source = result
        assert source == "grounding_candidate"
        # centered on the 0.7-confidence candidate (820, 510)
        assert roi.contains_point(820, 510)
        assert not roi.contains_point(120, 110)

    def test_priority_b_anchor_text_when_no_candidates(self):
        result = determine_zoom_roi(
            resolution=RESOLUTION,
            grounding_result=GroundingResult(found=False, candidates=[]),
            ocr_items=[
                OCRItem(text="TOTAL", bbox=(600, 400, 700, 430), confidence=0.8),
                OCRItem(text="other", bbox=(10, 10, 60, 30), confidence=0.9),
            ],
            target={"text": "OK", "nearby_texts": ["total"]},
        )
        assert result is not None
        roi, source = result
        assert source == "anchor_text"
        assert roi.contains_point(650, 415)

    def test_anchor_multiple_hits_takes_highest_confidence(self):
        result = determine_zoom_roi(
            resolution=RESOLUTION,
            grounding_result=None,
            ocr_items=[
                OCRItem(text="total a", bbox=(100, 100, 200, 130), confidence=0.5),
                OCRItem(text="total b", bbox=(900, 700, 1000, 730), confidence=0.95),
            ],
            target={"nearby_texts": ["total"]},
        )
        assert result is not None
        roi, _source = result
        assert roi.contains_point(950, 715)
        assert not roi.contains_point(150, 115)

    def test_anchor_neighborhood_wider_than_candidate_expansion(self):
        bbox = (900, 500, 940, 520)
        from_candidate = determine_zoom_roi(
            resolution=RESOLUTION,
            grounding_result=_grounding((bbox, 0.6)),
            expand_factor=2.0,
            min_size_px=16,
        )
        from_anchor = determine_zoom_roi(
            resolution=RESOLUTION,
            grounding_result=None,
            ocr_items=[OCRItem(text="anchor", bbox=bbox, confidence=0.9)],
            target={"nearby_texts": ["anchor"]},
            expand_factor=2.0,
            min_size_px=16,
        )
        assert from_candidate is not None and from_anchor is not None
        cand_roi, _ = from_candidate
        anchor_roi, _ = from_anchor
        assert (anchor_roi.x2 - anchor_roi.x1) > (cand_roi.x2 - cand_roi.x1)

    def test_priority_c_none_available_returns_none(self):
        # no candidates, no anchor hit → no grid sweep, escalation refused
        assert (
            determine_zoom_roi(
                resolution=RESOLUTION,
                grounding_result=GroundingResult(found=False, candidates=[]),
                ocr_items=[
                    OCRItem(text="unrelated", bbox=(0, 0, 50, 20), confidence=0.9)
                ],
                target={"text": "OK", "nearby_texts": ["missing anchor"]},
            )
            is None
        )

    def test_no_target_no_candidates_returns_none(self):
        assert (
            determine_zoom_roi(
                resolution=RESOLUTION,
                grounding_result=None,
                ocr_items=[],
                target=None,
            )
            is None
        )
