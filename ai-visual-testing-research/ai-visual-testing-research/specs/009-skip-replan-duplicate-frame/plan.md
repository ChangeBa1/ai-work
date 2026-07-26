# Implementation Plan: Skip Re-Plan on Duplicate Frame with Blocked Action

**Branch**: `009-skip-replan-duplicate-frame` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/009-skip-replan-duplicate-frame/spec.md`

## Summary

Add a short-circuit rule to the step iteration loop in `runtime/agent_runtime.py`: when the current iteration's observation frame has the same pixel-content hash as the previous iteration's observation AND the previous iteration's action was rejected by the RepeatGuard with reason `blocked_effect_pending` (incl. `_normalized_target` variant) or `ambiguous_fail_safe`, skip the Planner call and jump straight into the pre-existing repeat-guard-block verdict path (carry previous ActionEffect → `resolve_step_result` with escalation → recovery routing for `ambiguous_fail_safe`). Skipped iterations consume the normal step budget, carry the blocking decision forward (so chains of identical frames keep skipping), and leave a full telemetry trail: `ActionIteration.planner_skipped_reason="duplicate_frame_blocked_action"`, a `model_call_skipped` CounterEvent, and a `ModelCallAudit` with `outcome="skipped"` — while `model_calls.planner` does not grow. Exceptions: never skip on time-dependent steps (previous action wait-type, or verification spec declares `timeout_seconds`) and never on batch-repeat-key steps (no planner call exists there).

## Technical Context

**Language/Version**: Python 3.11+ (existing `vnc_agent` package, uv-managed)

**Primary Dependencies**: pydantic v2 (domain models), pytest / pytest-asyncio (tests); no new dependencies

**Storage**: existing SQLite run repository + JSON/HTML report artifacts; only additive fields flow through

**Testing**: `uv run pytest tests/unit tests/fixtures -q` and `uv run pytest tests/e2e -q` (offline Stub/FakeVNC infrastructure; see `tests/e2e/conftest.py`)

**Target Platform**: Windows/Linux desktop agent process (unchanged)

**Project Type**: single-project modular monolith (`vnc_agent/src/vnc_agent`)

**Performance Goals**: eliminate one full cloud planner round-trip (~4–5 s observed) per short-circuited iteration; zero added latency on non-skipped iterations (the skip predicate is a few field comparisons)

**Constraints**: change confined to `runtime/agent_runtime.py` (+ additive `domain/run.py` iteration fields + `reporting/json_report.py` field passthrough); MUST NOT touch `verification/business_resolver.py`, `perception/cache.py`, `perception/ocr/`, `execution/repeat_guard.py` decision logic, or the capture/dedup layer (parallel feature ownership)

**Scale/Scope**: one runtime predicate + one refactored shared verdict helper + 2 additive model fields + 1 report field + tests

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Deterministic Runtime Control — PASS.** The skip decision is a deterministic code predicate in the state machine loop; no model gains control. It directly implements the constitutional resource constraint "页面未变化不重复调用 Planner".
- **II. Separation of Concerns — PASS.** Planner/Grounder/Executor/Verifier roles unchanged; we only decide *not to consult* the Planner when its input is provably identical to a round whose output was blocked.
- **III. Keyboard-first routing — N/A.** No action-resolution priority change.
- **IV. Independent Observe-Act-Verify loop — PASS.** The short-circuit only triggers when no action will be executed this round (previous was blocked and nothing new can be proposed); verification still runs on the freshly captured observation via the existing `resolve_step_result` escalation path, which can re-observe. `uncertain` still never passes.
- **V. Controlled self-evolution — N/A.** No baseline/model/replay mutation.
- **VI. Domain-agnostic core — PASS.** New vocabulary (`planner_skipped_reason`, `duplicate_frame_blocked_action`, content-hash equality) is UI/business-agnostic. The diagnosing incident (add-shopping-bag) stays in test fixtures only; e2e tests exercise two unrelated generic scenarios (a click-on-button flow and a keypress flow) per the two-scenario rule.
- **Recovery/retry gate — PASS.** No new retry loop: skipped iterations flow through `StepController.start_iteration()` budget accounting; recovery reuse is under the existing per-failure-type caps. Frozen screen + blocked action terminates by budget exactly as today (FR-004).
- **Observability gate — PASS.** Uses the pre-existing telemetry contract kinds (`model_call_skipped` CounterEvent and `outcome="skipped"` ModelCallAudit — both defined by feature 004 but previously unused for planner) plus one additive report field; `derive_performance_summary` conservation is unaffected (skips count in `skipped_model_call_count`).

**Domain-Agnostic Core gate (Principle VI)**:

- [x] No business-specific fields, keywords, states, action categories, expected values, or flow branches added to core modules.
- [x] All scenario semantics live only in test fixtures.
- [x] Generic capability validated against two unrelated GUI scenarios (mouse-click flow, keyboard flow) in the e2e tests.

## Project Structure

### Documentation (this feature)

```text
specs/009-skip-replan-duplicate-frame/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── planner-skip-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
vnc_agent/
├── src/vnc_agent/
│   ├── runtime/
│   │   └── agent_runtime.py      # skip predicate + telemetry emission + shared blocked-verdict helper (MODIFIED)
│   ├── domain/
│   │   └── run.py                # ActionIteration: +planner_skipped_reason, +before_content_hash (ADDITIVE)
│   └── reporting/
│       └── json_report.py        # iteration output: +planner_skipped_reason (ADDITIVE)
└── tests/
    ├── unit/
    │   └── test_planner_skip_decision.py     # NEW: predicate unit tests
    └── e2e/
        └── test_scenario_11_skip_replan_duplicate_frame.py  # NEW: end-to-end skip/budget/telemetry/exception tests
```

**Structure Decision**: Existing single-project layout; three touched production files, all inside the sanctioned scope (runtime + additive iteration-record/report fields). `step_controller.py` and `telemetry.py` need no changes — existing budget semantics and telemetry kinds already cover the feature.

## Complexity Tracking

No constitution violations; table intentionally empty.
