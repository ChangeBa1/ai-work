# Implementation Plan: Evolution Hard-Case Mining & Dataset Export

**Branch**: `021-evolution-hardcase-export` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/021-evolution-hardcase-export/spec.md`

## Summary

Offline, read-only mining of "the model struggled here" steps from the SQLite run
store, exported as a JSONL training dataset (design §12.3/§12.4). Two new
`evolution/` modules (pure-predicate miner + exporter), one query-only repository
class, one additive `evolution:` config section, and one new
`vnc-agent evolution export` CLI subcommand. Nothing on the runtime path changes;
`experience_collector.py` stays byte-identical (write-only guard test untouched).

## Technical Context

**Language/Version**: Python 3.12 (uv-managed project in `vnc_agent/`)

**Primary Dependencies**: SQLAlchemy 2 async + aiosqlite (existing), typer CLI (existing), pydantic (config); no new dependencies

**Storage**: existing SQLite schema, read-only (SELECT-only repository); JSONL output file

**Testing**: pytest + pytest-asyncio (asyncio_mode=auto); typer CliRunner for CLI; temp SQLite via `tmp_path`

**Target Platform**: same as project (Windows/Linux CLI, offline)

**Performance Goals**: none binding — offline batch tool; single pass over rows per run

**Constraints**: zero runtime impact (FR-007); storage write path untouched; additive config only

**Scale/Scope**: 2 new modules + 1 repository class + config section + CLI subcommand + 3 test files + specs

## Constitution Check

*GATE: passed.*

- Principle I (deterministic runtime control): untouched — no runtime code changes; the exporter is deterministic over stored rows.
- Principle II (Planner/Grounder separation): untouched.
- Principle VI (Domain-Agnostic Core): criteria are generic signals (confidence, retries, recovery strategies, verification status, FailureType enum values) — no business vocabulary; thresholds/failure-type sets are config-declared.
- FR-044 lineage (experience collector write-only): preserved — mining reads what the collector and the run repository already wrote; no training, no assertion mutation, no replay rewrite. The exporter itself is also read-only w.r.t. the store.
- Security (FR-047/FR-049 lineage): rows pass the existing sensitive-field redaction convention; screenshots are referenced by (already masked) path, never copied or re-encoded.

**Domain-Agnostic Core gate (Principle VI)**:

- [x] No business-specific fields/states/branches.
- [x] No scenario semantics introduced (labels name generic model/interaction failure modes).
- [x] Generic capability validated with constructed row payloads, not business fixtures.

## Phase 0 — Research (inline; schema audit)

- **Persisted evidence audit**: recorded in spec Clarification 1 (tables & fields) and the criteria table (which §12.3 criteria are implementable, which lack data and why). Key findings: `candidate_index` is never persisted as a plain field (only folded into ModelCallAudit identity hashes) ⇒ Top-2 promotion uses the persisted `second_candidate` recovery strategy; `visual_experiences.failure_type` is `None` in practice (runtime calls `collect()` without the argument) ⇒ FailureType criterion sources from `recovery_attempts` payloads, reading the experience field only opportunistically; `WRONG_TARGET` does not exist in `FailureType`.
- **Screenshot path resolution**: `TestRunRow.payload["frames"][*]` carries `id` + `safe_image.path` (bundle publish path rooted at the artifacts root). Export maps `before_frame_id` → path, relativized to the artifacts root when possible (POSIX form), else passed through; unresolvable ⇒ null.
- **Redaction convention**: reuse `logging_setup._redact_value` + `DEFAULT_SENSITIVE` (includes `text_value`) unioned with `security.sensitive_field_names` — same substring semantics as runtime logging.
- **Recovery-attempt duplication**: attempts exist both embedded in `action_iterations.payload.recovery_attempts` and as `recovery_attempts` rows. Predicates are existence checks, so the miner consumes the union (duplicates harmless, robust to either source being pruned).
- **CLI precedent**: feature 016's `replay` sub-Typer (`api/cli.py`) is the pattern — sub-app + async helper + JSON to stdout + tests via `CliRunner` with a minimal yaml config dir.

## Phase 1 — Design

### Changes by file

1. `src/vnc_agent/config.py`
   - New `EvolutionConfig` (`hard_case_grounding_confidence_below=0.7`, `hard_case_high_confidence_at_least=0.9`, `hard_case_failure_types=["unexpected_dialog","target_not_found"]`), wired as `AgentConfig.evolution` with `default_factory` (additive).
2. `config/agent.yaml`
   - New commented `evolution:` section shipping the same defaults.
3. `src/vnc_agent/storage/repositories.py`
   - New `EvolutionExportRepository` (query-only): `list_runs(since)` → (run_id, test_case_id, started_at, payload); `list_step_rows(run_id)`; `list_iteration_rows(run_id)`; `list_recovery_rows(run_id)`; `list_experience_rows(run_id)`. SELECT-only; no writes anywhere.
4. `src/vnc_agent/evolution/hard_case_miner.py` (new)
   - `CRITERIA` closed label set; one pure predicate per criterion over plain payload dicts; `evaluate_step(evidence, cfg) -> list[str]`; `StepEvidence` dataclass.
5. `src/vnc_agent/evolution/dataset_exporter.py` (new)
   - `export_hard_cases(session_factory, *, out_path, evolution_cfg, sensitive_fields, artifacts_root, since, criteria_filter) -> ExportSummary`; row builder (`build_sample`) + frame-path map + redaction pass; JSONL writer; `ExportSummary` dataclass with `to_json_dict()`.
6. `src/vnc_agent/api/cli.py`
   - New `evolution` sub-Typer + `export` command (FR-005 options, summary JSON on stdout, exit 0/2). Imports of the new modules stay inside the command path.
7. Tests (new files)
   - `tests/unit/test_hard_case_miner.py` — hit/miss per criterion incl. threshold boundaries and missing-sub-object robustness.
   - `tests/unit/test_dataset_exporter.py` — row schema keys, correct/wrong bbox extraction, screenshot relativization + null fallback, redaction, config defaults pin (EvolutionConfig + shipped yaml).
   - `tests/integration/test_evolution_export_cli.py` — seeded temp SQLite end-to-end via CliRunner: labels/counts, `--since`, `--criteria` filter, unknown criterion exit 2, empty DB, store row counts unchanged (read-only proof).

### Row schema (hard-case-v1)

```json
{"schema_version":"hard-case-v1","run_id":"...","test_case_id":"...","step_id":"s1",
 "criteria":["low_grounding_confidence","mouse_verification_failed","retry_then_success"],
 "screenshot_path":"runs/<run>/bundles/<bundle>/safe_evidence.png",
 "target":{"role":null,"text":"会計","description":"checkout button","nearby_texts":["小計"]},
 "intent":"click checkout","correct_bbox":[150,85,170,95],
 "wrong_candidates":[{"iteration_index":0,"click_point":[100,50],
   "candidates":[{"bbox":[90,40,110,60],"confidence":0.4}]}],
 "page_memory_id":null,"verification":{"status":"passed","reason":"ok"},
 "final_status":"passed","iteration_count":2,
 "failure_types":["verification_failed"]}
```

### Non-changes (explicit)

- `evolution/experience_collector.py`, `runtime/`, `perception/`, `verification/`, `planning/`, `execution/`, `recovery/`, `memory/`, `replay/`: untouched.
- `storage/database.py` (schema) and every existing repository method: untouched.
- All existing tests: untouched.

## Project Structure

### Documentation (this feature)

```text
specs/021-evolution-hardcase-export/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
vnc_agent/
├── config/agent.yaml                                  # + evolution: section
├── src/vnc_agent/config.py                            # + EvolutionConfig
├── src/vnc_agent/storage/repositories.py              # + EvolutionExportRepository (read-only)
├── src/vnc_agent/evolution/hard_case_miner.py         # new
├── src/vnc_agent/evolution/dataset_exporter.py        # new
├── src/vnc_agent/api/cli.py                           # + evolution export subcommand
└── tests/
    ├── unit/test_hard_case_miner.py                   # new
    ├── unit/test_dataset_exporter.py                  # new
    └── integration/test_evolution_export_cli.py       # new
```

**Structure Decision**: single-project layout as-is; mining/export live in the
existing `evolution/` package next to the write-only collector they complement.

## Complexity Tracking

No constitution violations; table not needed.
