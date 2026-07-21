"""US8 T064: static scan — feature tests must not instantiate real VNCDriver."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # vnc_agent/tests

# Feature 002 offline test roots (plan.md three-tier taxonomy)
SCAN_GLOBS = [
    "fixtures/test_action_effect.py",
    "fixtures/test_repeat_guard.py",
    "fixtures/test_error_popup_classification.py",
    "fixtures/test_business_resolver.py",
    "fixtures/test_testcase_loader.py",
    "fixtures/test_report_builder.py",
    "unit/test_action_kind_classification.py",
    "unit/test_focus_path_gate.py",
    "e2e/test_scenario_10_no_duplicate_action.py",
    "e2e/test_scenario_11_error_popup_not_passed.py",
    "e2e/test_scenario_12_legacy_weak_assertion.py",
    "e2e/test_scenario_13_pos_bag_regression.py",
]

_FORBIDDEN_CALL = re.compile(r"(?<!Mock)(?<!Fake)\bVNCDriver\s*\(")
_FORBIDDEN_IMPORT = re.compile(
    r"^\s*(from\s+vncdotool\b|import\s+vncdotool\b|from\s+vnc_agent\.drivers\.vncdotool_driver\s+import)"
)


def test_no_real_vnc_driver_in_feature_tests():
    violations: list[str] = []
    for rel in SCAN_GLOBS:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if _FORBIDDEN_CALL.search(line) or _FORBIDDEN_IMPORT.search(line):
                if "MockVNCDriver" in line or "FakeVNC" in line:
                    continue
                violations.append(f"{rel}:{i}: {stripped}")
    assert not violations, "Real VNC usage found in offline feature tests:\n" + "\n".join(
        violations
    )
