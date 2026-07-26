# Tasks: Wait/Stability Default Tuning

**Input**: Design documents from `/specs/020-wait-tuning/`

**Prerequisites**: plan.md, spec.md

**Organization**: grouped by user story; US1 (tuned defaults + 2-sample path) is the MVP, US2 (floor guarantee) completes it. All paths relative to `vnc_agent/`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

*(none — existing project, no new dependencies)*

## Phase 2: Foundational — audits

- [X] T001 Pass-through audit (FR-005): confirm `api/cli.py` hands all five `cfg.agent.wait.*` values to `StabilityEngine` with no hard-coded overrides; fix wiring only if a gap exists (result: no gap — no code change)
- [X] T002 Affected-test sweep (spec Clarifications): grep wait params across `tests/`; list every construction site and confirm each passes explicit values (result: zero existing assertions depend on defaults)

## Phase 3: User Story 1 — Tuned defaults, 2-sample stable path (P1) 🎯 MVP

- [X] T003 [US1] `config/agent.yaml`: `wait.min_delay_ms 300→200`, `wait.capture_interval_ms 500→300`, `wait.stable_frame_count 3→2` (+ rationale/rollback comment); `max_delay_ms`/`pixel_diff_threshold` untouched (FR-001)
- [X] T004 [P] [US1] `src/vnc_agent/config.py::WaitConfig`: defaults mirrored to 200/300/2 (FR-002)
- [X] T005 [US1] New test file `tests/fixtures/test_wait_tuning.py`: pin `WaitConfig()` defaults and shipped `config/agent.yaml` wait values to FR-001 numbers (SC-003)
- [X] T006 [US1] Same file: 2-sample stable path — engine with default `stable_frame_count` over identical frames returns `end_reason="stable"` at exactly 2 logical samples / 1 unchanged comparison (FR-003, SC-002)

## Phase 4: User Story 2 — Floor guarantee (P2)

- [X] T007 [US2] Same file: `StabilityEngine(..., stable_frame_count=1)` clamps to effective 2 (FR-004)

## Phase 5: Polish & regression

- [X] T008 Full offline regression: `uv run pytest tests/unit tests/fixtures tests/e2e tests/integration -q` all green (1 pre-existing skip allowed) with zero modifications to existing tests (SC-004)

## Dependencies

- T001/T002 → T003/T004 (audits gate the "values-only" scope)
- T003/T004 → T005/T006/T007
- everything → T008
