"""PlannerProvider / GrounderProvider Protocols + factory (FR-046, research.md §13)."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, field_validator, model_validator

from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.grounding import GroundingResult
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.verification import VerificationResult, VerificationSpec
from vnc_agent.runtime.exceptions import ProviderContractError

# Models sometimes emit near-synonyms; coerce before Literal validation.
_VISION_ANSWER_ALIASES: dict[str, Literal["passed", "failed", "uncertain"]] = {
    "passed": "passed",
    "pass": "passed",
    "true": "passed",
    "yes": "passed",
    "ok": "passed",
    "failed": "failed",
    "fail": "failed",
    "false": "failed",
    "no": "failed",
    "ng": "failed",
    "not_passed": "failed",
    "not-passed": "failed",
    "notpassed": "failed",
    "uncertain": "uncertain",
    "unknown": "uncertain",
    "unsure": "uncertain",
}


class PlannerRequest(BaseModel):
    step_intent: str
    expected: VerificationSpec | dict[str, Any]
    structured_screen: StructuredScreen | dict[str, Any]
    iteration_index: int = 0
    remaining_iteration_budget: int = 0
    previous_verification_result: VerificationResult | dict[str, Any] | None = None
    recent_step_summaries: list[str] = Field(default_factory=list)
    risk_policy: dict[str, Any] = Field(default_factory=lambda: {"max_risk_level": "low"})


class PlannerResponse(BaseModel):
    task_completed_hint: bool = False
    semantic_action: SemanticAction
    needs_more_observation: bool = False


class VisionUnderstandingRequest(BaseModel):
    mode: Literal["describe", "answer_question"]
    image_ref: str
    structured_screen_hint: dict[str, Any] | None = None
    question: str | None = None

    @model_validator(mode="after")
    def mode_fields(self) -> VisionUnderstandingRequest:
        if self.mode == "answer_question" and not self.question:
            raise ValueError("question is required when mode=answer_question")
        if self.mode == "describe" and self.question is not None:
            raise ValueError("question must be null when mode=describe")
        return self


class VisionUnderstandingResponse(BaseModel):
    mode: Literal["describe", "answer_question"]
    description: str | None = None
    answer: Literal["passed", "failed", "uncertain"] | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    reason: str = ""
    model_name: str = ""

    @field_validator("answer", mode="before")
    @classmethod
    def coerce_answer_aliases(cls, value: Any) -> Any:
        if value is None or not isinstance(value, str):
            return value
        key = value.strip().lower().replace(" ", "_")
        if key in _VISION_ANSWER_ALIASES:
            return _VISION_ANSWER_ALIASES[key]
        # Unknown free-text from models → fail-safe uncertain (do not crash the run).
        if key:
            return "uncertain"
        return value

    @model_validator(mode="after")
    def mode_fields(self) -> VisionUnderstandingResponse:
        if self.mode == "describe" and self.description is None:
            raise ValueError("description required for mode=describe")
        if self.mode == "answer_question" and self.answer is None:
            raise ValueError("answer required for mode=answer_question")
        return self


class GroundingRequest(BaseModel):
    image_ref: str
    crop_offset: tuple[int, int] = (0, 0)
    target: dict[str, Any]
    resolution: tuple[int, int] | None = None
    ocr_candidates: list[dict[str, Any]] = Field(default_factory=list)
    template_candidates: list[dict[str, Any]] = Field(default_factory=list)


@runtime_checkable
class PlannerProvider(Protocol):
    async def plan(self, request: PlannerRequest) -> PlannerResponse: ...

    async def describe_screen(
        self, request: VisionUnderstandingRequest
    ) -> VisionUnderstandingResponse: ...


@runtime_checkable
class GrounderProvider(Protocol):
    async def ground(self, request: GroundingRequest) -> GroundingResult: ...


def validate_planner(impl: object) -> PlannerProvider:
    if not isinstance(impl, PlannerProvider):
        raise ProviderContractError(
            f"{type(impl).__name__} does not implement PlannerProvider "
            "(requires plan + describe_screen)"
        )
    return impl  # type: ignore[return-value]


def validate_grounder(impl: object) -> GrounderProvider:
    if not isinstance(impl, GrounderProvider):
        raise ProviderContractError(
            f"{type(impl).__name__} does not implement GrounderProvider (requires ground)"
        )
    return impl  # type: ignore[return-value]


def build_planner(models_cfg: Any) -> PlannerProvider:
    from vnc_agent.models.planner_client import HttpPlannerClient

    client = HttpPlannerClient(models_cfg.planner)
    return validate_planner(client)


def build_grounder(models_cfg: Any) -> GrounderProvider:
    from vnc_agent.models.mimo_grounder import MimoGrounderClient

    client = MimoGrounderClient(models_cfg.grounder)
    return validate_grounder(client)
