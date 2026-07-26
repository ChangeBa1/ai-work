# Tasks: Evolution Hard-Case Mining & Dataset Export

**Input**: Design documents from `/specs/021-evolution-hardcase-export/`

**Prerequisites**: plan.md, spec.md

**Organization**: grouped by user story; US1 (mine + export + CLI) is the MVP, US2 adds filters, US3 pins config tunability. All paths relative to `vnc_agent/`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

*(none — existing project, no new dependencies)*

## Phase 2: Foundational — schema audit & config

- [X] T001 Schema audit (spec Clarification 1 + criteria table): confirm which §12.3 criteria the persisted rows support; record unimplementable ones with missing-data reasons (result recorded in spec.md — no code)
- [X] T002 `src/vnc_agent/config.py`: add `EvolutionConfig` (thresholds + failure-type set, spec FR-008) wired as additive `AgentConfig.evolution`
- [X] T003 [P] `config/agent.yaml`: ship the commented `evolution:` section with defaults in lockstep with T002

## Phase 3: User Story 1 — Mine & export hard cases via CLI (P1) 🎯 MVP

- [X] T004 [US1] `src/vnc_agent/storage/repositories.py`: add query-only `EvolutionExportRepository` (list runs/steps/iterations/recovery/experiences; SELECT-only, FR-006)
- [X] T005 [US1] `src/vnc_agent/evolution/hard_case_miner.py`: `StepEvidence` + 8 pure criterion predicates + `evaluate_step` aggregator (FR-001, criteria table)
- [X] T006 [US1] `src/vnc_agent/evolution/dataset_exporter.py`: per-(run,step) grouping, sample builder (hard-case-v1 row schema, FR-003), frame→path map with root-relativization, recursive sensitive redaction (FR-004), JSONL writer + `ExportSummary` (FR-002/FR-005 data)
- [X] T007 [US1] `src/vnc_agent/api/cli.py`: `evolution` sub-Typer + `export` command (`--out/--db/--config/--artifacts-root/--since/--criteria`), summary JSON to stdout, exits 0/2 (FR-005, FR-007 lazy imports)
- [X] T008 [P] [US1] `tests/unit/test_hard_case_miner.py`: hit/miss per criterion, threshold boundaries (0.7 strict-below / 0.9 inclusive), missing sub-objects never crash or false-positive
- [X] T009 [P] [US1] `tests/unit/test_dataset_exporter.py`: row schema keys, correct_bbox/wrong_candidates extraction, screenshot relative path + null fallback, redaction of sensitive keys, empty-evidence behavior
- [X] T010 [US1] `tests/integration/test_evolution_export_cli.py`: seed temp SQLite (low-confidence retry step + clean step), end-to-end CLI export → row count, labels, summary consistency, empty-DB run, store row counts unchanged (SC-002/SC-004)

## Phase 4: User Story 2 — Date & criteria filters (P2)

- [X] T011 [US2] `--since` filtering (UTC normalization, NULL started_at excluded under filter) + `--criteria` subset filtering + unknown-criterion exit 2 in exporter/CLI (already scaffolded in T006/T007; complete + cover)
- [X] T012 [P] [US2] Integration tests for `--since`, `--criteria`, unknown criterion (extend `tests/integration/test_evolution_export_cli.py`)

## Phase 5: User Story 3 — Config tunability (P3)

- [X] T013 [US3] Tests pinning `EvolutionConfig` defaults + shipped `agent.yaml` `evolution:` values + threshold override changing miner verdicts (in `tests/unit/test_dataset_exporter.py` or dedicated block in T008 file)

## Phase 6: Polish & regression

- [X] T014 Guard intact: `tests/unit/test_experience_collector_write_only.py` passes with `experience_collector.py` byte-identical (FR-007)
- [X] T015 Full offline regression: `uv run pytest tests/unit tests/fixtures tests/e2e tests/integration -q` all green (1 pre-existing skip allowed) (SC-003)

## Dependencies

- T001 → everything (audit fixes the criteria vocabulary)
- T002/T003 → T005/T006
- T004 → T006 → T007
- T005 → T006, T008
- T006/T007 → T009/T010/T011 → T012/T013
- everything → T014/T015
