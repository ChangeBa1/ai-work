"""Recovery engine with Tier-2 budgets (data-model.md §8)."""

from __future__ import annotations

import asyncio

from vnc_agent.config import AppConfig, RecoveryPolicy
from vnc_agent.domain.focus_path import VerifiedFocusNavigationPath
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.recovery import FailureType, RecoveryAttempt, RecoveryStrategy
from vnc_agent.recovery.classifier import Classification
from vnc_agent.recovery.strategies import (
    ROUTING,
    StrategyContext,
    execute_strategy,
    normalize_focus_hint,
    try_build_focus_path,
)
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
        return list(ROUTING.get(ft, ["recapture"]))

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
        path_changing = strategy in {"second_candidate", "re_ground", "switch_to_keyboard"}
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

        self._tier2[ft.value] = used + 1
        self._step_strategy_index[ft.value] = step_idx + 1
        attempt = RecoveryAttempt(
            failure_type=ft,
            sub_reason=classification.sub_reason,
            strategy=strategy,
            attempt_index=used,
            max_retries=policy.max_retries,
            resolved=ok,
        )
        self.attempts.append(attempt)
        return attempt

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
