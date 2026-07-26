"""Recovery engine with Tier-2 budgets (data-model.md §8)."""

from __future__ import annotations

import asyncio

from vnc_agent.config import AppConfig, RecoveryPolicy
from vnc_agent.domain.focus_path import VerifiedFocusNavigationPath
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.recovery import (
    FailureType,
    PostmortemCorrectionPlan,
    RecoveryAttempt,
    RecoveryStrategy,
    ZoomRegroundPlan,
)
from vnc_agent.recovery.classifier import Classification
from vnc_agent.recovery.strategies import (
    ROUTING,
    StrategyContext,
    execute_strategy,
    normalize_focus_hint,
    try_build_focus_path,
)
from vnc_agent.recovery.zoom import determine_zoom_roi
from vnc_agent.runtime.exceptions import StepBudgetExhaustedError
from vnc_agent.runtime.step_controller import StepController


class RecoveryEngine:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        # Per ActionIteration: failure_type -> attempts used (Tier-2)
        self._tier2: dict[str, int] = {}
        # Per TestStep: advances preferred → fallback strategy across iterations
        # so we do not re-apply the same first strategy forever when Tier-2 resets
        self._step_strategy_index: dict[str, int] = {}
        self.attempts: list[RecoveryAttempt] = []
        # Side-effect flags (persist across ActionIterations within a step)
        self.prefer_keyboard = False
        self.candidate_index = 0
        self.need_restart_step = False
        self.need_reground = False
        # Feature 014: one-shot zoom escalation plan (consumed by the runtime's
        # grounding branch on the next ActionIteration) + per-step usage count.
        self.zoom_request: ZoomRegroundPlan | None = None
        self._zoom_attempts_step = 0
        # Feature 023: one-shot corrected-click plan from an accepted
        # post-mortem diagnosis (consumed by the next ActionIteration's
        # grounding branch) + per-step diagnosis cap counter (FR-008).
        self.postmortem_correction: PostmortemCorrectionPlan | None = None
        self._postmortem_attempts_step = 0
        # 002: verified focus path for prefer_keyboard (FR-020~024)
        self.focus_path: VerifiedFocusNavigationPath | None = None
        self._last_screen: StructuredScreen | None = None
        self._last_target_hint: str = ""
        # Known current keyboard focus (for structural tab-order derivation)
        self._last_known_focus_hint: str = ""
        # Within-run successful focus sequences keyed by normalized to_hint
        self._successful_focus_paths: dict[str, list[str]] = {}

    def reset_iteration(self) -> None:
        """
        Full reset of recovery state.

        MUST be called at **TestStep** start only (not every ActionIteration).
        Upgrade flags (candidate_index / prefer_keyboard / need_reground) are set by
        `_apply_side_effects` at the end of one iteration and must survive into the
        next iteration of the same step (T097 / FR-037).
        """
        self._tier2.clear()
        self._step_strategy_index.clear()
        self.attempts.clear()
        self.prefer_keyboard = False
        self.candidate_index = 0
        self.need_restart_step = False
        self.need_reground = False
        self.zoom_request = None
        self._zoom_attempts_step = 0
        self.postmortem_correction = None
        self._postmortem_attempts_step = 0
        self.focus_path = None
        self._last_screen = None
        self._last_target_hint = ""
        # Keep _last_known_focus_hint and _successful_focus_paths across TestSteps
        # within a run (T070 / prior_successful_replay is within-run, not within-step).

    def remember_screen(
        self,
        screen: StructuredScreen | None,
        *,
        target_hint: str = "",
        known_focus_hint: str = "",
    ) -> None:
        """Cache latest screen + hints for focus-path construction on switch_to_keyboard."""
        self._last_screen = screen
        if target_hint:
            self._last_target_hint = target_hint
        if known_focus_hint:
            self._last_known_focus_hint = known_focus_hint

    def remember_focus(self, focus_hint: str) -> None:
        """Record the currently known keyboard focus (OCR/template text)."""
        if focus_hint:
            self._last_known_focus_hint = focus_hint

    def record_successful_focus_path(self, path: VerifiedFocusNavigationPath) -> None:
        """
        Remember a within-run successful focus sequence for prior_successful_replay.

        After a focus path has been executed and verified, call this so a later
        switch_to_keyboard for the same target can reuse the sequence.
        """
        key = normalize_focus_hint(path.to_hint)
        if not key or not path.tab_sequence:
            return
        self._successful_focus_paths[key] = list(path.tab_sequence)
        # Focus is now on the target after a successful replay
        self._last_known_focus_hint = path.to_hint

    def begin_action_iteration(self) -> None:
        """
        Start a new ActionIteration within the current TestStep.

        Tier-2 budgets reset per ActionIteration (data-model.md §8), but upgrade
        flags and step-level strategy progression MUST be preserved.
        """
        self._tier2.clear()
        self.attempts.clear()

    def policy_for(self, ft: FailureType) -> RecoveryPolicy:
        return self.config.recovery_for(ft.value)

    def strategies_for(self, ft: FailureType) -> list[RecoveryStrategy]:
        strategies = list(ROUTING.get(ft, ["recapture"]))
        # Feature 023 (FR-007): disabling the post-mortem restores the
        # feature-022 WRONG_TARGET chain byte-for-byte (both the strategy
        # list and the step-level index progression over it).
        if (
            ft == FailureType.WRONG_TARGET
            and not self.config.agent.wrong_target_postmortem.enabled
        ):
            strategies = [s for s in strategies if s != "postmortem"]
        return strategies

    async def handle(
        self,
        classification: Classification,
        *,
        step_controller: StepController | None,
        ctx: StrategyContext,
        action_timeout: float = 10.0,
    ) -> RecoveryAttempt:
        ft = classification.failure_type

        # VNC disconnected: restart_step consumes Tier-1 directly
        if ft == FailureType.VNC_DISCONNECTED:
            if step_controller is None or step_controller.remaining_budget() <= 0:
                # Budget exhausted — MUST NOT restart_step
                attempt = RecoveryAttempt(
                    failure_type=ft,
                    strategy="restart_step",
                    attempt_index=0,
                    max_retries=1,
                    resolved=False,
                )
                self.attempts.append(attempt)
                return attempt
            policy = self.policy_for(ft)
            ok = await execute_strategy(
                "restart_step", ctx, timeout_seconds=action_timeout
            )
            try:
                if ok:
                    step_controller.consume_for_restart_step()
                    self.need_restart_step = True
            except StepBudgetExhaustedError:
                ok = False
            attempt = RecoveryAttempt(
                failure_type=ft,
                strategy="restart_step",
                attempt_index=0,
                max_retries=1,
                resolved=ok,
            )
            self.attempts.append(attempt)
            return attempt

        policy = self.policy_for(ft)
        used = self._tier2.get(ft.value, 0)
        strategies = self.strategies_for(ft)
        if used >= policy.max_retries:
            attempt = RecoveryAttempt(
                failure_type=ft,
                sub_reason=classification.sub_reason,
                strategy=strategies[-1],
                attempt_index=used,
                max_retries=policy.max_retries,
                resolved=False,
            )
            self.attempts.append(attempt)
            return attempt

        # Progress through preferred → fallback across the whole TestStep
        step_idx = self._step_strategy_index.get(ft.value, 0)
        strategy = strategies[min(step_idx, len(strategies) - 1)]
        # Feature 014 (FR-002/FR-006): the zoom escalation needs a derivable
        # ROI and an unexhausted per-step cap; otherwise substitute the next
        # strategy in the sequence (existing path continues, no grid sweep).
        zoom_plan: ZoomRegroundPlan | None = None
        if strategy == "zoom_reground":
            zoom_plan = self._plan_zoom(ctx)
            if zoom_plan is None:
                strategy = strategies[min(step_idx + 1, len(strategies) - 1)]
        # Feature 023 (FR-008): postmortem needs a capable runtime (client +
        # full evidence, signalled via ctx) and an unexhausted per-step cap;
        # otherwise substitute the next strategy — same refusal semantics as
        # the zoom escalation above.
        if strategy == "postmortem" and not self._postmortem_allowed(ctx):
            strategy = strategies[min(step_idx + 1, len(strategies) - 1)]
        path_changing = strategy in {
            "second_candidate",
            "re_ground",
            "zoom_reground",
            "switch_to_keyboard",
            "postmortem",
        }
        prerequisites_met = (
            (not policy.requires_strong_model or ctx.strong_model_available)
            and (
                not policy.requires_human_confirmation
                or ctx.human_confirmation_granted
            )
            and (policy.allows_action_path_change or not path_changing)
        )
        budget_available = True
        if policy.consumes_global_retry_budget and step_controller is not None:
            budget_available = step_controller.consume_global_retry_budget()
        if not prerequisites_met or not budget_available:
            attempt = RecoveryAttempt(
                failure_type=ft,
                sub_reason=classification.sub_reason,
                strategy=strategy,
                attempt_index=used,
                max_retries=policy.max_retries,
                resolved=False,
            )
            self.attempts.append(attempt)
            return attempt
        if policy.cooldown_ms > 0 and used > 0:
            await asyncio.sleep(policy.cooldown_ms / 1000.0)

        ok = await execute_strategy(strategy, ctx, timeout_seconds=action_timeout)
        self._apply_side_effects(strategy)
        if strategy == "zoom_reground" and zoom_plan is not None and ok:
            # One-shot plan for the next ActionIteration's grounding branch;
            # counted against the per-step cap (FR-006).
            self.zoom_request = zoom_plan
            self._zoom_attempts_step += 1
            self.need_reground = True
        if strategy == "postmortem" and ok:
            # Feature 023 (FR-008): the diagnosis itself runs in the runtime
            # right after handle() returns; the per-step cap is consumed on
            # selection so a failed diagnosis can never be re-attempted.
            self._postmortem_attempts_step += 1

        self._tier2[ft.value] = used + 1
        self._step_strategy_index[ft.value] = step_idx + 1
        attempt = RecoveryAttempt(
            failure_type=ft,
            sub_reason=classification.sub_reason,
            strategy=strategy,
            attempt_index=used,
            max_retries=policy.max_retries,
            resolved=ok,
            roi=zoom_plan.roi if strategy == "zoom_reground" and zoom_plan else None,
            scale_factor=(
                zoom_plan.scale_factor
                if strategy == "zoom_reground" and zoom_plan
                else None
            ),
            roi_source=(
                zoom_plan.roi_source
                if strategy == "zoom_reground" and zoom_plan
                else None
            ),
        )
        self.attempts.append(attempt)
        return attempt

    def _plan_zoom(self, ctx: StrategyContext) -> ZoomRegroundPlan | None:
        """Feature 014: derive a one-shot zoom plan or refuse (FR-002/FR-006).

        Refusal reasons: per-step cap exhausted, escalation disabled
        (max_per_step=0), no screen/resolution evidence, or no derivable ROI
        (no prior candidates and no anchor-text hit). The caller then
        substitutes the next strategy in the sequence.
        """
        zoom_cfg = self.config.agent.zoom_reground
        if self._zoom_attempts_step >= zoom_cfg.max_per_step:
            return None
        screen = ctx.screen or self._last_screen
        if screen is None:
            return None
        resolution = screen.resolution
        derived = determine_zoom_roi(
            resolution=resolution,
            grounding_result=ctx.grounding_result,
            ocr_items=screen.ocr_items,
            target=ctx.target,
            expand_factor=zoom_cfg.roi_expand_factor,
            min_size_px=zoom_cfg.min_roi_size_px,
        )
        if derived is None:
            return None
        roi, source = derived
        return ZoomRegroundPlan(
            roi=roi.as_tuple(),
            scale_factor=zoom_cfg.scale_factor,
            roi_source=source,  # type: ignore[arg-type]
        )

    def take_zoom_request(self) -> ZoomRegroundPlan | None:
        """One-shot consumption of the pending zoom plan (Feature 014)."""
        plan = self.zoom_request
        self.zoom_request = None
        return plan

    def _postmortem_allowed(self, ctx: StrategyContext) -> bool:
        """Feature 023 (FR-008): may the postmortem tier be selected now?"""
        pm_cfg = self.config.agent.wrong_target_postmortem
        if not pm_cfg.enabled:
            return False
        if self._postmortem_attempts_step >= pm_cfg.max_retries:
            return False
        return ctx.postmortem_capable

    def set_postmortem_correction(self, plan: PostmortemCorrectionPlan) -> None:
        """Store the one-shot corrected-click plan (Feature 023, FR-005)."""
        self.postmortem_correction = plan

    def take_postmortem_correction(self) -> PostmortemCorrectionPlan | None:
        """One-shot consumption of the pending corrected-click plan."""
        plan = self.postmortem_correction
        self.postmortem_correction = None
        return plan

    def tier2_exhausted(self, ft: FailureType) -> bool:
        policy = self.policy_for(ft)
        return self._tier2.get(ft.value, 0) >= policy.max_retries

    def _apply_side_effects(self, strategy: RecoveryStrategy) -> None:
        if strategy == "switch_to_keyboard":
            self.prefer_keyboard = True
            # T069: derive a real tab_sequence when evidence exists; else leave None
            # (FR-022 — never invent a default single Tab).
            self.focus_path = self._build_focus_path_for_keyboard()
        if strategy == "second_candidate":
            self.candidate_index += 1
        if strategy == "re_ground":
            self.need_reground = True
        if strategy == "restart_step":
            self.need_restart_step = True

    def _build_focus_path_for_keyboard(self) -> VerifiedFocusNavigationPath | None:
        """
        Build VerifiedFocusNavigationPath for prefer_keyboard.

        Priority:
        1. prior_successful_replay — within-run recorded sequence for same target
        2. structural_diff_confirmed — OCR/template reading-order delta from known
           focus hint to target hint

        Returns None when neither source yields a reliable non-empty sequence.
        """
        to_hint = self._last_target_hint
        from_hint = self._last_known_focus_hint
        key = normalize_focus_hint(to_hint)

        # 1) Within-run successful replay
        prior = self._successful_focus_paths.get(key) if key else None
        if prior:
            path = try_build_focus_path(
                self._last_screen,
                to_hint=to_hint,
                from_hint=from_hint,
                tab_sequence=prior,
                method="prior_successful_replay",
            )
            if path is not None:
                return path

        # 2) Structural derivation from anchor ordering on the last screen
        if self._last_screen is None or not to_hint or not from_hint:
            return None
        return try_build_focus_path(
            self._last_screen,
            to_hint=to_hint,
            from_hint=from_hint,
            tab_sequence=None,
            method="structural_diff_confirmed",
        )
