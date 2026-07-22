"""US2 T020 / Feature 003 T050: classify_action_kind explicit-vs-conservative
fallback (Constitution v1.1.0 Principle VI — no business vocabulary)."""

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.planning.action_classification import classify_action_kind


def test_unset_action_kind_defaults_non_idempotent_regardless_of_intent_text():
    """Conservative fallback (research.md §3): when action_kind is not
    explicitly declared, the classifier MUST NOT guess "idempotent" from
    intent text — it always conservatively returns "non_idempotent",
    independent of what the intent/target text says."""
    for intent in (
        "click the save button",
        "scroll the list slightly",
        "press the unlabeled icon",
        "refresh the current view",
    ):
        kind = classify_action_kind(
            SemanticAction(
                action_id="a",
                intent=intent,
                action_type="click",
                target=TargetDescription(text="btn"),
            )
        )
        assert kind == "non_idempotent", intent


def test_explicit_action_kind_respected():
    sa = SemanticAction(
        action_id="a",
        intent="click the save button",
        action_type="click",
        action_kind="idempotent",
    )
    assert classify_action_kind(sa) == "idempotent"
