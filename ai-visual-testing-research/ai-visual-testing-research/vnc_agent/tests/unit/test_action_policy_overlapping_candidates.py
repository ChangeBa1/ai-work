"""Top1/top2 ambiguity must be spatial, not purely confidence-based.

Regression guard for a live failure (run d08b9453, step
``select-scanner-simulator``): the grounder located the target correctly on the
first attempt and returned three near-identical boxes (IoU 0.86, centres 1px
apart) with confidences 0.90/0.85/0.80. The old check saw a 0.05 gap, declared
GROUNDING_LOW_CONFIDENCE/top1_top2_close and discarded a correct hit; the step
then burned every retry and the run failed. Overlapping candidates are the
grounder *agreeing with itself*, not competing targets.
"""

from datetime import datetime, timezone

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.recovery import FailureType
from vnc_agent.planning.action_policy import ActionPolicy, _bbox_iou


def _screen() -> StructuredScreen:
    return StructuredScreen(
        frame_id="f1",
        resolution=(1024, 768),
        captured_at=datetime.now(timezone.utc),
        ocr_items=[],
        image_path="x.png",
    )


def _click() -> SemanticAction:
    return SemanticAction(
        action_id="a",
        intent="click the ScannerSimulator window preview",
        action_type="click",
        target=TargetDescription(role="window_preview", description="preview area"),
    )


def _result(*boxes_and_confs) -> GroundingResult:
    return GroundingResult(
        found=True,
        candidates=[
            GroundingCandidate(bbox=b, confidence=c, coordinate_space="pixel")
            for b, c in boxes_and_confs
        ],
    )


def test_overlapping_candidates_are_agreement_not_ambiguity():
    """The exact live payload must now resolve to an executable click."""
    result = _result(
        ((222, 455, 326, 522), 0.90),
        ((220, 450, 328, 525), 0.85),
        ((225, 460, 323, 518), 0.80),
    )
    # Precondition: the gap alone would have tripped the old check.
    assert result.candidates[0].confidence - result.candidates[1].confidence < 0.08

    out = ActionPolicy().resolve(_click(), _screen(), grounding_result=result)

    assert out.outcome != "stop_recover"
    assert out.executable is not None
    assert out.executable.coordinates is not None
    x, y = out.executable.coordinates
    assert 222 <= x <= 326 and 455 <= y <= 522


def test_distinct_candidates_with_close_confidence_still_blocked():
    """Two genuinely different targets must keep tripping the guard."""
    result = _result(
        ((222, 455, 326, 522), 0.90),  # ScannerSi thumbnail
        ((645, 255, 905, 405), 0.85),  # CT5100 thumbnail, a different window
    )
    assert _bbox_iou(result.candidates[0].bbox, result.candidates[1].bbox) == 0.0

    out = ActionPolicy().resolve(_click(), _screen(), grounding_result=result)

    assert out.outcome == "stop_recover"
    assert out.failure_type == FailureType.GROUNDING_LOW_CONFIDENCE
    assert out.sub_reason == "top1_top2_close"


def test_overlap_does_not_rescue_a_genuinely_low_top1():
    """The overall-confidence floor is independent and must still apply."""
    result = _result(
        ((222, 455, 326, 522), 0.40),
        ((220, 450, 328, 525), 0.38),
    )

    out = ActionPolicy().resolve(_click(), _screen(), grounding_result=result)

    assert out.outcome == "stop_recover"
    assert out.sub_reason == "overall_low_confidence"


def test_bbox_iou_basics():
    assert _bbox_iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert _bbox_iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert _bbox_iou((0, 0, 10, 10), (0, 0, 0, 0)) == 0.0
    assert 0.85 < _bbox_iou((222, 455, 326, 522), (220, 450, 328, 525)) < 0.87
