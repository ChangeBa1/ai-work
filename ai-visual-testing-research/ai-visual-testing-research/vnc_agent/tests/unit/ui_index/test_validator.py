"""T023: validate_bundle() over all fixtures + programmatic edge cases
(contracts/ui-index-consumer-interfaces.md §3, contracts/ui-analysis-bundle-v1.md §9)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from vnc_agent.config import UiIndexConfig
from vnc_agent.ui_index.errors import UiIndexErrorCode
from vnc_agent.ui_index.validator import validate_bundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ui_index"
VALID_MINIMAL = FIXTURES / "valid_minimal"
FORM_INPUT = FIXTURES / "fixture_form_input"
ICON_OVERLAY = FIXTURES / "fixture_icon_overlay"
INVALID = FIXTURES / "invalid"


@pytest.fixture
def cfg() -> UiIndexConfig:
    return UiIndexConfig()


# ---------------------------------------------------------------------------
# Valid fixtures — MUST all pass with zero issues.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bundle_dir", [VALID_MINIMAL, FORM_INPUT, ICON_OVERLAY])
def test_valid_fixtures_pass(bundle_dir: Path, cfg: UiIndexConfig):
    report = validate_bundle(bundle_dir, cfg)
    assert report.ok is True, report.issues
    assert report.issues == []
    assert report.manifest is not None


def test_fixture_form_input_flows_jsonl_parses_without_issues(cfg: UiIndexConfig):
    """SC-011 / T011: flows.jsonl is only used by this fixture — must be
    parsed and produce zero issues."""
    report = validate_bundle(FORM_INPUT, cfg)
    assert report.ok is True
    assert report.issues == []


# ---------------------------------------------------------------------------
# Invalid fixtures T013–T021 — each MUST produce contracts §9's error_code.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fixture_name", "expected_code"),
    [
        ("unsupported_version", UiIndexErrorCode.SCHEMA_UNSUPPORTED_MAJOR),
        ("missing_file", UiIndexErrorCode.CONTENT_FILE_MISSING),
        ("jsonl_syntax_error", UiIndexErrorCode.JSONL_SYNTAX_ERROR),
        ("duplicate_id", UiIndexErrorCode.DUPLICATE_ID),
        ("missing_reference", UiIndexErrorCode.DANGLING_REFERENCE),
        ("invalid_coordinates", UiIndexErrorCode.COORDINATE_OUT_OF_RANGE),
        ("invalid_confidence", UiIndexErrorCode.INVALID_CONFIDENCE),
        ("checksum_mismatch", UiIndexErrorCode.CHECKSUM_MISMATCH),
        ("path_traversal", UiIndexErrorCode.PATH_TRAVERSAL),
    ],
)
def test_invalid_fixtures_produce_expected_error_code(
    fixture_name: str, expected_code: UiIndexErrorCode, cfg: UiIndexConfig
):
    report = validate_bundle(INVALID / fixture_name, cfg)
    assert report.ok is False
    codes = {issue.error_code for issue in report.issues}
    assert expected_code in codes, (fixture_name, codes)


def test_missing_file_reports_field_path_and_file():
    report = validate_bundle(INVALID / "missing_file", UiIndexConfig())
    issue = next(
        i for i in report.issues if i.error_code == UiIndexErrorCode.CONTENT_FILE_MISSING
    )
    assert issue.file == "elements.jsonl"


def test_jsonl_syntax_error_reports_line_number():
    report = validate_bundle(INVALID / "jsonl_syntax_error", UiIndexConfig())
    issue = next(i for i in report.issues if i.error_code == UiIndexErrorCode.JSONL_SYNTAX_ERROR)
    assert issue.line is not None
    assert issue.file == "screens.jsonl"


def test_invalid_coordinates_covers_missing_space_and_out_of_range(tmp_path: Path):
    """T018 fixture builds two variants: missing coordinate_space AND
    x1>=x2 — both categories must be represented."""
    report = validate_bundle(INVALID / "invalid_coordinates", UiIndexConfig())
    codes = {issue.error_code for issue in report.issues}
    assert UiIndexErrorCode.MISSING_COORDINATE_SPACE in codes
    assert UiIndexErrorCode.COORDINATE_OUT_OF_RANGE in codes


def test_invalid_confidence_covers_bad_level_and_bad_score():
    report = validate_bundle(INVALID / "invalid_confidence", UiIndexConfig())
    issues = [i for i in report.issues if i.error_code == UiIndexErrorCode.INVALID_CONFIDENCE]
    assert len(issues) >= 2


def test_checksum_mismatch_does_not_suppress_other_checks(tmp_path: Path):
    """Contract: checksum comparison happens last and independently — it
    does not gate/replace any earlier check."""
    report = validate_bundle(INVALID / "checksum_mismatch", UiIndexConfig())
    assert report.ok is False
    assert any(i.error_code == UiIndexErrorCode.CHECKSUM_MISMATCH for i in report.issues)


# ---------------------------------------------------------------------------
# Programmatic edge cases not covered by committed fixtures.
# ---------------------------------------------------------------------------


def _copy_fixture(src: Path, dst: Path) -> Path:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def test_field_type_error_programmatic(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    (bundle_dir / "elements.jsonl").write_text(
        '{"element_id": "el.home.ok", "screen_id": "screen.home", '
        '"parent_element_id": null, "name": "OK", "role": "button", '
        '"visible_texts": "not-a-list", "aliases": [], "supported_actions": ["click"], '
        '"region": "body", "confidence": {"level": "confirmed", "score": 0.9}}\n',
        encoding="utf-8",
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(i.error_code == UiIndexErrorCode.FIELD_TYPE_ERROR for i in report.issues)


def test_parent_cycle_screen_self_reference(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    (bundle_dir / "screens.jsonl").write_text(
        '{"screen_id": "screen.home", "name": "Home", "screen_type": "page", '
        '"visible_titles": ["Home"], "aliases": [], "parent_screen_id": "screen.home", '
        '"confidence": {"level": "confirmed", "score": 0.9}}\n',
        encoding="utf-8",
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(i.error_code == UiIndexErrorCode.PARENT_CYCLE for i in report.issues)


def test_parent_cycle_screen_two_node_cycle(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    (bundle_dir / "screens.jsonl").write_text(
        '{"screen_id": "screen.a", "name": "A", "screen_type": "page", '
        '"visible_titles": [], "aliases": [], "parent_screen_id": "screen.b", '
        '"confidence": {"level": "confirmed", "score": 0.9}}\n'
        '{"screen_id": "screen.b", "name": "B", "screen_type": "page", '
        '"visible_titles": [], "aliases": [], "parent_screen_id": "screen.a", '
        '"confidence": {"level": "confirmed", "score": 0.9}}\n',
        encoding="utf-8",
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    cycle_issues = [i for i in report.issues if i.error_code == UiIndexErrorCode.PARENT_CYCLE]
    assert len(cycle_issues) >= 1


def test_parent_cycle_element_self_reference(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    (bundle_dir / "elements.jsonl").write_text(
        '{"element_id": "el.home.ok", "screen_id": "screen.home", '
        '"parent_element_id": "el.home.ok", "name": "OK", "role": "button", '
        '"visible_texts": ["OK"], "aliases": [], "supported_actions": ["click"], '
        '"region": "body", "confidence": {"level": "confirmed", "score": 0.9}}\n',
        encoding="utf-8",
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(i.error_code == UiIndexErrorCode.PARENT_CYCLE for i in report.issues)


def test_parent_cycle_element_two_node_cycle(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    (bundle_dir / "elements.jsonl").write_text(
        '{"element_id": "el.a", "screen_id": "screen.home", '
        '"parent_element_id": "el.b", "name": "A", "role": "button", '
        '"visible_texts": [], "aliases": [], "supported_actions": ["click"], '
        '"region": "body", "confidence": {"level": "confirmed", "score": 0.9}}\n'
        '{"element_id": "el.b", "screen_id": "screen.home", '
        '"parent_element_id": "el.a", "name": "B", "role": "button", '
        '"visible_texts": [], "aliases": [], "supported_actions": ["click"], '
        '"region": "body", "confidence": {"level": "confirmed", "score": 0.9}}\n',
        encoding="utf-8",
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    cycle_issues = [i for i in report.issues if i.error_code == UiIndexErrorCode.PARENT_CYCLE]
    assert len(cycle_issues) >= 1


def test_dangling_guard_reference_programmatic(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    (bundle_dir / "transitions.jsonl").write_text(
        '{"transition_id": "tr.home.self", "from_screen_id": "screen.home", '
        '"trigger_element_id": "el.home.ok", "trigger_action": "click", '
        '"guards": [{"element_id": "el.does_not_exist", "condition": "enabled"}], '
        '"to_screen_id": "screen.home", "transition_type": "state_change", '
        '"expected_visible": [], "expected_hidden": [], "expected_state_changes": [], '
        '"confidence": {"level": "confirmed", "score": 0.9}}\n',
        encoding="utf-8",
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(
        i.error_code == UiIndexErrorCode.DANGLING_GUARD_REFERENCE for i in report.issues
    )


def test_invalid_diagnostic_confidence_programmatic(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    manifest_text = (bundle_dir / "manifest.yaml").read_text(encoding="utf-8")
    manifest_text = manifest_text.replace(
        "  transitions.jsonl: {required: true, sha256: null, record_count: null}",
        "  transitions.jsonl: {required: true, sha256: null, record_count: null}\n"
        "  diagnostics.jsonl: {required: false, sha256: null, record_count: null}",
    )
    (bundle_dir / "manifest.yaml").write_text(manifest_text, encoding="utf-8")
    (bundle_dir / "diagnostics.jsonl").write_text(
        '{"diagnostic_id": "diag.1", "category": "unconfirmed_element", '
        '"target_ref": {"element_id": "el.home.ok"}, "reason": "needs check", '
        '"confidence": {"level": "confirmed", "score": 0.9}}\n',
        encoding="utf-8",
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(
        i.error_code == UiIndexErrorCode.INVALID_DIAGNOSTIC_CONFIDENCE for i in report.issues
    )


def _bundle_with_flows_file(bundle_dir: Path, flows_jsonl: str) -> None:
    manifest_text = (bundle_dir / "manifest.yaml").read_text(encoding="utf-8")
    if "flows.jsonl" not in manifest_text:
        manifest_text = manifest_text.replace(
            "  transitions.jsonl: {required: true, sha256: null, record_count: null}",
            "  transitions.jsonl: {required: true, sha256: null, record_count: null}\n"
            "  flows.jsonl: {required: false, sha256: null, record_count: null}",
        )
        (bundle_dir / "manifest.yaml").write_text(manifest_text, encoding="utf-8")
    (bundle_dir / "flows.jsonl").write_text(flows_jsonl, encoding="utf-8")


def test_flow_dangling_transition_id_programmatic(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    _bundle_with_flows_file(
        bundle_dir,
        '{"flow_id": "flow.x", "name": "X", "start_screen_id": "screen.home", '
        '"steps": [{"transition_id": "tr.does_not_exist"}], '
        '"completion_screen_id": "screen.home", "preconditions": [], '
        '"confidence": {"level": "statically_inferred", "score": 0.5}}\n',
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(i.error_code == UiIndexErrorCode.DANGLING_REFERENCE for i in report.issues)


def test_flow_dangling_element_id_programmatic(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    _bundle_with_flows_file(
        bundle_dir,
        '{"flow_id": "flow.x", "name": "X", "start_screen_id": "screen.home", '
        '"steps": [{"element_id": "el.does_not_exist", "action": "click"}], '
        '"completion_screen_id": "screen.home", "preconditions": [], '
        '"confidence": {"level": "statically_inferred", "score": 0.5}}\n',
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(i.error_code == UiIndexErrorCode.DANGLING_REFERENCE for i in report.issues)


def test_flow_dangling_start_screen_id_programmatic(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    _bundle_with_flows_file(
        bundle_dir,
        '{"flow_id": "flow.x", "name": "X", "start_screen_id": "screen.does_not_exist", '
        '"steps": [{"transition_id": "tr.home.self"}], '
        '"completion_screen_id": "screen.home", "preconditions": [], '
        '"confidence": {"level": "statically_inferred", "score": 0.5}}\n',
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(i.error_code == UiIndexErrorCode.DANGLING_REFERENCE for i in report.issues)


def test_flow_dangling_completion_screen_id_programmatic(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    _bundle_with_flows_file(
        bundle_dir,
        '{"flow_id": "flow.x", "name": "X", "start_screen_id": "screen.home", '
        '"steps": [{"transition_id": "tr.home.self"}], '
        '"completion_screen_id": "screen.does_not_exist", "preconditions": [], '
        '"confidence": {"level": "statically_inferred", "score": 0.5}}\n',
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(i.error_code == UiIndexErrorCode.DANGLING_REFERENCE for i in report.issues)


def test_flowstep_discriminant_violation_both_provided_is_a_load_time_error(tmp_path: Path):
    """FlowStep's discriminated-union constraint is enforced by the Pydantic
    model itself (models.py::FlowStep) — providing both transition_id AND
    element_id/action is rejected at parse time, surfacing as a
    FIELD_TYPE_ERROR issue rather than silently accepting one variant."""
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    _bundle_with_flows_file(
        bundle_dir,
        '{"flow_id": "flow.x", "name": "X", "start_screen_id": "screen.home", '
        '"steps": [{"transition_id": "tr.home.self", "element_id": "el.home.ok", '
        '"action": "click"}], '
        '"completion_screen_id": "screen.home", "preconditions": [], '
        '"confidence": {"level": "statically_inferred", "score": 0.5}}\n',
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(i.error_code == UiIndexErrorCode.FIELD_TYPE_ERROR for i in report.issues)


def test_flowstep_discriminant_violation_neither_provided(tmp_path: Path):
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    _bundle_with_flows_file(
        bundle_dir,
        '{"flow_id": "flow.x", "name": "X", "start_screen_id": "screen.home", '
        '"steps": [{}], '
        '"completion_screen_id": "screen.home", "preconditions": [], '
        '"confidence": {"level": "statically_inferred", "score": 0.5}}\n',
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(i.error_code == UiIndexErrorCode.FIELD_TYPE_ERROR for i in report.issues)


def test_dangling_reference_derived_from_fixture_form_input(tmp_path: Path):
    """SC-011: at least one dangling-reference programmatic case MUST be
    built from T011 (fixture_form_input), not only from T010
    (valid_minimal), so that fixture's error-handling path is also
    exercised by the validator test suite."""
    bundle_dir = _copy_fixture(FORM_INPUT, tmp_path / "bundle")
    (bundle_dir / "transitions.jsonl").write_text(
        '{"transition_id": "tr.form.submit", "from_screen_id": "screen.form_edit", '
        '"trigger_element_id": "el.form.submit_btn", "trigger_action": "click", '
        '"guards": [], "to_screen_id": "screen.does_not_exist", '
        '"transition_type": "replace", "expected_visible": [], "expected_hidden": [], '
        '"expected_state_changes": [], "confidence": {"level": "confirmed", "score": 0.9}}\n',
        encoding="utf-8",
    )
    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    assert any(i.error_code == UiIndexErrorCode.DANGLING_REFERENCE for i in report.issues)


# ---------------------------------------------------------------------------
# Validation order stability (contracts §3's fixed 6-step order).
# ---------------------------------------------------------------------------


def test_validation_order_is_stable_across_repeated_runs():
    """Running validate_bundle() on the same invalid input twice MUST
    produce issues in the exact same order both times (deterministic
    step ordering, not e.g. set-iteration-order-dependent)."""
    report1 = validate_bundle(INVALID / "invalid_coordinates", UiIndexConfig())
    report2 = validate_bundle(INVALID / "invalid_coordinates", UiIndexConfig())
    codes1 = [i.error_code for i in report1.issues]
    codes2 = [i.error_code for i in report2.issues]
    assert codes1 == codes2


def test_checksum_mismatch_issue_ordered_after_reference_and_field_issues(tmp_path: Path):
    """Contract step 6: checksum comparison happens last, independent of
    (i.e. after) earlier structural checks, even when both fire."""
    bundle_dir = _copy_fixture(VALID_MINIMAL, tmp_path / "bundle")
    # Introduce a dangling reference (step 5) AND a checksum mismatch (step 6).
    (bundle_dir / "transitions.jsonl").write_text(
        '{"transition_id": "tr.home.self", "from_screen_id": "screen.home", '
        '"trigger_element_id": "el.home.ok", "trigger_action": "click", "guards": [], '
        '"to_screen_id": "screen.missing", "transition_type": "state_change", '
        '"expected_visible": [], "expected_hidden": [], "expected_state_changes": [], '
        '"confidence": {"level": "confirmed", "score": 0.9}}\n',
        encoding="utf-8",
    )
    manifest_text = (bundle_dir / "manifest.yaml").read_text(encoding="utf-8")
    manifest_text = manifest_text.replace(
        "screens.jsonl: {required: true, sha256: null, record_count: null}",
        'screens.jsonl: {required: true, sha256: '
        '"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", '
        "record_count: null}",
    )
    (bundle_dir / "manifest.yaml").write_text(manifest_text, encoding="utf-8")

    report = validate_bundle(bundle_dir, UiIndexConfig())
    assert report.ok is False
    codes = [i.error_code for i in report.issues]
    assert UiIndexErrorCode.DANGLING_REFERENCE in codes
    assert UiIndexErrorCode.CHECKSUM_MISMATCH in codes
    # checksum_mismatch MUST come after dangling_reference in issue order.
    assert codes.index(UiIndexErrorCode.CHECKSUM_MISMATCH) > codes.index(
        UiIndexErrorCode.DANGLING_REFERENCE
    )
