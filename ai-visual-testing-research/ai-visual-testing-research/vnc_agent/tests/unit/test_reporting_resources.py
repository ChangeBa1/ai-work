"""Phase 6 (T050): zh-CN resource registry completeness
(report-contract.md "Resource registry contract").
"""

from __future__ import annotations

import pytest

from vnc_agent.reporting.localization import (
    UnknownLocaleError,
    display,
    localize_error,
    registered_locales,
    resource_text,
)

REQUIRED_KEYS = [
    "report.title", "report.case", "report.status", "report.started_at",
    "report.ended_at", "report.step", "report.iteration", "report.evidence",
    "report.precondition", "report.action_audit", "report.performance_summary",
    "report.recovery_attempts", "report.failure_reason", "report.none",
    "report.unavailable", "report.evidence_error", "report.unknown_error",
]

STATUS_VALUES = ["passed", "failed", "cancelled", "running", "created"]
VERIFICATION_VALUES = ["passed", "failed", "uncertain"]
ACTION_EFFECT_VALUES = ["no_effect", "expected_effect", "unexpected_effect", "effect_uncertain"]
STAGE_STATUS_VALUES = ["completed", "failed", "cancelled", "unavailable"]
STAGE_NAMES = [
    "capture", "pixel_hash", "persistence", "OCR", "template", "vision",
    "planner", "grounder", "verification", "report_build", "report_output",
]
EVIDENCE_ERROR_KEYS = [
    "missing", "out_of_bounds", "truncated", "corrupted", "byte_size_mismatch",
    "hash_mismatch", "undecodable", "mask_mismatch", "wrong_purpose",
    "orphan_bundle", "not_found",
]
KNOWN_ERROR_CODES = [
    "decode_error", "mask_encode_error", "persistence_error", "logical_commit_error",
    "vnc_connect_failed", "vnc_disconnected", "black_screen", "page_not_stable",
    "target_not_found", "grounding_low_confidence", "action_no_effect",
    "focus_error", "input_method_error", "unexpected_dialog", "verification_failed",
    "timeout",
]


def test_zh_cn_is_registered():
    assert "zh-CN" in registered_locales()


@pytest.mark.parametrize("key", REQUIRED_KEYS)
def test_required_page_labels_present(key):
    assert resource_text("zh-CN", key)


@pytest.mark.parametrize("value", STATUS_VALUES)
def test_status_values_localized(value):
    d = display("zh-CN", "status", value)
    assert d.display_value
    assert d.machine_value == value


@pytest.mark.parametrize("value", VERIFICATION_VALUES)
def test_verification_values_localized(value):
    assert display("zh-CN", "verification", value).display_value


@pytest.mark.parametrize("value", ACTION_EFFECT_VALUES)
def test_action_effect_values_localized(value):
    assert display("zh-CN", "action_effect", value).display_value


@pytest.mark.parametrize("value", STAGE_STATUS_VALUES)
def test_stage_status_values_localized(value):
    assert display("zh-CN", "stage_status", value).display_value


@pytest.mark.parametrize("value", STAGE_NAMES)
def test_all_canonical_stage_names_localized(value):
    assert display("zh-CN", "stage_name", value).display_value


@pytest.mark.parametrize("value", EVIDENCE_ERROR_KEYS)
def test_evidence_error_keys_localized(value):
    assert resource_text("zh-CN", f"evidence_error.{value}")


@pytest.mark.parametrize("code", KNOWN_ERROR_CODES)
def test_known_error_codes_localize_and_keep_raw_code(code):
    text = localize_error("zh-CN", code, None)
    assert code in text  # raw code preserved verbatim


def test_unknown_error_code_uses_generic_message_and_keeps_raw_detail():
    text = localize_error("zh-CN", "totally_unknown_code_xyz", "raw detail 123")
    assert "totally_unknown_code_xyz" in text
    assert "raw detail 123" in text
    assert resource_text("zh-CN", "report.unknown_error") in text


def test_null_error_code_renders_null_marker_not_a_guess():
    text = localize_error("zh-CN", None, None)
    assert "code=null" in text


def test_unregistered_locale_fails_fast():
    with pytest.raises(UnknownLocaleError):
        resource_text("fr-FR", "report.title")
    with pytest.raises(UnknownLocaleError):
        display("fr-FR", "status", "passed")
    with pytest.raises(UnknownLocaleError):
        localize_error("fr-FR", "target_not_found", None)


def test_display_value_provides_machine_display_css_data_marker_triple():
    d = display("zh-CN", "status", "passed")
    assert d.machine_value == "passed"
    assert d.display_value == "通过"
    assert d.css_class == "status-passed"
    assert d.data_marker == "passed"
