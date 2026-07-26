"""Record-replay domain models (feature 016, overall_design.md §10.2/§11).

Pure data structures — recording lives in ``replay/recorder.py``, target
location in ``replay/locator.py``, execution in ``replay/player.py`` and the
patch lifecycle in ``replay/patch.py``. Everything here is business-agnostic
(Constitution VI): generic pixels, text tokens and geometry.

Lifecycle boundary vs feature 015 (spec Clarification 9): a ReplayScript is a
per-testcase versioned baseline generated from one fully-passed exploration
run; page/element memory is global, incrementally-updated online experience.
They share the fingerprint/retrieval pure functions and the masking rules but
are stored separately and never mixed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from vnc_agent.domain.action import ExecutableAction, SemanticAction
from vnc_agent.domain.memory import PageFingerprint
from vnc_agent.domain.verification import VerificationSpec

BBox = tuple[int, int, int, int]
NormalizedBBox = tuple[float, float, float, float]

ReplayLocateMethod = Literal[
    "template", "anchor", "bbox", "fallback_grounding", "keyboard"
]

ReplayPatchStatus = Literal["pending", "approved", "rejected"]


class ReplayAnchor(BaseModel):
    """One recorded anchor: nearby OCR text plus its bbox at record time.

    Design §11 stores anchor *texts* only; the bbox is an additive detail so
    the anchor-translation locate stage (spec Clarification 2) can compute a
    deterministic offset from recorded to current anchor positions.
    """

    text: str
    bbox: BBox


class ReplayStep(BaseModel):
    """One replayable step (design §11 ReplayStep, spec FR-001)."""

    replay_step_id: str
    # Source TestStep id (report/failure attribution, spec Clarification 10).
    step_id: str
    order_index: int = Field(ge=0)
    # Pre-action page identity built from the masked-safe frame (015 reuse).
    page_fingerprint: PageFingerprint
    semantic_action: SemanticAction
    preferred_method: Literal["keyboard", "mouse"]
    # Keyboard steps replay this snapshot verbatim (spec FR-004); for mouse
    # steps the coordinates are re-derived by the locate chain and this is
    # kept for audit only.
    recorded_executable: ExecutableAction | None = None
    # Masked-safe template crop persisted on disk; None when refused
    # (mask intersection) or the step is keyboard-only.
    target_template_path: str | None = None
    # True when the recorded target_region intersected a configured
    # security.mask_region: no template exists and every direct-locate stage
    # is skipped — the step goes straight to grounder fallback (spec FR-004).
    direct_fallback_only: bool = False
    # Design §11 anchor_texts (kept for the design-level contract) plus the
    # additive positioned anchors used for offset matching.
    anchor_texts: list[str] = Field(default_factory=list)
    anchors: list[ReplayAnchor] = Field(default_factory=list)
    # Recorded target_region in original-frame pixels (at the recorded
    # resolution — page_fingerprint.resolution).
    bbox: BBox | None = None
    # bbox normalized by the recorded resolution ([0,1] ratios). Direct use
    # is same-resolution only (spec Clarification 3); stored normalized so a
    # future cross-resolution feature needs no schema migration.
    normalized_bbox: NormalizedBBox | None = None
    # Frozen verification spec snapshot from record time — replay verifies
    # against this, not the (possibly edited) testcase (spec FR-006/US2-5).
    expected: VerificationSpec
    success_count: int = 0
    failure_count: int = 0
    version: int = Field(ge=1)

    @model_validator(mode="after")
    def _mouse_needs_geometry(self) -> ReplayStep:
        if self.preferred_method == "mouse" and not self.direct_fallback_only:
            if self.bbox is None or self.normalized_bbox is None:
                raise ValueError(
                    "a mouse ReplayStep without direct_fallback_only requires "
                    "bbox and normalized_bbox"
                )
        return self


class ReplayScript(BaseModel):
    """Ordered ReplayStep list for one test case version (spec FR-001)."""

    script_id: str
    test_case_id: str
    version: int = Field(ge=1)
    # Exploration run that produced this script (provenance).
    source_run_id: str
    created_at: datetime | None = None
    steps: list[ReplayStep] = Field(default_factory=list)

    @model_validator(mode="after")
    def _steps_ordered(self) -> ReplayScript:
        for i, step in enumerate(self.steps):
            if step.order_index != i:
                raise ValueError(
                    f"steps[{i}] has order_index={step.order_index}; script "
                    "steps must be contiguous and ordered from 0"
                )
        return self


class ReplayPatch(BaseModel):
    """Self-heal candidate produced by a successful replay fallback
    (design §11 ReplayPatch, ADR-005: never auto-applied — spec FR-009)."""

    patch_id: str
    script_id: str
    replay_step_id: str
    old_version: int
    proposed_version: int
    # Generic target evidence dicts (no business vocabulary): recorded
    # template/bbox/anchors vs. the grounder-resolved replacement.
    old_target: dict = Field(default_factory=dict)
    new_target: dict = Field(default_factory=dict)
    reason: str
    # Safe-frame evidence paths (pre-fallback observation / post-verify).
    before_image: str | None = None
    after_image: str | None = None
    verification_evidence: list[str] = Field(default_factory=list)
    status: ReplayPatchStatus = "pending"
    created_at: datetime | None = None


class ReplayStepAudit(BaseModel):
    """Iteration-level audit of one replay attempt (spec FR-012)."""

    replay_step_id: str
    script_version: int
    locate_method: ReplayLocateMethod
    page_similarity: float = 0.0
    template_score: float | None = None
    # Set when this (fallback) attempt generated a pending patch.
    patch_id: str | None = None


def normalize_bbox(bbox: BBox, resolution: tuple[int, int]) -> NormalizedBBox:
    """Normalize a pixel bbox by the frame resolution (record time)."""
    w, h = resolution
    if w <= 0 or h <= 0:
        raise ValueError(f"invalid resolution {resolution!r}")
    x1, y1, x2, y2 = bbox
    return (x1 / w, y1 / h, x2 / w, y2 / h)
