"""Agent Runtime: single ActionIteration + step budget + VNC restart integration."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from vnc_agent.domain.action import ExecutableAction, SemanticAction
from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.grounding import GroundingResult
from vnc_agent.domain.memory import MemoryHitAudit, MemoryLookupResult
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
from vnc_agent.perception.action_effect import (
    assess_wrong_target,
    blobs_intersecting_neighborhood,
    classify_action_effect,
)
from vnc_agent.perception.pipeline import ObservationPipeline
from vnc_agent.perception.stability import StabilityEngine
from vnc_agent.planning.action_classification import classify_action_kind
from vnc_agent.planning.action_policy import ActionPolicy
from vnc_agent.planning.click_point import safe_click_point
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
from vnc_agent.verification.answer_cache import CachedVisualAnswerer
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
        postmortem_client: Any = None,
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
            ocr_direct_click_min_confidence=(
                config.agent.planning.ocr_direct_click_min_confidence
            ),
            click_edge_inset_ratio=config.agent.click.edge_inset_ratio,
        )
        self.executor = ExecutionRouter(
            driver,
            default_timeout_seconds=config.agent.action.default_timeout_seconds,
        )
        # Feature 008: verification-path visual answers share the pipeline's
        # bounded AnalysisResultCache; test_run is resolved lazily because the
        # CLI attaches it to the capture service after construction.
        self.verifier = VerificationEngine(
            planner,
            answerer=CachedVisualAnswerer(
                cache=getattr(pipeline, "cache", None),
                test_run_provider=lambda: capture_service.test_run,
                provider_name=getattr(pipeline, "vision_provider_name", "planner-provider"),
                model=getattr(pipeline, "vision_model", "default"),
            ),
        )
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
        # Feature 015 (page-element-memory, spec Clarification 10): the memory
        # service exists only when enabled AND persistence is available; None
        # short-circuits every 015 wiring point below, keeping
        # `memory.enabled: false` byte-identical to the pre-015 runtime.
        self.memory = None
        mem_cfg = config.agent.memory
        if mem_cfg.enabled and repo is not None:
            from pathlib import Path

            from vnc_agent.memory.service import PageElementMemory
            from vnc_agent.storage.repositories import MemoryRepository

            template_dir = (
                Path(mem_cfg.storage_dir)
                if mem_cfg.storage_dir
                else Path(self.artifact_store.root) / "memory" / "templates"
            )
            self.memory = PageElementMemory(
                repo=MemoryRepository(repo.session_factory),
                template_dir=template_dir,
                config=mem_cfg,
                mask_regions=config.agent.security.mask_regions,
            )
        # Feature 015 (FR-008): element ids banned for the rest of the current
        # step after a memory direct click failed independent verification.
        self._memory_blocked_element_ids: set[str] = set()
        # Feature 023 (click-postmortem-correction): optional injected
        # diagnosis client (offline tests); None => a lightweight HTTP client
        # over the grounder endpoint/model config is built lazily on the
        # first WRONG_TARGET post-mortem (never on the hot path).
        self._postmortem_client = postmortem_client
        # Feature 016 (record-replay): replay persistence + auto-recorder.
        # Both exist only when replay is enabled AND persistence is
        # available; None short-circuits every 016 wiring point so
        # `replay.enabled: false` keeps exploration byte-identical (FR-013).
        self.replay_repo = None
        self.replay_recorder = None
        rp_cfg = config.agent.replay
        if rp_cfg.enabled and repo is not None:
            from pathlib import Path

            from vnc_agent.storage.repositories import ReplayRepository

            self.replay_repo = ReplayRepository(repo.session_factory)
            if rp_cfg.auto_generate:
                from vnc_agent.replay.recorder import ReplayRecorder

                replay_template_dir = (
                    Path(rp_cfg.storage_dir)
                    if rp_cfg.storage_dir
                    else Path(self.artifact_store.root) / "replay" / "templates"
                )
                self.replay_recorder = ReplayRecorder(
                    repo=self.replay_repo,
                    template_dir=replay_template_dir,
                    mask_regions=config.agent.security.mask_regions,
                )

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
        # Feature 016 (FR-005/FR-013): replay mode runs on its own execution
        # path — the exploration iteration loop below is never entered. The
        # player fails fast (ReplayUnavailableError) before any VNC
        # connection when replay is disabled or no script exists.
        if test_case.mode == "replay":
            from vnc_agent.replay.player import ReplayPlayer

            return await ReplayPlayer(self).run(
                test_case, human_confirmed_facts=human_confirmed_facts
            )

        # Preflight UI index before any step (and before VNC connect for fail-fast).
        self._load_ui_index_preflight()

        # Feature 016 (FR-003): fresh recording drafts for this exploration
        # run (fail-open side channel; no behavioral effect on the run).
        if self.replay_recorder is not None:
            self.replay_recorder.reset()

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
            # Feature 015 (FR-008): the memory ban list is per-step.
            self._memory_blocked_element_ids.clear()

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
                # Feature 022: upgraded attribution (stale_frame /
                # wrong_target) flows into the experience row's failure_type
                # — None on every other iteration (pre-022 value).
                await self.experience.collect(
                    run_id=ctx.run_id,
                    step_id=step.id,
                    iteration=iteration,
                    failure_type=iteration.failure_attribution,
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

        # Feature 016 (FR-003): a fully-passed exploration run auto-generates
        # a candidate replay script (design §10.1). Fail-open inside the
        # recorder — never affects the run result.
        if self.replay_recorder is not None and ctx.test_run.status == "passed":
            await self.replay_recorder.finalize(ctx)

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

    # Feature 009 (planner-skip-contract.md §1.2): blocked reasons that make
    # a re-plan on an identical frame provably informationless. blocked_
    # uncertain(_normalized_target) is deliberately excluded — an uncertain
    # previous effect leaves the Planner a chance to propose a *different*
    # corrective action on the same frame (research.md R3).
    _PLANNER_SKIP_BLOCKED_REASONS = frozenset(
        {
            "blocked_effect_pending",
            "blocked_effect_pending_normalized_target",
            "ambiguous_fail_safe",
        }
    )

    @classmethod
    def _planner_skip_reason(
        cls,
        step: TestStep,
        screen: StructuredScreen,
        previous_iteration: ActionIteration | None,
    ) -> str | None:
        """Feature 009 (FR-001/FR-006): stateless skip predicate
        (planner-skip-contract.md §1). Returns the skip reason when the
        planner call for this iteration would be provably informationless,
        else None. Missing evidence (null hashes / missing records) always
        disables the skip — fail open to the normal, more expensive path.
        """
        if previous_iteration is None:
            return None
        guard = previous_iteration.repeat_guard_decision
        if guard is None or guard.allowed:
            return None
        if guard.reason not in cls._PLANNER_SKIP_BLOCKED_REASONS:
            return None
        # §1.3 duplicate logical frame: non-null content-hash equality with
        # the previous round's observation (subsumes the capture-layer
        # `deduplicated` flag; robust to interleaved stability/post-action
        # captures — research.md R2).
        if screen.content_hash is None or previous_iteration.before_content_hash is None:
            return None
        if screen.content_hash != previous_iteration.before_content_hash:
            return None
        # §1.4 wait-semantics exception (a): previous planned action was
        # wait-type — time alone can change the next observation.
        prev_sa = previous_iteration.semantic_action
        if prev_sa is not None and (
            prev_sa.action_type == "wait" or prev_sa.micro_action_purpose == "wait"
        ):
            return None
        # §1.5 wait-semantics exception (b): the verification spec declares
        # an explicit time budget — an unchanged frame is an expected
        # intermediate state, not a dead end.
        if step.expected.timeout_seconds is not None:
            return None
        return "duplicate_frame_blocked_action"

    def _record_planner_skip(
        self,
        ctx: RunContext,
        *,
        step: TestStep,
        screen: StructuredScreen,
        iteration: ActionIteration,
        previous_iteration: ActionIteration,
        skip_reason: str,
        remaining_budget: int,
    ) -> None:
        """Feature 009 (FR-008): one `model_call_skipped` CounterEvent + one
        outcome="skipped" ModelCallAudit per skipped round — and never a
        planner `model_call` event or StageMeasurement, so
        `model_calls.planner` cannot grow (planner-skip-contract.md §3)."""
        from vnc_agent.runtime.telemetry import CounterEvent, ModelCallAudit, log_event

        try:
            request_identity = planner_identity(
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
                    "remaining_budget": remaining_budget,
                },
                structured_screen_identity=screen.content_hash or screen.frame_id,
                requested_model_config=_provider_identity_snapshot(self.planner),
                route_state=str(ctx.state_machine.state),
            )
        except MissingIdentityFieldError:
            request_identity = screen.content_hash or screen.frame_id
        source_ref = screen.duplicate_of_frame_id or previous_iteration.before_frame_id
        skipped_payload = {
            "model_role": "planner",
            "reason": skip_reason,
            "request_identity": request_identity,
        }
        ctx.test_run.counter_events.append(
            CounterEvent(
                kind="model_call_skipped",
                occurred_at=datetime.now(UTC),
                payload=skipped_payload,
            )
        )
        log_event("model_call_skipped_event", **skipped_payload)
        audit = ModelCallAudit(
            audit_id=str(uuid.uuid4()),
            run_id=ctx.run_id,
            step_id=step.id,
            frame_id=screen.frame_id,
            iteration_index=iteration.iteration_index,
            model_role="planner",
            request_identity=request_identity,
            context_identity=request_identity,
            sanitized_request={
                "step_intent": step.intent,
                "iteration_index": iteration.iteration_index,
            },
            sanitized_response={},
            outcome="skipped",
            source_ref=source_ref,
            reason=skip_reason,
        )
        ctx.test_run.model_call_audits.append(audit)
        log_event(
            "model_call_audit",
            run_id=ctx.run_id,
            step_id=step.id,
            frame_id=screen.frame_id,
            iteration_index=iteration.iteration_index,
            model_role="planner",
            request_identity=request_identity,
            context_identity=request_identity,
            outcome="skipped",
            reason=skip_reason,
        )

    async def _skip_planner_iteration(
        self,
        ctx: RunContext,
        step: TestStep,
        controller: StepController,
        iteration: ActionIteration,
        screen: StructuredScreen,
        previous_iteration: ActionIteration | None,
        skip_reason: str,
        t_stages: dict[str, int],
    ) -> VerificationResult:
        """Feature 009 (FR-002/FR-005/FR-007): a planner-skipped iteration —
        marks the record, carries the previous blocking RepeatGuardDecision
        forward (so identical-frame chains keep skipping,
        planner-skip-contract.md §4), emits the skip telemetry and follows
        the exact verdict path an in-iteration RepeatGuard block follows."""
        assert previous_iteration is not None
        carried = previous_iteration.repeat_guard_decision
        assert carried is not None and not carried.allowed
        iteration.planner_skipped_reason = skip_reason
        # Carried copy — distinguishable from a fresh guard evaluation by the
        # non-null planner_skipped_reason on this same record (FR-005).
        iteration.repeat_guard_decision = carried.model_copy()
        self._record_planner_skip(
            ctx,
            step=step,
            screen=screen,
            iteration=iteration,
            previous_iteration=previous_iteration,
            skip_reason=skip_reason,
            remaining_budget=controller.remaining_budget(),
        )
        log.info(
            "planner_skipped",
            run_id=ctx.run_id,
            step_id=step.id,
            iteration_index=iteration.iteration_index,
            reason=skip_reason,
            blocked_reason=carried.reason,
        )
        return await self._blocked_iteration_verdict(
            ctx,
            step,
            controller,
            iteration,
            screen,
            previous_iteration,
            carried.reason,
            t_stages,
            verify_trigger="planner_skip_duplicate_frame",
        )

    async def _blocked_iteration_verdict(
        self,
        ctx: RunContext,
        step: TestStep,
        controller: StepController,
        iteration: ActionIteration,
        screen: StructuredScreen,
        previous_iteration: ActionIteration | None,
        blocked_reason: str,
        t_stages: dict[str, int],
        *,
        verify_trigger: str,
    ) -> VerificationResult:
        """Shared no-execution verdict path: used both when RepeatGuard
        blocks this round's fresh proposal and when Feature 009 skips the
        planner on a duplicate frame with a carried blocked decision
        (planner-skip-contract.md §2 requires the two to be identical).
        Body extracted verbatim from the pre-009 in-iteration block branch."""
        if blocked_reason in {"dangerous_drift", "ambiguous_fail_safe"}:
            attempt = await self.recovery.handle(
                Classification(
                    failure_type=FailureType.TARGET_NOT_FOUND,
                    detail=blocked_reason,
                ),
                step_controller=controller,
                ctx=StrategyContext(driver=self.driver),
                action_timeout=self.config.agent.action.default_timeout_seconds,
            )
            iteration.recovery_attempts.append(attempt)
        # Strengthen verification without re-executing the non-idempotent action
        ctx.state_machine.force(AgentState.VERIFYING, verify_trigger)
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
            visual_override_confidence_threshold=(
                self.config.agent.verification.visual_override_confidence_threshold
            ),
        )
        t_stages["verifying"] = int((time.monotonic() - t0) * 1000)
        ctx.state_machine.force(AgentState.RECORDING, "record")
        if ctx.current_step_record is not None:
            ctx.current_step_record.stage_durations_ms.update(t_stages)
        return vr

    def _memory_direct_executable(
        self,
        sa: SemanticAction,
        lookup: MemoryLookupResult,
        screen: StructuredScreen,
    ) -> ExecutableAction:
        """Feature 015 (FR-006): build the direct-click ExecutableAction from
        a high-tier memory match — same safe_click_point geometry (feature
        013) and target_region conventions as the policy's mouse paths.
        ActionPolicy.resolve is deliberately not involved (FR-011)."""
        bbox = lookup.matched_bbox
        assert bbox is not None
        pt = safe_click_point(
            bbox,
            siblings=[],
            screen_resolution=screen.resolution,
            edge_inset_ratio=self.config.agent.click.edge_inset_ratio,
        )
        op = sa.action_type
        if op not in ("click", "double_click", "right_click"):
            op = "click"
        return ExecutableAction(
            method="mouse",
            operation=op,
            coordinates=(pt.x, pt.y),
            target_region=Region(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3]),
        )

    def _record_memory_hit(
        self,
        ctx: RunContext,
        *,
        step: TestStep,
        screen: StructuredScreen,
        iteration: ActionIteration,
        target: dict[str, Any],
        hit: MemoryHitAudit,
    ) -> None:
        """Feature 015 (FR-010): telemetry for one memory direct click —
        an `element_memory_hit` CounterEvent, a grounder `model_call_skipped`
        CounterEvent and an outcome="skipped" ModelCallAudit (same shape the
        feature-009 planner skip uses), plus a structured log event. Never a
        grounder `model_call` event or StageMeasurement — `model_calls.
        grounder` cannot grow from a memory hit."""
        from vnc_agent.runtime.telemetry import CounterEvent, ModelCallAudit, log_event

        try:
            request_identity = grounder_identity(
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
        except MissingIdentityFieldError:
            request_identity = screen.content_hash or screen.frame_id
        now = datetime.now(UTC)
        hit_payload = {
            "element_memory_id": hit.element_memory_id,
            "page_similarity": hit.page_similarity,
            "template_score": hit.template_score,
        }
        ctx.test_run.counter_events.append(
            CounterEvent(kind="element_memory_hit", occurred_at=now, payload=hit_payload)
        )
        skipped_payload = {
            "model_role": "grounder",
            "reason": "element_memory_hit",
            "request_identity": request_identity,
        }
        ctx.test_run.counter_events.append(
            CounterEvent(kind="model_call_skipped", occurred_at=now, payload=skipped_payload)
        )
        log_event("model_call_skipped_event", **skipped_payload)
        ctx.test_run.model_call_audits.append(
            ModelCallAudit(
                audit_id=str(uuid.uuid4()),
                run_id=ctx.run_id,
                step_id=step.id,
                frame_id=screen.frame_id,
                iteration_index=iteration.iteration_index,
                model_role="grounder",
                request_identity=request_identity,
                context_identity=request_identity,
                sanitized_request={"target": target},
                sanitized_response={
                    "matched_bbox": list(hit.matched_bbox),
                    "template_score": hit.template_score,
                },
                outcome="skipped",
                source_ref=hit.element_memory_id,
                reason="element_memory_hit",
            )
        )
        log_event(
            "element_memory_hit",
            run_id=ctx.run_id,
            step_id=step.id,
            frame_id=screen.frame_id,
            iteration_index=iteration.iteration_index,
            element_memory_id=hit.element_memory_id,
            page_memory_id=hit.page_memory_id,
            page_similarity=hit.page_similarity,
            template_score=hit.template_score,
            matched_bbox=list(hit.matched_bbox),
        )
        log.info(
            "element_memory_direct_click",
            run_id=ctx.run_id,
            step_id=step.id,
            iteration_index=iteration.iteration_index,
            element_memory_id=hit.element_memory_id,
            page_similarity=hit.page_similarity,
            template_score=hit.template_score,
        )

    def _get_postmortem_client(self) -> Any:
        """Feature 023: injected stub (tests) or a lazily built HTTP client
        over the grounder endpoint/model config (spec Clarification 5)."""
        if self._postmortem_client is None:
            from vnc_agent.models.postmortem_client import HttpPostmortemClient

            self._postmortem_client = HttpPostmortemClient(self.config.models.grounder)
        return self._postmortem_client

    def _record_postmortem_correction_applied(
        self,
        ctx: RunContext,
        *,
        step: TestStep,
        screen: StructuredScreen,
        iteration: ActionIteration,
        correction: Any,
    ) -> None:
        """Feature 023 (FR-005): telemetry for one applied corrected-click
        plan — the grounder call is skipped for this round, audited with the
        same `model_call_skipped` shape the 009/015 skips use. Never a
        grounder `model_call` event, so `model_calls.grounder` cannot grow."""
        from vnc_agent.runtime.telemetry import CounterEvent, ModelCallAudit, log_event

        request_identity = (
            f"postmortem_correction:{screen.content_hash or screen.frame_id}:"
            f"{list(correction.corrected_bbox)}"
        )
        skipped_payload = {
            "model_role": "grounder",
            "reason": "postmortem_correction",
            "request_identity": request_identity,
        }
        ctx.test_run.counter_events.append(
            CounterEvent(
                kind="model_call_skipped",
                occurred_at=datetime.now(UTC),
                payload=skipped_payload,
            )
        )
        log_event("model_call_skipped_event", **skipped_payload)
        ctx.test_run.model_call_audits.append(
            ModelCallAudit(
                audit_id=str(uuid.uuid4()),
                run_id=ctx.run_id,
                step_id=step.id,
                frame_id=screen.frame_id,
                iteration_index=iteration.iteration_index,
                model_role="grounder",
                request_identity=request_identity,
                context_identity=request_identity,
                sanitized_request={"source_iteration": correction.source_iteration_index},
                sanitized_response={
                    "corrected_bbox": list(correction.corrected_bbox),
                    "click_point": list(correction.click_point),
                    "confidence": correction.confidence,
                },
                outcome="skipped",
                source_ref=None,
                reason="postmortem_correction",
            )
        )
        log_event(
            "postmortem_correction_applied",
            run_id=ctx.run_id,
            step_id=step.id,
            iteration_index=iteration.iteration_index,
            corrected_bbox=list(correction.corrected_bbox),
            click_point=list(correction.click_point),
            confidence=correction.confidence,
        )
        log.info(
            "postmortem_correction_applied",
            run_id=ctx.run_id,
            step_id=step.id,
            iteration_index=iteration.iteration_index,
            corrected_bbox=list(correction.corrected_bbox),
        )

    async def _run_wrong_target_postmortem(
        self,
        ctx: RunContext,
        *,
        step: TestStep,
        iteration: ActionIteration,
        screen: StructuredScreen,
        after: StructuredScreen,
        target: dict[str, Any],
        wt_ev: Any,
        attempt: Any,
    ) -> bool:
        """Feature 023: run the full post-mortem (undo → annotate → diagnose
        → gates) for a WRONG_TARGET iteration whose recovery routing selected
        the `postmortem` strategy. Returns True iff an accepted correction
        plan was stored for the next ActionIteration; on refusal the attempt
        is downgraded to unresolved and the caller falls back to the 022
        chain. Fail-safe throughout (the diagnostician never raises)."""
        from vnc_agent.recovery.postmortem import PostmortemDiagnostician
        from vnc_agent.recovery.strategies import execute_strategy

        diagnostician = PostmortemDiagnostician(
            run_id=ctx.run_id,
            artifact_store=self.artifact_store,
            client=self._get_postmortem_client(),
            postmortem_cfg=self.config.agent.wrong_target_postmortem,
            memory_cfg=self.config.agent.memory,
            click_edge_inset_ratio=self.config.agent.click.edge_inset_ratio,
        )

        async def _send_undo() -> bool:
            return await execute_strategy(
                "postmortem_undo",
                StrategyContext(driver=self.driver),
                timeout_seconds=self.config.agent.action.default_timeout_seconds,
            )

        async def _reobserve() -> StructuredScreen:
            return await self.pipeline.observe(
                step_id=step.id, capture_source="recovery"
            )

        with measure_stage(
            ctx.test_run, stage="postmortem", run_id=ctx.run_id, step_id=step.id,
            frame_id=after.frame_id, iteration_index=iteration.iteration_index,
            clock=self.clock,
        ):
            result = await diagnostician.run(
                step_id=step.id,
                iteration_index=iteration.iteration_index,
                before_screen=screen,
                after_screen=after,
                target=target,
                evidence=wt_ev,
                send_undo=_send_undo,
                reobserve=_reobserve,
            )
        if result.undo_attempt is not None:
            iteration.recovery_attempts.append(result.undo_attempt)
        iteration.postmortem = result.audit
        # The engine recorded the attempt as "strategy ran"; the diagnosis
        # verdict decides whether the recovery actually resolved anything.
        attempt.resolved = result.plan is not None
        # Every actual diagnosis call is audited with the existing
        # ModelCallAudit convention (model_role="postmortem") and thereby
        # counted in performance_summary.model_calls (FR-010). A refusal
        # before the call (e.g. page_not_restored) leaves no response_ref
        # and records no model call — truthful accounting.
        if result.audit.response_ref is not None:
            identity = (
                f"postmortem:{screen.content_hash or screen.frame_id}:"
                f"{after.content_hash or after.frame_id}:{iteration.iteration_index}"
            )
            self._record_model_call_audit(
                ctx,
                step_id=step.id,
                frame_id=after.frame_id,
                iteration_index=iteration.iteration_index,
                model_role="postmortem",
                request_identity=identity,
                context_identity=identity,
                sanitized_request={
                    "target": target,
                    "evidence_reason": wt_ev.reason,
                },
                sanitized_response={
                    "outcome": result.audit.outcome,
                    "target_found": result.audit.target_found,
                    "confidence": result.audit.confidence,
                    "corrected_bbox": (
                        list(result.audit.corrected_bbox)
                        if result.audit.corrected_bbox is not None
                        else None
                    ),
                },
            )
        if result.plan is not None:
            self.recovery.set_postmortem_correction(result.plan)
        log.info(
            "postmortem_completed",
            run_id=ctx.run_id,
            step_id=step.id,
            iteration_index=iteration.iteration_index,
            outcome=result.audit.outcome,
            undo_performed=result.audit.undo_performed,
            corrected_bbox=(
                list(result.audit.corrected_bbox)
                if result.audit.corrected_bbox is not None
                else None
            ),
        )
        return result.plan is not None

    async def _pre_click_stale_check(
        self,
        ctx: RunContext,
        step: TestStep,
        screen: StructuredScreen,
        executable: ExecutableAction,
    ) -> str | None:
        """Feature 022 (FR-A01/FR-A02): quick pre-execution guard for mouse
        actions — one fresh capture through the shared FrameCaptureService
        (capture_source="pre_click_guard"; dedup/audit apply as for any other
        capture), then a deterministic ROI comparison of the target
        neighborhood against the observation frame that produced this
        action's coordinates. Zero model calls.

        Returns a detail string when the neighborhood changed (the action
        MUST NOT be sent), None to proceed. Every internal failure fails
        open to None — the guard is protective, never a new failure mode.
        """
        target_region = executable.target_region
        if target_region is None or not screen.image_path:
            return None
        try:
            outcome = await self.capture_service.capture(
                step_id=step.id, capture_source="pre_click_guard"
            )
        except Exception as exc:  # capture failure → existing flows own it later
            log.warning("pre_click_guard_capture_failed", error=str(exc), run_id=ctx.run_id)
            return None
        frame = outcome.frame
        # Fast path: identical logical content ⇒ nothing moved anywhere.
        if (
            frame.content_hash is not None
            and screen.content_hash is not None
            and frame.content_hash == screen.content_hash
        ):
            return None
        try:
            from vnc_agent.perception.screen_diff import compute_diff

            # Both sides are safe-evidence PNGs (identically masked) —
            # threshold=1.0 keeps `regions` empty, we only want local_blobs.
            _, _, guard_ratio, guard_blobs = compute_diff(
                screen.image_path, frame.image_path, threshold=1.0
            )
        except Exception as exc:
            log.warning("pre_click_guard_diff_failed", error=str(exc), run_id=ctx.run_id)
            return None
        hits = blobs_intersecting_neighborhood(
            guard_blobs,
            target_region,
            expand_ratio=self.config.agent.execution.stale_frame_region_expand_ratio,
            resolution=screen.resolution,
        )
        if not hits:
            return None
        h0 = hits[0]
        return (
            f"target neighborhood changed between observation and execution: "
            f"{len(hits)}/{len(guard_blobs)} blob(s) in neighborhood, "
            f"first=({h0.x1},{h0.y1},{h0.x2},{h0.y2}), "
            f"global_ratio={guard_ratio:.5f}, guard_frame={frame.id}"
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
        # Feature 009 (FR-009): record this round's observation content
        # identity so the duplicate-frame comparison is auditable from the
        # run record alone (planner-skip-contract.md §1.3).
        iteration.before_content_hash = screen.content_hash
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

        # Previous ActionIteration within this step (used by the Feature 009
        # planner short-circuit below and by RepeatGuard further down).
        previous_iteration: ActionIteration | None = None
        if ctx.current_step_record and len(ctx.current_step_record.iterations) > 1:
            previous_iteration = ctx.current_step_record.iterations[-2]

        # Feature 009 (FR-001, planner-skip-contract.md §1/§2): when this
        # round's observation is pixel-identical to the previous round's AND
        # the previous round's action was blocked by RepeatGuard
        # (blocked_effect_pending / ambiguous_fail_safe), a re-plan cannot
        # produce new information — skip the Planner call entirely and go
        # straight to the same verdict/recovery path an in-iteration block
        # follows. Never applies to batch_repeat_key steps (no planner call
        # exists on that path).
        if step.batch_repeat_key is None:
            skip_reason = self._planner_skip_reason(step, screen, previous_iteration)
            if skip_reason is not None:
                return await self._skip_planner_iteration(
                    ctx,
                    step,
                    controller,
                    iteration,
                    screen,
                    previous_iteration,
                    skip_reason,
                    t_stages,
                )

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
        # Feature 009: a planner-skipped iteration proposed and executed
        # nothing — it is transparent to RepeatGuard. Compare the new
        # proposal against the most recent iteration that actually carried a
        # planner proposal, so guard semantics are byte-for-byte identical to
        # the pre-skip behavior (a skip chain never weakens or strengthens
        # the identity comparison basis).
        guard_reference_iteration = previous_iteration
        if previous_iteration is not None and ctx.current_step_record:
            for prev in reversed(ctx.current_step_record.iterations[:-1]):
                if prev.planner_skipped_reason is None:
                    guard_reference_iteration = prev
                    break
        # Feature 003 (safety issue A): the previous round's resolved target
        # region, if grounding already happened for it. The proposed round's
        # region is always None here — grounding for it has not run yet at
        # this point in the pipeline (RepeatGuard runs before RESOLVING_
        # ACTION/GROUNDING) — has_target_evidence_conflict() treats a missing
        # region as "this dimension does not participate," it never
        # manufactures a conflict out of unavailable evidence.
        previous_resolved_region = _resolved_region_from_iteration(guard_reference_iteration)
        guard = self.repeat_guard.check(
            step.id,
            step.intent,
            sa,
            guard_reference_iteration,
            previous_resolved_region=previous_resolved_region,
            proposed_resolved_region=None,
        )
        iteration.repeat_guard_decision = guard

        if not guard.allowed:
            return await self._blocked_iteration_verdict(
                ctx,
                step,
                controller,
                iteration,
                screen,
                guard_reference_iteration,
                guard.reason,
                t_stages,
                verify_trigger="repeat_guard_block",
            )

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

        # Feature 015 (FR-006): non-null iff this iteration's click comes
        # straight from element memory (the grounder call is skipped).
        memory_executable: ExecutableAction | None = None
        # Feature 023 (FR-005): non-null iff this iteration's click comes
        # from an accepted post-mortem correction plan (memory + grounder
        # both skipped for this round; verification unchanged).
        postmortem_executable: ExecutableAction | None = None

        if policy_result.needs_grounding:
            ctx.state_machine.force(AgentState.GROUNDING, "ground")
            target = (
                sa.target.model_dump()
                if sa.target
                else {"description": sa.intent}
            )
            # Feature 014 (FR-003/FR-005): a pending zoom_reground plan from
            # the previous iteration's recovery replaces this grounding call's
            # input with the crop+upscale observation. observe_zoom failure
            # falls open to the normal full-screen request.
            zoom_plan = self.recovery.take_zoom_request()
            zoom_obs = None
            if zoom_plan is not None:
                zx1, zy1, zx2, zy2 = zoom_plan.roi
                try:
                    zoom_obs = await self.pipeline.observe_zoom(
                        roi=Region(x1=zx1, y1=zy1, x2=zx2, y2=zy2),
                        scale_factor=zoom_plan.scale_factor,
                        step_id=step.id,
                        capture_source="recovery",
                    )
                except Exception:
                    zoom_obs = None

            # Feature 023 (FR-005): a pending corrected-click plan from the
            # previous iteration's post-mortem is consumed here — one-shot,
            # highest priority for coordinate-producing click actions. A
            # pending plan facing a non-click proposal is dropped (fail-open
            # to the normal path — never applied to a non-click).
            correction = None
            if zoom_obs is None:
                correction = self.recovery.take_postmortem_correction()
            if correction is not None and sa.action_type in (
                "click",
                "double_click",
                "right_click",
            ):
                cb = correction.corrected_bbox
                postmortem_executable = ExecutableAction(
                    method="mouse",
                    operation=sa.action_type,
                    coordinates=correction.click_point,
                    target_region=Region(x1=cb[0], y1=cb[1], x2=cb[2], y2=cb[3]),
                )
                self._record_postmortem_correction_applied(
                    ctx,
                    step=step,
                    screen=screen,
                    iteration=iteration,
                    correction=correction,
                )

            # Feature 015 (FR-006): memory-first hot path — before any
            # grounder call, query page/element memory. A pending zoom plan
            # (feature 014) takes precedence over memory (the memory/normal
            # path already failed when zoom was scheduled); only coordinate-
            # producing mouse actions participate. A feature-023 corrected
            # click also bypasses memory (it is this step's targeted fix).
            memory_lookup: MemoryLookupResult | None = None
            if (
                self.memory is not None
                and zoom_obs is None
                and postmortem_executable is None
                and sa.action_type in ("click", "double_click", "right_click")
            ):
                memory_lookup = await self.memory.lookup(
                    screen,
                    target_hint,
                    exclude_element_ids=self._memory_blocked_element_ids,
                )
            if postmortem_executable is not None:
                # Feature 023 (FR-005): corrected click this round — memory
                # and grounder both skipped (audited above); execution and
                # verification below run completely unchanged.
                pass
            elif (
                memory_lookup is not None
                and memory_lookup.level == "high"
                and memory_lookup.matched_bbox is not None
                and memory_lookup.element is not None
                and memory_lookup.page is not None
            ):
                # Direct click from remembered evidence (design §21.3 "历史
                # 经验命中时不立即调用 MiMo") — the grounder is not called at
                # all this round. Independent verification below is unchanged
                # (FR-008 / Constitution IV).
                memory_executable = self._memory_direct_executable(
                    sa, memory_lookup, screen
                )
                iteration.memory_hit = MemoryHitAudit(
                    element_memory_id=memory_lookup.element.element_id,
                    page_memory_id=memory_lookup.page.page_id,
                    target_label=memory_lookup.element.target_label,
                    page_similarity=memory_lookup.page_similarity,
                    template_score=memory_lookup.template_score or 0.0,
                    matched_bbox=memory_lookup.matched_bbox,
                )
                self._record_memory_hit(
                    ctx,
                    step=step,
                    screen=screen,
                    iteration=iteration,
                    target=target,
                    hit=iteration.memory_hit,
                )
            else:
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
                    if zoom_obs is not None:
                        grounding_request = GroundingRequest(
                            image_ref=zoom_obs.image_path,
                            crop_offset=zoom_obs.crop_offset,
                            scale_factor=zoom_obs.scale_factor,
                            resolution=zoom_obs.resolution,
                            original_resolution=screen.resolution,
                            target=target,
                            ocr_candidates=[i.model_dump() for i in zoom_obs.ocr_items],
                            template_candidates=[],
                            ui_index_candidates=[],
                        )
                    else:
                        grounding_request = GroundingRequest(
                            image_ref=screen.path_for_model(),
                            crop_offset=screen.crop_offset,
                            resolution=screen.resolution,
                            target=target,
                            ocr_candidates=[i.model_dump() for i in screen.ocr_items],
                            template_candidates=[m.model_dump() for m in screen.template_matches],
                            ui_index_candidates=ui_index_candidates,
                        )
                        # Feature 015 (FR-007): medium-tier memory evidence
                        # (or high without a template confirmation) rides the
                        # existing template_candidates hint channel — never a
                        # direct click, the grounder decides.
                        if memory_lookup is not None and memory_lookup.element is not None:
                            grounding_request.template_candidates.append(
                                {
                                    "template_id": (
                                        "element_memory:"
                                        f"{memory_lookup.element.target_label}"
                                    ),
                                    "bbox": list(memory_lookup.element.bbox),
                                    "confidence": memory_lookup.page_similarity,
                                }
                            )
                    grounding = await self.grounder.ground(grounding_request)
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
                            "crop_offset": grounding_request.crop_offset,
                            "resolution": grounding_request.resolution,
                            # Feature 014 (FR-008): zoom transform identity
                            "scale_factor": grounding_request.scale_factor,
                            "original_resolution": grounding_request.original_resolution,
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

        if (
            memory_executable is None
            and postmortem_executable is None
            and policy_result.outcome == "stop_recover"
        ):
            clf = Classification(
                failure_type=policy_result.failure_type,  # type: ignore[arg-type]
                sub_reason=policy_result.sub_reason,
            )
            # Feature 014 (FR-002): give recovery the evidence to derive a
            # zoom_reground ROI — prefer the raw grounding result (it may
            # still hold out-of-bounds/low-confidence candidates that the
            # policy filtered away, which are exactly the ROI hints we want).
            raw_grounding = (
                grounding
                if grounding is not None and grounding.candidates
                else policy_result.grounding_result
            )
            attempt = await self.recovery.handle(
                clf,
                step_controller=controller,
                ctx=StrategyContext(
                    driver=self.driver,
                    screen=screen,
                    grounding_result=raw_grounding,
                    target=(
                        sa.target.model_dump()
                        if sa.target
                        else {"description": sa.intent}
                    ),
                ),
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

        if postmortem_executable is not None:
            executable = postmortem_executable
        elif memory_executable is not None:
            executable = memory_executable
        else:
            executable = policy_result.executable
        if executable is None:
            return VerificationResult(status="failed", reason="no executable action")
        iteration.executable_action = executable
        if policy_result.grounding_result:
            iteration.grounding_result = policy_result.grounding_result
        mark("resolving", t0)

        # Feature 022 (FR-A01/FR-A02): stale-frame guard — the coordinates in
        # `executable` were derived from `screen`, captured several model
        # calls ago. Before EXECUTING, re-capture once and veto the action if
        # the target neighborhood changed; the iteration then fails into the
        # STALE_FRAME recovery path (re-observe + re-locate on the next
        # iteration). Disabled ⇒ this block is skipped entirely (byte-
        # identical pre-022 behavior).
        if (
            self.config.agent.execution.stale_frame_check_enabled
            and executable.method == "mouse"
        ):
            t0 = time.monotonic()
            stale_detail = await self._pre_click_stale_check(
                ctx, step, screen, executable
            )
            mark("pre_click_guard", t0)
            if stale_detail is not None:
                iteration.failure_attribution = FailureType.STALE_FRAME.value
                log.info(
                    "stale_frame_detected",
                    run_id=ctx.run_id,
                    step_id=step.id,
                    iteration_index=iteration.iteration_index,
                    detail=stale_detail,
                )
                attempt = await self.recovery.handle(
                    Classification(
                        failure_type=FailureType.STALE_FRAME, detail=stale_detail
                    ),
                    step_controller=controller,
                    ctx=StrategyContext(driver=self.driver, screen=screen),
                    action_timeout=self.config.agent.action.default_timeout_seconds,
                )
                iteration.recovery_attempts.append(attempt)
                ctx.state_machine.force(AgentState.RECORDING, "stale_frame")
                if ctx.current_step_record is not None:
                    ctx.current_step_record.stage_durations_ms.update(t_stages)
                return VerificationResult(
                    status="failed", reason=f"stale_frame: {stale_detail}"
                )

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

        # Feature 022 (FR-B02/FR-B04): deterministic wrong-target assessment
        # for every executed mouse action with a resolved target_region —
        # pure geometry over the ActionEffect evidence, zero model calls.
        # `suspected` alone never changes the verdict (FR-B03 upgrade below
        # additionally requires a failed verification); it is always recorded
        # for telemetry/023.
        if executable.method == "mouse" and executable.target_region is not None:
            iteration.wrong_target_evidence = assess_wrong_target(
                action_effect,
                target_region=executable.target_region,
                click_point=executable.coordinates,
                resolution=(
                    after.resolution if after.resolution != (0, 0) else screen.resolution
                ),
                neighborhood_expand_ratio=perc.wrong_target_neighborhood_expand_ratio,
                global_diff_ratio_max=perc.wrong_target_global_diff_ratio_max,
            )
            if iteration.wrong_target_evidence.suspected:
                from vnc_agent.runtime.telemetry import log_event

                wt_ev = iteration.wrong_target_evidence
                log_event(
                    "wrong_target_suspected",
                    run_id=ctx.run_id,
                    step_id=step.id,
                    iteration_index=iteration.iteration_index,
                    nearest_blob_distance_px=wt_ev.nearest_blob_distance_px,
                    nearest_blob_direction=wt_ev.nearest_blob_direction,
                    global_diff_ratio=wt_ev.global_diff_ratio,
                    blob_count=wt_ev.blob_count,
                )

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
                visual_override_confidence_threshold=(
                    self.config.agent.verification.visual_override_confidence_threshold
                ),
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

        # Feature 015 (FR-004/FR-008): settle memory strictly *after* the
        # independent verification verdict. A memory-derived click that did
        # not pass bans that element for the rest of this step and bumps its
        # failure counter; every verified-passed mouse action with a resolved
        # target_region is written back (pre-action frame + region). Both
        # calls are fail-open inside the service.
        if self.memory is not None:
            if iteration.memory_hit is not None and vr.status != "passed":
                self._memory_blocked_element_ids.add(
                    iteration.memory_hit.element_memory_id
                )
                await self.memory.record_element_failure(
                    iteration.memory_hit.element_memory_id
                )
            if (
                vr.status == "passed"
                and executable.method == "mouse"
                and executable.target_region is not None
                and target_hint
            ):
                await self.memory.record_success(
                    screen, target_hint, executable.target_region
                )

        # Feature 016 (FR-003/FR-004): hand the verified-passed iteration to
        # the replay recorder as an in-memory draft (pre-action frame + the
        # resolved executable). Pure side channel — fail-open, no effect on
        # the exploration verdict (FR-013).
        if self.replay_recorder is not None and vr.status == "passed":
            self.replay_recorder.observe_passed_iteration(step, screen, sa, executable)

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

        # Feature 022 (FR-B03): only "suspected AND verification failed"
        # upgrades this iteration's attribution to WRONG_TARGET — a suspected
        # iteration whose verification passed stays passed (the response
        # region may legitimately live elsewhere) and was already logged
        # above. classify_action_no_effect() is None for expected_effect, so
        # this never double-routes recovery for the same iteration.
        wt_ev = iteration.wrong_target_evidence
        if wt_ev is not None and wt_ev.suspected and vr.status == "failed":
            iteration.failure_attribution = FailureType.WRONG_TARGET.value
            vr = vr.model_copy(
                update={"reason": f"wrong_target: {vr.reason or 'verification failed'}"}
            )
            self.recovery.remember_screen(
                after,
                target_hint=target_hint,
                known_focus_hint=self.recovery._last_known_focus_hint,
            )
            wt_target = (
                sa.target.model_dump() if sa.target else {"description": sa.intent}
            )
            # Feature 023 (FR-008): the runtime can diagnose only with full
            # click geometry + a readable post-click frame; the flag makes
            # the engine substitute the next chain entry otherwise.
            postmortem_capable = (
                self.config.agent.wrong_target_postmortem.enabled
                and wt_ev.click_point is not None
                and wt_ev.target_region is not None
                and bool(after.image_path)
            )
            attempt = await self.recovery.handle(
                Classification(
                    failure_type=FailureType.WRONG_TARGET,
                    detail=wt_ev.reason or "wrong_target_suspected",
                ),
                step_controller=controller,
                ctx=StrategyContext(
                    driver=self.driver,
                    screen=after,
                    grounding_result=iteration.grounding_result,
                    target=wt_target,
                    postmortem_capable=postmortem_capable,
                ),
                action_timeout=self.config.agent.action.default_timeout_seconds,
            )
            iteration.recovery_attempts.append(attempt)
            # Feature 023: routing selected the post-mortem tier — run the
            # undo/diagnose/gate pipeline now. A refusal downgrades the
            # attempt to unresolved and routes one normal fallback attempt
            # through the same budgets (022 chain resumes at recapture).
            if attempt.strategy == "postmortem" and attempt.resolved:
                corrected = await self._run_wrong_target_postmortem(
                    ctx,
                    step=step,
                    iteration=iteration,
                    screen=screen,
                    after=after,
                    target=wt_target,
                    wt_ev=wt_ev,
                    attempt=attempt,
                )
                if not corrected:
                    fallback = await self.recovery.handle(
                        Classification(
                            failure_type=FailureType.WRONG_TARGET,
                            detail="postmortem_fallback",
                        ),
                        step_controller=controller,
                        ctx=StrategyContext(
                            driver=self.driver,
                            screen=after,
                            grounding_result=iteration.grounding_result,
                            target=wt_target,
                        ),
                        action_timeout=self.config.agent.action.default_timeout_seconds,
                    )
                    iteration.recovery_attempts.append(fallback)
            log.info(
                "wrong_target_attributed",
                run_id=ctx.run_id,
                step_id=step.id,
                iteration_index=iteration.iteration_index,
                nearest_blob_distance_px=wt_ev.nearest_blob_distance_px,
                nearest_blob_direction=wt_ev.nearest_blob_direction,
                recovery_strategy=attempt.strategy,
            )

        # RECORDING
        ctx.state_machine.force(AgentState.RECORDING, "record")
        if ctx.current_step_record is not None:
            ctx.current_step_record.stage_durations_ms.update(t_stages)

        return vr
