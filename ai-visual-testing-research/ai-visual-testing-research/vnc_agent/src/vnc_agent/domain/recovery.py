"""Failure / recovery models (data-model.md §8)."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class FailureType(str, Enum):
    VNC_CONNECT_FAILED = "vnc_connect_failed"
    VNC_DISCONNECTED = "vnc_disconnected"
    BLACK_SCREEN = "black_screen"
    PAGE_NOT_STABLE = "page_not_stable"
    TARGET_NOT_FOUND = "target_not_found"
    GROUNDING_LOW_CONFIDENCE = "grounding_low_confidence"
    ACTION_NO_EFFECT = "action_no_effect"
    FOCUS_ERROR = "focus_error"
    INPUT_METHOD_ERROR = "input_method_error"
    UNEXPECTED_DIALOG = "unexpected_dialog"
    VERIFICATION_FAILED = "verification_failed"
    TIMEOUT = "timeout"


GroundingLowConfidenceReason = Literal["overall_low_confidence", "top1_top2_close"]

RecoveryStrategy = Literal[
    "recapture",
    "extra_wait",
    "second_candidate",
    "re_ground",
    "switch_to_keyboard",
    "release_modifiers",
    "press_escape",
    "win_d_reset",
    "restart_step",
]


class RecoveryAttempt(BaseModel):
    failure_type: FailureType
    sub_reason: GroundingLowConfidenceReason | None = None
    strategy: RecoveryStrategy
    attempt_index: int = Field(ge=0)
    max_retries: int = Field(ge=1)
    resolved: bool = False
