"""RunContext: accumulates TestRun / StepRecord / ActionIteration state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator
from uuid import uuid4

from vnc_agent.domain.run import ActionIteration, StepRecord, TestRun
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.runtime.state_machine import AgentState, StateMachine


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunContext:
    def __init__(self, test_case: TestCase, run_id: str | None = None) -> None:
        self.test_case = test_case
        self.run_id = run_id or str(uuid4())
        self.state_machine = StateMachine(AgentState.CREATED)
        self.test_run = TestRun(
            run_id=self.run_id,
            test_case_id=test_case.id,
            status="created",
            started_at=None,
            ended_at=None,
            steps=[],
        )
        self._step_queue: list[TestStep] = list(test_case.steps)
        self._step_index = -1
        self.current_step: TestStep | None = None
        self.current_step_record: StepRecord | None = None
        self.current_iteration: ActionIteration | None = None
        self.cancelled = False

    # --- step queue (US1: strict declaration order, no insert/omit) ---

    def step_queue(self) -> list[TestStep]:
        return list(self._step_queue)

    def has_next_step(self) -> bool:
        return self._step_index + 1 < len(self._step_queue)

    def advance_step(self) -> TestStep | None:
        """Move to next declared step in order. Returns None if exhausted."""
        if not self.has_next_step():
            return None
        self._step_index += 1
        self.current_step = self._step_queue[self._step_index]
        self.current_step.status = "running"
        self.current_step_record = StepRecord(
            step_id=self.current_step.id,
            final_status="running",
        )
        self.test_run.steps.append(self.current_step_record)
        self.current_iteration = None
        return self.current_step

    def iter_steps(self) -> Iterator[TestStep]:
        """Strict sequential iteration over declared steps."""
        for step in self._step_queue:
            yield step

    def begin_run(self) -> None:
        self.test_run.started_at = _utcnow()
        self.test_run.status = "running"

    def begin_iteration(self, index: int) -> ActionIteration:
        it = ActionIteration(iteration_index=index)
        self.current_iteration = it
        if self.current_step_record is not None:
            self.current_step_record.iterations.append(it)
        return it

    def mark_step_passed(self) -> None:
        if self.current_step is not None:
            self.current_step.status = "passed"
        if self.current_step_record is not None:
            self.current_step_record.final_status = "passed"

    def mark_step_failed(self, reason: str | None = None) -> None:
        if self.current_step is not None:
            self.current_step.status = "failed"
        if self.current_step_record is not None:
            self.current_step_record.final_status = "failed"
            if reason:
                self.current_step_record.failure_reason = reason

    def mark_step_cancelled(self) -> None:
        if self.current_step is not None and self.current_step.status == "running":
            self.current_step.status = "cancelled"
        if self.current_step_record is not None:
            self.current_step_record.final_status = "cancelled"

    def finish_run(self, status: str) -> None:
        self.test_run.status = status  # type: ignore[assignment]
        self.test_run.ended_at = _utcnow()

    def request_cancel(self) -> None:
        self.cancelled = True
