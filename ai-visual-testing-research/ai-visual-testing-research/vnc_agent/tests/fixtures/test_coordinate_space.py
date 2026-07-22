"""Feature 003 grounding coordinate-space contract tests (T027-T030)."""

import pytest

from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.models.coordinate_space import resolve_pixel_bbox
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.provider import GroundingRequest


def test_normalized_1000_on_1024x1568() -> None:
    resolved = resolve_pixel_bbox(
        (251, 402, 405, 459), "normalized_1000", (1024, 1568)
    )
    assert resolved == (257, 630, 415, 720)
    assert 630 <= resolved[1] <= resolved[3] <= 720


def test_conversion_happens_exactly_once() -> None:
    original = (251, 402, 405, 459)
    first = resolve_pixel_bbox(original, "pixel", (1024, 1568))
    second = resolve_pixel_bbox(first, "pixel", (1024, 1568))  # type: ignore[arg-type]
    assert first == original
    assert second == first


@pytest.mark.parametrize(
    ("bbox", "space"),
    [
        ((251, 402, 405, 459), None),
        ((0, 0, 2048, 200), "pixel"),
        ((10, 10, 20, 20), "unknown"),
        ((-1, 0, 100, 100), "normalized_1000"),
    ],
)
def test_missing_or_contradictory_or_unknown_rejected(bbox, space) -> None:
    assert resolve_pixel_bbox(bbox, space, (1024, 1568)) is None


@pytest.mark.asyncio
async def test_stub_grounder_drops_rejected_candidates() -> None:
    grounder = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(0, 0, 2048, 200),
                    coordinate_space="pixel",
                    confidence=0.9,
                )
            ],
        )
    )
    result = await grounder.ground(
        GroundingRequest(
            image_ref="offline.png",
            target={"text": "レジ袋"},
            resolution=(1024, 1568),
        )
    )
    assert result.found is False
    assert result.candidates == []
    assert result.coordinate_space_audit[0]["accepted"] is False


@pytest.mark.asyncio
async def test_mixed_coordinate_space_per_candidate() -> None:
    grounder = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(100, 200, 200, 300),
                    coordinate_space="pixel",
                    confidence=0.9,
                ),
                GroundingCandidate(
                    bbox=(500, 500, 750, 750),
                    coordinate_space="normalized_1000",
                    confidence=0.8,
                ),
            ],
        )
    )
    result = await grounder.ground(
        GroundingRequest(
            image_ref="offline.png",
            target={"text": "target"},
            resolution=(1000, 1600),
        )
    )
    assert result.candidates[0].bbox == (100, 200, 200, 300)
    assert result.candidates[1].bbox == (500, 800, 750, 1200)
    assert result.candidates[0].raw_bbox == (100, 200, 200, 300)
    assert result.candidates[1].raw_bbox == (500, 500, 750, 750)
