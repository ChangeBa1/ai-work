"""RepeatGuardDecision (data-model.md §6) — non-idempotent action re-execution gate."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from vnc_agent.domain.action_effect import ActionEffectStatus

RepeatGuardReason = Literal[
    "first_attempt",
    "different_action",
    "idempotent_action",
    "no_effect_confirmed",
    "blocked_effect_pending",
    "blocked_uncertain",
]


class RepeatGuardDecision(BaseModel):
    allowed: bool
    reason: RepeatGuardReason
    previous_action_effect_status: ActionEffectStatus | None = None
