"""T054: `generate-ui-analysis-index` skill files MUST NOT leak
implementation-detail parser/toolchain names, business-specific vocabulary,
or throwaway-project scaffolding (spec.md FR-021/029)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = REPO_ROOT / ".agents" / "skills" / "generate-ui-analysis-index"

# Framework/toolchain-specific parser implementation names — the skill must
# describe recognition goals in framework-agnostic terms, never instruct the
# reader to invoke (or depend on) one specific language's AST/analysis API.
FORBIDDEN_IMPLEMENTATION_TOKENS = [
    "Roslyn",
    "MSBuildWorkspace",
    "JavaParser",
    "TypeScript Compiler",
    "XAML",
]

# AI-external references that would tie this skill to a specific product's
# vocabulary or an unrelated third-party API surface (reused business-token
# scan mirrors tests/unit/test_no_business_keywords_in_core.py's approach).
FORBIDDEN_REFERENCE_TOKENS = [
    "Figma API",
    "pos-buy-bag-checkout",
    "pos-click-icon",
    "pos-hover-probe",
    "レジ袋",
    "購入",
    "支払い",
    "加购",
    "结算",
]

try:
    # Reuse the core-module business-keyword scan table so this skill's
    # deliverables are held to the same "no hardcoded business vocabulary"
    # bar as vnc-agent's own source (tests/unit/test_no_business_keywords_in_core.py).
    from tests.unit.test_no_business_keywords_in_core import (
        FORBIDDEN_TOKENS as _CORE_FORBIDDEN_TOKENS,
    )
except ImportError:
    _CORE_FORBIDDEN_TOKENS = []

FORBIDDEN_TOKENS = list(
    dict.fromkeys(
        [*FORBIDDEN_IMPLEMENTATION_TOKENS, *FORBIDDEN_REFERENCE_TOKENS, *_CORE_FORBIDDEN_TOKENS]
    )
)
_TOKEN_PATTERN = re.compile("|".join(re.escape(tok) for tok in FORBIDDEN_TOKENS))

FORBIDDEN_LIFECYCLE_FILES = ["README.md", "CHANGELOG.md"]


def _skip_if_skill_absent() -> None:
    if not SKILL_DIR.is_dir():
        pytest.skip(f"skill not present yet: {SKILL_DIR}")


def _iter_skill_files() -> list[Path]:
    return [p for p in sorted(SKILL_DIR.rglob("*")) if p.is_file()]


def test_skill_directory_exists():
    _skip_if_skill_absent()
    assert SKILL_DIR.is_dir()


def test_no_forbidden_tokens_anywhere_in_skill_files():
    _skip_if_skill_absent()
    violations: list[str] = []
    for path in _iter_skill_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, ValueError):
            continue  # binary assets (e.g. templates) are not scanned as text
        for i, line in enumerate(text.splitlines(), 1):
            match = _TOKEN_PATTERN.search(line)
            if match:
                rel = path.relative_to(SKILL_DIR).as_posix()
                violations.append(f"{rel}:{i}: forbidden token '{match.group(0)}': {line.strip()}")
    assert not violations, "\n".join(violations)


def test_no_readme_or_changelog_files_in_skill_directory():
    """FR-029: this skill is meant to be used long-term/repeatedly by other
    agents reading SKILL.md itself — it must not accumulate its own
    README.md/CHANGELOG.md as if it were a standalone throwaway project."""
    _skip_if_skill_absent()
    present = [name for name in FORBIDDEN_LIFECYCLE_FILES if (SKILL_DIR / name).is_file()]
    assert not present, f"unexpected lifecycle file(s) in skill dir: {present}"

    for path in _iter_skill_files():
        assert path.name not in FORBIDDEN_LIFECYCLE_FILES, path


def test_scanner_actually_discriminates_on_an_injected_forbidden_token(tmp_path: Path):
    """Proves the scan mechanism is discriminating, not a vacuous no-op."""
    sample = tmp_path / "injected.md"
    sample.write_text("Use Roslyn to parse the source tree.\n", encoding="utf-8")
    text = sample.read_text(encoding="utf-8")
    matches = [m.group(0) for line in text.splitlines() for m in [_TOKEN_PATTERN.search(line)] if m]
    assert matches == ["Roslyn"]
