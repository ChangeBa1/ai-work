"""Feature 024 (FR-013): test-case declaration fields + load-time validation.

A typo in `perception_scope` would otherwise degrade silently into "no
enhancement", which looks exactly like a correctly undeclared step — so it has
to fail at load time.
"""

from __future__ import annotations

import pytest
import yaml

from vnc_agent.domain.testcase import FieldValidationError, load_test_case

BASE = {
    "id": "tc-1",
    "name": "demo",
    "target_id": "win10-test-01",
    "mode": "explicit",
    "steps": [
        {
            "id": "s1",
            "name": "step one",
            "intent": "click something",
            "expected": {
                "operator": "all",
                "conditions": [{"type": "text_appears", "value": "OK"}],
            },
        }
    ],
}


def write(tmp_path, payload):
    path = tmp_path / "case.yaml"
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    return path


def with_scope(scope, *, plugins=None):
    payload = {**BASE, "steps": [{**BASE["steps"][0], "perception_scope": scope}]}
    if plugins is not None:
        payload["perception_plugins"] = plugins
    return payload


def test_omitted_scope_defaults_to_none(tmp_path):
    tc = load_test_case(write(tmp_path, BASE))
    assert tc.steps[0].perception_scope is None
    assert tc.perception_plugins == []


def test_explicit_none_loads(tmp_path):
    tc = load_test_case(write(tmp_path, with_scope("none")), known_plugins={"demo-window"})
    assert tc.steps[0].perception_scope == "none"


def test_declared_scope_loads_when_registered(tmp_path):
    tc = load_test_case(
        write(tmp_path, with_scope("demo-window")), known_plugins={"demo-window"}
    )
    assert tc.steps[0].perception_scope == "demo-window"


def test_unknown_plugin_is_rejected_with_field_path_and_options(tmp_path):
    with pytest.raises(FieldValidationError) as excinfo:
        load_test_case(
            write(tmp_path, with_scope("typo-window")), known_plugins={"demo-window"}
        )
    message = str(excinfo.value)
    assert "steps[0].perception_scope" in message
    assert "typo-window" in message
    assert "demo-window" in message, "the error should list the valid options"


def test_case_level_allow_list_rejects_out_of_list_scope(tmp_path):
    with pytest.raises(FieldValidationError) as excinfo:
        load_test_case(
            write(tmp_path, with_scope("demo-window", plugins=["other-window"])),
            known_plugins={"demo-window", "other-window"},
        )
    assert "perception_plugins" in str(excinfo.value)


def test_case_level_allow_list_accepts_listed_scope(tmp_path):
    tc = load_test_case(
        write(tmp_path, with_scope("demo-window", plugins=["demo-window"])),
        known_plugins={"demo-window"},
    )
    assert tc.perception_plugins == ["demo-window"]


def test_unknown_name_in_allow_list_is_rejected(tmp_path):
    payload = {**BASE, "perception_plugins": ["ghost-window"]}
    with pytest.raises(FieldValidationError) as excinfo:
        load_test_case(write(tmp_path, payload), known_plugins={"demo-window"})
    assert "perception_plugins[0]" in str(excinfo.value)


def test_without_a_registry_the_scope_is_not_registry_checked(tmp_path):
    """Pre-024 callers pass no registry; behaviour must be unchanged."""
    tc = load_test_case(write(tmp_path, with_scope("anything-goes")))
    assert tc.steps[0].perception_scope == "anything-goes"


def test_existing_test_cases_still_load_untouched(tmp_path):
    """The feature must not disturb existing suites: all shipped test cases load cleanly."""
    from pathlib import Path

    cases = sorted((Path(__file__).resolve().parents[2] / "testcases").glob("*.yaml"))
    assert cases, "expected shipped test cases"
    for case in cases:
        tc = load_test_case(case, known_plugins={"scanner-sim"})
        assert tc.id
