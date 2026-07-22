"""RepeatGuard — stable-identity gate for non-idempotent action execution
(Feature 003 T009 — safety issue A: a matching identity MUST NOT bypass the
target-safety conflict check)."""

from __future__ import annotations

from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.observation import Region
from vnc_agent.domain.repeat_guard import RepeatGuardDecision
from vnc_agent.domain.run import ActionIteration
from vnc_agent.execution.action_identity import compute_identity, identity_match
from vnc_agent.execution.target_consistency import (
    evaluate_target_consistency,
    has_target_evidence_conflict,
)
from vnc_agent.planning.action_classification import classify_action_kind


class RepeatGuard:
    """Stateless check against previous ActionIteration (contracts §4)."""

    def __init__(
        self,
        *,
        micro_action_risk_thresholds: dict[str, str] | None = None,
        target_region_conflict_iou_threshold: float = 0.10,
    ) -> None:
        self.micro_action_risk_thresholds = micro_action_risk_thresholds
        self.target_region_conflict_iou_threshold = target_region_conflict_iou_threshold

    def check(
        self,
        step_id: str,
        step_intent: str,
        proposed_action: SemanticAction,
        previous_iteration: ActionIteration | None,
        *,
        previous_resolved_region: Region | None = None,
        proposed_resolved_region: Region | None = None,
    ) -> RepeatGuardDecision:
        if previous_iteration is None:
            return RepeatGuardDecision(
                allowed=True,
                reason="first_attempt",
                previous_action_effect_status=None,
            )

        prev_effect = previous_iteration.action_effect
        prev_status = prev_effect.status if prev_effect is not None else None
        prev_action = previous_iteration.semantic_action

        kind = proposed_action.action_kind or classify_action_kind(proposed_action)
        if kind == "idempotent":
            return RepeatGuardDecision(
                allowed=True,
                reason="idempotent_action",
                previous_action_effect_status=prev_status,
            )

        if prev_action is None:
            return RepeatGuardDecision(
                allowed=False,
                reason="ambiguous_fail_safe",
                previous_action_effect_status=prev_status,
            )

        curr_identity = compute_identity(step_id, proposed_action)
        prev_identity = previous_iteration.canonical_identity or compute_identity(
            step_id, prev_action
        )
        match = identity_match(prev_identity, curr_identity)

        # Safety issue A: computed unconditionally, regardless of `match`.
        conflict = has_target_evidence_conflict(
            prev_action,
            proposed_action,
            previous_resolved_region=previous_resolved_region,
            proposed_resolved_region=proposed_resolved_region,
            target_region_conflict_iou_threshold=self.target_region_conflict_iou_threshold,
        )

        if match in ("action_id_match", "normalized_target_match") and not conflict:
            normalized = match == "normalized_target_match"
            if previous_iteration.execution_result is None and prev_status is None:
                reason = (
                    "no_effect_confirmed_normalized_target"
                    if normalized
                    else "no_effect_confirmed"
                )
                return RepeatGuardDecision(
                    allowed=True,
                    reason=reason,
                    previous_action_effect_status=None,
                )
            if prev_status == "no_effect":
                reason = (
                    "no_effect_confirmed_normalized_target"
                    if normalized
                    else "no_effect_confirmed"
                )
                return RepeatGuardDecision(
                    allowed=True,
                    reason=reason,
                    previous_action_effect_status=prev_status,
                )
            if prev_status == "effect_uncertain":
                reason = (
                    "blocked_uncertain_normalized_target"
                    if normalized
                    else "blocked_uncertain"
                )
            else:
                reason = (
                    "blocked_effect_pending_normalized_target"
                    if normalized
                    else "blocked_effect_pending"
                )
            return RepeatGuardDecision(
                allowed=False,
                reason=reason,
                previous_action_effect_status=prev_status,
            )

        # match == "no_action_id_ambiguous", OR match already matched but
        # conflict is True (safety issue A: MUST NOT skip this step, and
        # `no_effect` on the previous round MUST NOT exempt it either).
        if match == "different_step":
            # Structurally unreachable (RepeatGuard is only ever called with a
            # previous_iteration from the current TestStep); kept as a
            # defensive fallback rather than silently falling through.
            return RepeatGuardDecision(
                allowed=True,
                reason="first_attempt",
                previous_action_effect_status=prev_status,
            )

        outcome = evaluate_target_consistency(
            step_intent,
            prev_action,
            proposed_action,
            micro_action_risk_thresholds=self.micro_action_risk_thresholds,
        )
        if outcome == "dangerous_drift":
            return RepeatGuardDecision(
                allowed=False,
                reason="dangerous_drift",
                previous_action_effect_status=prev_status,
            )
        if outcome == "legitimate_micro_action":
            return RepeatGuardDecision(
                allowed=True,
                reason="legitimate_micro_action",
                previous_action_effect_status=prev_status,
            )
        # outcome == "ambiguous"
        if prev_status == "no_effect":
            return RepeatGuardDecision(
                allowed=True,
                reason="no_effect_confirmed",
                previous_action_effect_status=prev_status,
            )
        return RepeatGuardDecision(
            allowed=False,
            reason="ambiguous_fail_safe",
            previous_action_effect_status=prev_status,
        )
