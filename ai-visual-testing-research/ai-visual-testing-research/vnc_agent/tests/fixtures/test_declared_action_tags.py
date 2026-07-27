"""Feature 003 T027: ActionMatcher/ActionTagRule declarative audit tests
(FR-027/028). Complements the integration-level assertions in
test_report_builder.py::test_run_level_precondition_and_tag_audit."""

from datetime import UTC, datetime

from vnc_agent.domain.action import ExecutableAction, ExecutionResult, SemanticAction, TargetDescription
from vnc_agent.domain.reporting_tags import ActionMatcher, ActionTagRule
from vnc_agent.domain.run import ActionIteration, StepRecord, TestRun
from vnc_agent.reporting.json_report import build_report_dict


def _action(*, action_type="click", role=None, text=None, intent="do something") -> SemanticAction:
    return SemanticAction(
        action_id="a",
        intent=intent,
        action_type=action_type,
        target=TargetDescription(role=role, text=text),
        action_kind="non_idempotent",
    )


def test_matcher_fields_combine_with_and_semantics() -> None:
    matcher = ActionMatcher(action_type="click", target_role="button")
    matching = _action(action_type="click", role="button")
    wrong_type = _action(action_type="type_text", role="button")
    wrong_role = _action(action_type="click", role="row")

    assert matcher.matches(matching) is True
    assert matcher.matches(wrong_type) is False
    assert matcher.matches(wrong_role) is False


def test_unset_matcher_fields_do_not_constrain() -> None:
    matcher = ActionMatcher(action_type="click")
    assert matcher.matches(_action(action_type="click", role="anything")) is True
    assert matcher.matches(_action(action_type="click", role=None)) is True


def test_target_text_contains_and_intent_contains_are_substring_case_insensitive() -> None:
    matcher = ActionMatcher(target_text_contains="Bag", intent_contains="ADD")
    assert (
        matcher.matches(_action(text="my bag icon", intent="add item to list")) is True
    )
    assert matcher.matches(_action(text="unrelated", intent="add item")) is False


def test_an_action_may_match_zero_one_or_multiple_declared_tags() -> None:
    rules = [
        ActionTagRule(tag="clicks", matcher=ActionMatcher(action_type="click")),
        ActionTagRule(tag="buttons", matcher=ActionMatcher(target_role="button")),
        ActionTagRule(tag="keys", matcher=ActionMatcher(action_type="press_key")),
    ]
    now = datetime.now(UTC)
    matches_two = ActionIteration(
        iteration_index=0,
        semantic_action=_action(action_type="click", role="button"),
        executable_action=ExecutableAction(method="mouse", operation="click", coordinates=(1, 1)),
        execution_result=ExecutionResult(success=True, started_at=now, ended_at=now),
    )
    matches_none = ActionIteration(
        iteration_index=1,
        semantic_action=_action(action_type="scroll", role="row"),
        executable_action=ExecutableAction(method="mouse", operation="scroll", coordinates=(1, 1)),
        execution_result=ExecutionResult(success=True, started_at=now, ended_at=now),
    )
    run = TestRun(
        run_id="tags",
        test_case_id="case",
        steps=[StepRecord(step_id="s1", iterations=[matches_two, matches_none])],
    )
    data = build_report_dict(run, action_tags=rules)
    assert set(data["executed_action_log"][0]["tags"]) == {"clicks", "buttons"}
    assert data["executed_action_log"][1]["tags"] == []
    assert data["declared_tag_counts"] == {"clicks": 1, "buttons": 1, "keys": 0}


def test_blocked_proposal_is_not_counted_but_stays_in_per_iteration_audit() -> None:
    rules = [ActionTagRule(tag="clicks", matcher=ActionMatcher(action_type="click"))]
    blocked = ActionIteration(
        iteration_index=0,
        semantic_action=_action(action_type="click", role="button"),
        execution_result=None,
    )
    run = TestRun(
        run_id="tags-blocked",
        test_case_id="case",
        steps=[StepRecord(step_id="s1", iterations=[blocked])],
    )
    data = build_report_dict(run, action_tags=rules)
    assert data["executed_action_log"] == []
    assert data["declared_tag_counts"] == {"clicks": 0}
    # Still present in the per-iteration audit record.
    assert data["steps"][0]["iterations"][0]["semantic_action"]["action_id"] == "a"
