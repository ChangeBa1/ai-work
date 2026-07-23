"""Run / step / iteration / experience models (data-model.md §9–10)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from vnc_agent.domain.action import ExecutableAction, ExecutionResult, SemanticAction
from vnc_agent.domain.action_effect import ActionEffect
from vnc_agent.domain.action_identity import CanonicalActionIdentity
from vnc_agent.domain.grounding import GroundingResult
from vnc_agent.domain.observation import ScreenFrame
from vnc_agent.domain.recovery import RecoveryAttempt
from vnc_agent.domain.repeat_guard import RepeatGuardDecision
from vnc_agent.domain.verification import VerificationResult, VerificationSpec, WaitResult
from vnc_agent.runtime.telemetry import (
    CounterEvent,
    ModelCallAudit,
    PerformanceSummary,
    StageMeasurement,
)


class ActionIteration(BaseModel):
    iteration_index: int = Field(ge=0)
    before_frame_id: str | None = None
    after_frame_id: str | None = None
    semantic_action: SemanticAction | None = None
    grounding_result: GroundingResult | None = None
    executable_action: ExecutableAction | None = None
    execution_result: ExecutionResult | None = None
    wait_result: WaitResult | None = None
    verification_result: VerificationResult | None = None
    recovery_attempts: list[RecoveryAttempt] = Field(default_factory=list)
    # 002: independent ActionEffect + RepeatGuard records (data-model.md §6)
    action_effect: ActionEffect | None = None
    repeat_guard_decision: RepeatGuardDecision | None = None
    canonical_identity: CanonicalActionIdentity | None = None


class DeclaredFact(BaseModel):
    """Feature 003 (FR-024): a testcase/scenario-profile-declared named
    precondition fact. Reuses VerificationSpec directly — the same
    fact/assertion mechanism used for step-level business assertions,
    differing only in trigger timing (run-start vs. post-step)."""

    key: str
    spec: VerificationSpec


class RunPrecondition(BaseModel):
    facts: list[DeclaredFact] = Field(default_factory=list)


class FactEvaluation(BaseModel):
    key: str
    result: VerificationResult


class PreconditionEvaluation(BaseModel):
    status: Literal["not_required", "passed", "failed"] = "not_required"
    fact_evaluations: list[FactEvaluation] = Field(default_factory=list)
    checked_at: datetime | None = None


class HumanConfirmedFact(BaseModel):
    """Feature 003 (FR-024, real/online-environment runs): an independent
    human-confirmed value for a declared fact key. MUST NOT participate in
    PreconditionEvaluation's automatic pass/fail decision — it is written to
    the report purely as cross-checkable evidence."""

    key: str
    confirmed_value: str
    confirmed_at: datetime
    screenshot_ref: str | None = None


class StepRecord(BaseModel):
    step_id: str
    iterations: list[ActionIteration] = Field(default_factory=list)
    final_status: Literal["passed", "failed", "cancelled", "pending", "running"] = "pending"
    ocr_result_ref: str | None = None
    model_names: dict[str, str] = Field(default_factory=dict)
    raw_model_response_refs: list[str] = Field(default_factory=list)
    stage_durations_ms: dict[str, int] = Field(default_factory=dict)
    failure_reason: str | None = None


class TestRun(BaseModel):
    run_id: str
    test_case_id: str
    status: Literal["passed", "failed", "cancelled", "running", "created"] = "created"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    steps: list[StepRecord] = Field(default_factory=list)
    report_json_path: str | None = None
    report_html_path: str | None = None
    precondition_evaluation: PreconditionEvaluation = Field(
        default_factory=PreconditionEvaluation
    )
    human_confirmed_facts: list[HumanConfirmedFact] = Field(default_factory=list)
    # Feature 004: logical frame trace + append-only telemetry (data-model.md §12)
    frames: list[ScreenFrame] = Field(default_factory=list)
    stage_measurements: list[StageMeasurement] = Field(default_factory=list)
    counter_events: list[CounterEvent] = Field(default_factory=list)
    model_call_audits: list[ModelCallAudit] = Field(default_factory=list)
    performance_summary: PerformanceSummary | None = None


class VisualExperience(BaseModel):
    run_id: str
    step_id: str
    before_frame_id: str | None = None
    after_frame_id: str | None = None
    semantic_action: dict[str, Any] = Field(default_factory=dict)
    grounding_candidates: list[dict[str, Any]] = Field(default_factory=list)
    selected_candidate: dict[str, Any] | None = None
    execution_result: dict[str, Any] = Field(default_factory=dict)
    verification_result: dict[str, Any] = Field(default_factory=dict)
    outcome: Literal["success", "failure", "uncertain"]
    failure_type: str | None = None
