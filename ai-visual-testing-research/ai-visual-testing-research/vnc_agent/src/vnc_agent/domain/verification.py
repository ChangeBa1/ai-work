"""Wait / verification models (data-model.md §7)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from vnc_agent.domain.observation import Region

ConditionType = Literal[
    "text_appears",
    "text_disappears",
    "template_appears",
    "template_disappears",
    "region_changed",
    "screen_changed",
    "visual_question",
]

VerificationStatus = Literal["passed", "failed", "uncertain"]
WaitEndReason = Literal[
    "stable", "expected_condition", "timeout", "vnc_error", "cancelled"
]


class WaitResult(BaseModel):
    waited_ms: int = Field(ge=0)
    stable: bool
    end_reason: WaitEndReason


class VerificationCondition(BaseModel):
    type: ConditionType
    value: str = ""
    region: Region | None = None

    @model_validator(mode="before")
    @classmethod
    def coerce_region(cls, data: object) -> object:
        if isinstance(data, dict) and "region" in data and data["region"] is not None:
            r = data["region"]
            if isinstance(r, (list, tuple)) and len(r) == 4:
                data = {**data, "region": Region(x1=r[0], y1=r[1], x2=r[2], y2=r[3])}
        return data


class VerificationSpec(BaseModel):
    operator: Literal["all", "any"]
    conditions: list[VerificationCondition] = Field(min_length=1)
    timeout_seconds: int | None = Field(default=None, ge=1)


class VerificationResult(BaseModel):
    status: VerificationStatus
    evidence_refs: list[str] = Field(default_factory=list)
    matched_conditions: list[str] = Field(default_factory=list)
    failed_conditions: list[str] = Field(default_factory=list)
    uncertain_conditions: list[str] = Field(default_factory=list)
    reason: str = ""
    # 002: StepVerificationResult role (data-model.md §4) — independent of ActionEffect
    weak_assertion_warning: bool = False
    basis: Literal["business_assertion", "action_effect_only", "mixed"] = (
        "business_assertion"
    )


def aggregate_conditions(
    operator: Literal["all", "any"],
    statuses: list[VerificationStatus],
) -> VerificationStatus:
    """Compound assertion aggregation with uncertain contagion (FR-033)."""
    if not statuses:
        return "uncertain"
    if operator == "all":
        if any(s == "failed" for s in statuses):
            return "failed"
        if any(s == "uncertain" for s in statuses):
            return "uncertain"
        return "passed"
    # any
    if any(s == "passed" for s in statuses):
        return "passed"
    if any(s == "uncertain" for s in statuses):
        return "uncertain"
    return "failed"
