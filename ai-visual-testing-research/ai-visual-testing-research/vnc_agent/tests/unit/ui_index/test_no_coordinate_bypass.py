"""T040: raw ui-index coordinates never bypass the Grounder's coordinate-
resolution path (FR-009, FR-014, contracts/ui-index-consumer-interfaces.md
§9).

Covers three independent guarantees:
1. `SemanticAction` (Planner output) rejects raw coordinate fields — the
   sanitized `VisibleElementHint` sent to the Planner has no bbox to leak
   in the first place.
2. `GroundingResult.candidates[].bbox` values that originated from
   `GroundingRequest.ui_index_candidates` are only present after passing
   through `resolve_pixel_bbox()` — never copied verbatim from
   `Element.normalized_bounds`.
3. Every `ui_index`-sourced candidate is traceable in
   `GroundingResult.candidates[].reason` via a `"ui_index:"` (or bare
   `"ui_index"`) prefix, so a human auditor can always tell ocr/template/
   ui_index provenance apart directly from `GroundingResult`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.grounding import GroundingResult
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.provider import GroundingRequest


def test_semantic_action_rejects_raw_coordinate_fields():
    with pytest.raises((ValidationError, ValueError)):
        SemanticAction.model_validate(
            {
                "action_id": "a1",
                "intent": "click submit",
                "action_type": "click",
                "x": 640,
                "y": 900,
            }
        )


def test_semantic_action_rejects_coordinates_field():
    with pytest.raises((ValidationError, ValueError)):
        SemanticAction.model_validate(
            {
                "action_id": "a1",
                "intent": "click submit",
                "action_type": "click",
                "coordinates": [620, 900, 780, 960],
            }
        )


def _ui_index_candidate(
    *, bbox=(620, 900, 780, 960), coordinate_space="normalized_1000", label="Submit"
):
    return {
        "bbox": list(bbox),
        "coordinate_space": coordinate_space,
        "confidence": 0.95,
        "label": label,
        "reason": ", ".join([label]) if label else "",
        "source": "ui_index",
    }


async def test_ui_index_candidate_bbox_goes_through_resolve_pixel_bbox_not_verbatim():
    """A normalized_1000 candidate (values 0-1000) MUST be converted to real
    pixel coordinates scaled by `resolution` — the final bbox must differ
    from the raw normalized_1000 values whenever resolution != 1000x1000."""
    raw_bbox = (620, 900, 780, 960)
    grounder = StubGrounder(GroundingResult(found=False, candidates=[], model_name="stub"))
    request = GroundingRequest(
        image_ref="unused.png",
        target={"role": "button", "text": "Submit"},
        resolution=(2000, 2000),
        ui_index_candidates=[_ui_index_candidate(bbox=raw_bbox)],
    )
    result = await grounder.ground(request)

    assert result.found is True
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.raw_bbox == raw_bbox
    # normalized_1000 (620,900,780,960) scaled to a 2000x2000 resolution
    # becomes pixel bbox (1240,1800,1560,1920) — definitively not verbatim.
    assert candidate.bbox != raw_bbox
    assert candidate.bbox == (1240, 1800, 1560, 1920)


async def test_ui_index_candidate_out_of_range_is_rejected_not_clamped():
    """Contract: coordinates are never clamped or guessed — an
    out-of-declared-space candidate that cannot be resolved MUST be
    dropped entirely, not silently forced into range."""
    grounder = StubGrounder(GroundingResult(found=False, candidates=[], model_name="stub"))
    request = GroundingRequest(
        image_ref="unused.png",
        target={"role": "button", "text": "Submit"},
        resolution=(100, 100),
        # x2 (1500) exceeds pixel resolution width (100) under the declared
        # "pixel" space -> unresolvable, must be dropped rather than clamped.
        ui_index_candidates=[
            _ui_index_candidate(bbox=(0, 0, 1500, 50), coordinate_space="pixel")
        ],
    )
    result = await grounder.ground(request)
    assert result.candidates == []
    assert result.found is False


async def test_ui_index_candidate_reason_is_prefixed_for_traceability():
    grounder = StubGrounder(GroundingResult(found=False, candidates=[], model_name="stub"))
    request = GroundingRequest(
        image_ref="unused.png",
        target={"role": "button", "text": "Submit"},
        resolution=(1000, 1000),
        ui_index_candidates=[_ui_index_candidate(label="Submit")],
    )
    result = await grounder.ground(request)

    assert len(result.candidates) == 1
    assert result.candidates[0].reason.startswith("ui_index:")


async def test_ui_index_candidates_merge_with_model_candidates_not_replace():
    """ui_index candidates participate in the same fusion/top-3 path as
    model-produced candidates — they never form a separate bypass channel."""
    from vnc_agent.domain.grounding import GroundingCandidate

    model_candidate = GroundingCandidate(
        bbox=(10, 10, 20, 20),
        coordinate_space="pixel",
        confidence=0.99,
        label="model-found",
        reason="model",
    )
    grounder = StubGrounder(
        GroundingResult(found=True, candidates=[model_candidate], model_name="stub")
    )
    request = GroundingRequest(
        image_ref="unused.png",
        target={"role": "button", "text": "Submit"},
        resolution=(1000, 1000),
        ui_index_candidates=[_ui_index_candidate()],
    )
    result = await grounder.ground(request)

    assert len(result.candidates) == 2
    reasons = {c.reason for c in result.candidates}
    assert "model" in reasons
    assert any(r.startswith("ui_index") for r in reasons)


async def test_empty_ui_index_candidates_does_not_affect_result():
    model_candidate_result = GroundingResult(found=False, candidates=[], model_name="stub")
    grounder = StubGrounder(model_candidate_result)
    request = GroundingRequest(
        image_ref="unused.png",
        target={"role": "button", "text": "Submit"},
        resolution=(1000, 1000),
        ui_index_candidates=[],
    )
    result = await grounder.ground(request)
    assert result.found is False
    assert result.candidates == []
