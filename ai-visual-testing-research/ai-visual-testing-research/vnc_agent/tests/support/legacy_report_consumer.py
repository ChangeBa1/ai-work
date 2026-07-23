"""A representative pre-004 (feature 001-003) JSON report consumer.

Reads only the fields that existed before feature 004 and ignores anything
it doesn't recognize — the shape a real external consumer would have used.
Used to prove additive feature 004 fields never break old readers
(report-contract.md "Compatibility tests").
"""

from __future__ import annotations

from typing import Any


def legacy_business_result(report: dict[str, Any]) -> dict[str, Any]:
    """Extract the same business-facing summary a pre-004 consumer would
    have computed, touching only pre-004 keys."""
    steps = report["steps"]
    return {
        "run_id": report["run_id"],
        "test_case_id": report["test_case_id"],
        "status": report["status"],
        "step_count": len(steps),
        "passed_steps": [s["step_id"] for s in steps if s["status"] == "passed"],
        "failed_steps": [s["step_id"] for s in steps if s["status"] == "failed"],
        "weak_assertion_steps": [s["step_id"] for s in steps if s["weak_assertion_warning"]],
        "executed_action_count": len(report["executed_action_log"]),
        "declared_tag_counts": report["declared_tag_counts"],
        "first_iteration_before_path": (
            steps[0]["iterations"][0]["before_frame_path"]
            if steps and steps[0]["iterations"]
            else None
        ),
        "first_iteration_after_path": (
            steps[0]["iterations"][0]["after_frame_path"]
            if steps and steps[0]["iterations"]
            else None
        ),
    }
