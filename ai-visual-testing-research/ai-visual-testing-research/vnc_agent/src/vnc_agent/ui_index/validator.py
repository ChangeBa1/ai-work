"""Full bundle validation (contracts/ui-index-consumer-interfaces.md §3).

Six-step order, all issues collected (never stops early except a per-file
resource-limit hit, which only stops that one file's iteration):

1. `bundle_dir` existence/readability
2. manifest parse + schema MAJOR support
3. required `content_files` existence + path traversal
4. per file (screens -> elements -> transitions -> flows -> diagnostics),
   in line order: JSONL syntax -> field type -> duplicate id registration
5. cross-record referential integrity (parent cycles, guards/anchors/
   neighbors, coordinate space/range, confidence values)
6. `content_files.*.sha256` checksum comparison
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from vnc_agent.config import UiIndexConfig
from vnc_agent.ui_index.errors import UiIndexErrorCode, ValidationIssue, ValidationReport
from vnc_agent.ui_index.models import (
    Diagnostic,
    Element,
    ElementGuardRef,
    Flow,
    Screen,
    Transition,
)
from vnc_agent.ui_index.reader import iter_jsonl, read_manifest

# Fixed processing order (contracts §3 step 4).
_CONTENT_FILE_ORDER: tuple[str, ...] = (
    "screens.jsonl",
    "elements.jsonl",
    "transitions.jsonl",
    "flows.jsonl",
    "diagnostics.jsonl",
)


@dataclass
class BundleRecords:
    screens: dict[str, Screen] = field(default_factory=dict)
    elements: dict[str, Element] = field(default_factory=dict)
    transitions: dict[str, Transition] = field(default_factory=dict)
    flows: dict[str, Flow] = field(default_factory=dict)
    diagnostics: dict[str, Diagnostic] = field(default_factory=dict)


def _is_safe_relative_name(name: str) -> bool:
    if not name or name in {".", ".."}:
        return False
    if "/" in name or "\\" in name:
        return False
    if Path(name).is_absolute():
        return False
    return True


def _resolve_within(bundle_root: Path, name: str) -> Path | None:
    """Return the resolved path for `name` iff it stays inside `bundle_root`."""
    if not _is_safe_relative_name(name):
        return None
    candidate = (bundle_root / name).resolve()
    try:
        candidate.relative_to(bundle_root)
    except ValueError:
        return None
    return candidate


def _map_pydantic_error(
    err: dict[str, Any],
    *,
    file: str,
    line: int,
    is_diagnostic: bool,
) -> ValidationIssue:
    loc = err.get("loc", ())
    msg = str(err.get("msg", ""))
    field_path = ".".join(str(part) for part in loc) if loc else None

    if is_diagnostic and "must not be confirmed" in msg:
        return ValidationIssue(
            error_code=UiIndexErrorCode.INVALID_DIAGNOSTIC_CONFIDENCE,
            file=file,
            line=line,
            field_path=field_path,
            message=msg,
        )
    if loc and loc[0] == "confidence":
        return ValidationIssue(
            error_code=UiIndexErrorCode.INVALID_CONFIDENCE,
            file=file,
            line=line,
            field_path=field_path,
            message=msg,
        )
    if loc and loc[0] == "normalized_bounds":
        if len(loc) >= 2 and loc[1] == "coordinate_space":
            return ValidationIssue(
                error_code=UiIndexErrorCode.MISSING_COORDINATE_SPACE,
                file=file,
                line=line,
                field_path=field_path,
                message=msg,
            )
        return ValidationIssue(
            error_code=UiIndexErrorCode.COORDINATE_OUT_OF_RANGE,
            file=file,
            line=line,
            field_path=field_path,
            message=msg,
        )
    return ValidationIssue(
        error_code=UiIndexErrorCode.FIELD_TYPE_ERROR,
        file=file,
        line=line,
        field_path=field_path,
        message=msg,
    )


def _parse_record[ModelT: BaseModel](
    model_cls: type[ModelT],
    raw: dict[str, Any],
    *,
    file: str,
    line: int,
) -> tuple[ModelT | None, list[ValidationIssue]]:
    try:
        return model_cls.model_validate(raw), []
    except ValidationError as exc:
        is_diagnostic = model_cls is Diagnostic
        issues = [
            _map_pydantic_error(err, file=file, line=line, is_diagnostic=is_diagnostic)
            for err in exc.errors()
        ]
        return None, issues


def _find_cycle_members(parent_map: dict[str, str | None]) -> set[str]:
    """DFS colouring cycle detection; a self-reference is a cycle of size 1."""
    white, gray, black = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(parent_map, white)
    in_cycle: set[str] = set()

    def visit(node: str, path: list[str]) -> None:
        color[node] = gray
        path.append(node)
        parent = parent_map.get(node)
        if parent is not None and parent in parent_map:
            if color.get(parent) == gray:
                idx = path.index(parent)
                in_cycle.update(path[idx:])
            elif color.get(parent) == white:
                visit(parent, path)
        path.pop()
        color[node] = black

    for node in list(parent_map.keys()):
        if color[node] == white:
            visit(node, [])
    return in_cycle


def _check_parent_refs(
    items: dict[str, Any],
    *,
    parent_attr: str,
    file: str,
    issues: list[ValidationIssue],
) -> None:
    parent_map: dict[str, str | None] = {
        rid: getattr(rec, parent_attr) for rid, rec in items.items()
    }
    for rid, parent in parent_map.items():
        if parent is not None and parent not in items:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                    file=file,
                    line=None,
                    field_path=f"{rid}.{parent_attr}",
                    message=f"{parent_attr} references unknown id: {parent!r}",
                )
            )
    for rid in sorted(_find_cycle_members(parent_map)):
        issues.append(
            ValidationIssue(
                error_code=UiIndexErrorCode.PARENT_CYCLE,
                file=file,
                line=None,
                field_path=f"{rid}.{parent_attr}",
                message=f"{parent_attr} forms a parent cycle involving {rid!r}",
            )
        )


def _check_guard_refs(
    guards: list[Any],
    *,
    elements: dict[str, Element],
    file: str,
    owner_field_path: str,
    issues: list[ValidationIssue],
) -> None:
    for idx, guard in enumerate(guards):
        if isinstance(guard, ElementGuardRef) and guard.element_id not in elements:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.DANGLING_GUARD_REFERENCE,
                    file=file,
                    line=None,
                    field_path=f"{owner_field_path}[{idx}].element_id",
                    message=f"guard references unknown element_id: {guard.element_id!r}",
                )
            )


def _check_reference_integrity(records: BundleRecords, issues: list[ValidationIssue]) -> None:
    screens, elements = records.screens, records.elements

    _check_parent_refs(
        screens, parent_attr="parent_screen_id", file="screens.jsonl", issues=issues
    )
    _check_parent_refs(
        elements, parent_attr="parent_element_id", file="elements.jsonl", issues=issues
    )

    for eid, el in elements.items():
        if el.screen_id not in screens:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                    file="elements.jsonl",
                    field_path=f"{eid}.screen_id",
                    message=f"screen_id references unknown screen: {el.screen_id!r}",
                )
            )
        for anchor_idx, anchor_id in enumerate(el.anchors):
            if anchor_id not in elements:
                issues.append(
                    ValidationIssue(
                        error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                        file="elements.jsonl",
                        field_path=f"{eid}.anchors[{anchor_idx}]",
                        message=f"anchors references unknown element_id: {anchor_id!r}",
                    )
                )
        for neighbor_idx, neighbor in enumerate(el.neighbors):
            if neighbor.element_id not in elements:
                issues.append(
                    ValidationIssue(
                        error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                        file="elements.jsonl",
                        field_path=f"{eid}.neighbors[{neighbor_idx}].element_id",
                        message=f"neighbors references unknown element_id: {neighbor.element_id!r}",
                    )
                )

    for tid, tr in records.transitions.items():
        if tr.from_screen_id not in screens:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                    file="transitions.jsonl",
                    field_path=f"{tid}.from_screen_id",
                    message=f"from_screen_id references unknown screen: {tr.from_screen_id!r}",
                )
            )
        if tr.to_screen_id not in screens:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                    file="transitions.jsonl",
                    field_path=f"{tid}.to_screen_id",
                    message=f"to_screen_id references unknown screen: {tr.to_screen_id!r}",
                )
            )
        if tr.trigger_element_id not in elements:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                    file="transitions.jsonl",
                    field_path=f"{tid}.trigger_element_id",
                    message=(
                        f"trigger_element_id references unknown element: "
                        f"{tr.trigger_element_id!r}"
                    ),
                )
            )
        _check_guard_refs(
            tr.guards,
            elements=elements,
            file="transitions.jsonl",
            owner_field_path=f"{tid}.guards",
            issues=issues,
        )

    for fid, flow in records.flows.items():
        if flow.start_screen_id not in screens:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                    file="flows.jsonl",
                    field_path=f"{fid}.start_screen_id",
                    message=f"start_screen_id references unknown screen: {flow.start_screen_id!r}",
                )
            )
        if flow.completion_screen_id not in screens:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                    file="flows.jsonl",
                    field_path=f"{fid}.completion_screen_id",
                    message=(
                        f"completion_screen_id references unknown screen: "
                        f"{flow.completion_screen_id!r}"
                    ),
                )
            )
        for step_idx, step in enumerate(flow.steps):
            if step.transition_id is not None:
                if step.transition_id not in records.transitions:
                    issues.append(
                        ValidationIssue(
                            error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                            file="flows.jsonl",
                            field_path=f"{fid}.steps[{step_idx}].transition_id",
                            message=(
                                f"steps[{step_idx}].transition_id references unknown "
                                f"transition: {step.transition_id!r}"
                            ),
                        )
                    )
            elif step.element_id is not None and step.element_id not in elements:
                issues.append(
                    ValidationIssue(
                        error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                        file="flows.jsonl",
                        field_path=f"{fid}.steps[{step_idx}].element_id",
                        message=(
                            f"steps[{step_idx}].element_id references unknown element: "
                            f"{step.element_id!r}"
                        ),
                    )
                )
        _check_guard_refs(
            flow.preconditions,
            elements=elements,
            file="flows.jsonl",
            owner_field_path=f"{fid}.preconditions",
            issues=issues,
        )

    for did, diag in records.diagnostics.items():
        target = diag.target_ref
        if target is None:
            continue
        if target.screen_id is not None and target.screen_id not in screens:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                    file="diagnostics.jsonl",
                    field_path=f"{did}.target_ref.screen_id",
                    message=f"target_ref.screen_id references unknown screen: {target.screen_id!r}",
                )
            )
        if target.element_id is not None and target.element_id not in elements:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                    file="diagnostics.jsonl",
                    field_path=f"{did}.target_ref.element_id",
                    message=(
                        f"target_ref.element_id references unknown element: "
                        f"{target.element_id!r}"
                    ),
                )
            )
        if target.transition_id is not None and target.transition_id not in records.transitions:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.DANGLING_REFERENCE,
                    file="diagnostics.jsonl",
                    field_path=f"{did}.target_ref.transition_id",
                    message=(
                        f"target_ref.transition_id references unknown transition: "
                        f"{target.transition_id!r}"
                    ),
                )
            )


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


_MODEL_BY_FILE: dict[str, type[BaseModel]] = {
    "screens.jsonl": Screen,
    "elements.jsonl": Element,
    "transitions.jsonl": Transition,
    "flows.jsonl": Flow,
    "diagnostics.jsonl": Diagnostic,
}
_ID_FIELD_BY_FILE: dict[str, str] = {
    "screens.jsonl": "screen_id",
    "elements.jsonl": "element_id",
    "transitions.jsonl": "transition_id",
    "flows.jsonl": "flow_id",
    "diagnostics.jsonl": "diagnostic_id",
}


def validate_bundle_with_records(
    bundle_dir: Path,
    config: UiIndexConfig,
) -> tuple[ValidationReport, BundleRecords]:
    """`validate_bundle()` plus the parsed records — reused by `repository.py`
    so a valid bundle is parsed exactly once."""
    bundle_dir = Path(bundle_dir)
    issues: list[ValidationIssue] = []
    records = BundleRecords()

    # Steps 1-2: bundle_dir existence + manifest + schema MAJOR.
    manifest, manifest_issues = read_manifest(bundle_dir)
    issues.extend(manifest_issues)
    if manifest is None:
        return (
            ValidationReport(ok=False, bundle_dir=str(bundle_dir), issues=issues, manifest=None),
            records,
        )

    # Step 3: required content_files existence + path traversal.
    resolved_root = bundle_dir.resolve()
    safe_paths: dict[str, Path] = {}
    for name, entry in manifest.content_files.items():
        resolved = _resolve_within(resolved_root, name)
        if resolved is None:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.PATH_TRAVERSAL,
                    file=name,
                    message=f"content_files key escapes bundle_dir: {name!r}",
                )
            )
            continue
        safe_paths[name] = resolved
        if entry.required and not resolved.is_file():
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.CONTENT_FILE_MISSING,
                    file=name,
                    message=f"required content file is missing: {name}",
                )
            )

    # Step 4: fixed-order JSONL parsing + duplicate id registration.
    stores: dict[str, dict[str, BaseModel]] = {
        "screens.jsonl": records.screens,  # type: ignore[dict-item]
        "elements.jsonl": records.elements,  # type: ignore[dict-item]
        "transitions.jsonl": records.transitions,  # type: ignore[dict-item]
        "flows.jsonl": records.flows,  # type: ignore[dict-item]
        "diagnostics.jsonl": records.diagnostics,  # type: ignore[dict-item]
    }
    for file_name in _CONTENT_FILE_ORDER:
        path = safe_paths.get(file_name)
        if path is None or not path.is_file():
            continue
        model_cls = _MODEL_BY_FILE[file_name]
        id_field = _ID_FIELD_BY_FILE[file_name]
        store = stores[file_name]
        for line_no, item in iter_jsonl(
            path,
            max_bytes=config.max_content_file_bytes,
            max_records=config.max_content_file_records,
        ):
            if isinstance(item, ValidationIssue):
                issues.append(item)
                continue
            record, record_issues = _parse_record(
                model_cls, item, file=file_name, line=line_no
            )
            issues.extend(record_issues)
            if record is None:
                continue
            rid = getattr(record, id_field)
            if rid in store:
                issues.append(
                    ValidationIssue(
                        error_code=UiIndexErrorCode.DUPLICATE_ID,
                        file=file_name,
                        line=line_no,
                        field_path=id_field,
                        message=f"duplicate {id_field}: {rid!r}",
                    )
                )
                continue
            store[rid] = record

    # Step 5: cross-record referential integrity (only meaningful once ids
    # are fully registered from step 4).
    _check_reference_integrity(records, issues)

    # Step 6: checksum comparison — independent of prior content issues.
    for name, entry in manifest.content_files.items():
        if entry.sha256 is None:
            continue
        path = safe_paths.get(name)
        if path is None or not path.is_file():
            continue
        actual = _sha256_of_file(path)
        if actual != entry.sha256:
            issues.append(
                ValidationIssue(
                    error_code=UiIndexErrorCode.CHECKSUM_MISMATCH,
                    file=name,
                    message=f"sha256 mismatch for {name}: expected {entry.sha256}, got {actual}",
                )
            )

    report = ValidationReport(
        ok=len(issues) == 0,
        bundle_dir=str(bundle_dir),
        issues=issues,
        manifest=manifest,
    )
    return report, records


def validate_bundle(bundle_dir: Path, config: UiIndexConfig) -> ValidationReport:
    """FR-002: full two-pass validation, collecting every issue found."""
    report, _records = validate_bundle_with_records(bundle_dir, config)
    return report
