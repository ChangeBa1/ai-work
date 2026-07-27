"""Feature 021 (evolution-hardcase-export, FR-001): hard-case criteria.

Pure predicates over *persisted* row payloads (plain dicts, exactly as stored
by the run repository) implementing the achievable subset of the design's
§12.3 hard-case criteria — see specs/021-evolution-hardcase-export/spec.md
(criteria table) for the audit of which criteria the stored data supports and
which are documented as not implementable.

Offline only: imported exclusively by ``evolution/dataset_exporter.py`` /
the ``vnc-agent evolution export`` CLI path. Never touches storage itself and
never runs inside the agent runtime (zero-runtime-impact red line, FR-007).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vnc_agent.config import EvolutionConfig

#: Closed vocabulary of exportable hard-case labels (CLI --criteria values).
CRITERIA: tuple[str, ...] = (
    "low_grounding_confidence",
    "top2_promotion_success",
    "retry_then_success",
    "zoom_reground_used",
    "memory_fallback_failed",
    "mouse_verification_failed",
    "failure_type_hit",
    "high_confidence_failure",
)


@dataclass
class StepEvidence:
    """Everything persisted for one (run_id, step_id) that the miner reads.

    ``iterations`` are ActionIteration payload dicts sorted by
    iteration_index; ``recovery_attempts`` is the union of the dedicated
    table rows and the copies embedded in iteration payloads (predicates are
    existence checks, so duplicates are harmless); ``experience_failure_types``
    are the non-null ``failure_type`` strings from visual_experiences rows.
    """

    run_id: str
    step_id: str
    final_status: str = "pending"
    failure_reason: str | None = None
    iterations: list[dict[str, Any]] = field(default_factory=list)
    recovery_attempts: list[dict[str, Any]] = field(default_factory=list)
    experience_failure_types: list[str] = field(default_factory=list)


def _top1_confidence(iteration: dict[str, Any]) -> float | None:
    grounding = iteration.get("grounding_result") or {}
    candidates = grounding.get("candidates") or []
    if not candidates:
        return None
    first = candidates[0] or {}
    confidence = first.get("confidence")
    return float(confidence) if confidence is not None else None


def _verification_status(iteration: dict[str, Any]) -> str | None:
    vr = iteration.get("verification_result") or {}
    status = vr.get("status")
    return str(status) if status is not None else None


def _strategies(evidence: StepEvidence) -> set[str]:
    out: set[str] = set()
    for attempt in evidence.recovery_attempts:
        strategy = (attempt or {}).get("strategy")
        if strategy:
            out.add(str(strategy))
    return out


def collect_failure_types(evidence: StepEvidence) -> list[str]:
    """Distinct persisted FailureType strings observed for the step (sorted)."""
    found: set[str] = set()
    for attempt in evidence.recovery_attempts:
        ft = (attempt or {}).get("failure_type")
        if ft:
            found.add(str(ft))
    for ft in evidence.experience_failure_types:
        if ft:
            found.add(str(ft))
    return sorted(found)


# --- individual criteria (spec criteria table) ------------------------------


def is_low_grounding_confidence(evidence: StepEvidence, cfg: EvolutionConfig) -> bool:
    """Any iteration's top-1 grounding confidence strictly below threshold."""
    threshold = cfg.hard_case_grounding_confidence_below
    for it in evidence.iterations:
        confidence = _top1_confidence(it)
        if confidence is not None and confidence < threshold:
            return True
    return False


def is_top2_promotion_success(evidence: StepEvidence, cfg: EvolutionConfig) -> bool:
    """Top-1 failed but a promoted candidate succeeded — persisted proxy: a
    ``second_candidate`` recovery strategy on a step that finally passed
    (candidate_index itself is never stored as a plain field, spec Clarif. 2)."""
    return evidence.final_status == "passed" and "second_candidate" in _strategies(evidence)


def is_retry_then_success(evidence: StepEvidence, cfg: EvolutionConfig) -> bool:
    """Step needed more than one iteration before it finally passed."""
    return evidence.final_status == "passed" and len(evidence.iterations) > 1


def is_zoom_reground_used(evidence: StepEvidence, cfg: EvolutionConfig) -> bool:
    """The feature-014 zoom escalation was needed at least once."""
    return "zoom_reground" in _strategies(evidence)


def is_memory_fallback_failed(evidence: StepEvidence, cfg: EvolutionConfig) -> bool:
    """A feature-015 element-memory direct click failed verification."""
    for it in evidence.iterations:
        if it.get("memory_hit") and _verification_status(it) == "failed":
            return True
    return False


def is_mouse_verification_failed(evidence: StepEvidence, cfg: EvolutionConfig) -> bool:
    """A mouse-method iteration whose verification failed."""
    for it in evidence.iterations:
        executable = it.get("executable_action") or {}
        if executable.get("method") == "mouse" and _verification_status(it) == "failed":
            return True
    return False


def is_failure_type_hit(evidence: StepEvidence, cfg: EvolutionConfig) -> bool:
    """A configured FailureType (default: unexpected_dialog/target_not_found)
    was persisted for the step."""
    configured = set(cfg.hard_case_failure_types)
    return any(ft in configured for ft in collect_failure_types(evidence))


def is_high_confidence_failure(evidence: StepEvidence, cfg: EvolutionConfig) -> bool:
    """Top-1 confidence at/above the high threshold yet verification failed."""
    threshold = cfg.hard_case_high_confidence_at_least
    for it in evidence.iterations:
        confidence = _top1_confidence(it)
        if (
            confidence is not None
            and confidence >= threshold
            and _verification_status(it) == "failed"
        ):
            return True
    return False


_PREDICATES = {
    "low_grounding_confidence": is_low_grounding_confidence,
    "top2_promotion_success": is_top2_promotion_success,
    "retry_then_success": is_retry_then_success,
    "zoom_reground_used": is_zoom_reground_used,
    "memory_fallback_failed": is_memory_fallback_failed,
    "mouse_verification_failed": is_mouse_verification_failed,
    "failure_type_hit": is_failure_type_hit,
    "high_confidence_failure": is_high_confidence_failure,
}

assert set(_PREDICATES) == set(CRITERIA)


def evaluate_step(evidence: StepEvidence, cfg: EvolutionConfig) -> list[str]:
    """Sorted list of matched hard-case labels for one step (FR-001)."""
    return sorted(label for label, pred in _PREDICATES.items() if pred(evidence, cfg))
