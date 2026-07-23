"""Deterministic context-sensitive identity for Planner/Grounder/Verifier
(data-model.md §6A "ContextSensitiveIdentity",
perception-cache-contract.md "Role-specific request/context identity").

These three roles never enter the pixel-content `AnalysisResultCache`
(`perception/cache.py`) — none of these functions accept a content hash or
pixel array at all, structurally preventing that mistake. This module only
builds a stable canonical fingerprint of the REQUIRED identity fields so
callers (agent_runtime.py) can build an auditable `ModelCallAudit`; it never
itself decides whether a call may be skipped — deterministic route state is
supplied by the caller as one of the required fields.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


class MissingIdentityFieldError(ValueError):
    """A required identity field was missing (None) — same_context must be
    treated as false, never silently coerced to some default identity."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _digest(prefix: str, fields: dict[str, Any]) -> str:
    missing = [k for k, v in fields.items() if v is None]
    if missing:
        raise MissingIdentityFieldError(
            f"{prefix}: missing required identity fields: {sorted(missing)}"
        )
    return hashlib.sha256((prefix + "|" + _canonical(fields)).encode("utf-8")).hexdigest()


def planner_identity(
    *,
    request_semantics: Any,
    step_intent: str,
    action_history_state: Any,
    retry_iteration_state: Any,
    structured_screen_identity: str,
    requested_model_config: Any,
    route_state: Any,
) -> str:
    return _digest(
        "planner-identity-v1",
        {
            "request_semantics": request_semantics,
            "step_intent": step_intent,
            "action_history_state": action_history_state,
            "retry_iteration_state": retry_iteration_state,
            "structured_screen_identity": structured_screen_identity,
            "requested_model_config": requested_model_config,
            "route_state": route_state,
        },
    )


def grounder_identity(
    *,
    target_semantics: Any,
    candidate_set_identity: Any,
    coordinate_transform_identity: Any,
    requested_model_config: Any,
    retry_grounding_state: Any,
) -> str:
    return _digest(
        "grounder-identity-v1",
        {
            "target_semantics": target_semantics,
            "candidate_set_identity": candidate_set_identity,
            "coordinate_transform_identity": coordinate_transform_identity,
            "requested_model_config": requested_model_config,
            "retry_grounding_state": retry_grounding_state,
        },
    )


def verifier_identity(
    *,
    visual_question_or_assertion: Any,
    before_frame_identity: str,
    after_frame_identity: str,
    action_audit_context: Any,
    retry_iteration_state: Any,
    requested_model_config: Any,
) -> str:
    return _digest(
        "verifier-identity-v1",
        {
            "visual_question_or_assertion": visual_question_or_assertion,
            "before_frame_identity": before_frame_identity,
            "after_frame_identity": after_frame_identity,
            "action_audit_context": action_audit_context,
            "retry_iteration_state": retry_iteration_state,
            "requested_model_config": requested_model_config,
        },
    )


def same_context(a: str | None, b: str | None) -> bool:
    """True only when both identities are present and byte-equal. A missing
    identity (a failed canonicalization) is never "same"."""
    return a is not None and b is not None and a == b
