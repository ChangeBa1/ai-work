"""Constitution VI / feature 024 SC-005: the core carries no business words.

Feature 024's whole claim to being "pluggable" is that adding an application
means adding a data file, never editing `src/`. This test is the enforcement:
if a window title, control label or application name shows up in production
code, the feature is by definition not pluggable any more.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "vnc_agent"
PROFILES = Path(__file__).resolve().parents[2] / "profiles" / "app_perception"

# Vocabulary from the application under test that feature 024 could plausibly
# have leaked into core: window/application names and control labels.
FORBIDDEN = [
    "ScannerSimulator",
    "CashChanger",
    "CT5100",
    "CT6100",
    "ValueCardSimulator",
    "PointInfinity",
    "FaceMeService",
    "SelfFraudDetection",
    "POSPrinter",
    "TopMost",
    "Barcode:",
    "Favorite:",
    "scanner-sim",
    "cash-changer-sim",
]

# Business terms already understood to be scenario data, kept out of core.
FORBIDDEN_BUSINESS = ["金券", "預/現計", "小計", "レジ袋", "釣銭機"]


def _python_sources() -> list[Path]:
    return [p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts]


@pytest.mark.parametrize("word", FORBIDDEN + FORBIDDEN_BUSINESS)
def test_core_contains_no_application_vocabulary(word):
    needle = re.compile(re.escape(word), re.IGNORECASE)
    offenders = [
        f"{path.relative_to(SRC)}:{i}"
        for path in _python_sources()
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if needle.search(line)
    ]
    assert offenders == [], (
        f"business vocabulary {word!r} leaked into core: {offenders}. "
        "It belongs in a profile YAML, a test case or a fixture."
    )


def test_the_vocabulary_really_does_live_in_the_profiles():
    """Guard against the scan passing because the words exist nowhere at all:
    the shipped profiles must actually contain the application's terms."""
    corpus = "\n".join(p.read_text(encoding="utf-8") for p in PROFILES.glob("*.yaml"))
    assert "ScannerSimulator" in corpus
    assert "CashChanger" in corpus
    assert "TopMost" in corpus


def test_plugins_are_discovered_from_data_not_enumerated_in_code():
    """Adding an application must not require a code change: the registry
    finds profiles by scanning a configured directory, and no shipped profile
    name is written down anywhere in `src/`."""
    from vnc_agent.perception.app_plugins.registry import PluginRegistry

    registry = PluginRegistry.from_profiles_dir(PROFILES)
    discovered = registry.names()
    assert len(discovered) >= 2, "expected the shipped profiles to be discovered"

    package_text = "\n".join(
        p.read_text(encoding="utf-8")
        for p in (SRC / "perception" / "app_plugins").glob("*.py")
    )
    for name in discovered:
        assert name not in package_text, (
            f"profile {name!r} is hardcoded in the plugin package — "
            "discovery must be data-driven"
        )
