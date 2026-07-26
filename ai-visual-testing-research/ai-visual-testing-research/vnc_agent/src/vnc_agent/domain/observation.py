"""Observation / screen models (data-model.md §3, extended by feature 004 §1-4,8)."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Region(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int

    @model_validator(mode="after")
    def valid_box(self) -> Region:
        if not (self.x1 < self.x2 and self.y1 < self.y2):
            raise ValueError("Region must satisfy x1<x2 and y1<y2")
        return self

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)

    def contains_point(self, x: int, y: int) -> bool:
        return self.x1 <= x < self.x2 and self.y1 <= y < self.y2

    def center(self) -> tuple[int, int]:
        return ((self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2)


class CaptureScope(BaseModel):
    """Strict spatial + safety boundary for one capture (data-model.md §1)."""

    capture_kind: Literal["full_screen", "roi"]
    x: int
    y: int
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    resolution: tuple[int, int]
    pixel_format: str
    mask_identity: str
    private_persistence_allowed: bool


def scope_identity(scope: CaptureScope) -> str:
    """Stable canonical hash of `scope` fields only — no step id/timestamp."""
    parts = [
        scope.capture_kind,
        str(scope.x),
        str(scope.y),
        str(scope.width),
        str(scope.height),
        f"{scope.resolution[0]}x{scope.resolution[1]}",
        scope.pixel_format,
        scope.mask_identity,
        str(scope.private_persistence_allowed),
    ]
    preimage = "scope-identity-v1|" + "|".join(parts)
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


class PhysicalImageRef(BaseModel):
    """One actually-persisted screenshot file (data-model.md §3)."""

    physical_image_id: str
    owner_frame_id: str
    artifact_bundle_id: str
    purpose: Literal["safe_evidence", "private_model", "report_copy"]
    path: str
    byte_size: int = Field(ge=0)
    artifact_sha256: str
    content_hash: str | None
    mask_identity: str
    created_at: datetime


class OptimizationError(BaseModel):
    """A non-fatal optimization-path failure (data-model.md §8)."""

    stage: Literal["decode", "pixel_hash", "pixel_compare", "cache_get", "cache_put"]
    error_type: str
    message: str
    occurred_at: datetime
    fallback: Literal["unique_full_analysis", "cache_miss_full_analysis", "capture_failed"]


class ScreenFrame(BaseModel):
    id: str
    run_id: str
    vnc_session_id: str
    step_id: str | None = None
    capture_sequence: int
    capture_source: Literal[
        "observation",
        "stability_wait",
        "retry",
        "recovery",
        "post_action_verification",
        # Feature 022: quick pre-execution re-capture guarding a mouse action
        # against a stale observation frame (stale-frame check).
        "pre_click_guard",
    ]
    timestamp: datetime
    scope: CaptureScope
    content_hash: str | None
    deduplicated: bool
    duplicate_of_frame_id: str | None
    comparison_available: bool
    changed_since_last: bool | None
    safe_image: PhysicalImageRef
    model_image: PhysicalImageRef | None = None
    optimization_errors: list[OptimizationError] = Field(default_factory=list)
    # Feature 004 (report-contract.md `frames[]`): mirrors the StructuredScreen
    # built for this frame's component cache hits — component -> source
    # frame id. Set after the fact by the pipeline once analysis completes
    # (empty at capture time, when no analysis has happened yet).
    analysis_source_refs: dict[str, str] = Field(default_factory=dict)
    width: int = 0
    height: int = 0
    crop_offset: tuple[int, int] = (0, 0)

    @model_validator(mode="after")
    def _dedup_invariants(self) -> ScreenFrame:
        if self.deduplicated:
            if self.duplicate_of_frame_id is None:
                raise ValueError("deduplicated=true requires duplicate_of_frame_id")
            if self.content_hash is None:
                raise ValueError("deduplicated=true requires a non-null content_hash")
            if self.changed_since_last is not False:
                raise ValueError("deduplicated=true requires changed_since_last=false")
        else:
            if self.duplicate_of_frame_id is not None:
                raise ValueError("deduplicated=false requires duplicate_of_frame_id=null")
        if self.safe_image.purpose != "safe_evidence":
            raise ValueError("safe_image.purpose must always be safe_evidence")
        if self.model_image is not None:
            if self.model_image.purpose not in ("safe_evidence", "private_model"):
                raise ValueError("model_image.purpose must be safe_evidence or private_model")
            if (
                self.model_image.purpose == "private_model"
                and not self.scope.private_persistence_allowed
            ):
                raise ValueError(
                    "scope.private_persistence_allowed=false forbids a private_model model_image"
                )
        return self

    @property
    def image_path(self) -> str:
        return self.safe_image.path

    @property
    def model_image_path(self) -> str:
        return self.model_image.path if self.model_image is not None else self.safe_image.path

    def path_for_model(self) -> str:
        return self.model_image_path


class OCRItem(BaseModel):
    text: str
    bbox: tuple[int, int, int, int]
    confidence: float = Field(ge=0.0, le=1.0)
    normalized_text: str = ""

    @model_validator(mode="after")
    def default_normalized(self) -> OCRItem:
        if not self.normalized_text:
            self.normalized_text = self.text.strip().lower()
        return self


class TemplateMatch(BaseModel):
    template_id: str
    bbox: tuple[int, int, int, int]
    confidence: float = Field(ge=0.0, le=1.0)


class VisionUnderstanding(BaseModel):
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    model_name: str
    raw_response_ref: str = ""


class StructuredScreen(BaseModel):
    frame_id: str
    resolution: tuple[int, int]
    captured_at: datetime
    ocr_items: list[OCRItem] = Field(default_factory=list)
    template_matches: list[TemplateMatch] = Field(default_factory=list)
    changed_since_last: bool = False
    changed_regions: list[Region] = Field(default_factory=list)
    # 002: local connected components independent of global threshold (research.md §1)
    local_blobs: list[Region] = Field(default_factory=list)
    global_diff_ratio: float = 0.0
    vision_understanding: VisionUnderstanding | None = None
    image_path: str = ""  # local / evidence (masked when configured)
    # Feature 004 (data-model.md §7): mirrors the owning ScreenFrame's dedup
    # identity; analysis_source_refs maps component -> source frame id only
    # for components actually served from the analysis cache (a hit).
    content_hash: str | None = None
    deduplicated: bool = False
    duplicate_of_frame_id: str | None = None
    comparison_available: bool = True
    # Feature 008: additional identity mirrored from the owning ScreenFrame so
    # the verification path can key/window the vision_answer cached component
    # without access to the frame itself. Defaults disable caching (guarded
    # eligibility), never produce a wrong-key hit.
    capture_sequence: int = 0
    scope_key: str = ""
    analysis_source_refs: dict[str, str] = Field(default_factory=dict)
    crop_offset: tuple[int, int] = (0, 0)
    model_image_path: str = ""  # unmasked for model API (FR-049)

    def path_for_model(self) -> str:
        return self.model_image_path or self.image_path

    def to_hint_dict(self) -> dict[str, Any]:
        return {
            "ocr_items": [i.model_dump() for i in self.ocr_items],
            "template_matches": [m.model_dump() for m in self.template_matches],
            "changed_regions": [r.model_dump() for r in self.changed_regions],
            "changed_since_last": self.changed_since_last,
        }
