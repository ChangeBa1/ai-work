"""US1 + US3/6/7: YAML loader field-level errors and verification_mode rules."""

from pathlib import Path

import pytest
import yaml

from vnc_agent.domain.testcase import FieldValidationError, load_test_case

FIXTURES = Path(__file__).parent / "testcases"
ROOT = Path(__file__).resolve().parents[2]


def test_load_valid_smoke():
    path = ROOT / "testcases" / "smoke-connect.yaml"
    tc = load_test_case(path)
    assert tc.id == "smoke-connect-001"
    assert tc.mode == "explicit"
    assert len(tc.steps) >= 1


def test_load_missing_fields():
    with pytest.raises(FieldValidationError) as ei:
        load_test_case(FIXTURES / "missing-fields.yaml")
    paths = {e["path"] for e in ei.value.errors}
    assert "name" in paths or "target_id" in paths or "mode" in paths


def test_load_invalid_mode():
    with pytest.raises(FieldValidationError) as ei:
        load_test_case(FIXTURES / "invalid-mode.yaml")
    assert any("mode" in e["path"] for e in ei.value.errors)


def _write_case(tmp_path: Path, steps: list[dict]) -> Path:
    data = {
        "id": "loader-test",
        "name": "loader",
        "target_id": "win10-test-01",
        "mode": "explicit",
        "steps": steps,
    }
    p = tmp_path / "case.yaml"
    p.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return p


def test_business_mode_screen_changed_only_rejected(tmp_path: Path):
    """T031: verification_mode business + only screen_changed → FieldValidationError."""
    p = _write_case(
        tmp_path,
        [
            {
                "id": "s1",
                "name": "s1",
                "intent": "click",
                "verification_mode": "business",
                "expected": {
                    "operator": "all",
                    "conditions": [{"type": "screen_changed", "value": ""}],
                },
            }
        ],
    )
    with pytest.raises(FieldValidationError) as ei:
        load_test_case(p)
    assert any("expected.conditions" in e["path"] for e in ei.value.errors)


def test_business_mode_with_text_appears_loads(tmp_path: Path):
    """T032: business + screen_changed + text_appears loads OK."""
    p = _write_case(
        tmp_path,
        [
            {
                "id": "s1",
                "name": "s1",
                "intent": "click",
                "verification_mode": "business",
                "expected": {
                    "operator": "all",
                    "conditions": [
                        {"type": "screen_changed", "value": ""},
                        {"type": "text_appears", "value": "1点"},
                    ],
                },
            }
        ],
    )
    tc = load_test_case(p)
    assert tc.steps[0].verification_mode == "business"


def test_effect_only_screen_changed_loads(tmp_path: Path):
    """T051: effect_only + only screen_changed loads successfully."""
    p = _write_case(
        tmp_path,
        [
            {
                "id": "probe",
                "name": "probe",
                "intent": "hover",
                "verification_mode": "effect_only",
                "expected": {
                    "operator": "all",
                    "conditions": [{"type": "screen_changed", "value": ""}],
                },
            }
        ],
    )
    tc = load_test_case(p)
    assert tc.steps[0].verification_mode == "effect_only"


def test_pos_buy_bag_checkout_business_mode():
    """T036: the formal bag checkout case uses deterministic business mode."""
    path = ROOT / "testcases" / "pos-buy-bag-checkout.yaml"
    if not path.exists():
        pytest.skip("pos-buy-bag-checkout.yaml not present")
    tc = load_test_case(path)
    assert tc.steps
    assert all(s.verification_mode == "business" for s in tc.steps)
    assert all(
        any(c.type not in {"screen_changed", "region_changed"} for c in s.expected.conditions)
        for s in tc.steps
    )


def test_legacy_effect_only_warning_load_omitted_mode(tmp_path: Path):
    """Loader accepts omitted verification_mode with only screen_changed (US7)."""
    p = _write_case(
        tmp_path,
        [
            {
                "id": "legacy",
                "name": "legacy",
                "intent": "click bag",
                "expected": {
                    "operator": "all",
                    "conditions": [{"type": "screen_changed", "value": ""}],
                },
            }
        ],
    )
    tc = load_test_case(p)
    assert tc.steps[0].verification_mode is None
