# Tasks: Skip Re-Plan on Duplicate Frame with Blocked Action

**Input**: Design documents from `specs/009-skip-replan-duplicate-frame/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/planner-skip-contract.md, quickstart.md

**Tests**: Included — the feature is a runtime-behavior change to the Agent Runtime; the Constitution's test-coverage gate requires offline unit + e2e coverage, and the spec's SC-003/SC-004 are only checkable by tests.

**Organization**: Foundational model/report fields first (shared by all stories), then user stories in priority order.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 (skip), US2 (budget safety), US3 (observability), US4 (exceptions)
- All paths relative to `vnc_agent/`

## Path Conventions

Single-project layout: `src/vnc_agent/`, tests in `tests/unit`, `tests/e2e`.

## Phase 1: Setup

- [x] T001 Environment ready: `cd vnc_agent && uv sync`; baseline green run of `uv run pytest tests/unit tests/fixtures -q` and `uv run pytest tests/e2e -q` recorded before any change.

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T002 Add additive fields `planner_skipped_reason: str | None = None` and `before_content_hash: str | None = None` to `ActionIteration` in `src/vnc_agent/domain/run.py` (data-model.md §1).
- [x] T003 [P] Serialize `planner_skipped_reason` into the JSON report iteration object in `src/vnc_agent/reporting/json_report.py` (additive key, null default; contract §3).

## Phase 3: User Story 1 - Skip planner on duplicate frame + blocked action (P1) 🎯 MVP

### Tests for User Story 1 (write first, confirm they FAIL)

- [x] T004 [P] [US1] Unit tests `tests/unit/test_planner_skip_decision.py` for the skip predicate: each trigger reason in the set; excluded reasons (`blocked_uncertain`, `dangerous_drift`, any allowed reason); null current/previous hash; hash mismatch; no previous iteration (contract §1).
- [x] T005 [P] [US1] E2E `tests/e2e/test_scenario_11_skip_replan_duplicate_frame.py::test_skip_replan_on_frozen_screen`: frozen screen after one executed non-idempotent click (scenario-10-style fixtures), `max_retries=3`; assert `StubPlanner.plan_calls == 2` (it0 plan + it1 blocked plan), iterations ≥ 4, skipped iterations have no `semantic_action`/`execution_result`.

### Implementation for User Story 1

- [x] T006 [US1] In `src/vnc_agent/runtime/agent_runtime.py`: record `iteration.before_content_hash` from the observation on every iteration; add stateless `_planner_skip_reason(step, screen, previous_iteration)` predicate implementing contract §1 (trigger set, hash equality, wait-type/timeout exceptions; batch-repeat handled at call site).
- [x] T007 [US1] Refactor the existing RepeatGuard-block verdict branch body into helper `_blocked_iteration_verdict(...)` (carried ActionEffect → `resolve_step_result(escalate=True)` → recovery for `ambiguous_fail_safe`/`dangerous_drift`) and call it from the block branch — behavior byte-for-byte identical (research.md R4).
- [x] T008 [US1] Wire the skip: before PLANNING (non-batch path only), when `_planner_skip_reason` fires — set `planner_skipped_reason`, carry forward previous blocking `RepeatGuardDecision` (copy), and return via `_blocked_iteration_verdict` (contract §2, §4).

## Phase 4: User Story 2 - Budget-safe termination (P1)

- [x] T009 [P] [US2] E2E test `test_skip_iterations_consume_budget_and_step_fails`: same frozen scenario; assert total iterations == `max_retries + 1`, step `final_status == "failed"`, run failed with pre-existing budget semantics, and chained skips (every post-block iteration skipped — carried decision works) (FR-004/FR-005).
- [x] T010 [US2] Verify no new loop path: code review assertion that the skip branch returns through the normal iteration return (outer loop `start_iteration` accounting untouched) — no runtime change expected beyond T008.

## Phase 5: User Story 3 - Observability (P2)

### Tests (write first)

- [x] T011 [P] [US3] E2E test `test_skip_telemetry_and_report`: assert per skipped iteration — `planner_skipped_reason == "duplicate_frame_blocked_action"` on record and in JSON report; exactly one `model_call_skipped` CounterEvent (role planner, reason set, request_identity present); one `ModelCallAudit` outcome="skipped"; `performance_summary.model_calls["planner"] == StubPlanner.plan_calls`; `skipped_model_call_count == number of skipped iterations`; no planner StageMeasurement for skipped rounds (contract §3).

### Implementation

- [x] T012 [US3] In `agent_runtime.py` skip branch: emit `model_call_skipped` CounterEvent + skipped-outcome `ModelCallAudit` (planner_identity when computable, content-hash fallback; `source_ref` = previous frame id), mirrored to structured logs via `log_event` (research.md R7).

## Phase 6: User Story 4 - Time-dependent exception protection (P2)

- [x] T013 [P] [US4] Unit tests in `test_planner_skip_decision.py`: wait-type previous action (`action_type=="wait"`, `micro_action_purpose=="wait"`) → no skip; `timeout_seconds` on the spec → no skip (FR-006).
- [x] T014 [P] [US4] E2E test `test_no_skip_when_verification_declares_timeout`: frozen-screen scenario with `timeout_seconds` declared; assert planner is called every iteration (`plan_calls == iterations`) and no skip markers exist (SC-005).
- [x] T015 [US4] Confirm exception wiring in `_planner_skip_reason` (implemented in T006; this task is the verification pass against FR-006 acceptance scenarios).

## Phase 7: Cross-scenario validation & Polish

- [x] T016 [P] Second unrelated GUI scenario (Principle VI two-scenario rule): keyboard-flow variant in `test_scenario_11_skip_replan_duplicate_frame.py` (non-idempotent `press_key` step, e.g. enter, frozen screen) asserting the same skip + conservation behavior with no mouse involvement.
- [x] T017 Full regression: `uv run pytest tests/unit tests/fixtures -q` and `uv run pytest tests/e2e -q` green; record any environment-dependent integration failures with reasons (never faked).

## Dependencies & Execution Order

- Phase 2 (T002, T003) blocks everything downstream (fields must exist).
- T004/T005 before T006–T008 (test-first); T009 depends on T008; T011 before T012; T013/T014 before T015 verification pass.
- [P] tasks touch distinct files and may run concurrently.

## Implementation Strategy

MVP = Phases 1–3 (skip works, existing block-path semantics preserved). Phases 4–6 layer safety proof, telemetry, and exception coverage; Phase 7 closes the constitutional cross-scenario gate and regression.
