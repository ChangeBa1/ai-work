"""TestCase / TestStep models and YAML loader (data-model.md §1–2, FR-001~004)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from vnc_agent.domain.action import (
    BATCH_REPEAT_COUNT_MAX,
    BATCH_REPEAT_COUNT_MIN,
    BATCH_REPEAT_INTERVAL_MS_MAX,
    BATCH_REPEAT_INTERVAL_MS_MIN,
)
from vnc_agent.domain.reporting_tags import ActionTagRule
from vnc_agent.domain.run import RunPrecondition
from vnc_agent.domain.verification import VerificationSpec
from vnc_agent.drivers.key_mapping import is_batch_repeatable_key

# Weak action-effect evidence only (data-model.md §2) — cannot alone satisfy business mode
_WEAK_CONDITION_TYPES = frozenset({"screen_changed", "region_changed"})


class BatchRepeatKeyDeclaration(BaseModel):
    """Feature 005 (FR-001/005/006/007): author-declared batch repeat key
    press — the test-case-authoring surface for TestStep.batch_repeat_key."""

    key: str
    count: int
    interval_ms: int | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> BatchRepeatKeyDeclaration:
        if not is_batch_repeatable_key(self.key):
            raise ValueError(
                f"batch_repeat_key.key {self.key!r} is not a recognized non-modifier "
                "key (FR-005)"
            )
        if not (BATCH_REPEAT_COUNT_MIN <= self.count <= BATCH_REPEAT_COUNT_MAX):
            raise ValueError(
                f"batch_repeat_key.count must be between {BATCH_REPEAT_COUNT_MIN} and "
                f"{BATCH_REPEAT_COUNT_MAX} (FR-006), got {self.count!r}"
            )
        if self.interval_ms is not None and not (
            BATCH_REPEAT_INTERVAL_MS_MIN <= self.interval_ms <= BATCH_REPEAT_INTERVAL_MS_MAX
        ):
            raise ValueError(
                f"batch_repeat_key.interval_ms must be between "
                f"{BATCH_REPEAT_INTERVAL_MS_MIN} and {BATCH_REPEAT_INTERVAL_MS_MAX} "
                f"(FR-007), got {self.interval_ms!r}"
            )
        return self


class TestStep(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    expected: VerificationSpec
    timeout_seconds: int | None = Field(default=None, ge=1)
    max_retries: int = Field(default=3, ge=0)
    status: Literal["pending", "running", "passed", "failed", "cancelled"] = "pending"
    # 002: omitted → load accepts; runtime weak-assertion cap (FR-025/026)
    verification_mode: Literal["business", "effect_only"] | None = None
    # Feature 005: optional declarative batch repeat key press. When set,
    # the runtime bypasses the Planner for this step and constructs the
    # action deterministically from this declaration (FR-001/FR-014).
    batch_repeat_key: BatchRepeatKeyDeclaration | None = None
    # Feature 024 (FR-013): the ONLY switch that activates pre-grounding
    # sub-window enhancement for this step. Value = an app-perception plugin
    # (profile) name meaning "this step operates inside that sub-window", or
    # "none". Omitted is equivalent to "none": a frame containing a known
    # sub-window never enhances a step that does not ask for it.
    # Generic field — the value space is plugin names, not business terms.
    perception_scope: str | None = None
    # Feature 024: name of the control (from the profile's source_geometry)
    # this step targets. Naming it rather than describing it is what makes
    # text-less controls reachable at all — a bare input box has nothing for
    # OCR or a model to match on. Requires perception_scope; ignored without.
    perception_target: str | None = None


class TestCase(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    # Feature 016 (FR-011, additive): "replay" runs the latest recorded
    # ReplayScript for this test case (design §8.1/§10.2); "explicit"
    # semantics are unchanged.
    mode: Literal["explicit", "replay"]
    steps: list[TestStep] = Field(min_length=1)
    timeout_seconds: int = Field(default=600, ge=1)
    # Feature 003 (FR-024): optional declarative run-start precondition.
    # MUST NOT be a fixed business schema — core only defines the generic
    # named-fact container; concrete keys/assertions are testcase-supplied.
    precondition: RunPrecondition | None = None
    # Feature 003 (FR-027): optional declarative action-audit tags, merged
    # with AgentConfig.reporting.action_tags at report time (testcase
    # declarations take priority on a matching tag name).
    action_tags: list[ActionTagRule] = Field(default_factory=list)
    # Feature 024 (FR-013): optional allow-list of app-perception plugin
    # names usable by this test case. When non-empty, every step's
    # `perception_scope` must be a member — which turns a typo into a
    # load-time error instead of a silent no-enhancement run.
    perception_plugins: list[str] = Field(default_factory=list)

    @field_validator("mode")
    @classmethod
    def mode_must_be_known(cls, v: str) -> str:
        # Feature 016: "replay" joins "explicit" (FR-011); anything else is
        # still rejected with the original FR-004 message shape.
        if v not in ("explicit", "replay"):
            raise ValueError("mode must be 'explicit' or 'replay' (FR-004)")
        return v

    @model_validator(mode="after")
    def steps_non_empty(self) -> TestCase:
        if not self.steps:
            raise ValueError("steps must contain at least one TestStep")
        return self


class FieldValidationError(Exception):
    """Field-level validation failure for test-case loading (FR-003)."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        self.errors = errors
        lines = [f"{e['path']}: {e['reason']}" for e in errors]
        super().__init__("Test case validation failed:\n" + "\n".join(lines))


def _collect_pydantic_errors(exc: Exception) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if hasattr(exc, "errors"):
        for err in exc.errors():  # type: ignore[attr-defined]
            loc = ".".join(str(x) for x in err.get("loc", ()))
            errors.append({"path": loc or "<root>", "reason": err.get("msg", str(err))})
    else:
        errors.append({"path": "<root>", "reason": str(exc)})
    return errors


PERCEPTION_SCOPE_OFF = "none"


def _validate_perception_scopes(
    tc: TestCase, known_plugins: set[str] | None
) -> list[dict[str, str]]:
    """Feature 024 (FR-013): a declared scope must name a real plugin.

    Checked against the test case's own allow-list when it declares one, and
    against the registry when the caller supplies it. Catching this at load
    time is the point: a typo would otherwise degrade silently into "no
    enhancement", which looks identical to a correct undeclared step.
    """
    errors: list[dict[str, str]] = []
    allowed = set(tc.perception_plugins)
    for i, step in enumerate(tc.steps):
        scope = step.perception_scope
        if scope is None or scope == PERCEPTION_SCOPE_OFF:
            continue
        if allowed and scope not in allowed:
            errors.append(
                {
                    "path": f"steps[{i}].perception_scope",
                    "reason": (
                        f"{scope!r} is not in this test case's perception_plugins "
                        f"allow-list {sorted(allowed)} (FR-013)"
                    ),
                }
            )
            continue
        if known_plugins is not None and scope not in known_plugins:
            errors.append(
                {
                    "path": f"steps[{i}].perception_scope",
                    "reason": (
                        f"unknown app-perception plugin {scope!r}; "
                        f"registered: {sorted(known_plugins) or '<none>'} (FR-013)"
                    ),
                }
            )
    for i, name in enumerate(tc.perception_plugins):
        if known_plugins is not None and name not in known_plugins:
            errors.append(
                {
                    "path": f"perception_plugins[{i}]",
                    "reason": (
                        f"unknown app-perception plugin {name!r}; "
                        f"registered: {sorted(known_plugins) or '<none>'} (FR-013)"
                    ),
                }
            )
    return errors


def load_test_case(
    path: str | Path, *, known_plugins: set[str] | None = None
) -> TestCase:
    """Load and validate a YAML test case. Raises FieldValidationError with field paths.

    ``known_plugins`` (feature 024) enables registry-backed validation of
    ``perception_scope``; omitted keeps the pre-024 behavior.
    """
    path = Path(path)
    if not path.exists():
        raise FieldValidationError(
            [{"path": str(path), "reason": f"file not found: {path}"}]
        )
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise FieldValidationError(
            [{"path": str(path), "reason": f"YAML parse error: {e}"}]
        ) from e

    if raw is None or not isinstance(raw, dict):
        raise FieldValidationError(
            [{"path": "<root>", "reason": "test case root must be a mapping/object"}]
        )

    # Pre-check required top-level fields for clearer messages
    required = ["id", "name", "target_id", "mode", "steps"]
    missing = [k for k in required if k not in raw]
    if missing:
        raise FieldValidationError(
            [{"path": k, "reason": "required field missing"} for k in missing]
        )

    if raw.get("mode") not in ("explicit", "replay"):
        raise FieldValidationError(
            [
                {
                    "path": "mode",
                    "reason": (
                        f"must be 'explicit' or 'replay', got {raw.get('mode')!r} "
                        "(FR-004)"
                    ),
                }
            ]
        )

    try:
        tc = TestCase.model_validate(raw)
    except Exception as e:
        raise FieldValidationError(_collect_pydantic_errors(e)) from e

    # FR-008: explicit business mode requires at least one non-weak business assertion
    load_errors: list[dict[str, str]] = []
    for i, step in enumerate(tc.steps):
        if step.verification_mode != "business":
            continue
        conditions = step.expected.conditions
        has_business = any(c.type not in _WEAK_CONDITION_TYPES for c in conditions)
        if not has_business:
            load_errors.append(
                {
                    "path": f"steps[{i}].expected.conditions",
                    "reason": (
                        "business 模式下必须至少包含一个业务结果断言"
                        "（text_appears/text_disappears/template_appears/"
                        "template_disappears/visual_question 等），"
                        "当前仅含 screen_changed/region_changed（FR-008）"
                    ),
                }
            )
    # Feature 024 (FR-013): declared perception scopes must resolve.
    load_errors.extend(_validate_perception_scopes(tc, known_plugins))

    if load_errors:
        raise FieldValidationError(load_errors)

    return tc
