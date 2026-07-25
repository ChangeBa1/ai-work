"""T053: the `generate-ui-analysis-index` skill's bundle-contract reference
MUST stay in sync (same file names + same field-name set per file) with the
authoritative spec contract `contracts/ui-analysis-bundle-v1.md` (FR-023).

This is a purely mechanical table-scrape comparison — no natural-language
semantics are parsed, only the first column (a backtick-quoted field name)
of each markdown table row under a per-content-file section header.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC_CONTRACT = (
    REPO_ROOT
    / "specs"
    / "007-ui-analysis-index-consumption"
    / "contracts"
    / "ui-analysis-bundle-v1.md"
)
SKILL_CONTRACT = (
    REPO_ROOT
    / ".agents"
    / "skills"
    / "generate-ui-analysis-index"
    / "references"
    / "bundle-contract.md"
)

CONTENT_FILES = [
    "manifest.yaml",
    "screens.jsonl",
    "elements.jsonl",
    "transitions.jsonl",
    "flows.jsonl",
    "diagnostics.jsonl",
]

_HEADER_RE = re.compile(r"^#{1,3}\s+(.*)$")
_FIELD_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|")


def _extract_field_sets(text: str) -> dict[str, set[str]]:
    """Map each recognized content-file name to the set of field names found
    in table rows under its section header (up to the next header)."""
    sections: dict[str, set[str]] = {}
    current_file: str | None = None
    for line in text.splitlines():
        header_match = _HEADER_RE.match(line)
        if header_match:
            header_text = header_match.group(1)
            current_file = next(
                (name for name in CONTENT_FILES if name in header_text), None
            )
            if current_file is not None:
                sections.setdefault(current_file, set())
            continue
        if current_file is not None:
            field_match = _FIELD_ROW_RE.match(line.strip())
            if field_match:
                sections[current_file].add(field_match.group(1))
    return sections


@pytest.fixture(scope="module")
def spec_fields() -> dict[str, set[str]]:
    if not SPEC_CONTRACT.is_file():
        pytest.skip(f"authoritative spec contract not found: {SPEC_CONTRACT}")
    return _extract_field_sets(SPEC_CONTRACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def skill_fields() -> dict[str, set[str]]:
    if not SKILL_CONTRACT.is_file():
        pytest.skip(f"skill not present yet: {SKILL_CONTRACT}")
    return _extract_field_sets(SKILL_CONTRACT.read_text(encoding="utf-8"))


def test_both_contract_docs_declare_all_six_content_files(spec_fields, skill_fields):
    for name in CONTENT_FILES:
        assert name in spec_fields, f"spec contract missing section for {name}"
        assert name in skill_fields, f"skill bundle-contract.md missing section for {name}"


def test_spec_and_skill_field_sets_extracted_are_non_empty(spec_fields, skill_fields):
    """Sanity: fail loudly if the scrape itself is broken (vacuous pass
    guard), rather than silently reporting empty-set 'agreement'."""
    for name in CONTENT_FILES:
        assert spec_fields[name], f"spec contract: no fields scraped for {name}"
        assert skill_fields[name], f"skill contract: no fields scraped for {name}"


@pytest.mark.parametrize("content_file", CONTENT_FILES)
def test_field_name_sets_match_between_spec_and_skill(content_file, spec_fields, skill_fields):
    spec_set = spec_fields[content_file]
    skill_set = skill_fields[content_file]
    only_in_spec = spec_set - skill_set
    only_in_skill = skill_set - spec_set
    assert not only_in_spec and not only_in_skill, (
        f"{content_file}: field sets diverged between "
        f"{SPEC_CONTRACT.name} and {SKILL_CONTRACT.name} — "
        f"only_in_spec={sorted(only_in_spec)} only_in_skill={sorted(only_in_skill)}"
    )


def test_scraper_actually_discriminates_on_an_injected_mismatch(tmp_path: Path):
    """Proves the comparison mechanism isn't a vacuous no-op by injecting a
    divergent field name into a synthetic pair of docs."""
    doc_a = "## `screens.jsonl` — record fields\n\n| `screen_id` | string | yes |\n"
    doc_b = "## `screens.jsonl` — record fields\n\n| `screen_identifier` | string | yes |\n"
    fields_a = _extract_field_sets(doc_a)
    fields_b = _extract_field_sets(doc_b)
    assert fields_a["screens.jsonl"] != fields_b["screens.jsonl"]
