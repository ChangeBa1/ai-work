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
    # Feature 022 (wrong-click-detection): the observation frame that produced
    # this action's coordinates went stale before execution (pre-click guard
    # detected a change inside the target neighborhood) — the action was NOT
    # sent; recovery re-observes and re-locates.
    STALE_FRAME = "stale_frame"
    # Feature 022 (overall_design.md §9.10): the click landed but every
    # observed change happened away from the target neighborhood AND the
    # independent verification failed — the click most likely hit a
    # neighboring control. Recovery re-observes + re-grounds (same chain as
    # target_not_found).
    WRONG_TARGET = "wrong_target"


GroundingLowConfidenceReason = Literal["overall_low_confidence", "top1_top2_close"]

RecoveryStrategy = Literal[
    "recapture",
    "extra_wait",
    "second_candidate",
    "re_ground",
    "zoom_reground",
    "switch_to_keyboard",
    "release_modifiers",
    "press_escape",
    "win_d_reset",
    "restart_step",
    # Feature 023 (click-postmortem-correction): VLM post-mortem diagnosis of
    # a WRONG_TARGET click (engine selects; runtime performs the work) + the
    # single safe Esc that restores an accidentally changed page before the
    # diagnosis. Both are non-destructive by construction.
    "postmortem",
    "postmortem_undo",
]

# Feature 014 (FR-002): how the zoom_reground ROI was derived.
ZoomRoiSource = Literal["grounding_candidate", "anchor_text"]


class ZoomRegroundPlan(BaseModel):
    """Feature 014: one-shot zoom escalation plan produced by the recovery
    engine and consumed by the next ActionIteration's grounding branch.

    ``roi`` is in original full-frame pixel coordinates (x1, y1, x2, y2)."""

    roi: tuple[int, int, int, int]
    scale_factor: float = Field(gt=1.0)
    roi_source: ZoomRoiSource


# Feature 022 (FR-B02): 8-way screen direction from the target's center to
# the nearest change blob's center ("up" = toward smaller y). "center" is the
# degenerate zero-offset case.
WrongTargetDirection = Literal[
    "up",
    "up_right",
    "right",
    "down_right",
    "down",
    "down_left",
    "left",
    "up_left",
    "center",
]


class WrongTargetEvidence(BaseModel):
    """Feature 022 (FR-B02/FR-B04): deterministic wrong-click evidence
    computed from the ActionEffect's local blobs vs. the executed action's
    ``target_region`` — zero model calls. Attached additively to
    ``ActionIteration.wrong_target_evidence`` and consumed by feature 023's
    post-hoc diagnosis.

    ``suspected`` alone never fails an iteration; the runtime upgrades the
    failure attribution to ``WRONG_TARGET`` only when the same iteration's
    independent verification also failed (FR-B03)."""

    suspected: bool
    target_region: tuple[int, int, int, int] | None = None
    click_point: tuple[int, int] | None = None
    # Thresholds actually applied (config echo, for auditability).
    neighborhood_expand_ratio: float = Field(default=0.5, ge=0.0)
    global_diff_ratio_max: float = Field(default=0.10, gt=0.0, le=1.0)
    # Observed evidence.
    global_diff_ratio: float = 0.0
    blob_count: int = 0
    blobs_intersecting_neighborhood: int = 0
    max_blob_target_iou: float = 0.0
    nearest_blob_bbox: tuple[int, int, int, int] | None = None
    nearest_blob_distance_px: float | None = None
    # (dx, dy) from target center to nearest blob center, screen coordinates
    # (y grows downward).
    nearest_blob_offset: tuple[int, int] | None = None
    nearest_blob_direction: WrongTargetDirection | None = None
    reason: str = ""


# Feature 023 (FR-010): why a post-mortem ended the way it did. "corrected"
# is the only outcome that produces a PostmortemCorrectionPlan; every other
# value is a distinct fail-safe refusal that falls back to the 022 chain.
PostmortemOutcome = Literal[
    "corrected",
    "page_not_restored",
    "diagnosis_failed",
    "target_not_found",
    "low_confidence",
    "distance_exceeded",
]


class PostmortemCorrectionPlan(BaseModel):
    """Feature 023 (FR-005): one-shot corrected-click plan produced by an
    accepted post-mortem diagnosis and consumed by the next ActionIteration's
    grounding branch (skipping memory + grounder for that round).

    ``corrected_bbox`` is in original full-frame pixel coordinates;
    ``click_point`` is the deterministic ``safe_click_point(corrected_bbox,
    siblings=[])`` result computed at diagnosis time."""

    corrected_bbox: tuple[int, int, int, int]
    click_point: tuple[int, int]
    confidence: float = Field(ge=0.0, le=1.0)
    clicked_element: str = ""
    source_iteration_index: int = Field(default=0, ge=0)


class PostmortemAudit(BaseModel):
    """Feature 023 (FR-010): full audit of one post-mortem attempt, attached
    additively to ``ActionIteration.postmortem`` and mirrored in the JSON
    report. Null fields simply mean the pipeline refused before that stage."""

    outcome: PostmortemOutcome
    clicked_element: str | None = None
    target_found: bool | None = None
    confidence: float | None = None
    corrected_bbox: tuple[int, int, int, int] | None = None
    corrected_click_point: tuple[int, int] | None = None
    # Distance gate evidence (original click point → corrected click point).
    distance_px: float | None = None
    max_distance_px: float | None = None
    # Thresholds actually applied (config echo, for auditability).
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    # Undo (page restore) evidence — at most one Esc per diagnosis (FR-003).
    undo_performed: bool = False
    undo_restored_page: bool | None = None
    page_similarity: float | None = None
    # Artifact references (run-relative model/ directory convention).
    annotated_image_ref: str | None = None
    request_ref: str | None = None
    response_ref: str | None = None
    reason: str = ""


class RecoveryAttempt(BaseModel):
    failure_type: FailureType
    sub_reason: GroundingLowConfidenceReason | None = None
    strategy: RecoveryStrategy
    attempt_index: int = Field(ge=0)
    max_retries: int = Field(ge=1)
    resolved: bool = False
    # Feature 014 (FR-008): zoom_reground observability — populated only for
    # strategy == "zoom_reground"; None for every other strategy.
    roi: tuple[int, int, int, int] | None = None
    scale_factor: float | None = None
    roi_source: ZoomRoiSource | None = None
