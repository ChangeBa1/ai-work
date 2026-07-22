"""Deterministic stable action-identity computation and comparison."""

from __future__ import annotations

import re
from typing import Literal

from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.action_identity import CanonicalActionIdentity

IdentityMatch = Literal[
    "different_step",
    "action_id_match",
    "normalized_target_match",
    "no_action_id_ambiguous",
]


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", "", text.strip().lower())


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if left == right:
        return True
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right, strict=True)) <= 1
    short, long = (left, right) if len(left) < len(right) else (right, left)
    i = j = differences = 0
    while i < len(short) and j < len(long):
        if short[i] == long[j]:
            i += 1
            j += 1
            continue
        differences += 1
        if differences > 1:
            return False
        j += 1
    return True


def _targets_equivalent(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return left in right or right in left or _edit_distance_at_most_one(left, right)


def compute_identity(step_id: str, action: SemanticAction) -> CanonicalActionIdentity:
    target_text = action.target.text if action.target is not None else None
    normalized_target = _normalize(target_text) or _normalize(action.intent)
    action_id = action.action_id.strip() or None
    return CanonicalActionIdentity(
        step_id=step_id,
        action_type=action.action_type,
        action_id=action_id,
        normalized_target=normalized_target,
    )


def identity_match(
    prev: CanonicalActionIdentity,
    curr: CanonicalActionIdentity,
) -> IdentityMatch:
    if prev.step_id != curr.step_id:
        return "different_step"
    if (
        prev.action_type == curr.action_type
        and prev.action_id is not None
        and curr.action_id is not None
        and prev.action_id == curr.action_id
    ):
        return "action_id_match"
    if (
        prev.action_type == curr.action_type
        and _targets_equivalent(prev.normalized_target, curr.normalized_target)
    ):
        return "normalized_target_match"
    return "no_action_id_ambiguous"
