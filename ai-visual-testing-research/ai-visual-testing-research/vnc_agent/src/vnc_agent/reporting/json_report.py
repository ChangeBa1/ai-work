"""JSON report generation (contracts/report-schema.md, feature 004 report-contract.md).

Feature 004 (report-contract.md "Backward compatibility rule"): every
non-path field/key/type/enum/null-vs-default/array-order/status-aggregation
rule from features 001-003 is byte-for-byte unchanged. The only field-level
change is that `before_frame_path`/`after_frame_path` are now resolved
through the zero-copy safe-evidence resolver instead of a report-copy path
— when unavailable, the field is `null` rather than a dangling path (a
strict superset of the old null-on-"no observation happened" semantics).
Additive fields (`frames`, `stage_measurements`, `performance_summary`,
`display_status`, `localized_message`) are appended, never interleaved into
the old structure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnc_agent.domain.observation import ScreenFrame
from vnc_agent.domain.reporting_tags import ActionTagRule
from vnc_agent.domain.run import TestRun
from vnc_agent.reporting.localization import display, localize_error
from vnc_agent.reporting.safe_evidence import ResolvedEvidence, SafeEvidenceResolver
from vnc_agent.runtime.telemetry import derive_performance_summary

if TYPE_CHECKING:
    pass


def _matched_tags(it, action_tags: list[ActionTagRule]) -> list[str]:
    """Feature 003 (FR-027/028): a sent action MAY match 0/1/many declared
    tags — non-exclusive, core hardcodes no fixed category."""
    return [rule.tag for rule in action_tags if rule.matcher.matches(it.semantic_action)]


def _index_frames_by_safe_path(run: TestRun) -> dict[str, ScreenFrame]:
    by_path: dict[str, ScreenFrame] = {}
    for f in run.frames:
        by_path[f.safe_image.path] = f
    return by_path


def _resolve_legacy_path(
    raw_path: str | None,
    *,
    frames_by_path: dict[str, ScreenFrame],
    resolver: SafeEvidenceResolver | None,
) -> str | None:
    if not raw_path or resolver is None:
        return raw_path
    frame = frames_by_path.get(raw_path)
    if frame is None:
        # Not a frame safe path we recognize (e.g. legacy/manual data) —
        # leave untouched rather than guessing.
        return raw_path
    resolved = resolver.resolve(frame)
    if isinstance(resolved, ResolvedEvidence):
        return resolved.path
    return None


def build_report_dict(
    run: TestRun,
    *,
    action_tags: list[ActionTagRule] | None = None,
    safe_evidence_resolver: SafeEvidenceResolver | None = None,
    locale: str = "zh-CN",
) -> dict[str, Any]:
    tags = action_tags or []
    frames_by_path = _index_frames_by_safe_path(run)
    executed_action_log: list[dict[str, Any]] = []
    steps_out = []
    for step in run.steps:
        iterations = []
        for it in step.iterations:
            before_path = _resolve_legacy_path(
                it.before_frame_id, frames_by_path=frames_by_path, resolver=safe_evidence_resolver
            )
            after_path = _resolve_legacy_path(
                it.after_frame_id, frames_by_path=frames_by_path, resolver=safe_evidence_resolver
            )
            iterations.append(
                {
                    "iteration_index": it.iteration_index,
                    "before_frame_path": before_path,
                    "after_frame_path": after_path,
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
                    # Feature 007 (FR-013 / SC-006): explicit null when absent —
                    # same optional-field convention as action_effect / etc.
                    "ui_index_audit": (
                        it.ui_index_audit.model_dump(mode="json")
                        if it.ui_index_audit
                        else None
                    ),
                    # Feature 009 (FR-007): planner short-circuit marker —
                    # "duplicate_frame_blocked_action" on skipped rounds,
                    # explicit null on every normal round (contract §3).
                    "planner_skipped_reason": it.planner_skipped_reason,
                    # Feature 015 (FR-010): non-null iff this iteration's
                    # click came directly from element memory (grounder
                    # skipped); explicit null on every normal round.
                    "memory_hit": (
                        it.memory_hit.model_dump(mode="json")
                        if it.memory_hit
                        else None
                    ),
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

    frames_out = _build_frames_field(run, frames_by_path, safe_evidence_resolver)
    performance_summary = run.performance_summary or derive_performance_summary(run)
    display_status = display(locale, "status", status).display_value
    localized_message = (
        localize_error(locale, run.steps[-1].failure_reason, None)
        if status == "failed" and run.steps and run.steps[-1].failure_reason
        else None
    )

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
        # --- Feature 004 additive fields (report-contract.md) ---
        "frames": frames_out,
        "stage_measurements": [m.model_dump(mode="json") for m in run.stage_measurements],
        "performance_summary": performance_summary.model_dump(mode="json"),
        "display_status": display_status,
        "localized_message": localized_message,
    }


def _build_frames_field(
    run: TestRun,
    frames_by_path: dict[str, ScreenFrame],
    resolver: SafeEvidenceResolver | None,
) -> list[dict[str, Any]]:
    ordered = sorted(run.frames, key=lambda f: f.capture_sequence)
    out: list[dict[str, Any]] = []
    for f in ordered:
        resolved = resolver.resolve(f) if resolver is not None else None
        safe_path = resolved.path if isinstance(resolved, ResolvedEvidence) else None
        safe_sha = resolved.artifact_sha256 if isinstance(resolved, ResolvedEvidence) else None
        out.append(
            {
                "frame_id": f.id,
                "run_id": f.run_id,
                "step_id": f.step_id,
                "vnc_session_id": f.vnc_session_id,
                "capture_sequence": f.capture_sequence,
                "captured_at": f.timestamp.isoformat(),
                "content_hash": f.content_hash,
                "scope": f.scope.model_dump(mode="json"),
                "mask_identity": f.scope.mask_identity,
                "deduplicated": f.deduplicated,
                "duplicate_of_frame_id": f.duplicate_of_frame_id,
                "comparison_available": f.comparison_available,
                "changed_since_last": f.changed_since_last,
                "safe_image_path": safe_path,
                "safe_artifact_sha256": safe_sha,
                "artifact_bundle_id": f.safe_image.artifact_bundle_id,
                "analysis_source_refs": dict(f.analysis_source_refs),
            }
        )
    return out


def write_json_report(
    run: TestRun,
    path,
    *,
    action_tags: list[ActionTagRule] | None = None,
    safe_evidence_resolver: SafeEvidenceResolver | None = None,
    locale: str = "zh-CN",
) -> str:
    import json
    from pathlib import Path

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = build_report_dict(
        run, action_tags=action_tags, safe_evidence_resolver=safe_evidence_resolver, locale=locale
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)
