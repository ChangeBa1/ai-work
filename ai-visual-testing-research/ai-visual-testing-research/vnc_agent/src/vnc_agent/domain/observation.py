"""Observation / screen models (data-model.md §3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


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


class ScreenFrame(BaseModel):
    id: str
    run_id: str
    step_id: str | None = None
    image_path: str  # local persistence path (masked when mask_regions configured)
    width: int
    height: int
    timestamp: datetime
    crop_offset: tuple[int, int] = (0, 0)
    # Unmasked path for Planner/Grounder only (FR-049); empty → same as image_path
    model_image_path: str = ""

    def path_for_model(self) -> str:
        return self.model_image_path or self.image_path


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
