"""Append-only telemetry models (data-model.md §9-11, telemetry-contract.md).

`StageMeasurement`/`CounterEvent`/`ModelCallAudit` are immutable facts that
get appended to `TestRun` and mirrored into structured logs (logging_setup.py)
by the same event object — never recomputed independently per output.
`PerformanceSummary` is derived from those events and never hand-patched to
"fix" a conservation mismatch; mismatches are recorded, not hidden.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

CANONICAL_STAGES: tuple[str, ...] = (
    "capture",
    "pixel_hash",
    "persistence",
    "OCR",
    "template",
    "vision",
    "planner",
    "grounder",
    "verification",
    "report_build",
    "report_output",
)

StageStatus = Literal["completed", "failed", "cancelled", "unavailable"]


class StageMeasurement(BaseModel):
    measurement_id: str
    run_id: str
    step_id: str | None
    frame_id: str | None
    iteration_index: int | None
    stage: str
    started_at: datetime
    duration_ms: float | None
    status: StageStatus
    actual_call: bool
    cache_hit: bool
    source_ref: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> StageMeasurement:
        if self.stage not in CANONICAL_STAGES:
            raise ValueError(
                f"unknown stage {self.stage!r}; must be one of {CANONICAL_STAGES}"
            )
        if self.status == "unavailable" and self.duration_ms is not None:
            raise ValueError(
                "status=unavailable must have duration_ms=null, never a fabricated value"
            )
        if self.status in ("completed", "failed", "cancelled") and self.duration_ms is None:
            raise ValueError(f"status={self.status} requires an actually observed duration_ms")
        if self.actual_call and self.cache_hit:
            raise ValueError("actual_call and cache_hit are mutually exclusive")
        if self.status == "completed" and (self.error_type or self.error_message):
            raise ValueError("completed status must not carry stale error_type/error_message")
        return self


CounterKind = Literal[
    "analysis_cache_hit",
    "analysis_invocation",
    "model_call",
    "model_call_skipped",
    "physical_image_written",
    "physical_write_avoided",
    "frame_dedup_decision",
    "capture_attempt_failed",
]

_REQUIRED_PAYLOAD_KEYS: dict[str, tuple[str, ...]] = {
    "analysis_cache_hit": ("component", "frame_id", "source_ref"),
    "analysis_invocation": ("component", "invocation_id", "status"),
    "model_call": ("model_role", "invocation_id", "status"),
    "model_call_skipped": ("model_role", "reason", "request_identity"),
    "physical_image_written": ("physical_image_id", "purpose", "byte_size", "frame_id"),
    "physical_write_avoided": ("frame_id", "purpose", "source_physical_id", "byte_basis"),
    "frame_dedup_decision": ("frame_id", "eligible", "deduplicated", "reason"),
    "capture_attempt_failed": (
        "run_id",
        "step_id",
        "capture_source",
        "attempt_sequence",
        "error_type",
        "measurement_id",
    ),
}


class CounterEvent(BaseModel):
    kind: str
    occurred_at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> CounterEvent:
        if self.kind not in _REQUIRED_PAYLOAD_KEYS:
            raise ValueError(f"unknown counter event kind {self.kind!r}")
        missing = [k for k in _REQUIRED_PAYLOAD_KEYS[self.kind] if k not in self.payload]
        if missing:
            raise ValueError(f"{self.kind} payload missing required keys: {missing}")
        return self


ModelRole = Literal["vision", "planner", "grounder", "verification"]
AuditOutcome = Literal["actual", "skipped"]

_FORBIDDEN_KEY_TOKENS = (
    "password",
    "api_key",
    "secret",
    "token",
    "authorization",
    "credential",
)
_FORBIDDEN_VALUE_MARKERS = ("data:image", "frames_model", "private_model", "base64,")


def _scan_for_forbidden(value: Any, path: str = "root") -> None:
    if isinstance(value, (bytes, bytearray)):
        raise ValueError(f"{path}: raw bytes are not allowed in a sanitized audit payload")
    if isinstance(value, dict):
        for k, v in value.items():
            key_l = str(k).lower()
            if any(tok in key_l for tok in _FORBIDDEN_KEY_TOKENS):
                raise ValueError(f"{path}.{k}: forbidden sensitive key in sanitized audit payload")
            _scan_for_forbidden(v, f"{path}.{k}")
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            _scan_for_forbidden(v, f"{path}[{i}]")
    elif isinstance(value, str):
        low = value.lower()
        for marker in _FORBIDDEN_VALUE_MARKERS:
            if marker in low:
                raise ValueError(f"{path}: forbidden marker '{marker}' in sanitized audit payload")


class ModelCallAudit(BaseModel):
    audit_id: str
    run_id: str
    step_id: str | None
    frame_id: str | None
    iteration_index: int | None
    model_role: ModelRole
    request_identity: str
    context_identity: str
    sanitized_request: dict[str, Any] = Field(default_factory=dict)
    sanitized_response: dict[str, Any] = Field(default_factory=dict)
    outcome: AuditOutcome
    source_ref: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> ModelCallAudit:
        _scan_for_forbidden(self.sanitized_request, "sanitized_request")
        _scan_for_forbidden(self.sanitized_response, "sanitized_response")
        if self.outcome == "skipped" and not self.reason:
            raise ValueError("outcome=skipped requires a reason")
        return self


Completeness = Literal["complete", "partial"]


class PerformanceSummary(BaseModel):
    total_capture_count: int
    unique_frame_count: int
    duplicate_frame_count: int
    dedup_ratio: float | None
    physical_image_count: int
    physical_images_by_purpose: dict[str, int]
    avoided_write_count: int
    avoided_write_bytes: int
    cache_hits: dict[str, int]
    analysis_invocations: dict[str, int]
    model_calls: dict[str, int]
    actual_model_call_count: int
    skipped_model_call_count: int
    stage_totals_ms: dict[str, float | None]
    completeness: Completeness
    consistency_errors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _dedup_ratio_null_iff_zero_total(self) -> PerformanceSummary:
        if self.total_capture_count == 0 and self.dedup_ratio is not None:
            raise ValueError("dedup_ratio must be null when total_capture_count == 0")
        if self.total_capture_count != 0 and self.dedup_ratio is None:
            raise ValueError("dedup_ratio must be set when total_capture_count > 0")
        return self

    def check_conservation(self) -> list[str]:
        """Return conservation violations without mutating self (never auto-fixed)."""
        errors: list[str] = []
        if self.unique_frame_count + self.duplicate_frame_count != self.total_capture_count:
            errors.append(
                "unique_frame_count + duplicate_frame_count != total_capture_count: "
                f"{self.unique_frame_count} + {self.duplicate_frame_count} != "
                f"{self.total_capture_count}"
            )
        return errors
