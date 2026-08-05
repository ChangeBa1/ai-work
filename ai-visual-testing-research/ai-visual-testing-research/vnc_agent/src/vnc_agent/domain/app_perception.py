"""Feature 024 (app-perception-plugins): generic domain models for the
pluggable pre-grounding sub-window enhancement.

Every model here is deliberately business-agnostic: geometry, text, confidence.
Application/window/control vocabulary lives ONLY in the declarative profile
YAML files, test cases and fixtures (Constitution VI).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# The full, exhaustive set of activation outcomes (spec FR-011 ladder).
ActivationReason = Literal[
    # --- default path: the step simply did not declare a scope -------------
    "not_declared",
    "declared_off",
    # --- gates -------------------------------------------------------------
    "disabled",
    "plugin_not_registered",
    "plugin_not_allowed",
    "budget_exhausted",
    # Retained for backward compatibility with runs recorded before the
    # enhancement moved to the observation stage; no longer emitted. The
    # OCR refinement now benefits assertions and OCR-direct clicks too, so
    # it is no longer gated on the action producing a coordinate.
    "non_positional_action",
    # --- detection ---------------------------------------------------------
    "not_detected",
    "low_detection_confidence",
    "roi_not_subwindow",
    # --- observation -------------------------------------------------------
    "scale_not_beneficial",
    "observation_failed",
    # --- success -----------------------------------------------------------
    "activated",
    # Same frame already enhanced earlier in this step (content-hash hit):
    # the refined OCR is reused, costing no capture and no OCR pass.
    "activated_cached",
]

DetectionMethod = Literal["ocr_anchors", "template"]

AnchorRelation = Literal[
    "same_row",
    "same_column",
    "right_of",
    "left_of",
    "above",
    "below",
    "between",
]


class AnchorHit(BaseModel):
    """One profile-declared anchor text matched against a frame OCR item."""

    anchor_text: str
    matched_text: str
    bbox: tuple[int, int, int, int]
    confidence: float = Field(ge=0.0, le=1.0)


class SubWindowDetection(BaseModel):
    """Result of locating a known sub-window in the current frame.

    ``region`` is in ORIGINAL frame pixel coordinates and is already brought
    inside the frame using the viewing-window semantics of feature 014.
    """

    plugin_name: str
    region: tuple[int, int, int, int]
    confidence: float = Field(ge=0.0, le=1.0)
    method: DetectionMethod
    matched_anchors: list[AnchorHit] = Field(default_factory=list)
    area_ratio: float = Field(ge=0.0, le=1.0)


class ScopeHintMismatch(BaseModel):
    """Read-only warning: the step's target text clues resolve OUTSIDE the
    detected window (or straddle it), suggesting the declaration is wrong.

    This NEVER changes the activation outcome — declaring a scope is the test
    author's call (spec FR-011/FR-012). It exists purely for post-run triage.
    """

    clue_texts: list[str] = Field(default_factory=list)
    hits_inside: int = 0
    hits_outside: int = 0
    kind: Literal["all_outside", "straddling"]


class ActivationDecision(BaseModel):
    activated: bool
    reason_code: ActivationReason
    declared_scope: str | None = None
    declared_but_undetected: bool = False
    scope_hint_mismatch: ScopeHintMismatch | None = None


class AnchorConstraint(BaseModel):
    """A generic geometric relation between a candidate and profile anchors.

    Only generic relations live in core; which anchors and how strict is
    profile data. ``enforce=True`` makes a violation reject the candidate
    (strong prior); ``False`` only records it (weak hint) — spec FR-018.
    """

    subject: str
    relation: AnchorRelation
    anchors: list[str] = Field(min_length=1)
    tolerance_ratio: float = Field(default=0.25, ge=0.0, le=1.0)
    enforce: bool = False


class ConstraintViolation(BaseModel):
    subject: str
    relation: AnchorRelation
    anchors: list[str] = Field(default_factory=list)
    candidate_bbox: tuple[int, int, int, int]
    mode: Literal["record_only", "enforced"]


class GeometricPrediction(BaseModel):
    """A control located by solving design->screen from measured anchors.

    This is the only path that can locate a control carrying no text at all
    (a bare input box), which OCR can never find and a model can only guess
    at. It is deterministic, so it is auditable in a way a model answer is
    not: the solved transform and its residuals are recorded here.
    """

    control_name: str
    applied: bool = False
    reject_reason: str | None = None
    predicted_rect: tuple[int, int, int, int] | None = None
    click_point: tuple[int, int] | None = None
    scale_x: float | None = None
    scale_y: float | None = None
    offset_x: float | None = None
    offset_y: float | None = None
    anchor_count: int = 0
    max_residual_px: float | None = None
    residuals: list[tuple[str, float, float]] = Field(default_factory=list)


class PerceptionEnhancementAudit(BaseModel):
    """One record per iteration that reached the grounding branch (FR-024).

    Present even when nothing happened — the reason code says why, which is
    what makes "why was this step not enhanced?" answerable after the fact.
    """

    enabled: bool = False
    declared_scope: str | None = None
    plugin_name: str | None = None
    activated: bool = False
    reason_code: ActivationReason = "not_declared"
    declared_but_undetected: bool = False
    roi: tuple[int, int, int, int] | None = None
    detection_method: DetectionMethod | None = None
    detection_confidence: float | None = None
    matched_anchors: list[AnchorHit] = Field(default_factory=list)
    scale_factor: float | None = None
    upscaled_resolution: tuple[int, int] | None = None
    zoom_image_ref: str | None = None
    scope_hint_mismatch: ScopeHintMismatch | None = None
    constraint_violations: list[ConstraintViolation] = Field(default_factory=list)
    # Number of source-geometry derived hints handed to the grounder this
    # round (hints only — never a click source, spec FR-005e).
    source_geometry_hints: int = 0
    # --- OCR refinement bookkeeping (observation-stage enhancement) --------
    # Full-frame OCR items inside the sub-window that the refined read
    # replaced, and how many refined items took their place. A large
    # replacement count with an unchanged outcome is the signature of the
    # small-glyph misreads this feature exists to fix.
    ocr_items_replaced: int = 0
    ocr_items_added: int = 0
    # Whether this iteration actually reached the grounding branch. False
    # means the action was resolved earlier (OCR-direct click, element
    # memory, template, replay) — which is exactly the case that used to be
    # invisible in the report and made "not triggered" indistinguishable
    # from "broken".
    grounding_reached: bool = False
    # Which image the grounder was actually shown this round. Refining the
    # OCR is not enough on its own — the grounder is what picks the click
    # point — so being able to tell "it saw the magnified crop" from "it saw
    # the full frame" is what makes a bad click diagnosable.
    grounder_image: (
        Literal["full_frame", "app_perception_zoom", "zoom_reground"] | None
    ) = None
    # Non-null iff a source-geometry prediction was attempted this round.
    # `applied=True` means the click came from deterministic geometry rather
    # than from a model, which is the distinction a post-mortem needs first.
    geometric_prediction: GeometricPrediction | None = None
