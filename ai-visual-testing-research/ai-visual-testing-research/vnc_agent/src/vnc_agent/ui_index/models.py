"""Bundle content models (data-model.md §1) — wire-format aligned."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)

BundleCoordinateSpace = Literal["design_pixels", "normalized_1000"]
ConfidenceLevel = Literal[
    "confirmed",
    "statically_inferred",
    "visually_confirmed",
    "requires_runtime_verification",
]
NeighborDirection = Literal["up", "down", "left", "right", "near"]
RegionName = Literal[
    "header",
    "toolbar",
    "sidebar_left",
    "sidebar_right",
    "body",
    "footer",
    "statusbar",
    "modal",
    "unknown",
]
TransitionType = Literal["modal", "replace", "overlay", "state_change"]
GuardCondition = Literal["visible", "enabled", "hidden", "disabled"]
DiagnosticCategory = Literal[
    "unconfirmed_screen",
    "unconfirmed_element",
    "dynamic_element",
    "uncertain_transition",
    "unparsed_text",
    "requires_runtime_calibration",
]

_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_SCHEMA_VERSION_RE = re.compile(r"^\d+\.\d+$")


class Confidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    level: ConfidenceLevel
    score: float | None = None

    @field_validator("score")
    @classmethod
    def _score_range(cls, v: float | None) -> float | None:
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError("score must be in [0.0, 1.0]")
        return v


class NormalizedBounds(BaseModel):
    model_config = ConfigDict(extra="allow")

    coordinate_space: Literal["normalized_1000"]
    x1: int
    y1: int
    x2: int
    y2: int

    @model_validator(mode="after")
    def _ordering_and_range(self) -> NormalizedBounds:
        for name, val in (
            ("x1", self.x1),
            ("y1", self.y1),
            ("x2", self.x2),
            ("y2", self.y2),
        ):
            if not (0 <= val <= 1000):
                raise ValueError(f"{name} must be in [0, 1000]")
        if not (self.x1 < self.x2 and self.y1 < self.y2):
            raise ValueError("bounds require x1 < x2 and y1 < y2")
        return self


class NeighborRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    direction: NeighborDirection
    element_id: str


def _check_stable_id(v: str) -> str:
    if not _ID_RE.match(v):
        raise ValueError(f"invalid id format: {v!r}")
    return v


def _check_snake(v: str) -> str:
    if not _SNAKE_RE.match(v):
        raise ValueError(f"must be snake_case: {v!r}")
    return v


class Screen(BaseModel):
    model_config = ConfigDict(extra="allow")

    screen_id: str
    name: str
    screen_type: str
    visible_titles: list[str]
    aliases: list[str]
    parent_screen_id: str | None = None
    source_evidence: str | None = None
    confidence: Confidence
    metadata: dict[str, Any] | None = None

    @field_validator("screen_id")
    @classmethod
    def _id(cls, v: str) -> str:
        return _check_stable_id(v)

    @field_validator("screen_type")
    @classmethod
    def _stype(cls, v: str) -> str:
        return _check_snake(v)


class Element(BaseModel):
    model_config = ConfigDict(extra="allow")

    element_id: str
    screen_id: str
    parent_element_id: str | None = None
    name: str
    role: str
    visible_texts: list[str]
    aliases: list[str]
    supported_actions: list[str]
    state_conditions: dict[str, Any] = Field(default_factory=dict)
    region: RegionName = "unknown"
    normalized_bounds: NormalizedBounds | None = None
    anchors: list[str] = Field(default_factory=list)
    neighbors: list[NeighborRef] = Field(default_factory=list)
    expected_effects: list[str] = Field(default_factory=list)
    source_evidence: str | None = None
    confidence: Confidence
    metadata: dict[str, Any] | None = None

    @field_validator("element_id")
    @classmethod
    def _id(cls, v: str) -> str:
        return _check_stable_id(v)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        return _check_snake(v)

    @field_validator("supported_actions")
    @classmethod
    def _actions(cls, v: list[str]) -> list[str]:
        return [_check_snake(a) for a in v]


class ElementGuardRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    element_id: str
    condition: GuardCondition


class NamedGuardRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = None


GuardRef = Annotated[
    ElementGuardRef | NamedGuardRef,
    Field(union_mode="smart"),
]
_GUARD_ADAPTER: TypeAdapter[ElementGuardRef | NamedGuardRef] = TypeAdapter(GuardRef)


class Transition(BaseModel):
    model_config = ConfigDict(extra="allow")

    transition_id: str
    from_screen_id: str
    trigger_element_id: str
    trigger_action: str
    guards: list[ElementGuardRef | NamedGuardRef] = Field(default_factory=list)
    to_screen_id: str
    transition_type: TransitionType
    expected_visible: list[str] = Field(default_factory=list)
    expected_hidden: list[str] = Field(default_factory=list)
    expected_state_changes: list[str] = Field(default_factory=list)
    source_evidence: str | None = None
    confidence: Confidence

    @field_validator("trigger_action")
    @classmethod
    def _action(cls, v: str) -> str:
        return _check_snake(v)

    @field_validator("guards", mode="before")
    @classmethod
    def _parse_guards(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return v
        return [_GUARD_ADAPTER.validate_python(item) for item in v]


class TransitionStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    transition_id: str


class ElementActionStep(BaseModel):
    model_config = ConfigDict(extra="allow")

    element_id: str
    action: str

    @field_validator("action")
    @classmethod
    def _action(cls, v: str) -> str:
        return _check_snake(v)


class FlowStep(BaseModel):
    """Discriminated: exactly one of transition_id OR (element_id+action)."""

    model_config = ConfigDict(extra="allow")

    transition_id: str | None = None
    element_id: str | None = None
    action: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> FlowStep:
        has_tr = self.transition_id is not None
        has_el = self.element_id is not None or self.action is not None
        if has_tr and has_el:
            raise ValueError("FlowStep must not provide both transition_id and element_id/action")
        if has_tr:
            return self
        if self.element_id is not None and self.action is not None:
            _check_snake(self.action)
            return self
        raise ValueError("FlowStep requires transition_id or both element_id and action")


class Flow(BaseModel):
    model_config = ConfigDict(extra="allow")

    flow_id: str
    name: str
    start_screen_id: str
    steps: list[FlowStep] = Field(min_length=1)
    completion_screen_id: str
    preconditions: list[ElementGuardRef | NamedGuardRef] = Field(default_factory=list)
    confidence: Confidence

    @field_validator("preconditions", mode="before")
    @classmethod
    def _parse_pre(cls, v: Any) -> Any:
        if not isinstance(v, list):
            return v
        return [_GUARD_ADAPTER.validate_python(item) for item in v]


class TargetRef(BaseModel):
    model_config = ConfigDict(extra="allow")

    screen_id: str | None = None
    element_id: str | None = None
    transition_id: str | None = None


class Diagnostic(BaseModel):
    model_config = ConfigDict(extra="allow")

    diagnostic_id: str
    category: DiagnosticCategory
    target_ref: TargetRef | None = None
    reason: str
    confidence: Confidence
    source_evidence: str | None = None

    @model_validator(mode="after")
    def _no_confirmed(self) -> Diagnostic:
        if self.confidence.level == "confirmed":
            raise ValueError("Diagnostic.confidence.level must not be confirmed")
        return self


class ProducerInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    version: str


class Viewport(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ContentFileEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    required: bool
    sha256: str | None = None
    record_count: int | None = None


class BundleManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    schema_version: str
    bundle_id: str
    project_id: str
    generated_at: datetime
    producer: ProducerInfo
    source_revision: str
    frameworks: list[str]
    coordinate_spaces: list[BundleCoordinateSpace] = Field(min_length=1)
    default_viewports: list[Viewport] = Field(default_factory=list)
    content_files: dict[str, ContentFileEntry]
    metadata: dict[str, Any] | None = None

    @field_validator("schema_version")
    @classmethod
    def _sv(cls, v: str) -> str:
        if not _SCHEMA_VERSION_RE.match(v):
            raise ValueError("schema_version must match MAJOR.MINOR")
        return v
