"""Bundle readers — pure I/O, no cross-record validation (contracts §1-2).

`read_manifest()` only parses `manifest.yaml` (never touches content files).
`iter_jsonl()` is a pure generator that never loads a whole file into memory.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from vnc_agent.ui_index.errors import UiIndexErrorCode, ValidationIssue
from vnc_agent.ui_index.models import BundleManifest

# schema_version MAJOR values this consumer accepts (contracts/ui-analysis-bundle-v1.md §0).
SUPPORTED_SCHEMA_MAJORS: frozenset[int] = frozenset({1})


def _schema_major(schema_version: str) -> int | None:
    head = schema_version.split(".", 1)[0]
    try:
        return int(head)
    except ValueError:
        return None


def read_manifest(bundle_dir: Path) -> tuple[BundleManifest | None, list[ValidationIssue]]:
    """Parse `manifest.yaml` only — MUST NOT touch any content file.

    Returns `(None, [BUNDLE_DIR_NOT_FOUND])` when `bundle_dir` does not exist
    or is not a readable directory; `(None, [MANIFEST_MISSING])` when
    `manifest.yaml` itself is absent. `schema_version` MAJOR support is
    checked here, but an unsupported MAJOR still returns the parsed
    `BundleManifest` (for error-report identity) alongside a non-empty
    `issues` list.
    """
    bundle_dir = Path(bundle_dir)

    if not bundle_dir.is_dir():
        return (
            None,
            [
                ValidationIssue(
                    error_code=UiIndexErrorCode.BUNDLE_DIR_NOT_FOUND,
                    file=None,
                    line=None,
                    field_path=None,
                    message=f"bundle_dir does not exist or is not a directory: {bundle_dir}",
                )
            ],
        )

    manifest_path = bundle_dir / "manifest.yaml"
    if not manifest_path.is_file():
        return (
            None,
            [
                ValidationIssue(
                    error_code=UiIndexErrorCode.MANIFEST_MISSING,
                    file="manifest.yaml",
                    line=None,
                    field_path=None,
                    message="manifest.yaml is missing from bundle_dir",
                )
            ],
        )

    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        return (
            None,
            [
                ValidationIssue(
                    error_code=UiIndexErrorCode.FIELD_TYPE_ERROR,
                    file="manifest.yaml",
                    line=None,
                    field_path=None,
                    message=f"manifest.yaml is not valid YAML: {exc}",
                )
            ],
        )

    if not isinstance(raw, dict):
        return (
            None,
            [
                ValidationIssue(
                    error_code=UiIndexErrorCode.FIELD_TYPE_ERROR,
                    file="manifest.yaml",
                    line=None,
                    field_path=None,
                    message="manifest.yaml top level must be a mapping",
                )
            ],
        )

    try:
        manifest = BundleManifest.model_validate(raw)
    except ValidationError as exc:
        issues = [
            ValidationIssue(
                error_code=UiIndexErrorCode.FIELD_TYPE_ERROR,
                file="manifest.yaml",
                line=None,
                field_path=".".join(str(p) for p in err.get("loc", ())) or None,
                message=err.get("msg", str(exc)),
            )
            for err in exc.errors()
        ]
        return None, issues

    issues: list[ValidationIssue] = []
    major = _schema_major(manifest.schema_version)
    if major is None or major not in SUPPORTED_SCHEMA_MAJORS:
        issues.append(
            ValidationIssue(
                error_code=UiIndexErrorCode.SCHEMA_UNSUPPORTED_MAJOR,
                file="manifest.yaml",
                line=None,
                field_path="schema_version",
                message=(
                    f"unsupported schema_version MAJOR in {manifest.schema_version!r}; "
                    f"supported MAJOR set = {sorted(SUPPORTED_SCHEMA_MAJORS)}"
                ),
            )
        )
    return manifest, issues


def iter_jsonl(
    path: Path,
    *,
    max_bytes: int,
    max_records: int,
) -> Iterator[tuple[int, dict[str, Any] | ValidationIssue]]:
    """Stream one JSON object per line; never loads the whole file at once.

    Yields `(line_no, dict)` for a successfully parsed JSON object line, or
    `(line_no, ValidationIssue)` (JSONL_SYNTAX_ERROR) for a line that is not
    valid JSON or not a JSON object. Once cumulative bytes/lines exceed
    `max_bytes`/`max_records`, yields one RESOURCE_LIMIT_EXCEEDED issue and
    stops iterating immediately (nothing past the limit is read).
    """
    file_name = Path(path).name
    total_bytes = 0
    line_no = 0

    with Path(path).open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line_no += 1
            total_bytes += len(raw_line.encode("utf-8"))

            if total_bytes > max_bytes or line_no > max_records:
                yield (
                    line_no,
                    ValidationIssue(
                        error_code=UiIndexErrorCode.RESOURCE_LIMIT_EXCEEDED,
                        file=file_name,
                        line=line_no,
                        field_path=None,
                        message=(
                            f"{file_name} exceeded resource limits "
                            f"(max_bytes={max_bytes}, max_records={max_records})"
                        ),
                    ),
                )
                return

            stripped = raw_line.strip()
            if not stripped:
                continue

            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError as exc:
                yield (
                    line_no,
                    ValidationIssue(
                        error_code=UiIndexErrorCode.JSONL_SYNTAX_ERROR,
                        file=file_name,
                        line=line_no,
                        field_path=None,
                        message=f"invalid JSON: {exc}",
                    ),
                )
                continue

            if not isinstance(parsed, dict):
                yield (
                    line_no,
                    ValidationIssue(
                        error_code=UiIndexErrorCode.JSONL_SYNTAX_ERROR,
                        file=file_name,
                        line=line_no,
                        field_path=None,
                        message="each JSONL line must be a JSON object",
                    ),
                )
                continue

            yield (line_no, parsed)
