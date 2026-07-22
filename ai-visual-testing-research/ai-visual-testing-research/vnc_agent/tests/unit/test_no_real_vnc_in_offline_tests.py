"""US8 T064 / Feature 003 T003: static scan — offline tests must not instantiate
real VNCDriver.

Feature 003 (2026-07-22): generalized from a hardcoded per-file list to a glob
scan over the three offline test roots (fixtures/, unit/, e2e/), so newly added
scenario test files (e.g. test_scenario_form_submit.py) are automatically
covered without needing this file to be updated per addition.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # vnc_agent/tests
THIS_FILE = Path(__file__).resolve()

SCAN_DIRS = ["fixtures", "unit", "e2e"]

_FORBIDDEN_CALL = re.compile(r"(?<!Mock)(?<!Fake)\bVNCDriver\s*\(")
_FORBIDDEN_IMPORT = re.compile(
    r"^\s*(from\s+vncdotool\b|import\s+vncdotool\b|from\s+vnc_agent\.drivers\.vncdotool_driver\s+import)"
)


def _iter_offline_test_files() -> list[Path]:
    files: list[Path] = []
    for dir_name in SCAN_DIRS:
        dir_path = ROOT / dir_name
        if not dir_path.is_dir():
            continue
        files.extend(sorted(dir_path.glob("test_*.py")))
    return files


def test_no_real_vnc_driver_in_feature_tests():
    violations: list[str] = []
    for path in _iter_offline_test_files():
        if path.resolve() == THIS_FILE:
            continue
        rel = path.relative_to(ROOT).as_posix()
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
