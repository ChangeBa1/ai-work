"""Feature 003 T002/T050: static scan — core modules must not contain fixed
business-specific fields/keywords (Constitution v1.1.0 Principle VI).

T050 (/speckit-converge, 2026-07-22): removed the `planning/
action_classification.py` exclusion and added its former retail/payment
keyword tokens (レジ袋/購入/支払い/加购/结算) to the forbidden list, now that
`_DEFAULT_NON_IDEMPOTENT_KEYWORDS` has been generalized away — the whole
`planning/` package is scanned, with no carve-outs.
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
