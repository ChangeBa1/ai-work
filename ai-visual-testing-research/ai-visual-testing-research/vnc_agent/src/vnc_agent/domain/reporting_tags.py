"""Declarative action-tag audit models (Feature 003 T029, FR-027/028).

Core defines only the generic matcher/rule shape; testcases or scenario
profiles supply the concrete tag names and match criteria. Core MUST NOT
hardcode any fixed business category (Constitution v1.1.0 Principle VI).
"""

from __future__ import annotations

from pydantic import BaseModel

from vnc_agent.domain.action import ActionType, SemanticAction


class ActionMatcher(BaseModel):
    """Structured, optional-field-AND predicate — never a business keyword list."""

    action_type: ActionType | None = None
    target_role: str | None = None
    target_text_contains: str | None = None
    intent_contains: str | None = None

    def matches(self, semantic_action: SemanticAction | None) -> bool:
        if self.action_type is not None:
            if semantic_action is None or semantic_action.action_type != self.action_type:
                return False
        if self.target_role is not None:
            role = (
                (semantic_action.target.role if semantic_action and semantic_action.target else None)
                or ""
            )
            if self.target_role.strip().lower() != role.strip().lower():
                return False
        if self.target_text_contains is not None:
            text = (
                (semantic_action.target.text if semantic_action and semantic_action.target else None)
                or ""
            )
            if self.target_text_contains.lower() not in text.lower():
                return False
        if self.intent_contains is not None:
            intent = (semantic_action.intent if semantic_action else None) or ""
            if self.intent_contains.lower() not in intent.lower():
                return False
        return True


class ActionTagRule(BaseModel):
    tag: str
    matcher: ActionMatcher
