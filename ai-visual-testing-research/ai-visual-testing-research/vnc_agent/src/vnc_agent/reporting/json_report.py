"""JSON report generation (contracts/report-schema.md)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vnc_agent.domain.reporting_tags import ActionTagRule
from vnc_agent.domain.run import TestRun


def _matched_tags(it, action_tags: list[ActionTagRule]) -> list[str]:
    """Feature 003 (FR-027/028): a sent action MAY match 0/1/many declared
    tags — non-exclusive, core hardcodes no fixed category."""
    return [rule.tag for rule in action_tags if rule.matcher.matches(it.semantic_action)]


def build_report_dict(
    run: TestRun,
    *,
    action_tags: list[ActionTagRule] | None = None,
) -> dict[str, Any]:
    tags = action_tags or []
    executed_action_log: list[dict[str, Any]] = []
    steps_out = []
    for step in run.steps:
        iterations = []
        for it in step.iterations:
            iterations.append(
                {
                    "iteration_index": it.iteration_index,
                    "before_frame_path": it.before_frame_id,
                    "after_frame_path": it.after_frame_id,
                    "semantic_action": (
                        it.semantic_action.model_dump(mode="json")
                        if it.semantic_action
                        else None
                    ),
                    "grounding_candidates": (
                        [c.model_dump(mode="json") for c in it.grounding_result.candidates]
                        if it.grounding_result
                        else []
                    ),
                    "selected_candidate": None,
                    "executable_action": (
                        it.executable_action.model_dump(mode="json")
                        if it.executable_action
                        else None
                    ),
                    "execution_result": (
                        it.execution_result.model_dump(mode="json")
                        if it.execution_result
                        else None
                    ),
                    "wait_result": (
                        it.wait_result.model_dump(mode="json") if it.wait_result else None
                    ),
                    "verification_result": (
                        it.verification_result.model_dump(mode="json")
                        if it.verification_result
                        else {"status": "uncertain", "reason": "missing", "evidence_refs": []}
                    ),
                    "action_effect": (
                        it.action_effect.model_dump(mode="json")
                        if it.action_effect
                        else None
                    ),
                    "repeat_guard_decision": (
                        it.repeat_guard_decision.model_dump(mode="json")
                        if it.repeat_guard_decision
                        else None
                    ),
                    "canonical_action_identity": (
                        it.canonical_identity.model_dump(mode="json")
                        if it.canonical_identity
                        else None
                    ),
                    "coordinate_space_audit": (
                        it.grounding_result.coordinate_space_audit
                        if it.grounding_result
                        else []
                    ),
                    "recovery_attempts": [
                        r.model_dump(mode="json") for r in it.recovery_attempts
                    ],
                }
            )
            if it.execution_result is not None and it.execution_result.success is True:
                executed_action_log.append(
                    {
                        "step_id": step.step_id,
                        "iteration_index": it.iteration_index,
                        "canonical_action_identity": (
                            it.canonical_identity.model_dump(mode="json")
                            if it.canonical_identity
                            else None
                        ),
                        "executable_action": (
                            it.executable_action.model_dump(mode="json")
                            if it.executable_action
                            else None
                        ),
                        "execution_result": it.execution_result.model_dump(mode="json"),
                        "tags": _matched_tags(it, tags),
                    }
                )
        # Derive step-level labels from last verification (FR-013/027)
        last_vr = None
        for it in reversed(step.iterations):
            if it.verification_result is not None:
                last_vr = it.verification_result
                break
        weak_warn = bool(last_vr and last_vr.weak_assertion_warning)
        basis = last_vr.basis if last_vr else None
        effect_only_pass = bool(
            last_vr
            and last_vr.status == "passed"
            and last_vr.basis == "action_effect_only"
            and not last_vr.weak_assertion_warning
        )
        trusted_pass = bool(
            last_vr
            and last_vr.status == "passed"
            and last_vr.basis in ("business_assertion", "mixed")
        )
        steps_out.append(
            {
                "step_id": step.step_id,
                "status": step.final_status
                if step.final_status in ("passed", "failed", "cancelled")
                else "failed",
                "iterations": iterations,
                "model_names": step.model_names,
                "raw_model_response_refs": step.raw_model_response_refs,
                "stage_durations_ms": step.stage_durations_ms,
                "failure_reason": step.failure_reason,
                "weak_assertion_warning": weak_warn,
                "basis": basis,
                "verification_label": (
                    "weak_assertion_warning"
                    if weak_warn
                    else (
                        "effect_only_pass"
                        if effect_only_pass
                        else ("trusted_pass" if trusted_pass else None)
                    )
                ),
            }
        )

    status = run.status if run.status in ("passed", "failed", "cancelled") else "failed"
    # Feature 003 (FR-027/028): declared_tag_counts is an open, non-exclusive
    # zero-to-many mapping — no fixed business categories, no "unclassified"
    # catch-all bucket.
    declared_tag_counts: dict[str, int] = {rule.tag: 0 for rule in tags}
    for entry in executed_action_log:
        for tag in entry["tags"]:
            declared_tag_counts[tag] = declared_tag_counts.get(tag, 0) + 1
    return {
        "run_id": run.run_id,
        "test_case_id": run.test_case_id,
        "status": status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "ended_at": run.ended_at.isoformat() if run.ended_at else None,
        "precondition_evaluation": run.precondition_evaluation.model_dump(mode="json"),
        "human_confirmed_facts": [
            f.model_dump(mode="json") for f in run.human_confirmed_facts
        ],
        "executed_action_log": executed_action_log,
        "declared_tag_counts": declared_tag_counts,
        "steps": steps_out,
    }


def write_json_report(
    run: TestRun,
    path: str | Path,
    *,
    action_tags: list[ActionTagRule] | None = None,
) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = build_report_dict(run, action_tags=action_tags)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
