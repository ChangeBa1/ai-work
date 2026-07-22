"""Feature 003 typed configuration contract tests (T012/T028/T033).

Constitution v1.1.0 Principle VI: core config MUST NOT hardcode any
business-specific keyword list or fixed category enum.
"""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from vnc_agent.config import AgentConfig, load_agent_config
from vnc_agent.domain.reporting_tags import ActionMatcher, ActionTagRule

RECOVERY_FIELDS = {
    "max_retries",
    "cooldown_ms",
    "consumes_global_retry_budget",
    "allows_action_path_change",
    "requires_strong_model",
    "requires_human_confirmation",
}


def _default_raw_config() -> dict:
    path = Path(__file__).parents[2] / "config" / "agent.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_planning_no_longer_exposes_keyword_lists() -> None:
    config = load_agent_config(Path(__file__).parents[2] / "config")

    assert not hasattr(config.planning, "result_display_keywords")
    assert not hasattr(config.planning, "dismissal_keywords")
    assert 0 < config.planning.ocr_sanity_check_ratio <= 1


def test_planning_micro_action_risk_thresholds_are_generic_ui_categories() -> None:
    config = load_agent_config(Path(__file__).parents[2] / "config")

    assert 0 < config.planning.target_region_conflict_iou_threshold <= 1
    thresholds = config.planning.micro_action_risk_thresholds
    assert thresholds
    assert set(thresholds) <= {
        "dismiss_overlay",
        "scroll_reveal",
        "refocus",
        "wait",
        "re_observe",
    }
    assert all(v in ("low", "medium", "high") for v in thresholds.values())


def test_reporting_action_tags_defaults_to_empty_no_fixed_categories() -> None:
    config = load_agent_config(Path(__file__).parents[2] / "config")

    assert config.reporting.action_tags == []
    # No validator requiring specific category keys — a testcase/profile MAY
    # freely declare arbitrary tags via ActionTagRule.
    config2 = AgentConfig.model_validate(
        {
            "reporting": {
                "action_tags": [
                    {"tag": "example_tag", "matcher": {"action_type": "click"}}
                ]
            }
        }
    )
    assert config2.reporting.action_tags == [
        ActionTagRule(tag="example_tag", matcher=ActionMatcher(action_type="click"))
    ]


def test_recovery_policies_still_require_all_six_fields() -> None:
    config = load_agent_config(Path(__file__).parents[2] / "config")

    assert config.recovery
    for policy in config.recovery.values():
        assert RECOVERY_FIELDS <= set(policy.model_fields_set)


@pytest.mark.parametrize("missing_field", sorted(RECOVERY_FIELDS))
def test_each_recovery_policy_field_is_required(missing_field: str) -> None:
    raw = deepcopy(_default_raw_config())
    first_policy = next(iter(raw["recovery"].values()))
    first_policy.pop(missing_field)

    with pytest.raises(ValidationError):
        AgentConfig.model_validate(raw)
