"""T005: UiIndexErrorCode stable values + ValidationIssue/Report structure."""

from __future__ import annotations

from vnc_agent.ui_index.errors import UiIndexErrorCode, ValidationIssue, ValidationReport

EXPECTED_CODES = {
    "bundle_dir_not_found",
    "schema_unsupported_major",
    "manifest_missing",
    "content_file_missing",
    "jsonl_syntax_error",
    "field_type_error",
    "duplicate_id",
    "dangling_reference",
    "parent_cycle",
    "dangling_guard_reference",
    "missing_coordinate_space",
    "coordinate_out_of_range",
    "invalid_confidence",
    "invalid_diagnostic_confidence",
    "path_traversal",
    "resource_limit_exceeded",
    "checksum_mismatch",
}


def test_error_code_stable_string_values():
    values = {c.value for c in UiIndexErrorCode}
    assert values == EXPECTED_CODES
    assert len(values) == 17


def test_validation_issue_and_report_structure():
    issue = ValidationIssue(
        error_code=UiIndexErrorCode.DUPLICATE_ID,
        file="elements.jsonl",
        line=2,
        field_path="elements[1].element_id",
        message="duplicate element_id",
    )
    report = ValidationReport(ok=False, bundle_dir="/tmp/b", issues=[issue], manifest=None)
    assert report.ok is False
    assert report.issues[0].error_code == UiIndexErrorCode.DUPLICATE_ID
    assert report.issues[0].file == "elements.jsonl"
    assert report.issues[0].line == 2
    assert report.issues[0].field_path == "elements[1].element_id"
    empty = ValidationReport(ok=True, bundle_dir="/tmp/b", issues=[], manifest=None)
    assert empty.ok is True
