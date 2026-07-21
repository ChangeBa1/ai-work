"""ActionEffect models (data-model.md §3) — independent of StepVerificationResult."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from vnc_agent.domain.observation import Region

ActionEffectStatus = Literal[
    "no_effect",
    "expected_effect",
    "unexpected_effect",
    "effect_uncertain",
]

ErrorPopupSignal = Literal["ocr_keyword", "template", "none"]


class ActionEffectEvidence(BaseModel):
    global_diff_ratio: float = 0.0
    local_blobs: list[Region] = Field(default_factory=list)
    ocr_added: list[str] = Field(default_factory=list)
    ocr_removed: list[str] = Field(default_factory=list)
    template_added: list[str] = Field(default_factory=list)
    template_removed: list[str] = Field(default_factory=list)
    structured_state_changed: bool = False
    error_popup_signal: ErrorPopupSignal = "none"


class ActionEffect(BaseModel):
    status: ActionEffectStatus
    evidence: ActionEffectEvidence = Field(default_factory=ActionEffectEvidence)
    reason: str = ""
