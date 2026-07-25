"""T024: UiIndexBundle.load() (contracts/ui-index-consumer-interfaces.md §4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vnc_agent.config import UiIndexConfig
from vnc_agent.ui_index.repository import UiIndexBundle, UiIndexValidationError
from vnc_agent.ui_index.validator import validate_bundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ui_index"
VALID_MINIMAL = FIXTURES / "valid_minimal"
FORM_INPUT = FIXTURES / "fixture_form_input"
ICON_OVERLAY = FIXTURES / "fixture_icon_overlay"
INVALID = FIXTURES / "invalid"


def test_load_valid_minimal_returns_usable_instance():
    bundle = UiIndexBundle.load(VALID_MINIMAL)
    assert bundle.manifest.bundle_id == "bundle-valid-minimal"
    assert set(bundle.screens.keys()) == {"screen.home"}
    assert set(bundle.elements.keys()) == {"el.home.ok"}
    assert set(bundle.transitions.keys()) == {"tr.home.self"}


def test_load_form_input_index_counts_match_fixture_records():
    bundle = UiIndexBundle.load(FORM_INPUT)
    assert len(bundle.screens) == 2
    assert len(bundle.elements) == 3
    assert len(bundle.transitions) == 1
    # T011 is the only fixture that carries flows.jsonl — the loaded index
    # MUST include it.
    assert len(bundle.flows) == 1
    assert "flow.form_submit" in bundle.flows


def test_load_icon_overlay_index_counts_match_fixture_records():
    bundle = UiIndexBundle.load(ICON_OVERLAY)
    assert len(bundle.screens) == 2
    assert len(bundle.elements) == 3
    assert len(bundle.transitions) == 1


@pytest.mark.parametrize(
    "fixture_name",
    [
        "unsupported_version",
        "missing_file",
        "jsonl_syntax_error",
        "duplicate_id",
        "missing_reference",
        "invalid_coordinates",
        "invalid_confidence",
        "checksum_mismatch",
        "path_traversal",
    ],
)
def test_load_invalid_fixture_raises_validation_error(fixture_name: str):
    bundle_dir = INVALID / fixture_name
    with pytest.raises(UiIndexValidationError) as excinfo:
        UiIndexBundle.load(bundle_dir)
    assert excinfo.value.report.ok is False
    assert len(excinfo.value.report.issues) > 0


def test_validation_error_report_matches_direct_validate_bundle_call():
    bundle_dir = INVALID / "duplicate_id"
    cfg = UiIndexConfig()
    direct_report = validate_bundle(bundle_dir, cfg)

    with pytest.raises(UiIndexValidationError) as excinfo:
        UiIndexBundle.load(bundle_dir, cfg)

    loaded_report = excinfo.value.report
    assert loaded_report.ok == direct_report.ok
    assert [i.error_code for i in loaded_report.issues] == [
        i.error_code for i in direct_report.issues
    ]
    assert loaded_report.bundle_dir == direct_report.bundle_dir


def test_load_never_returns_partial_instance_on_failure():
    """Contract: MUST NOT return a 'partially usable' instance — loading
    fails atomically via exception, never a half-populated object."""
    bundle_dir = INVALID / "missing_reference"
    try:
        UiIndexBundle.load(bundle_dir)
        pytest.fail("expected UiIndexValidationError")
    except UiIndexValidationError:
        pass


def test_query_methods_are_pure_and_idempotent():
    """Contract §4: query methods are read-only/idempotent — repeated calls
    with the same args return equal results and don't mutate state."""
    bundle = UiIndexBundle.load(FORM_INPUT)
    before_screens = dict(bundle.screens)
    from vnc_agent.ui_index.query import query_by_role

    result1 = query_by_role(bundle, "button")
    result2 = query_by_role(bundle, "button")
    assert [e.element_id for e in result1] == [e.element_id for e in result2]
    assert bundle.screens == before_screens


def test_load_accepts_str_or_path_bundle_dir():
    bundle_from_str = UiIndexBundle.load(str(VALID_MINIMAL))
    bundle_from_path = UiIndexBundle.load(VALID_MINIMAL)
    assert bundle_from_str.manifest.bundle_id == bundle_from_path.manifest.bundle_id
