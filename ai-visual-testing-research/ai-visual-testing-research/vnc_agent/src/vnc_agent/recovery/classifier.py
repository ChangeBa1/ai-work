"""Failure classifier (FR-036)."""

from __future__ import annotations

from dataclasses import dataclass

from vnc_agent.domain.action_effect import ActionEffect
from vnc_agent.domain.grounding import GroundingResult
from vnc_agent.domain.recovery import FailureType, GroundingLowConfidenceReason
from vnc_agent.domain.verification import VerificationResult, WaitResult
from vnc_agent.planning.action_policy import _bbox_iou
from vnc_agent.runtime.exceptions import (
    ActionTimeoutError,
    VNCConnectionError,
    VNCDisconnectedError,
)


@dataclass
class Classification:
    failure_type: FailureType
    sub_reason: GroundingLowConfidenceReason | None = None
    detail: str = ""


def classify_exception(exc: BaseException) -> Classification:
    if isinstance(exc, VNCConnectionError):
        return Classification(FailureType.VNC_CONNECT_FAILED, detail=str(exc))
    if isinstance(exc, VNCDisconnectedError):
        return Classification(FailureType.VNC_DISCONNECTED, detail=str(exc))
    if isinstance(exc, ActionTimeoutError):
        return Classification(FailureType.TIMEOUT, detail=str(exc))
    if isinstance(exc, TimeoutError):
        return Classification(FailureType.TIMEOUT, detail=str(exc))
    return Classification(FailureType.TIMEOUT, detail=str(exc))


def classify_grounding(
    result: GroundingResult,
    *,
    overall_threshold: float = 0.55,
    top1_top2_min_gap: float = 0.08,
    top1_top2_distinct_max_iou: float = 0.5,
    width: int = 0,
    height: int = 0,
) -> Classification | None:
    """Return classification if grounding is not actionable; None if OK."""
    if not result.found or not result.candidates:
        return Classification(FailureType.TARGET_NOT_FOUND)

    cands = result.candidates
    if width > 0 and height > 0:
        cands = [c for c in cands if c.is_within(width, height)]
        if not cands:
            return Classification(FailureType.TARGET_NOT_FOUND, detail="all out of bounds")

    top = cands[0]
    if top.confidence < overall_threshold:
        return Classification(
            FailureType.GROUNDING_LOW_CONFIDENCE,
            sub_reason="overall_low_confidence",
        )
    if len(cands) >= 2:
        gap = cands[0].confidence - cands[1].confidence
        # Near-identical boxes are one target described twice, not a genuine
        # ambiguity — see ActionPolicy.top1_top2_distinct_max_iou.
        distinct = _bbox_iou(cands[0].bbox, cands[1].bbox) <= top1_top2_distinct_max_iou
        if gap < top1_top2_min_gap and distinct:
            return Classification(
                FailureType.GROUNDING_LOW_CONFIDENCE,
                sub_reason="top1_top2_close",
            )
    return None


def classify_wait(wait: WaitResult) -> Classification | None:
    if wait.end_reason == "vnc_error":
        return Classification(FailureType.VNC_DISCONNECTED)
    if wait.end_reason == "timeout" and not wait.stable:
        return Classification(FailureType.PAGE_NOT_STABLE)
    return None


def classify_verification(result: VerificationResult) -> Classification | None:
    if result.status == "failed":
        return Classification(FailureType.VERIFICATION_FAILED, detail=result.reason)
    return None


def classify_action_no_effect(
    action_effect: ActionEffect | bool,
) -> Classification | None:
    """
    002: accept ActionEffect (preferred) or legacy bool for backward compatibility.

    - no_effect → ACTION_NO_EFFECT
    - unexpected_effect → UNEXPECTED_DIALOG
    - effect_uncertain / expected_effect → no classification (RepeatGuard / resolver)
    """
    # Legacy path: bare bool (001 call sites / tests)
    if isinstance(action_effect, bool):
        if not action_effect:
            return Classification(FailureType.ACTION_NO_EFFECT)
        return None

    if not isinstance(action_effect, ActionEffect):
        return None
    if action_effect.status == "no_effect":
        return Classification(
            FailureType.ACTION_NO_EFFECT, detail=action_effect.reason
        )
    if action_effect.status == "unexpected_effect":
        return Classification(
            FailureType.UNEXPECTED_DIALOG, detail=action_effect.reason
        )
    return None
