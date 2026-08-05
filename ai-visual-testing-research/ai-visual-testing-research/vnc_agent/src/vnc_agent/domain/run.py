"""Run / step / iteration / experience models (data-model.md §9–10)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from vnc_agent.domain.action import ExecutableAction, ExecutionResult, SemanticAction
from vnc_agent.domain.action_effect import ActionEffect
from vnc_agent.domain.action_identity import CanonicalActionIdentity
from vnc_agent.domain.app_perception import PerceptionEnhancementAudit
from vnc_agent.domain.grounding import GroundingResult
from vnc_agent.domain.memory import MemoryHitAudit
from vnc_agent.domain.observation import ScreenFrame
from vnc_agent.domain.recovery import PostmortemAudit, RecoveryAttempt, WrongTargetEvidence
from vnc_agent.domain.repeat_guard import RepeatGuardDecision
from vnc_agent.domain.replay import ReplayStepAudit
from vnc_agent.domain.verification import VerificationResult, VerificationSpec, WaitResult
from vnc_agent.runtime.telemetry import (
    CounterEvent,
    ModelCallAudit,
    PerformanceSummary,
    StageMeasurement,
)
from vnc_agent.ui_index.audit import IndexUsageAuditRecord


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
    # Feature 007 (FR-013): index-usage audit for this iteration; None when
    # no bundle is configured is never the case — build_hints() always
    # returns a record (outcome="not_configured" in that case).
    ui_index_audit: IndexUsageAuditRecord | None = None
    # Feature 009 (FR-007/FR-009): planner short-circuit marker + this
    # iteration's observation content identity. `planner_skipped_reason` is
    # non-null iff the planner call was skipped for this iteration
    # ("duplicate_frame_blocked_action"); in that case repeat_guard_decision
    # is a carried copy of the previous iteration's blocking decision, not a
    # fresh guard evaluation (contract §4).
    planner_skipped_reason: str | None = None
    before_content_hash: str | None = None
    # Feature 015 (FR-010): non-null iff this iteration's click was produced
    # directly from element memory (grounder skipped). Verification is never
    # exempted by a memory hit (FR-008).
    memory_hit: MemoryHitAudit | None = None
    # Feature 016 (FR-012): non-null iff this iteration belongs to a replay-
    # mode run — records which ReplayStep/script version it replayed and how
    # the target was located (template/anchor/bbox/fallback_grounding/
    # keyboard). Always null on exploration iterations.
    replay_audit: ReplayStepAudit | None = None
    # Feature 022 (FR-B04): deterministic wrong-click evidence computed for
    # every executed mouse action with a resolved target_region (suspected or
    # not); null for keyboard/region-less iterations. Consumed by feature
    # 023's post-hoc diagnosis.
    wrong_target_evidence: WrongTargetEvidence | None = None
    # Feature 022: upgraded failure attribution for this iteration —
    # "stale_frame" (guard vetoed execution) or "wrong_target" (suspected +
    # independent verification failed). Null on every other iteration; a
    # plain verification failure stays attributed via VerificationResult.
    failure_attribution: str | None = None
    # Feature 023 (FR-010): non-null iff a WRONG_TARGET post-mortem ran for
    # this iteration — outcome, corrected bbox/click point, gate evidence,
    # undo flags and diagnosis artifact refs. Null everywhere else.
    postmortem: PostmortemAudit | None = None
    # Feature 024 (FR-024): one record for every iteration that reached the
    # grounding branch — including the ones that were NOT enhanced, whose
    # reason code is what makes "why wasn't this step enhanced?" answerable.
    # Null on iterations that never called the grounder.
    perception_enhancement: PerceptionEnhancementAudit | None = None


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
