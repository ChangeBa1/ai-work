# Implementation Plan: Batch Repeat Key Press

**Branch**: `005-batch-repeat-keypress` | **Date**: 2026-07-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-batch-repeat-keypress/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Test-case authors currently clear a text field (e.g. ScannerSimulator's Barcode box) by writing an
`intent` prose step that the Planner LLM re-interprets on every retry, producing one Backspace per
`ActionIteration` — each iteration paying a full screenshot + OCR + Planner + post-action-verification
cost. This feature adds a **deterministic, declarative** `batch_repeat_key` field on `TestStep` that
lets the author state "press `backspace` `N` times" directly. When present, the runtime skips the
Planner call for that step, builds the `SemanticAction` itself, and routes it through the existing
`ActionPolicy → ExecutionRouter → KeyboardExecutor` pipeline exactly like any other keyboard action.
`KeyboardExecutor` gains one new method, `press_key_repeat`, that loops a bounded, fail-fast send of a
single key with an optional inter-send delay — with **no** perception/planner/grounder/verifier calls
inside the loop. Wait-stable and post-action verification run exactly once afterward, unchanged. The
existing `press_key`, `hotkey`, and `type_text` paths are not touched.

## Technical Context

**Language/Version**: Python 3.12 (existing `vnc_agent` package, `requires-python = ">=3.12"`)

**Primary Dependencies**: pydantic 2 (domain models/validation), pytest + pytest-asyncio (tests),
existing in-repo layers only — no new third-party dependency

**Storage**: N/A for this feature (reuses existing SQLite run/iteration persistence via
`storage/repositories.py`; the two new `ExecutionResult` fields are additional optional Pydantic
columns picked up by the existing serialization path, no schema migration authored by this feature)

**Testing**: pytest (unit, e2e-offline via `FakeVNC`/`StubPlanner`), TDD — tests written before the
corresponding production code for each of: model validation, policy routing, execution success,
partial-failure reporting, and press_key/hotkey compatibility

**Target Platform**: Same as existing `vnc_agent` runtime — Windows VNC target under test, agent
process itself is platform-agnostic Python

**Project Type**: Single project (existing modular monolith, per Constitution "架构约束") — no new
service, process, or project is introduced

**Performance Goals**: Zero screenshot/OCR/Planner/Grounder/Verifier calls between individual key
sends within a batch (SC-002); clearing a ~20-character field completes in 1 `ActionIteration` instead
of up to `max_retries` iterations (SC-001, SC-006, SC-007)

**Constraints**: Repeat count 1–50 inclusive, no default (FR-006); inter-send interval 0–500ms,
default 50ms (FR-007); target key excludes modifier keys (ctrl/alt/shift/win) and is drawn from the
existing `press_key` vocabulary only (FR-005); no key-down/wait/key-up "held" mode (FR-010); fail-fast
on first send error, no per-key retry inside the batch action itself (spec Clarifications 2026-07-24)

**Scale/Scope**: One new `TestStep` field, one new `SemanticAction`/`ExecutableAction` action type,
one new `KeyboardExecutor` method, one new `ExecutionRouter` dispatch branch, two new optional
`ExecutionResult` fields, one runtime bypass branch, one updated test-case YAML. ~7 source files
touched, no unrelated refactor.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I (Deterministic Runtime Control)**: PASS. The batch action is decided entirely by
  code — the author's declared `key`/`count`/`interval_ms` values flow unchanged through validated
  Pydantic models into a bounded `for` loop. No model is asked to decide the repeat count, and the
  Planner is not invoked at all for a declared batch step (stronger than the existing per-iteration
  Planner call already made for `press_key`/`hotkey`/`type_text`).
- **Principle II (Planner/Grounder/Executor/Verifier separation)**: PASS. `press_key_repeat` is
  purely an Executor-layer concern (`KeyboardExecutor`); it never touches Grounder or Verifier
  responsibilities, and does not let the Executor self-certify success — the existing independent
  post-action Verifier still runs once after the batch.
- **Principle III (Keyboard-first execution priority)**: PASS. A declared batch key-press is even
  more deterministic than the existing "verified replay action" tier — it is author-declared and
  validated before any device interaction, sitting at least as high in the priority order as
  existing keyboard paths, and never falls through to visual grounding.
- **Principle IV (Observe→Act→Verify independent loop)**: PASS. Pre-action observation happens once
  before the batch; post-action stability wait + independent re-observation + verification happen
  once after — unchanged from the existing single-action lifecycle (FR-004). The loop's own key
  sends are not treated as self-certifying evidence.
- **Principle V (Controlled self-evolution)**: N/A — this feature adds no experience-memory,
  self-healing, or replay-baseline mutation behavior.

**Domain-Agnostic Core gate (Principle VI)**:

- [x] No business-specific fields, keywords, states, action categories, expected values, or flow
      branches are being added to core modules. `batch_repeat_key` is a generic
      `{key, count, interval_ms}` declaration with no Barcode/POS/ScannerSimulator vocabulary
      anywhere in `domain/`, `planning/`, `execution/`, or `runtime/`.
- [x] All business/scenario semantics (which field, which key, which count) live only in testcase
      YAML: the ScannerSimulator scenario (`vnc_agent/testcases/pos-scan-magazine-checkout.yaml`)
      and a new business-agnostic fixture testcase used for the second, unrelated scenario proof.
- [x] Cross-scenario contract test planned: `test_scenario_16_batch_repeat_key.py` (generic, offline,
      arbitrary key/count via `FakeVNC`/`StubPlanner`) plus a live-scenario proof via the updated
      `pos-scan-magazine-checkout.yaml` — two unrelated scenarios, per Principle VI's ≥2-scenario
      requirement, following the existing precedent in
      `tests/e2e/test_declarative_interface_cross_scenario.py`.

No violations requiring justification — Complexity Tracking table is empty.

## Project Structure

### Documentation (this feature)

```text
specs/005-batch-repeat-keypress/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── testcase-batch-repeat-key-schema.md
│   └── execution-layer-contract.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

**Structure Decision**: Existing single-project layout under `vnc_agent/` is reused as-is (Option 1,
no new top-level directory). This feature only touches existing modules inside `src/vnc_agent/` and
adds test files inside the existing `tests/unit/` and `tests/e2e/` trees, matching current conventions
(`test_scenario_NN_*.py` for e2e, flat files under `tests/unit/` for isolated component tests).

```text
vnc_agent/
├── src/vnc_agent/
│   ├── domain/
│   │   ├── action.py          # MODIFY: ActionType, SemanticAction, ExecutableAction,
│   │   │                      #   ExecutionResult, batch-repeat bound constants
│   │   └── testcase.py        # MODIFY: BatchRepeatKeyDeclaration + TestStep.batch_repeat_key
│   ├── drivers/
│   │   └── key_mapping.py     # MODIFY: add is_batch_repeatable_key() helper (reuses KEY_MAP/MODIFIERS)
│   ├── planning/
│   │   └── action_policy.py   # MODIFY: ActionPolicy.resolve() new "press_key_repeat" branch
│   ├── execution/
│   │   ├── keyboard_executor.py  # MODIFY: new press_key_repeat() method
│   │   └── router.py             # MODIFY: dispatch + ExecutionResult population
│   └── runtime/
│       ├── exceptions.py      # MODIFY: new KeyRepeatSendError
│       └── agent_runtime.py   # MODIFY: run_action_iteration() Planner-bypass branch
├── testcases/
│   └── pos-scan-magazine-checkout.yaml   # MODIFY: clear-barcode step → batch_repeat_key
└── tests/
    ├── fixtures/testcases/
    │   └── generic-batch-repeat-key-example.yaml   # NEW: 2nd, unrelated scenario fixture
    ├── unit/
    │   ├── test_batch_repeat_key_validation.py     # NEW: model validation (bounds/keys)
    │   ├── test_action_policy_priority.py           # MODIFY: add press_key_repeat routing case
    │   ├── test_execution_router_batch_repeat.py    # NEW: router dispatch + result population
    │   ├── test_keyboard_executor_repeat.py         # NEW: loop success + fail-fast partial failure
    │   └── test_testcase_validation.py               # MODIFY: batch_repeat_key YAML-level bounds
    └── e2e/
        └── test_scenario_16_batch_repeat_key.py      # NEW: full-runtime cross-scenario proof
```

## Complexity Tracking

> No entries — Constitution Check has no unresolved violations.
