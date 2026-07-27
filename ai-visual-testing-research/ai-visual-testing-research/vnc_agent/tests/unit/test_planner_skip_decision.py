"""Feature 009 (T004/T013): unit tests for AgentRuntime._planner_skip_reason
(planner-skip-contract.md §1)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.repeat_guard import RepeatGuardDecision
from vnc_agent.domain.run import ActionIteration
from vnc_agent.domain.testcase import TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.runtime.agent_runtime import AgentRuntime

SKIP = "duplicate_frame_blocked_action"
HASH = "h" * 64
OTHER_HASH = "x" * 64


def _step(*, timeout_seconds: int | None = None) -> TestStep:
    return TestStep(
        id="s1",
        name="s1",
        intent="click target",
        expected=VerificationSpec(
            operator="all",
            conditions=[VerificationCondition(type="screen_changed", value="")],
            timeout_seconds=timeout_seconds,
        ),
    )


def _screen(content_hash: str | None = HASH) -> StructuredScreen:
    return StructuredScreen(
        frame_id="frame-now",
        resolution=(300, 200),
        captured_at=datetime.now(UTC),
        content_hash=content_hash,
    )


def _click(**overrides) -> SemanticAction:
    base = dict(
        action_id="a1",
        intent="click target",
        action_type="click",
        action_kind="non_idempotent",
    )
    base.update(overrides)
    return SemanticAction(**base)


def _prev(
    *,
    reason: str = "blocked_effect_pending",
    allowed: bool = False,
    before_content_hash: str | None = HASH,
    semantic_action: SemanticAction | None = None,
    guard: bool = True,
    planner_skipped_reason: str | None = None,
) -> ActionIteration:
    return ActionIteration(
        iteration_index=1,
        before_content_hash=before_content_hash,
        semantic_action=semantic_action if semantic_action is not None else _click(),
        repeat_guard_decision=(
            RepeatGuardDecision(allowed=allowed, reason=reason) if guard else None
        ),
        planner_skipped_reason=planner_skipped_reason,
    )


# --- §1.2 trigger reason set -------------------------------------------------


@pytest.mark.parametrize(
    "reason",
    [
        "blocked_effect_pending",
        "blocked_effect_pending_normalized_target",
        "ambiguous_fail_safe",
    ],
)
def test_skip_on_trigger_reasons(reason):
    prev = _prev(reason=reason)
    assert AgentRuntime._planner_skip_reason(_step(), _screen(), prev) == SKIP


@pytest.mark.parametrize(
    "reason",
    ["blocked_uncertain", "blocked_uncertain_normalized_target", "dangerous_drift"],
)
def test_no_skip_on_excluded_blocked_reasons(reason):
    prev = _prev(reason=reason)
    assert AgentRuntime._planner_skip_reason(_step(), _screen(), prev) is None


@pytest.mark.parametrize(
    "reason",
    ["first_attempt", "idempotent_action", "no_effect_confirmed", "legitimate_micro_action"],
)
def test_no_skip_when_previous_action_was_allowed(reason):
    prev = _prev(reason=reason, allowed=True)
    assert AgentRuntime._planner_skip_reason(_step(), _screen(), prev) is None


def test_no_skip_without_previous_iteration_or_decision():
    assert AgentRuntime._planner_skip_reason(_step(), _screen(), None) is None
    prev = _prev(guard=False)
    assert AgentRuntime._planner_skip_reason(_step(), _screen(), prev) is None


# --- §1.3 duplicate logical frame -------------------------------------------


def test_no_skip_on_hash_mismatch():
    prev = _prev(before_content_hash=OTHER_HASH)
    assert AgentRuntime._planner_skip_reason(_step(), _screen(), prev) is None


def test_no_skip_when_current_hash_missing():
    prev = _prev()
    assert AgentRuntime._planner_skip_reason(_step(), _screen(content_hash=None), prev) is None


def test_no_skip_when_previous_hash_missing():
    prev = _prev(before_content_hash=None)
    assert AgentRuntime._planner_skip_reason(_step(), _screen(), prev) is None


# --- §1.4/§1.5 wait-semantics exceptions (FR-006) ---------------------------


def test_no_skip_when_previous_action_is_wait_type():
    wait_action = SemanticAction(
        action_id="w1", intent="wait for page", action_type="wait"
    )
    prev = _prev(semantic_action=wait_action)
    assert AgentRuntime._planner_skip_reason(_step(), _screen(), prev) is None


def test_no_skip_when_previous_action_has_wait_micro_purpose():
    prev = _prev(semantic_action=_click(micro_action_purpose="wait"))
    assert AgentRuntime._planner_skip_reason(_step(), _screen(), prev) is None


def test_no_skip_when_verification_spec_declares_timeout():
    prev = _prev()
    step = _step(timeout_seconds=5)
    assert AgentRuntime._planner_skip_reason(step, _screen(), prev) is None


# --- §4 carried-decision chaining -------------------------------------------


def test_skip_chains_through_carried_decision_of_skipped_iteration():
    """A skipped iteration (no semantic_action, carried blocking decision)
    keeps the chain skipping while the frame stays identical."""
    prev = ActionIteration(
        iteration_index=2,
        before_content_hash=HASH,
        semantic_action=None,
        repeat_guard_decision=RepeatGuardDecision(
            allowed=False, reason="blocked_effect_pending"
        ),
        planner_skipped_reason=SKIP,
    )
    assert AgentRuntime._planner_skip_reason(_step(), _screen(), prev) == SKIP


def test_chain_ends_when_frame_finally_changes():
    prev = ActionIteration(
        iteration_index=2,
        before_content_hash=HASH,
        semantic_action=None,
        repeat_guard_decision=RepeatGuardDecision(
            allowed=False, reason="ambiguous_fail_safe"
        ),
        planner_skipped_reason=SKIP,
    )
    changed = _screen(content_hash=OTHER_HASH)
    assert AgentRuntime._planner_skip_reason(_step(), changed, prev) is None
