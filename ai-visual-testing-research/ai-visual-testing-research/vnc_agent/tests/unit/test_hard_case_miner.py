"""Feature 021 unit tests: hard-case criteria hit/miss on constructed row
payloads (spec FR-001, criteria table)."""

from __future__ import annotations

from vnc_agent.config import EvolutionConfig
from vnc_agent.evolution.hard_case_miner import (
    CRITERIA,
    StepEvidence,
    collect_failure_types,
    evaluate_step,
    is_failure_type_hit,
    is_high_confidence_failure,
    is_low_grounding_confidence,
    is_memory_fallback_failed,
    is_mouse_verification_failed,
    is_retry_then_success,
    is_top2_promotion_success,
    is_zoom_reground_used,
)

CFG = EvolutionConfig()


def _iteration(
    *,
    index: int = 0,
    confidence: float | None = None,
    verification: str | None = None,
    method: str | None = None,
    memory_hit: dict | None = None,
    recovery: list[dict] | None = None,
) -> dict:
    it: dict = {"iteration_index": index}
    if confidence is not None:
        it["grounding_result"] = {
            "found": True,
            "candidates": [{"bbox": [10, 10, 30, 30], "confidence": confidence}],
        }
    if verification is not None:
        it["verification_result"] = {"status": verification, "reason": "r"}
    if method is not None:
        it["executable_action"] = {"method": method, "operation": "click"}
    if memory_hit is not None:
        it["memory_hit"] = memory_hit
    if recovery is not None:
        it["recovery_attempts"] = recovery
    return it


def _evidence(iterations: list[dict], *, final_status: str = "passed", **kw) -> StepEvidence:
    return StepEvidence(
        run_id="r1", step_id="s1", final_status=final_status, iterations=iterations, **kw
    )


# --- low_grounding_confidence -------------------------------------------------


def test_low_confidence_hit_below_threshold():
    ev = _evidence([_iteration(confidence=0.4)])
    assert is_low_grounding_confidence(ev, CFG)


def test_low_confidence_boundary_is_strict():
    ev = _evidence([_iteration(confidence=0.7)])
    assert not is_low_grounding_confidence(ev, CFG)


def test_low_confidence_threshold_from_config():
    cfg = EvolutionConfig(hard_case_grounding_confidence_below=0.5)
    ev = _evidence([_iteration(confidence=0.6)])
    assert not is_low_grounding_confidence(ev, cfg)
    assert is_low_grounding_confidence(ev, CFG)


def test_low_confidence_no_grounding_is_no_signal():
    ev = _evidence([_iteration(verification="failed")])
    assert not is_low_grounding_confidence(ev, CFG)


# --- top2_promotion_success ----------------------------------------------------


def test_top2_promotion_requires_second_candidate_and_pass():
    attempts = [{"strategy": "second_candidate", "failure_type": "grounding_low_confidence"}]
    assert is_top2_promotion_success(
        _evidence([_iteration()], recovery_attempts=attempts), CFG
    )
    assert not is_top2_promotion_success(
        _evidence([_iteration()], final_status="failed", recovery_attempts=attempts), CFG
    )
    assert not is_top2_promotion_success(_evidence([_iteration()]), CFG)


# --- retry_then_success ---------------------------------------------------------


def test_retry_then_success_hits_on_multi_iteration_pass():
    ev = _evidence([_iteration(index=0), _iteration(index=1)])
    assert is_retry_then_success(ev, CFG)


def test_retry_then_success_misses_single_iteration_or_failure():
    assert not is_retry_then_success(_evidence([_iteration()]), CFG)
    assert not is_retry_then_success(
        _evidence([_iteration(index=0), _iteration(index=1)], final_status="failed"), CFG
    )


# --- zoom_reground_used ----------------------------------------------------------


def test_zoom_reground_used_from_recovery_strategy():
    ev = _evidence(
        [_iteration()],
        recovery_attempts=[{"strategy": "zoom_reground", "failure_type": "target_not_found"}],
    )
    assert is_zoom_reground_used(ev, CFG)
    assert not is_zoom_reground_used(_evidence([_iteration()]), CFG)


# --- memory_fallback_failed -------------------------------------------------------


def test_memory_fallback_failed_requires_hit_and_failed_verification():
    hit = {"page_memory_id": "p1", "element_memory_id": "e1"}
    assert is_memory_fallback_failed(
        _evidence([_iteration(memory_hit=hit, verification="failed")]), CFG
    )
    assert not is_memory_fallback_failed(
        _evidence([_iteration(memory_hit=hit, verification="passed")]), CFG
    )
    assert not is_memory_fallback_failed(
        _evidence([_iteration(verification="failed")]), CFG
    )


# --- mouse_verification_failed ------------------------------------------------------


def test_mouse_verification_failed():
    assert is_mouse_verification_failed(
        _evidence([_iteration(method="mouse", verification="failed")]), CFG
    )
    assert not is_mouse_verification_failed(
        _evidence([_iteration(method="keyboard", verification="failed")]), CFG
    )
    assert not is_mouse_verification_failed(
        _evidence([_iteration(method="mouse", verification="passed")]), CFG
    )


# --- failure_type_hit -----------------------------------------------------------------


def test_failure_type_hit_from_recovery_and_experience():
    ev = _evidence(
        [_iteration()],
        recovery_attempts=[{"strategy": "press_escape", "failure_type": "unexpected_dialog"}],
    )
    assert is_failure_type_hit(ev, CFG)
    ev2 = _evidence([_iteration()], experience_failure_types=["target_not_found"])
    assert is_failure_type_hit(ev2, CFG)
    ev3 = _evidence(
        [_iteration()],
        recovery_attempts=[{"strategy": "extra_wait", "failure_type": "page_not_stable"}],
    )
    assert not is_failure_type_hit(ev3, CFG)  # not in the configured default set


def test_failure_type_set_is_configurable():
    cfg = EvolutionConfig(hard_case_failure_types=["page_not_stable"])
    ev = _evidence(
        [_iteration()],
        recovery_attempts=[{"strategy": "extra_wait", "failure_type": "page_not_stable"}],
    )
    assert is_failure_type_hit(ev, cfg)


def test_collect_failure_types_is_distinct_sorted():
    ev = _evidence(
        [_iteration()],
        recovery_attempts=[
            {"strategy": "a", "failure_type": "timeout"},
            {"strategy": "b", "failure_type": "timeout"},
        ],
        experience_failure_types=["black_screen"],
    )
    assert collect_failure_types(ev) == ["black_screen", "timeout"]


# --- high_confidence_failure --------------------------------------------------------------


def test_high_confidence_failure_inclusive_boundary():
    assert is_high_confidence_failure(
        _evidence([_iteration(confidence=0.9, verification="failed")]), CFG
    )
    assert not is_high_confidence_failure(
        _evidence([_iteration(confidence=0.89, verification="failed")]), CFG
    )
    assert not is_high_confidence_failure(
        _evidence([_iteration(confidence=0.95, verification="passed")]), CFG
    )


# --- aggregator ------------------------------------------------------------------------------


def test_evaluate_step_returns_sorted_matched_labels():
    ev = _evidence(
        [
            _iteration(index=0, confidence=0.4, method="mouse", verification="failed"),
            _iteration(index=1, confidence=0.8, verification="passed"),
        ]
    )
    labels = evaluate_step(ev, CFG)
    assert labels == sorted(labels)
    assert set(labels) == {
        "low_grounding_confidence",
        "mouse_verification_failed",
        "retry_then_success",
    }


def test_evaluate_step_clean_step_matches_nothing():
    ev = _evidence([_iteration(confidence=0.95, method="mouse", verification="passed")])
    assert evaluate_step(ev, CFG) == []


def test_evaluate_step_empty_evidence_never_crashes():
    assert evaluate_step(StepEvidence(run_id="r", step_id="s"), CFG) == []
    # Iterations with entirely missing sub-objects are "no signal".
    assert evaluate_step(_evidence([{}], final_status="failed"), CFG) == []


def test_criteria_vocabulary_is_closed_and_stable():
    assert set(CRITERIA) == {
        "low_grounding_confidence",
        "top2_promotion_success",
        "retry_then_success",
        "zoom_reground_used",
        "memory_fallback_failed",
        "mouse_verification_failed",
        "failure_type_hit",
        "high_confidence_failure",
    }
