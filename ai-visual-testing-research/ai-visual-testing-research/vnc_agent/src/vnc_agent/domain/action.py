"""Semantic / executable action models (data-model.md §4/§6, FR-013)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from vnc_agent.domain.observation import Region

ActionType = Literal[
    "click",
    "double_click",
    "right_click",
    "type_text",
    "press_key",
    "hotkey",
    "scroll",
    "drag",
    "wait",
    "finish",
]


class TargetDescription(BaseModel):
    role: str | None = None
    text: str | None = None
    description: str = ""
    nearby_texts: list[str] = Field(default_factory=list)


class SemanticAction(BaseModel):
    """Semantic action — MUST NOT contain raw x/y coordinates (FR-013)."""

    action_id: str
    intent: str
    action_type: ActionType
    target: TargetDescription | None = None
    text_value: str | None = None
    text_value_ref: str | None = None
    keys: list[str] = Field(default_factory=list)
    # Feature 003: widened from Literal["low"] to the full Constitution
    # low/medium/high action-safety grading (research.md §4).
    risk_level: Literal["low", "medium", "high"] = "low"
    # 002: Planner may set; else classify_action_kind() fills (data-model.md §5)
    action_kind: Literal["idempotent", "non_idempotent"] | None = None
    # Feature 003 (FR-006/012/013): Planner MAY declare a closed, UI-generic
    # interaction purpose for a target independent of the step's primary
    # non-idempotent action (e.g. dismissing an overlay, scrolling to reveal
    # the real target). A declared purpose is how step-intent-consistency is
    # satisfied for such a micro-action — see execution/target_consistency.py.
    micro_action_purpose: (
        Literal["dismiss_overlay", "scroll_reveal", "refocus", "wait", "re_observe"]
        | None
    ) = None

    @model_validator(mode="before")
    @classmethod
    def reject_coords(cls, data: object) -> object:
        if isinstance(data, dict):
            forbidden = {"x", "y", "coordinates", "point", "bbox"}
            present = forbidden.intersection(data.keys())
            if present:
                raise ValueError(
                    f"SemanticAction must not contain coordinate fields: {present} (FR-013)"
                )
        return data


class ExecutableAction(BaseModel):
    method: Literal["keyboard", "mouse"]
    operation: str
    coordinates: tuple[int, int] | None = None
    keys: list[str] = Field(default_factory=list)
    text: str | None = None
    target_region: Region | None = None


class ExecutionResult(BaseModel):
    success: bool  # "sent" only, not step passed (FR-024)
    started_at: datetime
    ended_at: datetime
    timed_out: bool = False
    target_region: Region | None = None
    actual_click_point: tuple[int, int] | None = None
    error_code: str | None = None
    error_message: str | None = None
