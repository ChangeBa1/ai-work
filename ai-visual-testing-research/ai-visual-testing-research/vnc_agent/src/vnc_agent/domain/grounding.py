"""Grounding result models (data-model.md §5)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class GroundingCandidate(BaseModel):
    bbox: tuple[int, int, int, int]  # x1,y1,x2,y2 in original VNC pixels
    coordinate_space: Literal["pixel", "normalized_1000"] | None = None
    raw_bbox: tuple[int, int, int, int] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    label: str | None = None
    reason: str = ""

    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def is_within(self, width: int, height: int) -> bool:
        x1, y1, x2, y2 = self.bbox
        return 0 <= x1 < x2 <= width and 0 <= y1 < y2 <= height


class GroundingResult(BaseModel):
    found: bool
    candidates: list[GroundingCandidate] = Field(default_factory=list, max_length=3)
    model_name: str = ""
    raw_response_ref: str = ""
    coordinate_space_audit: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def found_consistency(self) -> GroundingResult:
        if not self.found and self.candidates:
            raise ValueError("found=false requires empty candidates list (FR-016)")
        if len(self.candidates) > 3:
            raise ValueError("candidates length must be ≤ 3 (FR-016)")
        return self


def filter_in_bounds(
    candidates: list[GroundingCandidate],
    width: int,
    height: int,
) -> list[GroundingCandidate]:
    """Drop out-of-bounds candidates before Action Policy (FR-019)."""
    return [c for c in candidates if c.is_within(width, height)]
