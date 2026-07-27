"""Replay-mode execution (feature 016, overall_design.md §10.2, spec FR-005~010).

``ReplayPlayer`` is a *separate* execution path from the exploration
iteration loop (``AgentRuntime.run_action_iteration`` is never entered): the
"what to do next" information comes entirely from the recorded ReplayStep
sequence, so the Planner is never called (design §21.3 回放成功时不调用
Planner). Per mouse step the direct-locate chain runs (fingerprint tier →
template → OCR anchor → same-resolution bbox → ``safe_click_point``);
keyboard steps replay their recorded key sequence verbatim. Every executed
attempt goes through the unchanged independent verification engine with the
verification spec frozen in the ReplayStep (Constitution IV — replay never
exempts verification).

Failure of the direct path escalates once per step to a grounder fallback
through the existing ``GroundingRequest``/``ActionPolicy.resolve`` channel;
a verified fallback success generates a *pending* ReplayPatch (ADR-005 — the
stored script's target fields are read-only during replay; only
success/failure statistics are updated) and feeds feature 015's memory via
its public ``record_success`` entry point. A failed fallback ends the run
with the failing ReplayStep named in the failure reason.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np

from vnc_agent.domain.action import ExecutableAction
from vnc_agent.domain.observation import Region, StructuredScreen
from vnc_agent.domain.replay import ReplayScript, ReplayStep, ReplayStepAudit
from vnc_agent.domain.run import ActionIteration, HumanConfirmedFact
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.logging_setup import get_logger
from vnc_agent.memory.fingerprint import (
    build_page_fingerprint,
    classify_page_match,
    page_similarity,
)
from vnc_agent.memory.service import normalize_target_label
from vnc_agent.models.provider import GroundingRequest
from vnc_agent.perception.action_effect import classify_action_effect
from vnc_agent.planning.click_point import safe_click_point
from vnc_agent.replay.locator import LocateResult, locate_target, semantic_target_label
from vnc_agent.replay.patch import build_pending_patch, warn_if_auto_apply_configured
from vnc_agent.runtime.context_identity import (
    MissingIdentityFieldError,
    grounder_identity,
    verifier_identity,
)
from vnc_agent.runtime.exceptions import ReplayUnavailableError, VNCConnectionError
from vnc_agent.runtime.run_context import RunContext
from vnc_agent.runtime.state_machine import AgentState
from vnc_agent.runtime.telemetry import CounterEvent, log_event, measure_stage
from vnc_agent.verification.business_resolver import (
    evaluate_precondition,
    resolve_step_result,
)

if TYPE_CHECKING:
    from vnc_agent.domain.testcase import TestCase, TestStep
    from vnc_agent.runtime.agent_runtime import AgentRuntime

log = get_logger("replay_player")


def _provider_identity_snapshot(provider: Any) -> dict[str, Any]:
    cfg = getattr(provider, "cfg", None)
    if cfg is not None:
        return {"provider": type(provider).__name__, "model": getattr(cfg, "model", None)}
    return {"provider": type(provider).__name__}


class _StepOutcome:
    """Internal per-step verdict."""

    def __init__(self, passed: bool, failure_reason: str | None = None) -> None:
        self.passed = passed
        self.failure_reason = failure_reason


class ReplayPlayer:
    """Drives one mode:"replay" run on top of an assembled AgentRuntime."""

    def __init__(self, runtime: AgentRuntime) -> None:
        self.rt = runtime
        self.cfg = runtime.config
        self.replay_cfg = runtime.config.agent.replay
        self.mem_cfg = runtime.config.agent.memory

    # ------------------------------------------------------------------
    # preflight (fail fast, before any VNC connection — spec FR-005)
    # ------------------------------------------------------------------

    async def preflight(self, test_case: TestCase) -> ReplayScript:
        if not self.replay_cfg.enabled:
            raise ReplayUnavailableError(
                "replay.enabled is false — enable it in config/agent.yaml to run "
                f"test case {test_case.id!r} in replay mode"
            )
        if self.rt.replay_repo is None:
            raise ReplayUnavailableError(
                "replay mode requires persistence (no repository configured); "
                "cannot load a recorded script"
            )
        script = await self.rt.replay_repo.get_latest_script(test_case.id)
        if script is None:
            raise ReplayUnavailableError(
                f"no replay script recorded for test case {test_case.id!r} — run "
                "it once in exploration mode (mode: explicit) first"
            )
        declared = [s.id for s in test_case.steps]
        recorded = [s.step_id for s in script.steps]
        if declared != recorded:
            raise ReplayUnavailableError(
                f"replay script v{script.version} for test case {test_case.id!r} "
                f"records steps {recorded} but the test case declares {declared}; "
                "re-run exploration to record a fresh script"
            )
        return script

    # ------------------------------------------------------------------
    # run shell (mirrors AgentRuntime.run's connect/report envelope)
    # ------------------------------------------------------------------

    async def run(
        self,
        test_case: TestCase,
        *,
        human_confirmed_facts: list[HumanConfirmedFact] | None = None,
    ) -> RunContext:
        script = await self.preflight(test_case)

        ctx = RunContext(
            test_case,
            run_id=self.rt.capture_service.run_id,
            human_confirmed_facts=human_confirmed_facts,
        )
        ctx.begin_run()
        ctx.state_machine.transition(AgentState.CONNECTING, "start")
        try:
            await self.rt.driver.connect()
        except Exception as e:
            log.error("vnc_connect_failed", error=str(e), run_id=ctx.run_id)
            ctx.finish_run("failed")
            ctx.state_machine.force(AgentState.FAILED, "vnc_connect_failed")
            if self.rt.repo:
                await self.rt.repo.save_run(ctx.test_run)
            raise VNCConnectionError(str(e)) from e

        ctx.state_machine.transition(AgentState.PREPARING, "connected")
        self.rt.capture_service.test_run = ctx.test_run
        self.rt.artifact_store.recover_orphans(ctx.run_id, referenced_bundle_ids=set())
        log_event(
            "replay_run_started",
            run_id=ctx.run_id,
            test_case_id=test_case.id,
            script_id=script.script_id,
            script_version=script.version,
        )

        run_failed = False
        for replay_step in script.steps:
            if ctx.cancelled:
                ctx.mark_step_cancelled()
                ctx.finish_run("cancelled")
                ctx.state_machine.force(AgentState.CANCELLED, "cancel")
                break
            step = ctx.advance_step()
            assert step is not None and step.id == replay_step.step_id
            outcome = await self._run_replay_step(ctx, step, replay_step, script)
            if outcome.passed:
                ctx.mark_step_passed()
                ctx.state_machine.force(AgentState.STEP_COMPLETED_PASSED, "passed")
                if self.rt.repo and ctx.current_step_record:
                    await self.rt.repo.save_step(ctx.run_id, ctx.current_step_record)
            else:
                ctx.mark_step_failed(outcome.failure_reason)
                ctx.state_machine.force(AgentState.STEP_COMPLETED_FAILED, "failed")
                if self.rt.repo and ctx.current_step_record:
                    await self.rt.repo.save_step(ctx.run_id, ctx.current_step_record)
                ctx.finish_run("failed")
                ctx.state_machine.force(AgentState.FAILED, "step_failed")
                run_failed = True
                break
        else:
            ctx.finish_run("passed")
            ctx.state_machine.force(AgentState.PASSED, "all_passed")

        if ctx.test_run.status == "running":  # cancelled mid-loop edge
            ctx.finish_run("cancelled")

        if self.rt.repo:
            await self.rt.repo.save_run(ctx.test_run)
        if self.rt.report_builder:
            self.rt.report_builder.build(ctx.test_run, formats=self.rt.report_formats)
            if self.rt.repo:
                await self.rt.repo.save_run(ctx.test_run)
        log_event(
            "replay_run_finished",
            run_id=ctx.run_id,
            test_case_id=test_case.id,
            script_version=script.version,
            status=ctx.test_run.status,
            failed=run_failed,
        )
        return ctx

    # ------------------------------------------------------------------
    # one replay step (direct attempt + at most one grounder fallback)
    # ------------------------------------------------------------------

    async def _run_replay_step(
        self,
        ctx: RunContext,
        step: TestStep,
        replay_step: ReplayStep,
        script: ReplayScript,
    ) -> _StepOutcome:
        # --- iteration 0: observe + direct attempt ----------------------
        iteration = ctx.begin_iteration(0)
        ctx.state_machine.force(AgentState.OBSERVING, "iteration_start")
        screen = await self.rt.pipeline.observe(
            step_id=step.id, capture_source="observation"
        )
        iteration.before_frame_id = screen.image_path
        iteration.before_content_hash = screen.content_hash
        ctx.state_machine.force(AgentState.UNDERSTANDING, "observed")

        # Run-start precondition gate (same semantics as exploration).
        if (
            ctx.test_case.precondition is not None
            and ctx.test_run.precondition_evaluation.checked_at is None
        ):
            precondition_eval = await evaluate_precondition(
                ctx.test_case.precondition, screen, self.rt.verifier
            )
            ctx.test_run.precondition_evaluation = precondition_eval
            if precondition_eval.status == "failed":
                iteration.verification_result = VerificationResult(
                    status="failed", reason="precondition_failed"
                )
                return _StepOutcome(
                    False,
                    self._failure_reason(replay_step, "precondition_failed"),
                )

        iteration.semantic_action = replay_step.semantic_action

        frame = self._read_frame(screen.image_path)
        fingerprint = build_page_fingerprint(frame, screen.ocr_items, screen.resolution)
        similarity = page_similarity(fingerprint, replay_step.page_fingerprint)
        level = classify_page_match(
            similarity,
            same_resolution=(
                tuple(screen.resolution) == tuple(replay_step.page_fingerprint.resolution)
            ),
            high=self.mem_cfg.page_match_high,
            medium=self.mem_cfg.page_match_medium,
            low=self.mem_cfg.page_match_low,
        )
        allowed_levels = (
            ("high",)
            if self.replay_cfg.min_page_match_level == "high"
            else ("high", "medium")
        )

        if replay_step.preferred_method == "keyboard":
            # Design §11 keyboard replay: the recorded key sequence is
            # replayed verbatim; a below-tier fingerprint only warns —
            # independent verification is the correctness gate (spec
            # Clarification 7).
            if level not in allowed_levels:
                log.warning(
                    "replay_keyboard_below_page_match_level",
                    replay_step_id=replay_step.replay_step_id,
                    level=level,
                    similarity=similarity,
                )
            executable = replay_step.recorded_executable
            if executable is None:
                return _StepOutcome(
                    False,
                    self._failure_reason(replay_step, "keyboard step has no recorded action"),
                )
            iteration.executable_action = executable
            vr, after = await self._execute_and_verify(
                ctx, step, iteration, replay_step, executable, screen
            )
            iteration.replay_audit = self._audit(
                replay_step, script, "keyboard", similarity, None, None
            )
            self._record_step_replayed(ctx, replay_step, script, "keyboard")
            await self._bump_stats(replay_step, passed=vr.status == "passed")
            if vr.status == "passed":
                return _StepOutcome(True)
            # No visual fallback for keyboard steps (spec FR-008).
            return _StepOutcome(
                False,
                self._failure_reason(
                    replay_step, f"keyboard replay verification {vr.status}: {vr.reason}"
                ),
            )

        # --- mouse step: direct-locate chain ----------------------------
        located: LocateResult | None = None
        if level in allowed_levels:
            template = self._read_frame(replay_step.target_template_path or "")
            located = locate_target(
                frame,
                screen.ocr_items,
                replay_step,
                template,
                current_resolution=screen.resolution,
                template_match_threshold=self.replay_cfg.template_match_threshold,
                bbox_expand_ratio=self.replay_cfg.bbox_expand_ratio,
                anchor_offset_tolerance_px=self.replay_cfg.anchor_offset_tolerance_px,
            )

        if located is not None:
            executable = self._executable_from_bbox(replay_step, located.bbox, screen)
            iteration.executable_action = executable
            vr, after = await self._execute_and_verify(
                ctx, step, iteration, replay_step, executable, screen
            )
            iteration.replay_audit = self._audit(
                replay_step, script, located.method, similarity, located.template_score, None
            )
            if vr.status == "passed":
                self._record_step_replayed(ctx, replay_step, script, located.method)
                await self._bump_stats(replay_step, passed=True)
                return _StepOutcome(True)
            # Direct hit executed but verification did not pass — one
            # fallback attempt on a fresh observation (spec FR-008).
            return await self._fallback_iteration(
                ctx,
                step,
                replay_step,
                script,
                iteration_index=1,
                reason=f"direct locate ({located.method}) verification {vr.status}",
            )

        # Nothing located directly (or fingerprint tier too low /
        # direct_fallback_only) — fall back within this same iteration.
        reason = (
            "page fingerprint below required tier"
            if level not in allowed_levels
            else (
                "step is direct_fallback_only (masked region)"
                if replay_step.direct_fallback_only
                else "template/anchor/bbox locate all missed"
            )
        )
        return await self._fallback_in_iteration(
            ctx, step, replay_step, script, iteration, screen, similarity, reason
        )

    # ------------------------------------------------------------------
    # fallback grounding (at most once per step — spec Clarification 6)
    # ------------------------------------------------------------------

    async def _fallback_iteration(
        self,
        ctx: RunContext,
        step: TestStep,
        replay_step: ReplayStep,
        script: ReplayScript,
        *,
        iteration_index: int,
        reason: str,
    ) -> _StepOutcome:
        """Fallback on a fresh observation in a new ActionIteration."""
        iteration = ctx.begin_iteration(iteration_index)
        ctx.state_machine.force(AgentState.OBSERVING, "replay_fallback")
        screen = await self.rt.pipeline.observe(step_id=step.id, capture_source="retry")
        iteration.before_frame_id = screen.image_path
        iteration.before_content_hash = screen.content_hash
        iteration.semantic_action = replay_step.semantic_action
        frame = self._read_frame(screen.image_path)
        fingerprint = build_page_fingerprint(frame, screen.ocr_items, screen.resolution)
        similarity = page_similarity(fingerprint, replay_step.page_fingerprint)
        return await self._fallback_in_iteration(
            ctx, step, replay_step, script, iteration, screen, similarity, reason
        )

    async def _fallback_in_iteration(
        self,
        ctx: RunContext,
        step: TestStep,
        replay_step: ReplayStep,
        script: ReplayScript,
        iteration: ActionIteration,
        screen: StructuredScreen,
        similarity: float,
        reason: str,
    ) -> _StepOutcome:
        sa = replay_step.semantic_action
        ctx.state_machine.force(AgentState.GROUNDING, "replay_fallback_ground")
        target = sa.target.model_dump() if sa.target else {"description": sa.intent}
        template_candidates: list[dict[str, Any]] = []
        if replay_step.bbox is not None:
            # The recorded target rides the existing hint channel — the
            # grounder decides (same hint semantics as feature 015 FR-007).
            template_candidates.append(
                {
                    "template_id": f"replay_step:{replay_step.replay_step_id}",
                    "bbox": list(replay_step.bbox),
                    "confidence": similarity,
                }
            )
        grounding_request = GroundingRequest(
            image_ref=screen.path_for_model(),
            crop_offset=screen.crop_offset,
            resolution=screen.resolution,
            target=target,
            ocr_candidates=[i.model_dump() for i in screen.ocr_items],
            template_candidates=template_candidates,
            ui_index_candidates=[],
        )
        with measure_stage(
            ctx.test_run, stage="grounder", run_id=ctx.run_id, step_id=step.id,
            frame_id=screen.frame_id, iteration_index=iteration.iteration_index,
            clock=self.rt.clock,
        ):
            grounding = await self.rt.grounder.ground(grounding_request)
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
                },
                requested_model_config=_provider_identity_snapshot(self.rt.grounder),
                retry_grounding_state={
                    "iteration_index": iteration.iteration_index,
                    "candidate_index": 0,
                },
            )
            self.rt._record_model_call_audit(
                ctx,
                step_id=step.id,
                frame_id=screen.frame_id,
                iteration_index=iteration.iteration_index,
                model_role="grounder",
                request_identity=grounder_req_id,
                context_identity=grounder_req_id,
                sanitized_request={"target": target, "trigger": "replay_fallback"},
                sanitized_response={
                    "found": grounding.found,
                    "candidate_count": len(grounding.candidates),
                },
            )
        except MissingIdentityFieldError:
            pass

        # Existing consensus gate — used, never modified (spec Clarification 4).
        policy_result = self.rt.policy.resolve(sa, screen, grounding_result=grounding)
        executable = policy_result.executable
        if policy_result.grounding_result:
            iteration.grounding_result = policy_result.grounding_result
        if executable is None or executable.method != "mouse":
            iteration.replay_audit = self._audit(
                replay_step, script, "fallback_grounding", similarity, None, None
            )
            self._record_step_replayed(ctx, replay_step, script, "fallback_grounding")
            await self._bump_stats(replay_step, passed=False)
            return _StepOutcome(
                False,
                self._failure_reason(
                    replay_step, f"{reason}; grounder fallback found no actionable target"
                ),
            )

        iteration.executable_action = executable
        vr, after = await self._execute_and_verify(
            ctx, step, iteration, replay_step, executable, screen
        )
        patch_id: str | None = None
        if vr.status == "passed":
            patch_id = await self._generate_patch(
                ctx, replay_step, script, executable, reason, screen, after, vr
            )
            # Feature 015 co-write (spec FR-010): a verified fallback success
            # feeds the global element memory through its public entry point.
            if (
                self.rt.memory is not None
                and executable.target_region is not None
            ):
                label = semantic_target_label(sa)
                if normalize_target_label(label):
                    await self.rt.memory.record_success(
                        screen, label, executable.target_region
                    )
        iteration.replay_audit = self._audit(
            replay_step, script, "fallback_grounding", similarity, None, patch_id
        )
        self._record_step_replayed(ctx, replay_step, script, "fallback_grounding")
        await self._bump_stats(replay_step, passed=vr.status == "passed")
        if vr.status == "passed":
            return _StepOutcome(True)
        return _StepOutcome(
            False,
            self._failure_reason(
                replay_step,
                f"{reason}; grounder fallback verification {vr.status}: {vr.reason}",
            ),
        )

    # ------------------------------------------------------------------
    # execute + independent verification (Constitution IV — unchanged gates)
    # ------------------------------------------------------------------

    async def _execute_and_verify(
        self,
        ctx: RunContext,
        step: TestStep,
        iteration: ActionIteration,
        replay_step: ReplayStep,
        executable: ExecutableAction,
        screen: StructuredScreen,
    ) -> tuple[VerificationResult, StructuredScreen]:
        t_stages: dict[str, int] = {}
        ctx.state_machine.force(AgentState.EXECUTING, "execute")
        t0 = time.monotonic()
        try:
            exec_result = await self.rt.executor.execute(executable)
        except Exception as e:
            iteration.execution_result = None
            vr = VerificationResult(status="failed", reason=f"execute error: {e}")
            iteration.verification_result = vr
            return vr, screen
        iteration.execution_result = exec_result
        t_stages["executing"] = int((time.monotonic() - t0) * 1000)

        ctx.state_machine.force(AgentState.WAITING, "wait")
        t0 = time.monotonic()
        wait_result = await self.rt.stability.wait_stable(step_id=step.id)
        iteration.wait_result = wait_result
        t_stages["waiting"] = int((time.monotonic() - t0) * 1000)

        ctx.state_machine.force(AgentState.VERIFYING, "verify")
        t0 = time.monotonic()
        after = await self.rt.pipeline.observe(
            step_id=step.id, capture_source="post_action_verification"
        )
        iteration.after_frame_id = after.image_path

        perc = self.cfg.agent.perception
        action_effect = classify_action_effect(
            screen,
            after,
            intent=replay_step.semantic_action.intent,
            local_blob_min_ratio=perc.local_blob_min_ratio,
            error_keywords=list(perc.error_keywords),
        )
        iteration.action_effect = action_effect

        async def _reobserve_after() -> StructuredScreen:
            return await self.rt.pipeline.observe(
                step_id=step.id, capture_source="post_action_verification"
            )

        with measure_stage(
            ctx.test_run, stage="verification", run_id=ctx.run_id, step_id=step.id,
            frame_id=after.frame_id, iteration_index=iteration.iteration_index,
            clock=self.rt.clock,
        ):
            # The verification spec is the ReplayStep's frozen snapshot
            # (spec FR-006); engine/arbitration are the unchanged feature
            # 002/011 machinery.
            vr = await resolve_step_result(
                replay_step.expected,
                step.verification_mode,
                action_effect,
                after,
                planner=self.rt.planner,
                reobserve=_reobserve_after,
                engine=self.rt.verifier,
                escalate=True,
                visual_override_confidence_threshold=(
                    self.cfg.agent.verification.visual_override_confidence_threshold
                ),
            )
        t_stages["verifying"] = int((time.monotonic() - t0) * 1000)
        iteration.verification_result = vr

        try:
            verifier_req_id = verifier_identity(
                visual_question_or_assertion={
                    "operator": replay_step.expected.operator,
                    "conditions": [c.type for c in replay_step.expected.conditions],
                },
                before_frame_identity=screen.content_hash or screen.frame_id,
                after_frame_identity=after.content_hash or after.frame_id,
                action_audit_context={
                    "status": action_effect.status,
                    "error_popup_signal": action_effect.evidence.error_popup_signal,
                },
                retry_iteration_state=iteration.iteration_index,
                requested_model_config=_provider_identity_snapshot(self.rt.planner),
            )
            self.rt._record_model_call_audit(
                ctx,
                step_id=step.id,
                frame_id=after.frame_id,
                iteration_index=iteration.iteration_index,
                model_role="verification",
                request_identity=verifier_req_id,
                context_identity=verifier_req_id,
                sanitized_request={"operator": replay_step.expected.operator},
                sanitized_response={"status": vr.status},
            )
        except MissingIdentityFieldError:
            pass

        ctx.state_machine.force(AgentState.RECORDING, "record")
        if ctx.current_step_record is not None:
            ctx.current_step_record.stage_durations_ms.update(t_stages)
        return vr, after

    # ------------------------------------------------------------------
    # patch + stats + telemetry helpers
    # ------------------------------------------------------------------

    async def _generate_patch(
        self,
        ctx: RunContext,
        replay_step: ReplayStep,
        script: ReplayScript,
        executable: ExecutableAction,
        reason: str,
        before_screen: StructuredScreen,
        after_screen: StructuredScreen,
        vr: VerificationResult,
    ) -> str | None:
        """Persist the pending self-heal candidate (fail-open — the step's
        pass verdict never depends on patch storage)."""
        try:
            patch = build_pending_patch(
                script=script,
                step=replay_step,
                new_executable=executable,
                reason=reason,
                before_image=before_screen.image_path or None,
                after_image=after_screen.image_path or None,
                verification_evidence=vr.evidence_refs,
            )
            warn_if_auto_apply_configured(self.replay_cfg.patch_auto_apply)
            assert self.rt.replay_repo is not None
            await self.rt.replay_repo.save_patch(patch)
            payload = {
                "patch_id": patch.patch_id,
                "replay_step_id": replay_step.replay_step_id,
                "script_version": script.version,
            }
            ctx.test_run.counter_events.append(
                CounterEvent(
                    kind="replay_patch_generated",
                    occurred_at=datetime.now(UTC),
                    payload=payload,
                )
            )
            log_event("replay_patch_generated", run_id=ctx.run_id, **payload)
            return patch.patch_id
        except Exception as exc:
            log_event(
                "replay_patch_store_failed",
                run_id=ctx.run_id,
                replay_step_id=replay_step.replay_step_id,
                error=str(exc),
            )
            return None

    async def _bump_stats(self, replay_step: ReplayStep, *, passed: bool) -> None:
        """Statistics-only script write (spec Clarification 5 / ADR-005:
        target fields stay read-only). Fail-open."""
        try:
            assert self.rt.replay_repo is not None
            await self.rt.replay_repo.bump_step_stats(
                replay_step.replay_step_id, passed=passed
            )
        except Exception as exc:
            log_event(
                "replay_stats_write_failed",
                replay_step_id=replay_step.replay_step_id,
                error=str(exc),
            )

    def _record_step_replayed(
        self,
        ctx: RunContext,
        replay_step: ReplayStep,
        script: ReplayScript,
        method: str,
    ) -> None:
        payload = {
            "replay_step_id": replay_step.replay_step_id,
            "method": method,
            "script_version": script.version,
        }
        ctx.test_run.counter_events.append(
            CounterEvent(
                kind="replay_step_replayed",
                occurred_at=datetime.now(UTC),
                payload=payload,
            )
        )
        log_event("replay_step_replayed", run_id=ctx.run_id, **payload)

    def _audit(
        self,
        replay_step: ReplayStep,
        script: ReplayScript,
        method: str,
        similarity: float,
        template_score: float | None,
        patch_id: str | None,
    ) -> ReplayStepAudit:
        return ReplayStepAudit(
            replay_step_id=replay_step.replay_step_id,
            script_version=script.version,
            locate_method=method,  # type: ignore[arg-type]
            page_similarity=similarity,
            template_score=template_score,
            patch_id=patch_id,
        )

    def _failure_reason(self, replay_step: ReplayStep, reason: str) -> str:
        """Spec Clarification 10: the failing ReplayStep is always named."""
        return (
            f"replay step failed: replay_step_id={replay_step.replay_step_id} "
            f"step_id={replay_step.step_id} reason={reason}"
        )

    def _executable_from_bbox(
        self, replay_step: ReplayStep, bbox: tuple[int, int, int, int], screen: StructuredScreen
    ) -> ExecutableAction:
        """Direct-locate hit -> click action through the unchanged feature
        013 safe-click geometry (spec FR-006)."""
        pt = safe_click_point(
            bbox,
            siblings=[],
            screen_resolution=screen.resolution,
            edge_inset_ratio=self.cfg.agent.click.edge_inset_ratio,
        )
        op = replay_step.semantic_action.action_type
        if op not in ("click", "double_click", "right_click"):
            op = "click"
        return ExecutableAction(
            method="mouse",
            operation=op,
            coordinates=(pt.x, pt.y),
            target_region=Region(x1=bbox[0], y1=bbox[1], x2=bbox[2], y2=bbox[3]),
        )

    def _read_frame(self, image_path: str) -> np.ndarray | None:
        if not image_path:
            return None
        img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        return img if img is not None and img.size else None


__all__ = ["ReplayPlayer"]
