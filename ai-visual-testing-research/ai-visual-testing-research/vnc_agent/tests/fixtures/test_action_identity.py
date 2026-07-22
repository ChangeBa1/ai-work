"""Feature 003 stable action identity tests (T007/T012)."""

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.execution.action_identity import compute_identity, identity_match


def _action(
    *,
    action_id: str = "act-1",
    action_type: str = "click",
    intent: str = "点击购物袋按钮",
    text: str = "レジ袋",
    role: str | None = "button",
    description: str = "购物袋按钮",
) -> SemanticAction:
    return SemanticAction(
        action_id=action_id,
        action_type=action_type,  # type: ignore[arg-type]
        intent=intent,
        target=TargetDescription(role=role, text=text, description=description),
        action_kind="non_idempotent",
    )


def test_real_incident_replay_action_id_is_decisive_despite_wording_changes() -> None:
    first = compute_identity("add-bag", _action())
    rewritten = compute_identity(
        "add-bag",
        _action(
            intent="点击 OCR 标记的购物袋区域并加入购物车",
            text="ジ袋",
            role="list item",
            description="商品列表中的购物袋商品行",
        ),
    )
    assert identity_match(first, rewritten) == "action_id_match"


def test_step_and_action_type_boundaries() -> None:
    first = compute_identity("step-1", _action())
    assert identity_match(first, compute_identity("step-2", _action())) == "different_step"
    typed = _action(action_type="type_text")
    assert identity_match(first, compute_identity("step-1", typed)) == "no_action_id_ambiguous"


def test_ocr_tolerant_target_match_without_action_id_match() -> None:
    first = compute_identity("step-1", _action(action_id="", text="レジ袋"))
    noisy = compute_identity("step-1", _action(action_id="other", text="ジ袋"))
    assert identity_match(first, noisy) == "normalized_target_match"


def test_unrelated_target_is_ambiguous() -> None:
    first = compute_identity("step-1", _action(action_id="a", text="レジ袋"))
    other = compute_identity("step-1", _action(action_id="b", text="削除"))
    assert identity_match(first, other) == "no_action_id_ambiguous"


def test_different_step_never_blocks_identity() -> None:
    first = compute_identity("one", _action(action_id="shared"))
    second = compute_identity("two", _action(action_id="shared"))
    assert identity_match(first, second) == "different_step"
