"""Stable semantic-action identity values for repeat prevention."""

from __future__ import annotations

from pydantic import BaseModel

from vnc_agent.domain.action import ActionType


class CanonicalActionIdentity(BaseModel):
    step_id: str
    action_type: ActionType
    action_id: str | None = None
    normalized_target: str
