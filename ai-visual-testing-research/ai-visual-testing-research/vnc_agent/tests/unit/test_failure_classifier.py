"""US8: FailureType classification including grounding sub-reasons."""

from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.recovery import FailureType
from vnc_agent.recovery.classifier import classify_grounding
from vnc_agent.runtime.exceptions import VNCConnectionError, VNCDisconnectedError
from vnc_agent.recovery.classifier import classify_exception


def test_found_false_is_target_not_found():
    r = GroundingResult(found=False, candidates=[])
    c = classify_grounding(r)
    assert c is not None
    assert c.failure_type == FailureType.TARGET_NOT_FOUND


def test_overall_low_confidence():
    r = GroundingResult(
        found=True,
        candidates=[GroundingCandidate(bbox=(0, 0, 10, 10), confidence=0.2)],
    )
    c = classify_grounding(r, overall_threshold=0.55)
    assert c is not None
    assert c.failure_type == FailureType.GROUNDING_LOW_CONFIDENCE
    assert c.sub_reason == "overall_low_confidence"


def test_top1_top2_close():
    r = GroundingResult(
        found=True,
        candidates=[
            GroundingCandidate(bbox=(0, 0, 10, 10), confidence=0.8),
            GroundingCandidate(bbox=(20, 20, 30, 30), confidence=0.79),
        ],
    )
    c = classify_grounding(r, overall_threshold=0.55, top1_top2_min_gap=0.08)
    assert c is not None
    assert c.sub_reason == "top1_top2_close"


def test_vnc_exceptions():
    assert classify_exception(VNCConnectionError("x")).failure_type == FailureType.VNC_CONNECT_FAILED
    assert classify_exception(VNCDisconnectedError("x")).failure_type == FailureType.VNC_DISCONNECTED
