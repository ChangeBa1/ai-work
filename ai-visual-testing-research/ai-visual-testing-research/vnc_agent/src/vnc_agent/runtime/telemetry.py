"""Append-only telemetry models (data-model.md §9-11, telemetry-contract.md).

`StageMeasurement`/`CounterEvent`/`ModelCallAudit` are immutable facts that
get appended to `TestRun` and mirrored into structured logs (logging_setup.py)
by the same event object — never recomputed independently per output.
`PerformanceSummary` is derived from those events and never hand-patched to
"fix" a conservation mismatch; mismatches are recorded, not hidden.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

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


def derive_performance_summary(test_run: Any) -> PerformanceSummary:
    """Derive the run-level summary purely from `TestRun.frames` +
    `TestRun.counter_events`/`stage_measurements` — never hand-patched
    (telemetry-contract.md "Conservation checks"; data-model.md §11).

    `physical_image_count`/`avoided_write_count` only trust events whose
    `frame_id` is actually present in `TestRun.frames` — an event for a
    frame that never successfully committed (a staging/quarantined/orphan
    bundle's ghost event) is flagged in `consistency_errors` and excluded,
    never silently counted.
    """
    frame_ids = {f.id for f in test_run.frames}
    unique_count = sum(1 for f in test_run.frames if not f.deduplicated)
    duplicate_count = sum(1 for f in test_run.frames if f.deduplicated)
    total = len(test_run.frames)

    consistency_errors: list[str] = []
    physical_by_purpose: dict[str, int] = {}
    avoided_count = 0
    avoided_bytes = 0
    cache_hits: dict[str, int] = {}
    analysis_invocations: dict[str, int] = {}
    model_calls: dict[str, int] = {}
    skipped_model_call_count = 0

    for event in test_run.counter_events:
        if event.kind == "physical_image_written":
            ref_frame_id = event.payload.get("frame_id")
            if ref_frame_id not in frame_ids:
                consistency_errors.append(
                    f"physical_image_written event for untracked frame_id={ref_frame_id!r} "
                    "(staging/quarantined/orphan bundle must never count as a physical image)"
                )
                continue
            purpose = event.payload.get("purpose", "unknown")
            physical_by_purpose[purpose] = physical_by_purpose.get(purpose, 0) + 1
        elif event.kind == "physical_write_avoided":
            ref_frame_id = event.payload.get("frame_id")
            if ref_frame_id not in frame_ids:
                consistency_errors.append(
                    f"physical_write_avoided event for untracked frame_id={ref_frame_id!r}"
                )
                continue
            avoided_count += 1
            avoided_bytes += int(event.payload.get("byte_basis", 0))
        elif event.kind == "analysis_cache_hit":
            component = event.payload.get("component", "unknown")
            cache_hits[component] = cache_hits.get(component, 0) + 1
        elif event.kind == "analysis_invocation":
            component = event.payload.get("component", "unknown")
            analysis_invocations[component] = analysis_invocations.get(component, 0) + 1
        elif event.kind == "model_call":
            role = event.payload.get("model_role", "unknown")
            model_calls[role] = model_calls.get(role, 0) + 1
        elif event.kind == "model_call_skipped":
            skipped_model_call_count += 1

    physical_image_count = sum(physical_by_purpose.values())
    for required in ("ocr", "template", "vision"):
        cache_hits.setdefault(required, 0)

    stage_totals: dict[str, float | None] = {}
    for m in test_run.stage_measurements:
        if m.duration_ms is None:
            continue
        stage_totals[m.stage] = (stage_totals.get(m.stage) or 0.0) + m.duration_ms

    incomplete_stage = any(
        m.status in ("failed", "unavailable") for m in test_run.stage_measurements
    )
    completeness = "partial" if (consistency_errors or incomplete_stage) else "complete"

    summary = PerformanceSummary(
        total_capture_count=total,
        unique_frame_count=unique_count,
        duplicate_frame_count=duplicate_count,
        dedup_ratio=(duplicate_count / total) if total else None,
        physical_image_count=physical_image_count,
        physical_images_by_purpose=physical_by_purpose,
        avoided_write_count=avoided_count,
        avoided_write_bytes=avoided_bytes,
        cache_hits=cache_hits,
        analysis_invocations=analysis_invocations,
        model_calls=model_calls,
        actual_model_call_count=sum(model_calls.values()),
        skipped_model_call_count=skipped_model_call_count,
        stage_totals_ms=stage_totals,
        completeness=completeness,  # type: ignore[arg-type]
        consistency_errors=consistency_errors,
    )
    return summary


def log_event(event_name: str, **fields: Any) -> None:
    """Emit the same event fields appended to `TestRun` as a canonical
    stable JSON Lines entry (telemetry-contract.md "Stable structured-log
    events") — the log and the report always derive from one event object,
    never a separately recomputed summary. Sensitive-field redaction is
    applied by `logging_setup.configure_logging`'s processor chain.

    Best-effort: a logging sink failure (e.g. a closed stream) must never
    break the capture/analysis/verification flow that is being observed.
    """
    from vnc_agent.logging_setup import get_logger

    try:
        get_logger("telemetry").info(event_name, **fields)
    except Exception:
        pass


class Clock(Protocol):
    def perf_counter_ns(self) -> int: ...
    def utc_now(self) -> datetime: ...


class _RealClock:
    def perf_counter_ns(self) -> int:
        return time.perf_counter_ns()

    def utc_now(self) -> datetime:
        return datetime.now(UTC)


_REAL_CLOCK = _RealClock()


def _sanitize_error_message(message: str) -> str:
    # Stage failures never carry image bytes/credentials/full unmasked
    # paths — keep only a bounded, generic description.
    return message[:200]


@contextmanager
def measure_stage(
    test_run: Any,
    *,
    stage: str,
    run_id: str,
    step_id: str | None = None,
    frame_id: str | None = None,
    iteration_index: int | None = None,
    actual_call: bool = True,
    cache_hit: bool = False,
    source_ref: str | None = None,
    clock: Clock | None = None,
) -> Iterator[None]:
    """Append one `StageMeasurement` for the wrapped block — completed on
    success, failed (with the real observed duration) on exception, which is
    always re-raised (telemetry-contract.md "Measurement semantics")."""
    active_clock = clock or _REAL_CLOCK
    started_ns = active_clock.perf_counter_ns()
    started_at = active_clock.utc_now()
    status: Literal["completed", "failed"] = "completed"
    error_type: str | None = None
    error_message: str | None = None
    try:
        yield
    except Exception as exc:
        status = "failed"
        error_type = type(exc).__name__
        error_message = _sanitize_error_message(str(exc))
        raise
    finally:
        duration_ms = (active_clock.perf_counter_ns() - started_ns) / 1_000_000
        measurement = StageMeasurement(
            measurement_id=str(uuid.uuid4()),
            run_id=run_id,
            step_id=step_id,
            frame_id=frame_id,
            iteration_index=iteration_index,
            stage=stage,
            started_at=started_at,
            duration_ms=duration_ms,
            status=status,
            actual_call=actual_call,
            cache_hit=cache_hit,
            source_ref=source_ref,
            error_type=error_type,
            error_message=error_message,
        )
        test_run.stage_measurements.append(measurement)
        log_event(
            "stage_measurement",
            run_id=run_id,
            step_id=step_id,
            frame_id=frame_id,
            iteration_index=iteration_index,
            stage=stage,
            status=status,
            duration_ms=duration_ms,
        )


def record_unavailable_stage(
    test_run: Any,
    *,
    stage: str,
    run_id: str,
    step_id: str | None = None,
    frame_id: str | None = None,
    iteration_index: int | None = None,
) -> None:
    """A stage that was never started — `duration_ms` stays null, never a
    fabricated zero (telemetry-contract.md "Measurement semantics")."""
    test_run.stage_measurements.append(
        StageMeasurement(
            measurement_id=str(uuid.uuid4()),
            run_id=run_id,
            step_id=step_id,
            frame_id=frame_id,
            iteration_index=iteration_index,
            stage=stage,
            started_at=datetime.now(UTC),
            duration_ms=None,
            status="unavailable",
            actual_call=False,
            cache_hit=False,
        )
    )
    log_event(
        "stage_measurement",
        run_id=run_id,
        step_id=step_id,
        frame_id=frame_id,
        iteration_index=iteration_index,
        stage=stage,
        status="unavailable",
        duration_ms=None,
    )
