"""Feature 003 T002/T050: static scan — core modules must not contain fixed
business-specific fields/keywords (Constitution v1.1.0 Principle VI).

T050 (/speckit-converge, 2026-07-22): removed the `planning/
action_classification.py` exclusion and added its former retail/payment
keyword tokens (レジ袋/購入/支払い/加购/结算) to the forbidden list, now that
`_DEFAULT_NON_IDEMPOTENT_KEYWORDS` has been generalized away — the whole
`planning/` package is scanned, with no carve-outs.

Feature 004 (T063, 2026-07-23): added `perception` and `storage` to the
scan — the new FrameCaptureService/AnalysisResultCache/ArtifactStore/
safe-evidence/telemetry modules live there and must stay just as
business-agnostic. Also added the two-unrelated-GUI-scenario fixture
vocabulary (`tests/fixtures/testcases/generic-form-flow.yaml` /
`generic-icon-menu-flow.yaml`) as forbidden core tokens — that vocabulary
must only ever appear in fixtures/tests, never as a hardcoded branch in
core capture/cache/reporting logic.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "vnc_agent"

SCAN_TARGETS = [
    "domain",
    "config.py",
    "execution",
    "reporting",
    "verification",
    "api",
    "planning",
    "runtime",
    "perception",
    "storage",
]

FORBIDDEN_TOKENS = [
    "confirmed_cart",
    "cart_items",
    "cart_amount",
    "add_to_bag",
    "subtotal",
    "clear_or_reset",
    "extract_cart_state",
    "result_display_keywords",
    "dismissal_keywords",
    "category_keywords",
    # Feature 003 T050: former action_classification.py retail/payment
    # vocabulary — precise, low-false-positive-risk tokens only (generic
    # English words like "pay"/"confirm"/"add"/"cancel" are deliberately
    # excluded from this list; they would false-positive on legitimate
    # generic identifiers such as `requires_human_confirmation`).
    "レジ袋",
    "購入",
    "支払い",
    "加购",
    "结算",
    # Feature 004 T063: the two unrelated cross-scenario GUI fixtures' own
    # vocabulary — must only ever live in tests/fixtures/testcases/*.yaml
    # and the cross-scenario test file, never as a core hardcoded branch.
    "generic-form-flow",
    "generic-icon-menu-flow",
    "generic_form_flow",
    "generic_icon_menu_flow",
    "toolbar_icon",
    "menu_item",
]

_TOKEN_PATTERN = re.compile("|".join(re.escape(tok) for tok in FORBIDDEN_TOKENS))


def _iter_scan_files() -> list[Path]:
    files: list[Path] = []
    for target in SCAN_TARGETS:
        path = SRC_ROOT / target
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(path.rglob("*.py")))
    return files


def test_core_modules_contain_no_business_specific_tokens():
    violations: list[str] = []
    for path in _iter_scan_files():
        rel = path.relative_to(SRC_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            match = _TOKEN_PATTERN.search(line)
            if match:
                violations.append(f"{rel}:{i}: forbidden token '{match.group(0)}': {line.strip()}")
    assert not violations, (
        "Business-specific tokens found in core modules "
        "(Constitution v1.1.0 Principle VI violation):\n" + "\n".join(violations)
    )


def test_scanner_itself_fails_on_an_injected_forbidden_token(tmp_path: Path):
    """Proves the scan mechanism is actually discriminating — not a
    vacuously-passing no-op — by injecting a forbidden token into a sample
    file and confirming the same pattern used above matches it."""
    sample = tmp_path / "injected.py"
    sample.write_text(
        "def handler():\n    return generic_form_flow_special_case()\n", encoding="utf-8"
    )
    text = sample.read_text(encoding="utf-8")
    matches = [
        f"{i}: {m.group(0)}"
        for i, line in enumerate(text.splitlines(), 1)
        for m in [_TOKEN_PATTERN.search(line)]
        if m
    ]
    assert matches, "the scanner must detect an injected forbidden token in a sample file"
