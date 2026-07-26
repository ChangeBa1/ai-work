"""Feature 021 unit tests: hard-case-v1 row schema, screenshot path handling,
sensitive redaction and the additive evolution config (spec FR-003/FR-004/FR-008)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml

from vnc_agent.config import EvolutionConfig, load_agent_config
from vnc_agent.evolution.dataset_exporter import (
    SCHEMA_VERSION,
    UnknownCriterionError,
    build_frame_path_map,
    build_sample,
    redact_sample,
    relativize_screenshot_path,
    run_started_within,
    validate_criteria_filter,
)
from vnc_agent.evolution.hard_case_miner import StepEvidence

ROW_KEYS = {
    "schema_version",
    "run_id",
    "test_case_id",
    "step_id",
    "criteria",
    "screenshot_path",
    "target",
    "intent",
    "correct_bbox",
    "wrong_candidates",
    "page_memory_id",
    "verification",
    "final_status",
    "iteration_count",
    "failure_types",
}


def _evidence() -> StepEvidence:
    return StepEvidence(
        run_id="run-1",
        step_id="s1",
        final_status="passed",
        iterations=[
            {
                "iteration_index": 0,
                "before_frame_id": "f0",
                "semantic_action": {
                    "intent": "click checkout",
                    "target": {
                        "role": None,
                        "text": "会計",
                        "description": "checkout button",
                        "nearby_texts": ["小計"],
                    },
                },
                "grounding_result": {
                    "found": True,
                    "candidates": [{"bbox": [90, 40, 110, 60], "confidence": 0.4}],
                },
                "executable_action": {"method": "mouse", "operation": "click"},
                "execution_result": {"actual_click_point": [100, 50]},
                "verification_result": {"status": "failed", "reason": "no change"},
            },
            {
                "iteration_index": 1,
                "before_frame_id": "f1",
                "semantic_action": {
                    "intent": "click checkout",
                    "target": {"text": "会計", "description": "", "nearby_texts": []},
                },
                "grounding_result": {
                    "found": True,
                    "candidates": [{"bbox": [150, 85, 170, 95], "confidence": 0.9}],
                },
                "executable_action": {"method": "mouse", "operation": "click"},
                "execution_result": {
                    "actual_click_point": [160, 90],
                    "target_region": {"x1": 150, "y1": 85, "x2": 170, "y2": 95},
                },
                "verification_result": {"status": "passed", "reason": "ok"},
            },
        ],
        recovery_attempts=[
            {"strategy": "second_candidate", "failure_type": "verification_failed"}
        ],
    )


def _sample(**overrides):
    kwargs = dict(
        test_case_id="tc-1",
        criteria=["low_grounding_confidence", "retry_then_success"],
        frame_paths={"f0": "artifacts/runs/run-1/bundles/b0/safe_evidence.png"},
        artifacts_root="artifacts",
    )
    kwargs.update(overrides)
    return build_sample(_evidence(), **kwargs)


def test_row_schema_keys_and_traceability():
    row = _sample()
    assert set(row) == ROW_KEYS
    assert row["schema_version"] == SCHEMA_VERSION
    assert (row["run_id"], row["step_id"], row["test_case_id"]) == ("run-1", "s1", "tc-1")
    assert row["final_status"] == "passed"
    assert row["iteration_count"] == 2
    assert row["intent"] == "click checkout"
    assert row["target"]["text"] == "会計"
    assert row["failure_types"] == ["verification_failed"]
    assert row["verification"] == {"status": "passed", "reason": "ok"}


def test_correct_bbox_from_passed_iteration_target_region():
    row = _sample()
    assert row["correct_bbox"] == [150, 85, 170, 95]


def test_wrong_candidates_from_failed_iterations_only():
    row = _sample()
    assert row["wrong_candidates"] == [
        {
            "iteration_index": 0,
            "click_point": [100, 50],
            "candidates": [{"bbox": [90, 40, 110, 60], "confidence": 0.4}],
        }
    ]


def test_screenshot_path_relative_posix_and_null_fallback():
    row = _sample()
    assert row["screenshot_path"] == "runs/run-1/bundles/b0/safe_evidence.png"
    # unresolvable frame id → null, sample still built
    row2 = _sample(frame_paths={})
    assert row2["screenshot_path"] is None


def test_relativize_passes_through_outside_root():
    p = relativize_screenshot_path("elsewhere\\x\\y.png", "artifacts")
    assert p == "elsewhere/x/y.png"
    assert relativize_screenshot_path(None, "artifacts") is None


def test_frame_path_map_reads_safe_image_paths():
    payload = {
        "frames": [
            {"id": "f0", "safe_image": {"path": "artifacts/runs/r/bundles/b/safe_evidence.png"}},
            {"id": "f1", "safe_image": {}},
            {},
        ]
    }
    assert build_frame_path_map(payload) == {
        "f0": "artifacts/runs/r/bundles/b/safe_evidence.png"
    }
    assert build_frame_path_map({}) == {}


def test_redaction_uses_default_and_configured_sensitive_keys():
    row = {
        "target": {"text": "ok", "text_value": "secret typed text"},
        "custom_field": {"operator_badge": "12345"},
        "intent": "fine",
    }
    redacted = redact_sample(row, ["operator_badge"])
    assert redacted["target"]["text_value"] == "***REDACTED***"
    assert redacted["custom_field"]["operator_badge"] == "***REDACTED***"
    assert redacted["target"]["text"] == "ok"
    assert redacted["intent"] == "fine"


def test_validate_criteria_filter():
    assert validate_criteria_filter(None) is None
    assert validate_criteria_filter([]) is None
    assert validate_criteria_filter(["zoom_reground_used"]) == {"zoom_reground_used"}
    try:
        validate_criteria_filter(["nope"])
    except UnknownCriterionError as e:
        assert "nope" in str(e) and "low_grounding_confidence" in str(e)
    else:
        raise AssertionError("unknown criterion must raise")


def test_since_filter_utc_normalization_and_null_started_at():
    since = datetime(2026, 7, 1, tzinfo=UTC)
    assert run_started_within(datetime(2026, 7, 10), since)  # naive == UTC
    assert not run_started_within(datetime(2026, 6, 1), since)
    assert not run_started_within(None, since)
    assert run_started_within(None, None)


# --- FR-008: additive evolution config ---------------------------------------


def test_evolution_config_defaults():
    cfg = EvolutionConfig()
    assert cfg.hard_case_grounding_confidence_below == 0.7
    assert cfg.hard_case_high_confidence_at_least == 0.9
    assert cfg.hard_case_failure_types == ["unexpected_dialog", "target_not_found"]


def test_agent_config_without_evolution_section_uses_defaults(tmp_path: Path):
    (tmp_path / "agent.yaml").write_text("step:\n  default_timeout_seconds: 60\n", "utf-8")
    cfg = load_agent_config(tmp_path)
    assert cfg.evolution.hard_case_grounding_confidence_below == 0.7


def test_shipped_agent_yaml_evolution_section_matches_defaults():
    shipped = Path(__file__).resolve().parents[2] / "config" / "agent.yaml"
    raw = yaml.safe_load(shipped.read_text(encoding="utf-8"))
    assert raw["evolution"] == {
        "hard_case_grounding_confidence_below": 0.7,
        "hard_case_high_confidence_at_least": 0.9,
        "hard_case_failure_types": ["unexpected_dialog", "target_not_found"],
    }
