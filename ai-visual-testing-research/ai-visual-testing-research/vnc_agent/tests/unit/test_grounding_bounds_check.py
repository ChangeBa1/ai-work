"""US4: Out-of-bounds candidates filtered (FR-019)."""

from vnc_agent.domain.grounding import GroundingCandidate, filter_in_bounds


def test_filter_out_of_bounds():
    cands = [
        GroundingCandidate(bbox=(10, 10, 50, 50), confidence=0.9),
        GroundingCandidate(bbox=(900, 10, 950, 50), confidence=0.8),  # out if w=800
        GroundingCandidate(bbox=(-5, 0, 10, 10), confidence=0.7),
    ]
    ok = filter_in_bounds(cands, 800, 600)
    assert len(ok) == 1
    assert ok[0].bbox == (10, 10, 50, 50)


def test_all_oob_empty():
    cands = [GroundingCandidate(bbox=(1000, 1000, 1100, 1100), confidence=0.9)]
    assert filter_in_bounds(cands, 800, 600) == []
