"""RepeatGuard — block re-execution of non-idempotent actions after effect (FR-014~016)."""

from __future__ import annotations

import re

from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.repeat_guard import RepeatGuardDecision
from vnc_agent.domain.run import ActionIteration
from vnc_agent.planning.action_classification import classify_action_kind


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    t = text.strip().lower()
    t = re.sub(r"\s+", " ", t)
    return t


def _target_key(action: SemanticAction) -> str:
    if action.target is None:
        return ""
    return _normalize(
        " ".join(
            filter(
                None,
                [
                    action.target.role,
                    action.target.text,
                    action.target.description,
                ],
            )
        )
    )


def actions_semantically_equivalent(a: SemanticAction, b: SemanticAction) -> bool:
    if a.action_type != b.action_type:
        return False
    if _target_key(a) and _target_key(a) == _target_key(b):
        return True
    if _normalize(a.intent) and _normalize(a.intent) == _normalize(b.intent):
        return True
    return False


class RepeatGuard:
    """Stateless check against previous ActionIteration (contracts §3)."""

    def check(
        self,
        proposed_action: SemanticAction,
        previous_iteration: ActionIteration | None,
    ) -> RepeatGuardDecision:
        if previous_iteration is None:
            return RepeatGuardDecision(
                allowed=True,
                reason="first_attempt",
                previous_action_effect_status=None,
            )

        prev_effect = previous_iteration.action_effect
        prev_status = prev_effect.status if prev_effect is not None else None
        prev_vr = previous_iteration.verification_result
        prev_action = previous_iteration.semantic_action

        kind = proposed_action.action_kind or classify_action_kind(proposed_action)
        if kind == "idempotent":
            return RepeatGuardDecision(
                allowed=True,
                reason="idempotent_action",
                previous_action_effect_status=prev_status,
            )

        if prev_action is None or not actions_semantically_equivalent(
            proposed_action, prev_action
        ):
            return RepeatGuardDecision(
                allowed=True,
                reason="different_action",
                previous_action_effect_status=prev_status,
            )

        # FR-016 positive branch: after strengthened verification confirmed no_effect
        if prev_status == "no_effect":
            return RepeatGuardDecision(
                allowed=True,
                reason="no_effect_confirmed",
                previous_action_effect_status=prev_status,
            )

        # Block when previous effect was not no_effect and business result still uncertain
        if prev_status in ("expected_effect", "effect_uncertain", "unexpected_effect"):
            vr_status = prev_vr.status if prev_vr is not None else "uncertain"
            if vr_status == "uncertain":
                reason = (
                    "blocked_uncertain"
                    if prev_status == "effect_uncertain"
                    else "blocked_effect_pending"
                )
                return RepeatGuardDecision(
                    allowed=False,
                    reason=reason,
                    previous_action_effect_status=prev_status,
                )

        # Previous iteration already concluded (passed/failed) or no effect data → allow
        return RepeatGuardDecision(
            allowed=True,
            reason="different_action",
            previous_action_effect_status=prev_status,
        )
