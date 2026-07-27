"""Agent state machine (data-model.md §12)."""

from __future__ import annotations

from enum import Enum
from typing import Iterable


class AgentState(str, Enum):
    CREATED = "CREATED"
    CONNECTING = "CONNECTING"
    PREPARING = "PREPARING"
    OBSERVING = "OBSERVING"
    UNDERSTANDING = "UNDERSTANDING"
    PLANNING = "PLANNING"
    RESOLVING_ACTION = "RESOLVING_ACTION"
    GROUNDING = "GROUNDING"
    EXECUTING = "EXECUTING"
    WAITING = "WAITING"
    VERIFYING = "VERIFYING"
    RECORDING = "RECORDING"
    RECOVERING = "RECOVERING"
    STEP_COMPLETED_PASSED = "STEP_COMPLETED_PASSED"
    STEP_COMPLETED_FAILED = "STEP_COMPLETED_FAILED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


# Allowed transitions (source → allowed targets)
TRANSITIONS: dict[AgentState, frozenset[AgentState]] = {
    AgentState.CREATED: frozenset({AgentState.CONNECTING, AgentState.CANCELLED}),
    AgentState.CONNECTING: frozenset(
        {AgentState.PREPARING, AgentState.RECOVERING, AgentState.FAILED, AgentState.CANCELLED}
    ),
    AgentState.PREPARING: frozenset(
        {AgentState.OBSERVING, AgentState.RECOVERING, AgentState.CANCELLED}
    ),
    AgentState.OBSERVING: frozenset(
        {
            AgentState.UNDERSTANDING,
            AgentState.RECOVERING,
            AgentState.CANCELLED,
        }
    ),
    AgentState.UNDERSTANDING: frozenset(
        {AgentState.PLANNING, AgentState.RECOVERING, AgentState.CANCELLED}
    ),
    AgentState.PLANNING: frozenset(
        {AgentState.RESOLVING_ACTION, AgentState.RECOVERING, AgentState.CANCELLED}
    ),
    AgentState.RESOLVING_ACTION: frozenset(
        {
            AgentState.GROUNDING,
            AgentState.EXECUTING,
            AgentState.RECOVERING,
            AgentState.CANCELLED,
        }
    ),
    AgentState.GROUNDING: frozenset(
        {AgentState.EXECUTING, AgentState.RECOVERING, AgentState.CANCELLED}
    ),
    AgentState.EXECUTING: frozenset(
        {AgentState.WAITING, AgentState.RECOVERING, AgentState.CANCELLED}
    ),
    AgentState.WAITING: frozenset(
        {AgentState.VERIFYING, AgentState.RECOVERING, AgentState.CANCELLED}
    ),
    AgentState.VERIFYING: frozenset(
        {AgentState.RECORDING, AgentState.RECOVERING, AgentState.CANCELLED}
    ),
    AgentState.RECORDING: frozenset(
        {
            AgentState.STEP_COMPLETED_PASSED,
            AgentState.STEP_COMPLETED_FAILED,
            AgentState.OBSERVING,  # next iteration
            AgentState.RECOVERING,
            AgentState.CANCELLED,
        }
    ),
    AgentState.RECOVERING: frozenset(
        {
            AgentState.OBSERVING,
            AgentState.UNDERSTANDING,
            AgentState.PLANNING,
            AgentState.RESOLVING_ACTION,
            AgentState.GROUNDING,
            AgentState.EXECUTING,
            AgentState.WAITING,
            AgentState.VERIFYING,
            AgentState.RECORDING,
            AgentState.STEP_COMPLETED_FAILED,
            AgentState.FAILED,
            AgentState.CANCELLED,
        }
    ),
    AgentState.STEP_COMPLETED_PASSED: frozenset(
        {AgentState.OBSERVING, AgentState.PASSED, AgentState.CANCELLED}
    ),
    AgentState.STEP_COMPLETED_FAILED: frozenset({AgentState.FAILED}),
    AgentState.PASSED: frozenset(),
    AgentState.FAILED: frozenset(),
    AgentState.CANCELLED: frozenset(),
}

TERMINAL_STATES = frozenset(
    {AgentState.PASSED, AgentState.FAILED, AgentState.CANCELLED}
)


class InvalidTransitionError(Exception):
    def __init__(self, source: AgentState, target: AgentState) -> None:
        super().__init__(f"Invalid state transition: {source.value} → {target.value}")
        self.source = source
        self.target = target


class StateMachine:
    def __init__(self, initial: AgentState = AgentState.CREATED) -> None:
        self.state = initial
        self.history: list[tuple[AgentState, AgentState, str]] = []

    def can_transition(self, target: AgentState) -> bool:
        return target in TRANSITIONS.get(self.state, frozenset())

    def transition(self, target: AgentState, reason: str = "") -> AgentState:
        if not self.can_transition(target):
            raise InvalidTransitionError(self.state, target)
        prev = self.state
        self.state = target
        self.history.append((prev, target, reason))
        return self.state

    def force(self, target: AgentState, reason: str = "force") -> AgentState:
        """Bypass table for terminal cancels already validated by caller."""
        prev = self.state
        self.state = target
        self.history.append((prev, target, reason))
        return self.state

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES
