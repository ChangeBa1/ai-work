"""Non-idempotent action kind classification (research.md §3, FR-013)."""

from __future__ import annotations

from typing import Literal

from vnc_agent.domain.action import SemanticAction

ActionKind = Literal["idempotent", "non_idempotent"]

# Default keyword table (research.md §3) — configurable via classify_action_kind(keywords=...)
_DEFAULT_NON_IDEMPOTENT_KEYWORDS: list[str] = [
    "加入",
    "添加",
    "加购",
    "購入",
    "レジ袋",
    "add",
    "append",
    "删除",
    "移除",
    "取消",
    "remove",
    "delete",
    "cancel",
    "提交",
    "确认",
    "送出",
    "submit",
    "confirm",
    "支付",
    "结算",
    "支払い",
    "pay",
    "checkout",
]


def classify_action_kind(
    action: SemanticAction | str,
    *,
    keywords: list[str] | None = None,
) -> ActionKind:
    """
    Return action_kind for a SemanticAction (or raw intent string).

    Priority:
    1. Explicit ``SemanticAction.action_kind`` if set
    2. Keyword match on intent (and target text/description)
    3. Conservative fallback: ``non_idempotent``
    """
    if isinstance(action, SemanticAction):
        if action.action_kind in ("idempotent", "non_idempotent"):
            return action.action_kind
        parts = [action.intent or ""]
        if action.target is not None:
            parts.append(action.target.text or "")
            parts.append(action.target.description or "")
            parts.append(action.target.role or "")
        text = " ".join(parts)
    else:
        text = action or ""

    table = keywords if keywords is not None else _DEFAULT_NON_IDEMPOTENT_KEYWORDS
    lowered = text.lower()
    for kw in table:
        if not kw:
            continue
        if kw.lower() in lowered or kw in text:
            return "non_idempotent"

    # Conservative fallback when no keyword matches (research.md §3)
    return "non_idempotent"
