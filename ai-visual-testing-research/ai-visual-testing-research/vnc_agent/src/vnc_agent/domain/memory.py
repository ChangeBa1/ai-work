"""Page/element memory domain models (feature 015, overall_design.md §12/§13).

Pure data structures — fingerprint *computation* lives in
``memory/fingerprint.py``, retrieval/matching in ``memory/retrieval.py`` and
persistence orchestration in ``memory/service.py``. Everything here is
business-agnostic (Constitution VI): generic pixels, text tokens and geometry.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

#: Fingerprint schema version — bump when the preimage semantics change so
#: stale fingerprints can never silently mis-compare.
FINGERPRINT_VERSION = "pfp-v1"

PageMatchLevel = Literal["high", "medium", "low", "none"]


class PageFingerprint(BaseModel):
    """Deterministic page identity (design §13): perceptual hash + normalized
    OCR keyword set + coarse OCR layout grid + resolution.

    ``phash`` is a 64-bit hex string ("" when no image was available);
    ``ocr_tokens`` and ``layout_cells`` are sorted, de-duplicated lists so two
    fingerprints built from the same inputs compare equal field-by-field.
    """

    version: str = FINGERPRINT_VERSION
    phash: str = ""
    ocr_tokens: list[str] = Field(default_factory=list)
    # Occupied cells of an 8x8 grid over the frame, "col,row" strings.
    layout_cells: list[str] = Field(default_factory=list)
    resolution: tuple[int, int]


class PageMemory(BaseModel):
    """One remembered page (design §12.1 页面记忆, MVP subset)."""

    page_id: str
    fingerprint: PageFingerprint
    resolution: tuple[int, int]
    hit_count: int = 0
    last_seen_at: datetime | None = None
    created_at: datetime | None = None


class ElementMemory(BaseModel):
    """One remembered clickable element (design §12.1 元素记忆, MVP subset)."""

    element_id: str
    page_id: str
    # Normalized semantic label of the target (same normalization as the
    # runtime's target hint: stripped text/description/intent).
    target_label: str
    # Masked-safe template crop persisted on disk; None when the template was
    # refused (mask intersection) or lost.
    template_path: str | None = None
    # Most recent successful target_region (original-frame pixels).
    bbox: tuple[int, int, int, int]
    # Nearby OCR texts at write time (anchor evidence, max 5).
    anchor_texts: list[str] = Field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    consecutive_success_count: int = 0
    last_success_at: datetime | None = None
    created_at: datetime | None = None


class MemoryLookupResult(BaseModel):
    """Result of a memory retrieval for one (screen, target_label) query.

    Public contract for feature 016's replay player (spec "016 扩展点"):
    ``level=="high"`` with a non-null ``matched_bbox`` is the only state that
    authorizes a direct click; ``level=="medium"`` (or high without a template
    confirmation) is hint-only evidence for the grounder.
    """

    level: PageMatchLevel
    page: PageMemory | None = None
    page_similarity: float = 0.0
    element: ElementMemory | None = None
    template_score: float | None = None
    # Template-match-confirmed bbox in current-frame pixels (direct-click
    # evidence); None when the neighborhood match did not reach threshold.
    matched_bbox: tuple[int, int, int, int] | None = None


class MemoryHitAudit(BaseModel):
    """Iteration-level audit of a memory direct click (spec FR-010)."""

    source: Literal["element_memory"] = "element_memory"
    element_memory_id: str
    page_memory_id: str
    target_label: str
    page_similarity: float
    template_score: float
    matched_bbox: tuple[int, int, int, int]
