"""US2 T020: classify_action_kind keyword + conservative fallback."""

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.planning.action_classification import classify_action_kind


def test_keywords_non_idempotent():
    for intent in (
        "点击加入购物袋",
        "添加商品",
        "レジ袋を選択",
        "add to bag",
        "删除该项",
        "remove item",
        "提交订单",
        "submit form",
        "支付",
        "pay now",
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


def test_unrelated_intent_defaults_non_idempotent():
    """Conservative fallback when no keyword matches (research.md §3)."""
    kind = classify_action_kind(
        SemanticAction(
            action_id="a",
            intent="scroll the product list slightly",
            action_type="scroll",
        )
    )
    assert kind == "non_idempotent"


def test_explicit_action_kind_respected():
    sa = SemanticAction(
        action_id="a",
        intent="加入购物袋",
        action_type="click",
        action_kind="idempotent",
    )
    assert classify_action_kind(sa) == "idempotent"
