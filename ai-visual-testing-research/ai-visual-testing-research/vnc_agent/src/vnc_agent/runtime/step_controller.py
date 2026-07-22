"""Step-level shared budget (research.md §10, data-model.md §2/§8)."""

from __future__ import annotations

from vnc_agent.runtime.exceptions import StepBudgetExhaustedError


class StepController:
    """
    Single remaining-budget counter shared by:
    - verification-failure retries
    - in-step micro-action iterations
    - VNC reconnect full-step restarts (restart_step)

    All three consume the same Tier-1 counter (TestStep.max_retries).
    """

    def __init__(self, max_retries: int) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        # Budget = number of additional ActionIterations after the first (index 0).
        # Total iterations allowed = max_retries + 1
        self.max_retries = max_retries
        self.remaining = max_retries
        self.iteration_index = 0
        self._exhausted = False
        self._reserved_recovery_iterations = 0

    @property
    def exhausted(self) -> bool:
        return self._exhausted or self.remaining < 0

    def can_start_iteration(self) -> bool:
        """True if another ActionIteration may begin (including the first)."""
        if self.iteration_index == 0 and not self._exhausted:
            return True
        return (
            self.remaining > 0 or self._reserved_recovery_iterations > 0
        ) and not self._exhausted

    def start_iteration(self) -> int:
        """
        Begin a new ActionIteration. Returns the iteration_index.
        First call does not consume remaining; subsequent calls consume 1.
        """
        if self.iteration_index == 0 and not self._exhausted:
            idx = 0
            self.iteration_index = 1  # next will be 1
            return idx
        if self._reserved_recovery_iterations > 0 and not self._exhausted:
            self._reserved_recovery_iterations -= 1
            idx = self.iteration_index
            self.iteration_index += 1
            return idx
        if self.remaining <= 0:
            self._exhausted = True
            raise StepBudgetExhaustedError(
                f"Tier-1 budget exhausted (max_retries={self.max_retries})"
            )
        self.remaining -= 1
        idx = self.iteration_index
        self.iteration_index += 1
        return idx

    def consume_for_restart_step(self) -> int:
        """
        restart_step directly consumes one Tier-1 unit (data-model.md §8).
        Returns new iteration_index to use after restart.
        """
        if self.remaining <= 0:
            self._exhausted = True
            raise StepBudgetExhaustedError(
                "Tier-1 budget exhausted; MUST NOT attempt restart_step"
            )
        return self.start_iteration()

    def remaining_budget(self) -> int:
        return max(0, self.remaining)

    def consume_global_retry_budget(self) -> bool:
        """Atomically consume one shared recovery/retry unit when available."""
        if self.remaining <= 0 or self._exhausted:
            self._exhausted = True
            self.remaining = 0
            return False
        self.remaining -= 1
        self._reserved_recovery_iterations += 1
        return True

    def mark_exhausted(self) -> None:
        self._exhausted = True
        self.remaining = 0
        self._reserved_recovery_iterations = 0
