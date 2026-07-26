"""Feature 021 (evolution-hardcase-export, FR-002..FR-005): JSONL exporter.

Offline, read-only dataset export of hard-case steps (overall_design.md §12.4):
one JSON object per line — screenshot *path* (never the file itself), target
semantics, correct bbox, wrong candidates, verification outcome, traceability
ids and the matched hard-case criteria labels. Runs exclusively under the
``vnc-agent evolution export`` CLI subcommand; storage access goes through the
query-only :class:`~vnc_agent.storage.repositories.EvolutionExportRepository`.

Sensitive handling (FR-004): every row passes the existing sensitive-field
redaction convention (``logging_setup._redact_value`` key-substring semantics)
with the union of the config's ``security.sensitive_field_names`` and the
built-in ``DEFAULT_SENSITIVE`` set. Screenshots referenced by path are already
masked at capture time (feature 001 FR-049); their bytes are never copied,
re-read or re-encoded here — consumers resolve paths themselves.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vnc_agent.config import EvolutionConfig
from vnc_agent.evolution.hard_case_miner import (
    CRITERIA,
    StepEvidence,
    collect_failure_types,
    evaluate_step,
)
from vnc_agent.logging_setup import DEFAULT_SENSITIVE, _redact_value
from vnc_agent.storage.repositories import EvolutionExportRepository

SCHEMA_VERSION = "hard-case-v1"


class UnknownCriterionError(ValueError):
    """A --criteria value outside the closed CRITERIA vocabulary."""

    def __init__(self, unknown: Iterable[str]) -> None:
        self.unknown = sorted(unknown)
        super().__init__(
            f"unknown criteria: {self.unknown}; valid criteria: {sorted(CRITERIA)}"
        )


@dataclass
class ExportSummary:
    """Stdout contract of the export command (spec FR-005)."""

    output: str
    total_runs_scanned: int = 0
    total_steps_scanned: int = 0
    exported_samples: int = 0
    criteria_counts: dict[str, int] = field(
        default_factory=lambda: {label: 0 for label in CRITERIA}
    )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "total_runs_scanned": self.total_runs_scanned,
            "total_steps_scanned": self.total_steps_scanned,
            "exported_samples": self.exported_samples,
            "criteria_counts": dict(self.criteria_counts),
        }


def validate_criteria_filter(criteria: Iterable[str] | None) -> set[str] | None:
    """Normalize the CLI --criteria values; None/empty means "all"."""
    values = [c for c in (criteria or []) if c]
    if not values:
        return None
    unknown = set(values) - set(CRITERIA)
    if unknown:
        raise UnknownCriterionError(unknown)
    return set(values)


def _to_utc(dt: datetime) -> datetime:
    """Naive datetimes from SQLite are runtime-written UTC (spec Clarif. 9)."""
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def run_started_within(started_at: datetime | None, since: datetime | None) -> bool:
    """--since filter: unknown start time is excluded only under a filter."""
    if since is None:
        return True
    if started_at is None:
        return False
    return _to_utc(started_at) >= _to_utc(since)


def build_frame_path_map(run_payload: dict[str, Any]) -> dict[str, str]:
    """frame_id -> safe_evidence screenshot path from the run's frames[]."""
    out: dict[str, str] = {}
    for frame in run_payload.get("frames") or []:
        frame_id = (frame or {}).get("id")
        safe = (frame or {}).get("safe_image") or {}
        path = safe.get("path")
        if frame_id and path:
            out[str(frame_id)] = str(path)
    return out


def relativize_screenshot_path(path: str | None, artifacts_root: str | None) -> str | None:
    """Express a stored screenshot path relative to the artifacts root when
    possible (POSIX separators). Paths outside the root pass through as-is
    (POSIX-normalized); the file is never touched (path reference only)."""
    if not path:
        return None
    if artifacts_root:
        try:
            rel = Path(path).relative_to(Path(artifacts_root))
            return rel.as_posix()
        except ValueError:
            pass
    return PurePath(path).as_posix()


def _region_to_bbox(region: dict[str, Any] | None) -> list[int] | None:
    if not region:
        return None
    try:
        return [int(region["x1"]), int(region["y1"]), int(region["x2"]), int(region["y2"])]
    except (KeyError, TypeError, ValueError):
        return None


def _candidate_bboxes(iteration: dict[str, Any]) -> list[dict[str, Any]]:
    grounding = iteration.get("grounding_result") or {}
    out: list[dict[str, Any]] = []
    for cand in grounding.get("candidates") or []:
        cand = cand or {}
        bbox = cand.get("bbox")
        out.append(
            {
                "bbox": list(bbox) if bbox is not None else None,
                "confidence": cand.get("confidence"),
            }
        )
    return out


def _verification_status(iteration: dict[str, Any]) -> str | None:
    return (iteration.get("verification_result") or {}).get("status")


def _correct_bbox(iterations: list[dict[str, Any]]) -> list[int] | None:
    """From the last passed iteration: execution target_region, else its top
    grounding candidate bbox (FR-003)."""
    for it in reversed(iterations):
        if _verification_status(it) != "passed":
            continue
        execution = it.get("execution_result") or {}
        bbox = _region_to_bbox(execution.get("target_region"))
        if bbox is not None:
            return bbox
        candidates = _candidate_bboxes(it)
        if candidates and candidates[0].get("bbox"):
            return [int(v) for v in candidates[0]["bbox"]]
    return None


def _wrong_candidates(iterations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Failed iterations contribute their executed click point and every
    grounding candidate they saw (FR-003)."""
    out: list[dict[str, Any]] = []
    for it in iterations:
        if _verification_status(it) != "failed":
            continue
        execution = it.get("execution_result") or {}
        click_point = execution.get("actual_click_point")
        out.append(
            {
                "iteration_index": it.get("iteration_index"),
                "click_point": list(click_point) if click_point is not None else None,
                "candidates": _candidate_bboxes(it),
            }
        )
    return out


def _first_non_null(iterations: list[dict[str, Any]], *path: str) -> Any:
    for it in iterations:
        value: Any = it
        for key in path:
            value = (value or {}).get(key)
            if value is None:
                break
        if value is not None:
            return value
    return None


def build_sample(
    evidence: StepEvidence,
    *,
    test_case_id: str,
    criteria: list[str],
    frame_paths: dict[str, str],
    artifacts_root: str | None,
) -> dict[str, Any]:
    """One hard-case-v1 JSONL row (spec FR-003) — before redaction."""
    iterations = evidence.iterations
    frame_id = _first_non_null(iterations, "before_frame_id") or _first_non_null(
        iterations, "after_frame_id"
    )
    screenshot = relativize_screenshot_path(
        frame_paths.get(str(frame_id)) if frame_id else None, artifacts_root
    )
    target = _first_non_null(iterations, "semantic_action", "target")
    intent = _first_non_null(iterations, "semantic_action", "intent")
    memory_hit = _first_non_null(iterations, "memory_hit")
    last_verification = (
        (iterations[-1].get("verification_result") or {}) if iterations else {}
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": evidence.run_id,
        "test_case_id": test_case_id,
        "step_id": evidence.step_id,
        "criteria": list(criteria),
        "screenshot_path": screenshot,
        "target": target,
        "intent": intent,
        "correct_bbox": _correct_bbox(iterations),
        "wrong_candidates": _wrong_candidates(iterations),
        "page_memory_id": (memory_hit or {}).get("page_memory_id"),
        "verification": {
            "status": last_verification.get("status"),
            "reason": last_verification.get("reason"),
        },
        "final_status": evidence.final_status,
        "iteration_count": len(iterations),
        "failure_types": collect_failure_types(evidence),
    }


def redact_sample(sample: dict[str, Any], sensitive_fields: Iterable[str]) -> dict[str, Any]:
    """FR-004: recursive key-substring redaction, same convention as logging."""
    sensitive = frozenset(
        s.lower() for s in set(sensitive_fields) | set(DEFAULT_SENSITIVE)
    )
    return {k: _redact_value(k, v, sensitive) for k, v in sample.items()}


async def collect_step_evidence(
    repo: EvolutionExportRepository, run: dict[str, Any]
) -> list[StepEvidence]:
    """Group one run's persisted rows into per-step evidence bundles."""
    run_id = run["run_id"]
    step_rows = await repo.list_step_rows(run_id)
    iteration_rows = await repo.list_iteration_rows(run_id)
    recovery_rows = await repo.list_recovery_rows(run_id)
    experience_rows = await repo.list_experience_rows(run_id)

    by_step: dict[str, StepEvidence] = {}

    def _get(step_id: str) -> StepEvidence:
        if step_id not in by_step:
            by_step[step_id] = StepEvidence(run_id=run_id, step_id=step_id)
        return by_step[step_id]

    for row in step_rows:
        ev = _get(row["step_id"])
        ev.final_status = row["final_status"]
        ev.failure_reason = row["failure_reason"]

    for row in iteration_rows:
        payload = dict(row["payload"])
        payload.setdefault("iteration_index", row["iteration_index"])
        ev = _get(row["step_id"])
        ev.iterations.append(payload)
        # Union of embedded copies and dedicated rows (existence semantics).
        ev.recovery_attempts.extend(payload.get("recovery_attempts") or [])

    for row in recovery_rows:
        _get(row["step_id"]).recovery_attempts.append(row["payload"])

    for row in experience_rows:
        ft = (row["payload"] or {}).get("failure_type")
        if ft:
            _get(row["step_id"]).experience_failure_types.append(str(ft))

    for ev in by_step.values():
        ev.iterations.sort(key=lambda it: it.get("iteration_index") or 0)
    return [by_step[k] for k in sorted(by_step)]


async def export_hard_cases(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    out_path: str | Path,
    evolution_cfg: EvolutionConfig,
    sensitive_fields: Iterable[str] = (),
    artifacts_root: str | None = None,
    since: datetime | None = None,
    criteria_filter: Iterable[str] | None = None,
) -> ExportSummary:
    """Scan the store read-only, mine hard cases, write JSONL (FR-002)."""
    wanted = validate_criteria_filter(criteria_filter)
    repo = EvolutionExportRepository(session_factory)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = ExportSummary(output=str(out))

    runs = [r for r in await repo.list_runs() if run_started_within(r["started_at"], since)]
    summary.total_runs_scanned = len(runs)

    with out.open("w", encoding="utf-8", newline="\n") as fh:
        for run in runs:
            frame_paths = build_frame_path_map(run["payload"])
            for evidence in await collect_step_evidence(repo, run):
                summary.total_steps_scanned += 1
                labels = evaluate_step(evidence, evolution_cfg)
                if not labels:
                    continue
                if wanted is not None and not (set(labels) & wanted):
                    continue
                sample = build_sample(
                    evidence,
                    test_case_id=run["test_case_id"],
                    criteria=labels,
                    frame_paths=frame_paths,
                    artifacts_root=artifacts_root,
                )
                sample = redact_sample(sample, sensitive_fields)
                fh.write(json.dumps(sample, ensure_ascii=False) + "\n")
                summary.exported_samples += 1
                for label in labels:
                    summary.criteria_counts[label] += 1
    return summary
