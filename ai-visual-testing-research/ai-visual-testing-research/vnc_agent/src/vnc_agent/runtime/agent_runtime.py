"""Agent Runtime: single ActionIteration + step budget + VNC restart integration."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.grounding import GroundingResult
from vnc_agent.domain.observation import Region, StructuredScreen
from vnc_agent.domain.recovery import FailureType
from vnc_agent.domain.run import ActionIteration, HumanConfirmedFact
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.evolution.experience_collector import ExperienceCollector
from vnc_agent.execution.action_identity import compute_identity
from vnc_agent.execution.repeat_guard import RepeatGuard
from vnc_agent.execution.router import ExecutionRouter, compute_batch_repeat_timeout_seconds
from vnc_agent.logging_setup import get_logger
from vnc_agent.models.provider import GrounderProvider, GroundingRequest, PlannerProvider
from vnc_agent.perception.action_effect import classify_action_effect
from vnc_agent.perception.pipeline import ObservationPipeline
from vnc_agent.perception.stability import StabilityEngine
from vnc_agent.planning.action_classification import classify_action_kind
from vnc_agent.planning.action_policy import ActionPolicy
from vnc_agent.planning.planner import PlannerOrchestrator
from vnc_agent.recovery.classifier import (
    Classification,
    classify_action_no_effect,
)
from vnc_agent.recovery.engine import RecoveryEngine
from vnc_agent.recovery.strategies import StrategyContext
from vnc_agent.runtime.context_identity import (
    MissingIdentityFieldError,
    grounder_identity,
    planner_identity,
    verifier_identity,
)
from vnc_agent.runtime.exceptions import (
    PlanValidationError,
    StepBudgetExhaustedError,
    VNCConnectionError,
    VNCDisconnectedError,
)
from vnc_agent.runtime.run_context import RunContext
from vnc_agent.runtime.state_machine import AgentState
from vnc_agent.runtime.step_controller import StepController
from vnc_agent.runtime.telemetry import measure_stage
from vnc_agent.verification.business_resolver import (
    evaluate_precondition,
    resolve_step_result,
)
from vnc_agent.verification.engine import VerificationEngine

if TYPE_CHECKING:
    from vnc_agent.config import AppConfig
    from vnc_agent.drivers.base import VNCDriver
    from vnc_agent.perception.screenshot import FrameCaptureService
    from vnc_agent.reporting.report_builder import ReportBuilder
    from vnc_agent.storage.artifact_store import ArtifactStore
    from vnc_agent.storage.repositories import RunRepository

log = get_logger("agent_runtime")


def _resolved_region_from_iteration(iteration: ActionIteration | None) -> Region | None:
    """Feature 003: top-ranked resolved Grounding candidate's bbox, if any
    grounding happened for that iteration (used as target-evidence-conflict
    spatial input; see execution/target_consistency.py::
    has_target_evidence_conflict)."""
    if iteration is None or iteration.grounding_result is None:
        return None
    candidates = iteration.grounding_result.candidates
    if not candidates:
        return None
    x1, y1, x2, y2 = candidates[0].bbox
    return Region(x1=x1, y1=y1, x2=x2, y2=y2)


def _provider_identity_snapshot(provider: Any) -> dict[str, Any]:
    """Requested-model identity for a context-sensitive audit — never the
    response's `model_name`, always the request-side config (perception-
    cache-contract.md "Configuration/model invalidation")."""
    cfg = getattr(provider, "cfg", None)
    if cfg is not None:
        return {"provider": type(provider).__name__, "model": getattr(cfg, "model", None)}
    return {"provider": type(provider).__name__}


def _semantic_target_label(sa: SemanticAction) -> str:
    """Normalized label for the element a SemanticAction aims at (focus memory)."""
    if sa.target is not None:
        return (
            sa.target.text
            or sa.target.description
            or sa.target.role
            or sa.intent
            or ""
        ).strip()
    return (sa.intent or "").strip()


class AgentRuntime:
    def __init__(
        self,
        *,
        config: AppConfig,
        driver: VNCDriver,
        planner: PlannerProvider,
        grounder: GrounderProvider,
        pipeline: ObservationPipeline,
        stability: StabilityEngine,
        capture_service: FrameCaptureService,
        artifact_store: ArtifactStore,
        repo: RunRepository | None = None,
        report_builder: ReportBuilder | None = None,
        experience: ExperienceCollector | None = None,
        report_formats: tuple[str, ...] = ("json", "html"),
        clock: Any = None,
    ) -> None:
        self.config = config
        self.driver = driver
        self.planner_orch = PlannerOrchestrator(planner)
        self.grounder = grounder
        self.pipeline = pipeline
        self.stability = stability
        # Feature 004: the one shared run/session-scoped capture service —
        # `pipeline`/`stability` already reference this same instance.
        self.capture_service = capture_service
        self.artifact_store = artifact_store
        self.clock = clock
        self.policy = ActionPolicy(
            overall_confidence_threshold=config.agent.grounding.overall_confidence_threshold,
            top1_top2_min_gap=config.agent.grounding.top1_top2_min_gap,
            ocr_sanity_check_ratio=config.agent.planning.ocr_sanity_check_ratio,
        )
        self.executor = ExecutionRouter(
            driver,
            default_timeout_seconds=config.agent.action.default_timeout_seconds,
        )
        self.verifier = VerificationEngine(planner)
        self.recovery = RecoveryEngine(config)
        self.repeat_guard = RepeatGuard(
            micro_action_risk_thresholds=config.agent.planning.micro_action_risk_thresholds,
            target_region_conflict_iou_threshold=(
                config.agent.planning.target_region_conflict_iou_threshold
            ),
        )
        self.repo = repo
        self.report_builder = report_builder
        self.experience = experience or ExperienceCollector(repo)
        self.report_formats = report_formats
        self.planner = planner
        self._ui_index_bundle = None

    def _load_ui_index_preflight(self) -> None:
        """FR-012: fail before first step when an explicit invalid bundle is configured."""
        ui_cfg = self.config.agent.ui_index
        if not ui_cfg.bundle_dir:
            self._ui_index_bundle = None
            return
        from vnc_agent.ui_index.repository import UiIndexBundle, UiIndexValidationError

        try:
            self._ui_index_bundle = UiIndexBundle.load(ui_cfg.bundle_dir, ui_cfg)
        except UiIndexValidationError:
            raise

    async def run(
        self,
        test_case: TestCase,
        *,
        human_confirmed_facts: list[HumanConfirmedFact] | None = None,
    ) -> RunContext:
        # Preflight UI index before any step (and before VNC connect for fail-fast).
        self._load_ui_index_preflight()

        ctx = RunContext(
            test_case,
            run_id=self.capture_service.run_id,
            human_confirmed_facts=human_confirmed_facts,
        )
        ctx.begin_run()
        ctx.state_machine.transition(AgentState.CONNECTING, "start")

        try:
            await self.driver.connect()
        except Exception as e:
            log.error("vnc_connect_failed", error=str(e), run_id=ctx.run_id)
            ctx.finish_run("failed")
            ctx.state_machine.force(AgentState.FAILED, "vnc_connect_failed")
            if self.repo:
                await self.repo.save_run(ctx.test_run)
            raise VNCConnectionError(str(e)) from e

        w, h = self.driver.resolution
        log.info("vnc_connected", run_id=ctx.run_id, width=w, height=h)
        ctx.state_machine.transition(AgentState.PREPARING, "connected")

        # Feature 004: bind the shared capture service to this run's TestRun
        # and reconcile any leftover staging/orphan bundles before the first
        # capture (frame-capture-contract.md "startup/reconnect recovery").
        self.capture_service.test_run = ctx.test_run
        self.artifact_store.recover_orphans(ctx.run_id, referenced_bundle_ids=set())

        while ctx.has_next_step():
            if ctx.cancelled:
                ctx.mark_step_cancelled()
                ctx.finish_run("cancelled")
                ctx.state_machine.force(AgentState.CANCELLED, "cancel")
                break

            step = ctx.advance_step()
            assert step is not None
            max_retries = (
                step.max_retries
                if step.max_retries is not None
                else self.config.agent.step.default_max_retries
            )
            controller = StepController(max_retries)
            step_failed = False
            failure_reason: str | None = None
            # T097: full recovery reset once per TestStep so upgrade flags
            # (candidate_index / prefer_keyboard / need_reground) survive across
            # ActionIterations within the same step.
            self.recovery.reset_iteration()

            while True:
                if ctx.cancelled:
                    ctx.mark_step_cancelled()
                    ctx.finish_run("cancelled")
                    ctx.state_machine.force(AgentState.CANCELLED, "cancel")
                    if self.repo:
                        await self.repo.save_run(ctx.test_run)
                    return ctx

                try:
                    if not controller.can_start_iteration():
                        step_failed = True
                        failure_reason = "step budget exhausted"
                        break
                    iter_idx = controller.start_iteration()
                except StepBudgetExhaustedError:
                    step_failed = True
                    failure_reason = "step budget exhausted"
                    break

                # Tier-2 only — keep cross-iteration upgrade flags (T097)
                self.recovery.begin_action_iteration()
                iteration = ctx.begin_iteration(iter_idx)
                ctx.state_machine.force(AgentState.OBSERVING, "iteration_start")

                try:
                    vr = await self.run_action_iteration(
                        ctx, step, controller, iteration
                    )
                except VNCDisconnectedError as e:
                    # FR-039 + Clarification 2026-07-21: budget gates restart_step
                    if controller.remaining_budget() <= 0:
                        step_failed = True
                        failure_reason = f"vnc disconnected with no budget: {e}"
                        break
                    attempt = await self.recovery.handle(
                        Classification(failure_type=FailureType.VNC_DISCONNECTED),
                        step_controller=controller,
                        ctx=StrategyContext(driver=self.driver),
                        action_timeout=self.config.agent.action.default_timeout_seconds,
                    )
                    iteration.recovery_attempts.append(attempt)
                    if not attempt.resolved:
                        step_failed = True
                        failure_reason = "vnc reconnect failed"
                        break
                    # Feature 004: successful reconnect rotates the capture
                    # session and clears `previous` (frame-capture-contract.md)
                    self._rotate_capture_session(ctx)
                    # restart from OBSERVING — continue loop (budget already consumed)
                    continue
                except Exception as e:
                    log.exception("iteration_error", error=str(e))
                    step_failed = True
                    failure_reason = str(e)
                    break

                if vr is None:
                    # cancelled mid-iteration
                    break

                iteration.verification_result = vr
                await self.experience.collect(
                    run_id=ctx.run_id, step_id=step.id, iteration=iteration
                )

                if vr.status == "passed":
                    ctx.mark_step_passed()
                    ctx.state_machine.force(AgentState.STEP_COMPLETED_PASSED, "passed")
                    break

                # failed / uncertain
                if not controller.can_start_iteration():
                    step_failed = True
                    failure_reason = vr.reason or vr.status
                    break
                # continue next iteration (budget consumed on start_iteration)

            if ctx.test_run.status == "cancelled":
                break

            if step_failed:
                ctx.mark_step_failed(failure_reason)
                ctx.state_machine.force(AgentState.STEP_COMPLETED_FAILED, "failed")
                if self.repo and ctx.current_step_record:
                    await self.repo.save_step(ctx.run_id, ctx.current_step_record)
                ctx.finish_run("failed")
                ctx.state_machine.force(AgentState.FAILED, "step_failed")
                # MUST NOT schedule subsequent steps (FR-035)
                break
            else:
                if self.repo and ctx.current_step_record:
                    await self.repo.save_step(ctx.run_id, ctx.current_step_record)
        else:
            # all steps passed
            ctx.finish_run("passed")
            ctx.state_machine.force(AgentState.PASSED, "all_passed")

        if self.repo:
            await self.repo.save_run(ctx.test_run)
        if self.report_builder:
            # T100: honour --json-only via report_formats
            self.report_builder.build(ctx.test_run, formats=self.report_formats)
            if self.repo:
                await self.repo.save_run(ctx.test_run)
        return ctx

    def _rotate_capture_session(self, ctx: RunContext) -> None:
        """New VNC session id, clear `previous`, reconcile orphan bundles left
        by a mid-run disconnect (frame-capture-contract.md "Logical/physical
        invariants" + "startup/reconnect recovery"). Also clears the bounded
        analysis cache — perception-cache-contract.md "Capacity and
        lifecycle" requires session reset to drop every entry."""
        self.capture_service.vnc_session_id = str(uuid.uuid4())
        self.capture_service.clear()
        cache = getattr(self.pipeline, "cache", None)
        if cache is not None:
            cache.clear()
        referenced: set[str] = set()
        for f in ctx.test_run.frames:
            referenced.add(f.safe_image.artifact_bundle_id)
            if f.model_image is not None:
                referenced.add(f.model_image.artifact_bundle_id)
        self.artifact_store.recover_orphans(ctx.run_id, referenced)

    def _record_model_call_audit(
        self,
        ctx: RunContext,
        *,
        step_id: str | None,
        frame_id: str | None,
        iteration_index: int | None,
        model_role: str,
        request_identity: str,
        context_identity: str,
        sanitized_request: dict[str, Any],
        sanitized_response: dict[str, Any],
    ) -> None:
        """Every actual Planner/Grounder/Verifier call gets a sanitized audit
        record + a `model_call` counter event — these roles are never served
        from the pixel-content cache (context_identity.py has no
        content_hash/pixels parameter at all), so every applicable call here
        is outcome="actual" (perception-cache-contract.md "Explicit
        exclusions"; data-model.md §6A)."""
        from vnc_agent.runtime.telemetry import CounterEvent, ModelCallAudit, log_event

        invocation_id = str(uuid.uuid4())
        audit = ModelCallAudit(
            audit_id=str(uuid.uuid4()),
            run_id=ctx.run_id,
            step_id=step_id,
            frame_id=frame_id,
            iteration_index=iteration_index,
            model_role=model_role,  # type: ignore[arg-type]
            request_identity=request_identity,
            context_identity=context_identity,
            sanitized_request=sanitized_request,
            sanitized_response=sanitized_response,
            outcome="actual",
            source_ref=None,
            reason=None,
        )
        ctx.test_run.model_call_audits.append(audit)
        model_call_payload = {
            "model_role": model_role,
            "invocation_id": invocation_id,
            "status": "completed",
        }
        ctx.test_run.counter_events.append(
            CounterEvent(
                kind="model_call", occurred_at=datetime.now(UTC), payload=model_call_payload
            )
        )
        log_event("model_call_event", **model_call_payload)
        log_event(
            "model_call_audit",
            run_id=ctx.run_id,
            step_id=step_id,
            frame_id=frame_id,
            iteration_index=iteration_index,
            model_role=model_role,
            request_identity=request_identity,
            context_identity=context_identity,
            sanitized_request=sanitized_request,
            sanitized_response=sanitized_response,
            outcome="actual",
        )

    async def run_action_iteration(
        self,
        ctx: RunContext,
        step: TestStep,
        controller: StepController,
        iteration: ActionIteration,
    ) -> VerificationResult | None:
        """
        One ActionIteration:
        OBSERVING→UNDERSTANDING→PLANNING→RESOLVING_ACTION→(GROUNDING)?→
        EXECUTING→WAITING→VERIFYING→RECORDING
        """
        t_stages: dict[str, int] = {}

        def mark(name: str, t0: float) -> None:
            t_stages[name] = int((time.monotonic() - t0) * 1000)

        # OBSERVING
        t0 = time.monotonic()
        screen = await self.pipeline.observe(step_id=step.id, capture_source="observation")
        iteration.before_frame_id = screen.image_path
        mark("observing", t0)
        if ctx.cancelled:
            return None

        # UNDERSTANDING (already partly in pipeline)
        ctx.state_machine.force(AgentState.UNDERSTANDING, "observed")

        if (
            ctx.test_case.precondition is not None
            and ctx.test_run.precondition_evaluation.checked_at is None
        ):
            precondition_eval = await evaluate_precondition(
                ctx.test_case.precondition, screen, self.verifier
            )
            ctx.test_run.precondition_evaluation = precondition_eval
            if precondition_eval.status == "failed":
                controller.mark_exhausted()
                evidence_refs = [
                    ref
                    for fe in precondition_eval.fact_evaluations
                    for ref in fe.result.evidence_refs
                ]
                result = VerificationResult(
                    status="failed",
                    reason="precondition_failed",
                    evidence_refs=evidence_refs,
                )
                iteration.verification_result = result
                ctx.state_machine.force(AgentState.RECORDING, "precondition_failed")
                return result
        ctx.state_machine.force(AgentState.PLANNING, "plan")

        # PLANNING
        t0 = time.monotonic()
        if step.batch_repeat_key is not None:
            # Feature 005: author-declared batch repeat key — deterministic,
            # code-constructed SemanticAction; the Planner is not called at
            # all for this step (FR-002/FR-003/FR-014). Falls through into
            # the same RepeatGuard/ActionPolicy/Executor/wait/verify
            # sequence below as any Planner-produced action.
            sa = SemanticAction(
                action_id=f"{step.id}-batch-repeat",
                intent=step.intent,
                action_type="press_key_repeat",
                keys=[step.batch_repeat_key.key],
                repeat_count=step.batch_repeat_key.count,
                repeat_interval_ms=step.batch_repeat_key.interval_ms,
                risk_level="low",
            )
            mark("planning", t0)
        else:
            prev_vr = None
            if ctx.current_step_record and len(ctx.current_step_record.iterations) > 1:
                prev = ctx.current_step_record.iterations[-2]
                prev_vr = prev.verification_result
            try:
                with measure_stage(
                    ctx.test_run, stage="planner", run_id=ctx.run_id, step_id=step.id,
                    frame_id=screen.frame_id, iteration_index=iteration.iteration_index,
                    clock=self.clock,
                ):
                    plan = await self.planner_orch.plan(
                        step,
                        screen,
                        iteration_index=iteration.iteration_index,
                        remaining_budget=controller.remaining_budget(),
                        previous_verification=prev_vr,
                        ui_index_bundle=self._ui_index_bundle,
                        ui_index_config=self.config.agent.ui_index,
                        ui_index_audit_sink=iteration,
                    )
            except PlanValidationError as e:
                iteration.verification_result = VerificationResult(
                    status="failed", reason=f"plan validation: {e}"
                )
                mark("planning", t0)
                return iteration.verification_result
            # task_completed_hint is advisory only — still verify
            sa = plan.semantic_action
            mark("planning", t0)

            # Feature 004 (T039): Planner is context-sensitive — never
            # served from the pixel-content cache; every actual call gets a
            # sanitized audit record with its full canonical
            # request/context identity.
            try:
                planner_req_id = planner_identity(
                    request_semantics={
                        "intent": step.intent,
                        "conditions": [c.type for c in step.expected.conditions],
                    },
                    step_intent=step.intent,
                    action_history_state=(
                        f"iterations={len(ctx.current_step_record.iterations)}"
                        if ctx.current_step_record
                        else "iterations=0"
                    ),
                    retry_iteration_state={
                        "iteration_index": iteration.iteration_index,
                        "remaining_budget": controller.remaining_budget(),
                    },
                    structured_screen_identity=screen.content_hash or screen.frame_id,
                    requested_model_config=_provider_identity_snapshot(self.planner),
                    route_state=str(ctx.state_machine.state),
                )
                self._record_model_call_audit(
                    ctx,
                    step_id=step.id,
                    frame_id=screen.frame_id,
                    iteration_index=iteration.iteration_index,
                    model_role="planner",
                    request_identity=planner_req_id,
                    context_identity=planner_req_id,
                    sanitized_request={
                        "step_intent": step.intent,
                        "iteration_index": iteration.iteration_index,
                    },
                    sanitized_response={
                        "action_type": sa.action_type,
                        "task_completed_hint": plan.task_completed_hint,
                    },
                )
            except MissingIdentityFieldError:
                pass

        # Annotate action_kind when left unset (FR-013). Feature 005:
        # deliberately applies to the batch-repeat bypass path too (`sa`
        # from either branch above never sets action_kind itself), so a
        # declared batch is classified by the same conservative
        # non_idempotent default as any other undeclared action — RepeatGuard
        # below is never weakened for a batch of a non-idempotent key (e.g.
        # "enter") on step retry. See research.md / analysis finding D1.
        if sa.action_kind is None:
            sa = sa.model_copy(update={"action_kind": classify_action_kind(sa)})
        iteration.semantic_action = sa
        iteration.canonical_identity = compute_identity(step.id, sa)

        # RepeatGuard before RESOLVING_ACTION (contracts §5)
        previous_iteration: ActionIteration | None = None
        if ctx.current_step_record and len(ctx.current_step_record.iterations) > 1:
            previous_iteration = ctx.current_step_record.iterations[-2]
        # Feature 003 (safety issue A): the previous round's resolved target
        # region, if grounding already happened for it. The proposed round's
        # region is always None here — grounding for it has not run yet at
        # this point in the pipeline (RepeatGuard runs before RESOLVING_
        # ACTION/GROUNDING) — has_target_evidence_conflict() treats a missing
        # region as "this dimension does not participate," it never
        # manufactures a conflict out of unavailable evidence.
        previous_resolved_region = _resolved_region_from_iteration(previous_iteration)
        guard = self.repeat_guard.check(
            step.id,
            step.intent,
            sa,
            previous_iteration,
            previous_resolved_region=previous_resolved_region,
            proposed_resolved_region=None,
        )
        iteration.repeat_guard_decision = guard

        if not guard.allowed:
            if guard.reason in {"dangerous_drift", "ambiguous_fail_safe"}:
                attempt = await self.recovery.handle(
                    Classification(
                        failure_type=FailureType.TARGET_NOT_FOUND,
                        detail=guard.reason,
                    ),
                    step_controller=controller,
                    ctx=StrategyContext(driver=self.driver),
                    action_timeout=self.config.agent.action.default_timeout_seconds,
                )
                iteration.recovery_attempts.append(attempt)
            # Strengthen verification without re-executing the non-idempotent action
            ctx.state_machine.force(AgentState.VERIFYING, "repeat_guard_block")
            t0 = time.monotonic()
            prev_ae = (
                previous_iteration.action_effect
                if previous_iteration and previous_iteration.action_effect
                else ActionEffect(
                    status="effect_uncertain",
                    evidence=ActionEffectEvidence(),
                    reason="repeat_guard_block",
                )
            )
            iteration.action_effect = prev_ae

            async def _reobserve() -> StructuredScreen:
                return await self.pipeline.observe(step_id=step.id, capture_source="retry")

            vr = await resolve_step_result(
                step.expected,
                step.verification_mode,
                prev_ae,
                screen,
                planner=self.planner,
                reobserve=_reobserve,
                engine=self.verifier,
                escalate=True,
            )
            mark("verifying", t0)
            ctx.state_machine.force(AgentState.RECORDING, "record")
            if ctx.current_step_record is not None:
                ctx.current_step_record.stage_durations_ms.update(t_stages)
            return vr

        # RESOLVING_ACTION (+ optional GROUNDING)
        ctx.state_machine.force(AgentState.RESOLVING_ACTION, "resolve")
        t0 = time.monotonic()
        target_hint = _semantic_target_label(sa)
        # Feed target + last-known focus into recovery so switch_to_keyboard can
        # derive a real tab_sequence (T070 wiring for T069 algorithm).
        self.recovery.remember_screen(
            screen,
            target_hint=target_hint,
            known_focus_hint=self.recovery._last_known_focus_hint,
        )

        grounding: GroundingResult | None = None
        policy_result = self.policy.resolve(
            sa,
            screen,
            grounding_result=None,
            prefer_keyboard=self.recovery.prefer_keyboard,
            focus_path=self.recovery.focus_path,
            candidate_index=self.recovery.candidate_index,
        )
        # Track whether this iteration will execute a recovery-derived focus path
        active_focus_path = (
            self.recovery.focus_path
            if (
                policy_result.outcome == "focus"
                and self.recovery.focus_path is not None
                and policy_result.executable is not None
                and list(policy_result.executable.keys)
                == list(self.recovery.focus_path.tab_sequence)
            )
            else None
        )

        if policy_result.needs_grounding:
            ctx.state_machine.force(AgentState.GROUNDING, "ground")
            target = (
                sa.target.model_dump()
                if sa.target
                else {"description": sa.intent}
            )
            # FR-049: model API receives unmasked image (model_image_path)
            with measure_stage(
                ctx.test_run, stage="grounder", run_id=ctx.run_id, step_id=step.id,
                frame_id=screen.frame_id, iteration_index=iteration.iteration_index,
                clock=self.clock,
            ):
                from vnc_agent.ui_index.runtime_adapter import build_hints

                _hints, ui_index_candidates, _audit = build_hints(
                    self._ui_index_bundle,
                    screen,
                    self.config.agent.ui_index,
                )
                grounding = await self.grounder.ground(
                    GroundingRequest(
                        image_ref=screen.path_for_model(),
                        crop_offset=screen.crop_offset,
                        resolution=screen.resolution,
                        target=target,
                        ocr_candidates=[i.model_dump() for i in screen.ocr_items],
                        template_candidates=[m.model_dump() for m in screen.template_matches],
                        ui_index_candidates=ui_index_candidates,
                    )
                )
            iteration.grounding_result = grounding
            try:
                grounder_req_id = grounder_identity(
                    target_semantics=target,
                    candidate_set_identity={
                        "ocr_count": len(screen.ocr_items),
                        "template_count": len(screen.template_matches),
                        "screen": screen.content_hash or screen.frame_id,
                    },
                    coordinate_transform_identity={
                        "crop_offset": screen.crop_offset,
                        "resolution": screen.resolution,
                    },
                    requested_model_config=_provider_identity_snapshot(self.grounder),
                    retry_grounding_state={
                        "iteration_index": iteration.iteration_index,
                        "candidate_index": self.recovery.candidate_index,
                    },
                )
                self._record_model_call_audit(
                    ctx,
                    step_id=step.id,
                    frame_id=screen.frame_id,
                    iteration_index=iteration.iteration_index,
                    model_role="grounder",
                    request_identity=grounder_req_id,
                    context_identity=grounder_req_id,
                    sanitized_request={"target": target},
                    sanitized_response={
                        "found": grounding.found,
                        "candidate_count": len(grounding.candidates),
                    },
                )
            except MissingIdentityFieldError:
                pass
            policy_result = self.policy.resolve(
                sa,
                screen,
                grounding_result=grounding,
                prefer_keyboard=self.recovery.prefer_keyboard,
                focus_path=self.recovery.focus_path,
                candidate_index=self.recovery.candidate_index,
            )

        if policy_result.outcome == "stop_recover":
            clf = Classification(
                failure_type=policy_result.failure_type,  # type: ignore[arg-type]
                sub_reason=policy_result.sub_reason,
            )
            attempt = await self.recovery.handle(
                clf,
                step_controller=controller,
                ctx=StrategyContext(driver=self.driver),
            )
            iteration.recovery_attempts.append(attempt)
            if policy_result.grounding_result:
                iteration.grounding_result = policy_result.grounding_result
            # After recovery, fail this iteration so Tier-1 may retry
            mark("resolving", t0)
            return VerificationResult(
                status="failed",
                reason=f"action policy stop: {clf.failure_type}",
            )

        executable = policy_result.executable
        if executable is None:
            return VerificationResult(status="failed", reason="no executable action")
        iteration.executable_action = executable
        if policy_result.grounding_result:
            iteration.grounding_result = policy_result.grounding_result
        mark("resolving", t0)

        # EXECUTING
        ctx.state_machine.force(AgentState.EXECUTING, "execute")
        t0 = time.monotonic()
        try:
            if executable.operation == "press_key_repeat":
                # Feature 005 remediation (analysis finding F1): size the
                # timeout for a press_key_repeat action from its own
                # count/interval so a spec-legal worst-case batch doesn't
                # silently hit the router's static default and lose
                # requested_count/completed_count.
                exec_result = await self.executor.execute(
                    executable,
                    timeout_seconds=compute_batch_repeat_timeout_seconds(
                        executable.repeat_count,
                        executable.repeat_interval_ms,
                        self.executor.default_timeout_seconds,
                    ),
                )
            else:
                # Every other operation: call site byte-for-byte unchanged
                # (no timeout_seconds kwarg at all) — preserves compatibility
                # with any test/tooling that replaces `self.executor.execute`
                # with a narrower single-argument callable (FR-011/FR-012).
                exec_result = await self.executor.execute(executable)
        except VNCDisconnectedError:
            raise
        except Exception as e:
            exec_result = None
            iteration.execution_result = None
            mark("executing", t0)
            return VerificationResult(status="failed", reason=f"execute error: {e}")
        iteration.execution_result = exec_result
        mark("executing", t0)

        # WAITING
        ctx.state_machine.force(AgentState.WAITING, "wait")
        t0 = time.monotonic()
        wait_result = await self.stability.wait_stable(step_id=step.id)
        iteration.wait_result = wait_result
        mark("waiting", t0)
        if wait_result.end_reason == "vnc_error":
            raise VNCDisconnectedError("disconnected during wait")

        # VERIFYING — independent post-action observation + ActionEffect
        ctx.state_machine.force(AgentState.VERIFYING, "verify")
        t0 = time.monotonic()
        after = await self.pipeline.observe(
            step_id=step.id, capture_source="post_action_verification"
        )
        iteration.after_frame_id = after.image_path

        perc = self.config.agent.perception
        action_effect = classify_action_effect(
            screen,
            after,
            intent=sa.intent,
            local_blob_min_ratio=perc.local_blob_min_ratio,
            error_keywords=list(perc.error_keywords),
        )
        iteration.action_effect = action_effect

        async def _reobserve_after() -> StructuredScreen:
            return await self.pipeline.observe(
                step_id=step.id, capture_source="post_action_verification"
            )

        with measure_stage(
            ctx.test_run, stage="verification", run_id=ctx.run_id, step_id=step.id,
            frame_id=after.frame_id, iteration_index=iteration.iteration_index,
            clock=self.clock,
        ):
            vr = await resolve_step_result(
                step.expected,
                step.verification_mode,
                action_effect,
                after,
                planner=self.planner,
                reobserve=_reobserve_after,
                engine=self.verifier,
                escalate=True,
            )
        mark("verifying", t0)

        # Feature 004 (T039): every post-action Verifier execution is
        # audited — it always runs on fresh, independently captured evidence
        # and is never skipped or served from the pixel-content cache
        # (Constitution Principle IV; perception-cache-contract.md "Explicit
        # exclusions").
        try:
            verifier_req_id = verifier_identity(
                visual_question_or_assertion={
                    "operator": step.expected.operator,
                    "conditions": [c.type for c in step.expected.conditions],
                },
                before_frame_identity=screen.content_hash or screen.frame_id,
                after_frame_identity=after.content_hash or after.frame_id,
                action_audit_context={
                    "status": action_effect.status,
                    "error_popup_signal": action_effect.evidence.error_popup_signal,
                },
                retry_iteration_state=iteration.iteration_index,
                requested_model_config=_provider_identity_snapshot(self.planner),
            )
            self._record_model_call_audit(
                ctx,
                step_id=step.id,
                frame_id=after.frame_id,
                iteration_index=iteration.iteration_index,
                model_role="verification",
                request_identity=verifier_req_id,
                context_identity=verifier_req_id,
                sanitized_request={"operator": step.expected.operator},
                sanitized_response={"status": vr.status},
            )
        except MissingIdentityFieldError:
            pass

        # T070 (a): when the action is confirmed to have landed, remember the
        # operated element as the current keyboard focus for later structural
        # tab-order derivation on switch_to_keyboard.
        action_landed = (
            action_effect.status == "expected_effect" or vr.status == "passed"
        )
        if action_landed and target_hint:
            self.recovery.remember_focus(target_hint)

        # T070 (b): when a recovery-built focus_path keyboard walk succeeded,
        # record it for prior_successful_replay within this run.
        if action_landed and active_focus_path is not None:
            self.recovery.record_successful_focus_path(active_focus_path)

        # Recovery routing based on ActionEffect (replaces bare changed_since_last)
        if vr.status in ("failed", "uncertain"):
            clf_ae = classify_action_no_effect(action_effect)
            if clf_ae is not None:
                self.recovery.remember_screen(
                    after,
                    target_hint=target_hint,
                    known_focus_hint=self.recovery._last_known_focus_hint,
                )
                attempt = await self.recovery.handle(
                    clf_ae,
                    step_controller=controller,
                    ctx=StrategyContext(driver=self.driver),
                    action_timeout=self.config.agent.action.default_timeout_seconds,
                )
                iteration.recovery_attempts.append(attempt)

        # RECORDING
        ctx.state_machine.force(AgentState.RECORDING, "record")
        if ctx.current_step_record is not None:
            ctx.current_step_record.stage_durations_ms.update(t_stages)

        return vr
