---

description: "Task list for feature 005: Batch Repeat Key Press"
---

# Tasks: Batch Repeat Key Press

**Input**: Design documents from `/specs/005-batch-repeat-keypress/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md,
data-model.md, contracts/

**Tests**: TDD explicitly requested by the user — every behavioral task below has a paired test task
that MUST be written and observed failing before its implementation task is done.

**Organization**: Tasks are grouped by user story (spec.md P1/P2/P2) to enable independent
implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- All file paths are repository-relative

## Path Conventions

Single existing project, no new top-level directories. All paths are under `vnc_agent/`:
`vnc_agent/src/vnc_agent/...` (production code), `vnc_agent/tests/...` (tests),
`vnc_agent/testcases/...` (live test-case YAML).

---

## Phase 1: Setup

**Purpose**: Establish a green baseline before touching any file, so later regression checks
(FR-011/FR-012/SC-005) have something concrete to compare against.

- [X] T001 Run the full existing suite from `vnc_agent/`: `pytest tests/unit tests/e2e
      tests/integration -q`. Confirm it is 100% green (integration tests requiring a live VNC are
      already skip-gated by `VNC_AGENT_INTEGRATION`). Record the pass count — Phase 7 (Polish) will
      re-run this exact command and expect the same or a strictly larger green count, never smaller.
      **Baseline: 337 passed, 1 skipped, 0 failed.**

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared domain-layer types every user story's code and tests import:
`is_batch_repeatable_key()`, the batch-repeat bound constants, the extended `ActionType`/
`SemanticAction`/`ExecutableAction`/`ExecutionResult`, and `KeyRepeatSendError`. This is the "动作
模型校验" (action-model validation) layer in isolation from policy/routing/execution.

**⚠️ CRITICAL**: No user story task can start until this phase is complete.

- [X] T002 [P] Write failing tests in NEW `vnc_agent/tests/unit/test_batch_repeat_key_validation.py`
      covering: (a) `drivers.key_mapping.is_batch_repeatable_key()` — accepts `"backspace"`,
      `"delete"`, `"tab"`, arrow keys, `"f1"`..`"f12"`; rejects modifier keys (`"ctrl"`, `"alt"`,
      `"shift"`, `"win"`, `"super"`, `"meta"`, `"cmd"`) and unknown names; (b) constructing
      `SemanticAction(action_type="press_key_repeat", keys=["backspace"], repeat_count=20)` succeeds
      and defaults `repeat_interval_ms` behavior is inspectable; (c) construction is rejected when:
      `keys` has 0 or 2+ entries, `keys[0]` is a modifier or unknown key, `repeat_count` is `None`/`0`/
      negative/`51`, `repeat_interval_ms` is negative or `501`; (d) constructing any *other*
      `action_type` (e.g. `"press_key"`) with a non-`None` `repeat_count` or `repeat_interval_ms` is
      rejected (keeps existing action types provably clean, FR-011). Follow the existing style in
      `vnc_agent/tests/unit/test_action_policy_priority.py` (plain `pytest` functions, direct
      `SemanticAction(...)` construction, `pytest.raises`).

- [X] T003 [P] Implement `is_batch_repeatable_key(name: str) -> bool` in
      `vnc_agent/src/vnc_agent/drivers/key_mapping.py`, built on the existing `KEY_MAP`, `MODIFIERS`,
      and `normalize_key()` already in that file. Do not change `KEY_MAP`, `MODIFIERS`, or
      `normalize_key()`'s existing behavior. Makes the helper-related assertions in T002 pass.

- [X] T004 Implement, in `vnc_agent/src/vnc_agent/domain/action.py`: the constants
      `BATCH_REPEAT_COUNT_MIN = 1`, `BATCH_REPEAT_COUNT_MAX = 50`,
      `BATCH_REPEAT_INTERVAL_MS_MIN = 0`, `BATCH_REPEAT_INTERVAL_MS_MAX = 500`,
      `BATCH_REPEAT_INTERVAL_MS_DEFAULT = 50`; add `"press_key_repeat"` to the `ActionType` Literal;
      add `repeat_count: int | None = None` and `repeat_interval_ms: int | None = None` to
      `SemanticAction`, plus a new `model_validator` (alongside the existing `reject_coords`) enforcing
      the accept/reject rules from T002(b)(c)(d) using `is_batch_repeatable_key()` from T003; add the
      same two optional fields to `ExecutableAction`; add `requested_count: int | None = None` and
      `completed_count: int | None = None` to `ExecutionResult`. Do not modify `reject_coords` or any
      other existing field/validator. **Depends on T003.** Makes the remainder of T002 pass.

- [X] T005 [P] Implement `KeyRepeatSendError(VNCAgentError)` in
      `vnc_agent/src/vnc_agent/runtime/exceptions.py` with attributes `key: str`,
      `requested_count: int`, `completed_count: int`, `cause: Exception`, following the existing style
      of that file (e.g. `ActionTimeoutError`). No behavior beyond attribute storage is needed here —
      its raising/handling behavior is tested in Phase 5 (US3).

**Checkpoint**: `pytest tests/unit/test_batch_repeat_key_validation.py -v` is fully green. Re-run
Phase 1's baseline command — still green, nothing else changed yet.

---

## Phase 3: User Story 1 - Clear a text field with one declared action (Priority: P1) 🎯 MVP

**Goal**: A declared `batch_repeat_key` on a `TestStep` resolves to exactly one `ExecutableAction`,
executed by `KeyboardExecutor` with zero perception/Planner/Grounder/Verifier calls between the
individual key sends, the Planner is not called at all for that step, and the existing
wait-stable + post-action verification still run exactly once, unchanged. MVP scope only: a single
key, sent discretely `count` times — no macros, no key sequences, no key-down/held mode (FR-010,
FR-015).

**Independent Test**: `vnc_agent/tests/e2e/test_scenario_16_batch_repeat_key.py`, run standalone —
offline via `FakeVNC`/`StubPlanner`, no live VNC required.

### Tests for User Story 1 (write first, confirm they FAIL) ⚠️

- [X] T006 [P] [US1] Write failing tests in NEW `vnc_agent/tests/unit/test_keyboard_executor_repeat.py`
      for `KeyboardExecutor.press_key_repeat(key, count, interval_ms) -> int` (happy path only in
      this task; partial-failure cases are added later in T016): using a fake/mock driver
      (`unittest.mock.AsyncMock` or a small local fake, matching the `VNCDriver` Protocol's
      `send_key`), assert (a) `driver.send_key(key)` is called exactly `count` times with the same
      `key`; (b) each send is a single call — never a "key down" followed later by a "key up" call;
      (c) `asyncio.sleep(interval_ms / 1000.0)` (or equivalent) happens between consecutive sends but
      **not** after the last send — assert the sleep call count is `count - 1`; (d) the method returns
      `count` on success.

- [X] T007 [P] [US1] Write failing tests in NEW
      `vnc_agent/tests/unit/test_execution_router_batch_repeat.py` for `ExecutionRouter.execute()`
      given an `ExecutableAction(method="keyboard", operation="press_key_repeat", keys=["backspace"],
      repeat_count=20, repeat_interval_ms=50)` (success case only in this task; partial-failure cases
      are added later in T017): stub/patch `KeyboardExecutor.press_key_repeat` to return `20`, call
      `router.execute(action)`, and assert the returned `ExecutionResult` has
      `requested_count == 20`, `completed_count == 20`, `success is True`. Also assert, for an
      unrelated `ExecutableAction(operation="press_key", ...)`, that `requested_count` and
      `completed_count` are both `None` (compatibility guard co-located with the new test file).
      Follow the construction style already used in `vnc_agent/tests/integration/test_execution.py`.
      **Also** (remediation for analysis finding F1 — spec-legal `count`×`interval_ms` can exceed the
      configured default per-action timeout, 10s in `vnc_agent/config/agent.yaml`, silently losing
      `requested_count`/`completed_count` on timeout): in the same new file, write failing tests for a
      new pure function `compute_batch_repeat_timeout_seconds(repeat_count: int,
      repeat_interval_ms: int, default_timeout_seconds: float) -> float` (no `ExecutionRouter`
      instance needed): (a) for a small batch (e.g. `count=5, interval_ms=50`) whose
      `(count - 1) * interval_ms / 1000.0` is well under `default_timeout_seconds`, the function
      returns `default_timeout_seconds` unchanged; (b) for a large batch (e.g. `count=50,
      interval_ms=500` — both individually within FR-006/FR-007's legal ranges, worst case
      `(50-1)*0.5 = 24.5s`), the function returns a value `>= 24.5 + <margin>` and strictly greater
      than `default_timeout_seconds`; (c) the returned value is always
      `>= default_timeout_seconds` (never shrinks the existing default).

- [X] T008 [P] [US1] In `vnc_agent/tests/unit/test_action_policy_priority.py`, add failing test cases
      for: (a) `ActionPolicy.resolve()` given `SemanticAction(action_type="press_key_repeat",
      keys=["backspace"], repeat_count=20, repeat_interval_ms=None)` returns
      `PolicyResult(outcome="keyboard")` whose `executable.operation == "press_key_repeat"`,
      `executable.keys == ["backspace"]`, `executable.repeat_count == 20`, and
      `executable.repeat_interval_ms == 50` (the default substituted when the semantic action's is
      `None`); (b) **regression** — re-assert (do not delete) that existing `press_key` and `hotkey`
      `SemanticAction`s still resolve to the exact same `PolicyResult` shape as before this feature
      (outcome, executable.method, executable.operation, executable.keys) — add explicit assertions
      to `test_hotkey_preferred_over_grounding` and a new `test_press_key_still_resolves_unchanged`
      case if one does not already exist, so a future regression in the new branch's placement is
      caught here.

- [X] T009 [P] [US1] **First**, extend `FakeVNC` in `vnc_agent/tests/e2e/conftest.py` with a single
      shared ordered log `self.call_log: list[str] = []`: append `"capture"` at the top of
      `capture_screen()`, and append `f"key:{key}"` at the top of `send_key()` (purely additive —
      `self.i`/frame-selection logic and `self.keys` are unchanged, so every existing e2e test that
      relies on `FakeVNC` is unaffected). **Do not** use a bare total-call counter for this (analysis
      finding F2): `StabilityEngine.wait_stable()` — called once after every action via the existing,
      unrelated runtime flow — itself issues its own `capture_service.capture()` →
      `driver.capture_screen()` calls in a polling loop (at least `stable_frame_count - 1 + 1` of them;
      2 with the e2e fixture's `stable_frame_count=2` config), so a correct implementation's *total*
      `capture_screen()` count per iteration is roughly 4 (pipeline's pre-/post-action `observe()` +
      the stability wait's own polling), not 2 — an exact-total assertion would fail against a correct
      implementation. An ordered log checked for *contiguity*, not a magic total, is what actually
      proves FR-003/SC-002 without coupling the test to `StabilityEngine`'s unrelated internals. Then
      create NEW fixture `vnc_agent/tests/fixtures/testcases/generic-batch-repeat-key-example.yaml` —
      a small, business-agnostic `TestCase` (one step, generic field/label wording, no POS/Barcode/
      ScannerSimulator vocabulary) whose one step declares `batch_repeat_key: {key: backspace,
      count: 5}`. Then write a failing test in NEW
      `vnc_agent/tests/e2e/test_scenario_16_batch_repeat_key.py`, following the pattern in
      `vnc_agent/tests/e2e/test_declarative_interface_cross_scenario.py` and
      `vnc_agent/tests/e2e/test_scenario_02_keyboard_first.py`: load the fixture via
      `load_test_case()`, run it through `build_runtime()` (from `tests/e2e/conftest.py`) with a
      `StubPlanner` and a `StubGrounder`, and assert: `stub_planner.plan_calls == 0` for the batch
      step's iteration(s); **`grounder.calls == []`** (remediation for F-003/SC-002 coverage gap —
      proves Grounding is never reached, not just that the Planner wasn't called); **the 5
      `"key:backspace"` entries in `drv.call_log` are contiguous — no `"capture"` entry appears between
      the first and the last of them** (remediation for the same gap — proves zero screenshots happen
      *between* the individual key sends, regardless of how many captures happen before or after the
      batch from `observe()`/`wait_stable()`); `drv.keys == ["backspace"] * 5` (via `FakeVNC.keys`,
      unchanged); the iteration's `execution_result.requested_count ==
      execution_result.completed_count == 5`; and the step recorded exactly one post-action
      verification (one iteration with a terminal `verification_result`, not five).

### Implementation for User Story 1

- [X] T010 [P] [US1] In `vnc_agent/src/vnc_agent/planning/action_policy.py`, add a new branch at the
      top of `ActionPolicy.resolve()` (before the existing "1) Explicit keys / hotkey" branch):
      when `action.action_type == "press_key_repeat"`, return
      `PolicyResult(outcome="keyboard", executable=ExecutableAction(method="keyboard",
      operation="press_key_repeat", keys=list(action.keys), repeat_count=action.repeat_count,
      repeat_interval_ms=action.repeat_interval_ms or BATCH_REPEAT_INTERVAL_MS_DEFAULT))` and return
      unconditionally (never fall through to focus-navigation/OCR/Grounding). Do not reorder or
      modify any existing branch. **Depends on Phase 2 only** — independent of T011/T012. Makes
      T008(a) pass; T008(b) must still pass unchanged.

- [X] T011 [P] [US1] In `vnc_agent/src/vnc_agent/execution/keyboard_executor.py`, add
      `async def press_key_repeat(self, key: str, count: int, interval_ms: int) -> int` to
      `KeyboardExecutor`: loop `count` times calling `await self.driver.send_key(key)` (a discrete
      press-and-release each time — never key-down/wait/key-up), sleeping
      `interval_ms / 1000.0` seconds between sends but not after the last one, and returning `count`
      on completion. Fail-fast error handling is added later in T018 — this task only needs the
      happy path to make T006 pass. **Depends on Phase 2 only** — independent of T010.

- [X] T012 [US1] In `vnc_agent/src/vnc_agent/execution/router.py`: extend `_dispatch()` with a branch
      for `action.operation == "press_key_repeat"` that awaits
      `self.keyboard.press_key_repeat(action.keys[0], action.repeat_count,
      action.repeat_interval_ms)` and returns its result (change `_dispatch()`'s return type from
      implicit `None` to `int | None`, `None` for every other operation); extend `execute()` so that
      when `action.operation == "press_key_repeat"` and dispatch succeeds, the returned
      `ExecutionResult` sets `requested_count = action.repeat_count` and
      `completed_count = <the value _dispatch returned>`; for every other operation both fields stay
      `None`. Do not change any other branch of `_dispatch()` or `execute()`. **Depends on T011.**
      Makes T007's success-case assertions pass.
      **Also** (remediation for F1): add module-level constant `BATCH_REPEAT_TIMEOUT_MARGIN_SECONDS =
      5.0` and function `compute_batch_repeat_timeout_seconds(repeat_count: int,
      repeat_interval_ms: int, default_timeout_seconds: float) -> float` to this same file:
      `return max(default_timeout_seconds, (repeat_count - 1) * (repeat_interval_ms / 1000.0) +
      BATCH_REPEAT_TIMEOUT_MARGIN_SECONDS)` (the `repeat_count - 1` matches T011's "sleep between
      sends, not after the last one" — there are exactly `count - 1` inter-send delays in the whole
      batch). This is a pure, side-effect-free function — it does not itself change `execute()`'s
      timeout handling; T013 is responsible for calling it and passing the result as
      `execute(..., timeout_seconds=...)`. Makes T007's new timeout-helper assertions pass.

- [X] T013 [US1] In `vnc_agent/src/vnc_agent/runtime/agent_runtime.py`, inside
      `run_action_iteration()`, immediately before the existing `plan = await
      self.planner_orch.plan(...)` call: if `step.batch_repeat_key is not None`, construct
      `sa = SemanticAction(action_id=<a stable id, e.g. f"{step.id}-batch-repeat">, intent=step.intent,
      action_type="press_key_repeat", keys=[step.batch_repeat_key.key],
      repeat_count=step.batch_repeat_key.count,
      repeat_interval_ms=step.batch_repeat_key.interval_ms, risk_level="low")` — **deliberately do
      NOT set `action_kind` here** (remediation for analysis finding D1: hardcoding
      `action_kind="idempotent"` for every declared key, including non-idempotent ones like `enter`
      or `pagedown`, would bypass `RepeatGuard`'s safety checks on step retry, contradicting the
      existing conservative default in `planning/action_classification.py`). Skip the
      `planner_orch.plan()` call and its following `_record_model_call_audit(...,
      model_role="planner", ...)` block entirely for this iteration, then run the bypass-constructed
      `sa` through the **same** `if sa.action_kind is None: sa = sa.model_copy(update={"action_kind":
      classify_action_kind(sa)})` line the existing Planner path already applies today (restructure so
      this one line runs after either the Planner call or the bypass, not duplicated) — this leaves
      every `press_key_repeat` action classified `non_idempotent` by the same conservative default
      every other undeclared action already gets, so `RepeatGuard` still runs its full safety check on
      any step retry. Set `iteration.semantic_action`/`iteration.canonical_identity` exactly as the
      existing code does right after planning today, and fall through into the unchanged
      `RepeatGuard`/`ActionPolicy.resolve()` sequence that already exists below.
      **Also** (remediation for F1): when calling the executor for a `press_key_repeat` action, pass
      an explicit timeout instead of relying on the router's static default:
      `exec_result = await self.executor.execute(executable, timeout_seconds=
      compute_batch_repeat_timeout_seconds(executable.repeat_count, executable.repeat_interval_ms,
      self.executor.default_timeout_seconds) if executable.operation == "press_key_repeat" else
      None)` (import `compute_batch_repeat_timeout_seconds` from `execution/router.py`, added in
      T012) — for every other operation this passes `timeout_seconds=None`, which is exactly today's
      behavior (uses the router's own default), so FR-011/FR-012 compatibility is preserved.
      When `step.batch_repeat_key is None`, behavior is byte-for-byte unchanged (existing Planner call
      path, existing no-argument `execute()` call). **Depends on T010 and T012.** Makes T009 pass.

**Checkpoint**: `pytest tests/unit/test_keyboard_executor_repeat.py
tests/unit/test_execution_router_batch_repeat.py tests/unit/test_action_policy_priority.py
tests/e2e/test_scenario_16_batch_repeat_key.py -v` all green. Re-run Phase 1's full baseline command —
still green (press_key/hotkey regression confirmed). **This is the MVP checkpoint** — User Story 1 is
independently functional and demoable.

---

## Phase 4: User Story 2 - Reject invalid batch requests before anything runs (Priority: P2)

**Goal**: A malformed `batch_repeat_key` declaration in test-case YAML (bad key, bad count, bad
interval) is rejected by `load_test_case()` before a run starts — no VNC connection, no screenshot, no
key ever sent.

**Independent Test**: `vnc_agent/tests/unit/test_testcase_validation.py` new cases — pure
`load_test_case()`/`TestStep(...)` construction, no runtime/driver involved at all.

### Tests for User Story 2 (write first, confirm they FAIL) ⚠️

- [X] T014 [P] [US2] In `vnc_agent/tests/unit/test_testcase_validation.py`, add failing tests
      following the existing style (`_spec()` helper, direct `TestStep(...)` construction,
      `pytest.raises`): (a) `TestStep(..., batch_repeat_key={"key": "backspace", "count": 20})`
      succeeds and `step.batch_repeat_key.count == 20`, `step.batch_repeat_key.interval_ms is None`;
      (b) `batch_repeat_key={"key": "shift", "count": 5}` (modifier key) raises `ValidationError`;
      (c) `batch_repeat_key={"key": "nope", "count": 5}` (unknown key) raises `ValidationError`;
      (d) `batch_repeat_key={"key": "backspace", "count": 0}` and `count: 51` both raise
      `ValidationError`; (e) `batch_repeat_key={"key": "backspace", "count": 5, "interval_ms": -1}`
      and `interval_ms: 501` both raise `ValidationError`; (f) a `TestStep` that omits
      `batch_repeat_key` entirely still loads with `step.batch_repeat_key is None`
      (compatibility — existing test cases unaffected).

### Implementation for User Story 2

- [X] T015 [US2] In `vnc_agent/src/vnc_agent/domain/testcase.py`: add a `BatchRepeatKeyDeclaration`
      Pydantic model with fields `key: str`, `count: int`, `interval_ms: int | None = None`, and a
      `model_validator` enforcing `is_batch_repeatable_key(key)` (imported from
      `vnc_agent.drivers.key_mapping`) and the `BATCH_REPEAT_COUNT_MIN/MAX` /
      `BATCH_REPEAT_INTERVAL_MS_MIN/MAX` bounds (imported from `vnc_agent.domain.action`, both added
      in T004); add `batch_repeat_key: BatchRepeatKeyDeclaration | None = None` to `TestStep`. Do not
      change any other `TestStep`/`TestCase` field or the `load_test_case()` control flow beyond what
      Pydantic validation already provides (existing `FieldValidationError` wrapping already applies
      automatically). **Depends on T003, T004.** Makes T014 pass.

**Checkpoint**: `pytest tests/unit/test_testcase_validation.py -v` green. Full baseline still green.
US1 and US2 both independently functional.

---

## Phase 5: User Story 3 - Get an accurate report when a batch is interrupted (Priority: P2)

**Goal**: When a key send fails partway through a batch, execution stops immediately (fail-fast, no
per-key retry inside the batch action) and the resulting `ExecutionResult` accurately reports the
planned count, the count actually completed, and the failure reason.

**Independent Test**: unit-level — force `driver.send_key()` to raise partway through a
`press_key_repeat` call and inspect the resulting exception / `ExecutionResult`.

### Tests for User Story 3 (write first, confirm they FAIL) ⚠️

- [X] T016 [P] [US3] In `vnc_agent/tests/unit/test_keyboard_executor_repeat.py` (extends the file
      created in T006), add failing tests: (a) a fake driver whose `send_key` raises on the 8th call
      (of a planned `count=20`) — `press_key_repeat` raises `KeyRepeatSendError` with
      `requested_count == 20`, `completed_count == 7`, `key == <the key>`, `cause` set to the
      underlying exception, and **no further `send_key` calls happen after the failure** (assert the
      mock's call count stops at 8, proving fail-fast/no retry); (b) a fake driver whose `send_key`
      raises on the very first call — `completed_count == 0`.

- [X] T017 [P] [US3] In `vnc_agent/tests/unit/test_execution_router_batch_repeat.py` (extends the file
      created in T007), add failing tests: given a `KeyboardExecutor.press_key_repeat` stubbed to
      raise `KeyRepeatSendError(key="backspace", requested_count=20, completed_count=7,
      cause=RuntimeError("boom"))`, `ExecutionRouter.execute()` returns an `ExecutionResult` with
      `success is False`, `requested_count == 20`, `completed_count == 7`,
      `error_code == "key_repeat_partial"`, and a non-empty `error_message` that references the key
      and/or the underlying cause.

### Implementation for User Story 3

- [X] T018 [US3] In `vnc_agent/src/vnc_agent/execution/keyboard_executor.py`, extend
      `press_key_repeat()` (from T011) to wrap each `await self.driver.send_key(key)` call: on
      exception, stop the loop immediately (no retry of the failed send, no further sends) and raise
      `KeyRepeatSendError(key=key, requested_count=count, completed_count=<sends completed so far>,
      cause=<the caught exception>)` (chained via `raise ... from cause`). The happy path from T011 is
      otherwise unchanged. **Depends on T011, T005.** Makes T016 pass.

- [X] T019 [US3] In `vnc_agent/src/vnc_agent/execution/router.py`, extend `execute()` (from T012) to
      catch `KeyRepeatSendError` specifically — alongside, and checked before, the existing generic
      `except Exception` — and populate `ExecutionResult(success=False,
      requested_count=e.requested_count, completed_count=e.completed_count,
      error_code="key_repeat_partial", error_message=<built from e.key and e.cause>)`. The existing
      `asyncio.TimeoutError` and generic-`Exception` branches remain otherwise unchanged. **Depends on
      T012, T018.** Makes T017 pass.

**Checkpoint**: `pytest tests/unit/test_keyboard_executor_repeat.py
tests/unit/test_execution_router_batch_repeat.py -v` fully green (happy-path cases from Phase 3 AND
partial-failure cases from this phase). Full baseline still green. US1, US2, and US3 all
independently functional — the feature is functionally complete.

---

## Phase 6: ScannerSimulator Integration Validation (after implementation)

**Purpose**: Prove the feature against the real, originally-motivating scenario, and complete the
Constitution Principle VI ≥2-unrelated-scenario proof (generic fixture from T009 + this real POS
scenario). Deliberately sequenced after Phases 3–5 so the declarative field being used here is
already fully implemented and unit/e2e-tested.

- [X] T020 In `vnc_agent/testcases/pos-scan-magazine-checkout.yaml`, replace the
      `clear-barcode-with-backspace` step's current `intent` prose ("本步骤每次只做一件事：
      action_type=press_key... 本步可能通过多次重试连续 Backspace 直到框空") with a
      `batch_repeat_key: {key: backspace, count: 20}` declaration. Update the step's `intent` to a
      short label describing the now-deterministic action (Planner is bypassed for this step, but
      `intent` remains a required field used for reporting). Reduce `max_retries` from `20` to a small
      whole-step safety net (e.g. `2`) — it now governs retrying the *entire* declared batch on
      failure, not per-keystroke retries. Leave the step's `expected` verification block exactly as
      it is today (already checks only that the Barcode field is empty, matching the
      Clarifications 2026-07-24 decision — no focus re-check needed).

- [X] T021 Validate the updated YAML and the cross-scenario proof: run
      `python -c "from vnc_agent.domain.testcase import load_test_case; tc =
      load_test_case('testcases/pos-scan-magazine-checkout.yaml'); step = next(s for s in tc.steps if
      s.id == 'clear-barcode-with-backspace'); print(step.batch_repeat_key)"` from `vnc_agent/` and
      confirm it prints `BatchRepeatKeyDeclaration(key='backspace', count=20, interval_ms=None)`
      with no `FieldValidationError`. Then confirm both this file and the generic fixture from T009
      (`tests/fixtures/testcases/generic-batch-repeat-key-example.yaml`) each independently declare
      `batch_repeat_key` on an unrelated scenario (generic vs. POS/ScannerSimulator), satisfying the
      Constitution Principle VI ≥2-scenario requirement for this feature. **Depends on T020, T015.**

**Checkpoint**: ScannerSimulator scenario proven compatible with the new declarative field, offline.
(A live VNC run against `win10-test-01`, per quickstart.md step 6, is optional/manual and out of
scope for this task list.)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final repo-wide checks that span every prior phase.

- [X] T022 [P] Re-run the Phase 1 baseline from `vnc_agent/`: `pytest tests/unit tests/e2e
      tests/integration -q`. Confirm 100% pass, with a pass count ≥ the Phase 1 baseline (SC-005) —
      every pre-existing test (including `test_execution.py`'s live-VNC-gated smoke test if run with
      `VNC_AGENT_INTEGRATION=1`, and `test_scenario_02_keyboard_first.py`'s keyboard-first path)
      continues to pass unmodified.

- [X] T023 [P] Run `ruff check src/ tests/` from `vnc_agent/` and fix any lint findings introduced by
      this feature's new/changed files (all files touched are already covered by the existing
      `[tool.ruff]` config in `vnc_agent/pyproject.toml` — no config changes expected).

- [X] T024 Constitution Principle VI check: grep
      `vnc_agent/src/vnc_agent/{domain,planning,execution,runtime}` for any literal
      "Barcode"/"ScannerSimulator"/"POS" (or similar business-specific) strings introduced by this
      feature's source changes. Confirm none exist — the only place those words may legitimately
      appear is `vnc_agent/testcases/pos-scan-magazine-checkout.yaml` and this feature's `specs/`
      docs.

- [X] T025 Run through `specs/005-batch-repeat-keypress/quickstart.md` steps 1–5 end to end (step 6 is
      optional/manual, requires a live VNC target) and confirm every documented expected outcome
      actually holds against the finished implementation.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all user stories.**
- **User Story 1 (Phase 3)**: Depends on Foundational only.
- **User Story 2 (Phase 4)**: Depends on Foundational only (T015 needs T003+T004 from Foundational,
  not anything from Phase 3) — **independently implementable in parallel with Phase 3** by a
  different engineer/agent if desired.
- **User Story 3 (Phase 5)**: Depends on Foundational **and** on T011/T012 from Phase 3 (it extends
  `press_key_repeat`'s error handling and `execute()`'s exception handling, both first created in
  Phase 3) — cannot start until Phase 3's T011 and T012 are done. Can proceed in parallel with
  Phase 4 (US2), which it does not touch.
- **ScannerSimulator Integration (Phase 6)**: Depends on Phase 3 (T009's fixture pattern) and Phase 4
  (T015, so the YAML field actually validates). Deliberately placed after all three user stories per
  the explicit requirement that integration validation follow implementation.
- **Polish (Phase 7)**: Depends on everything above.

### User Story Dependency Summary

- **US1 (P1)**: No dependency on US2 or US3. This is the MVP.
- **US2 (P2)**: No dependency on US1 or US3 — could even be implemented first if preferred; ordered
  second here only because it matches spec.md's priority listing.
- **US3 (P2)**: Depends on US1's `KeyboardExecutor.press_key_repeat` (T011) and
  `ExecutionRouter.execute` (T012) existing to extend — cannot be fully independent of US1's
  implementation (though its *tests* in T016/T017 can be written any time after Phase 2).

### Within Each Phase

- Tests are written and confirmed failing before their paired implementation task.
- `[P]`-marked tasks touch different files and have no unmet dependency on another incomplete task
  in this list — safe to run concurrently (e.g., by parallel subagents).
- Non-`[P]` tasks either share a file with a preceding task in the same phase or explicitly depend on
  one — run them in listed order.

---

## Parallel Execution Examples

### Phase 2 (Foundational)

```text
# In parallel:
T002 Write failing tests in tests/unit/test_batch_repeat_key_validation.py
T005 Implement KeyRepeatSendError in runtime/exceptions.py

# Then, sequentially (T003 before T004 — T004 imports T003's helper):
T003 Implement is_batch_repeatable_key() in drivers/key_mapping.py
T004 Implement SemanticAction/ExecutableAction/ExecutionResult fields in domain/action.py
```

### Phase 3 (US1) — test-writing

```text
# All four in parallel — four different files, no interdependency:
T006 tests/unit/test_keyboard_executor_repeat.py
T007 tests/unit/test_execution_router_batch_repeat.py
T008 tests/unit/test_action_policy_priority.py
T009 tests/fixtures/testcases/generic-batch-repeat-key-example.yaml + tests/e2e/test_scenario_16_batch_repeat_key.py
```

### Phase 3 (US1) — implementation

```text
# In parallel (independent of each other, both depend only on Phase 2):
T010 planning/action_policy.py
T011 execution/keyboard_executor.py

# Then sequentially:
T012 execution/router.py            (depends on T011)
T013 runtime/agent_runtime.py       (depends on T010 AND T012)
```

### Phases 4 and 5 relative to each other

```text
# Once Phase 3's T011/T012 are done, these two phases can proceed in parallel
# (different files, no shared dependency between them):
Phase 4 (US2): T014 → T015                  # domain/testcase.py
Phase 5 (US3): T016, T017 (parallel) → T018 → T019   # keyboard_executor.py, router.py
```

---

## Implementation Strategy

### MVP First (User Story 1 only)

1. Phase 1: Setup — capture baseline.
2. Phase 2: Foundational — shared model layer (blocking).
3. Phase 3: User Story 1 — batch declaration executes as one `ExecutableAction`, zero
   perception/model calls mid-batch, Planner bypassed, existing wait/verify reused.
4. **STOP and VALIDATE**: run Phase 3's checkpoint. This alone delivers the spec's entire reason for
   existing (P1 is explicitly "the only story required for a usable MVP" per spec.md).
5. MVP scope is intentionally narrow: single key, discrete press-and-release only — no macros, no
   key sequences, no held/long-press mode (FR-010, FR-015 — already enforced structurally by T004's
   `SemanticAction` validator accepting exactly one key, and by T011 never issuing anything but
   paired send calls).

### Incremental Delivery

1. Setup + Foundational → foundation ready.
2. Add US1 → validate independently → MVP demoable.
3. Add US2 (can run in parallel with US1 once Foundational is done) → validate independently —
   authoring safety net in place.
4. Add US3 (needs US1's T011/T012 first) → validate independently — diagnosability of interrupted
   runs in place.
5. Phase 6 — prove it against the real ScannerSimulator scenario that motivated the feature.
6. Phase 7 — final regression, lint, and Constitution checks.

### Parallel Team / Agent Strategy

- One agent: Foundational (T002–T005), then US1 (T006–T013) — the critical path.
- A second agent, once Foundational is done: US2 (T014–T015) in parallel with the first agent's US1
  work — no file overlap.
- A third stream: US3 (T016–T019) starts as soon as US1's T011/T012 land.
- Phase 6 and Phase 7 are single-threaded final gates after everything above converges.

---

## Notes

- `[P]` tasks = different files, no unmet dependency — safe to hand to parallel subagents.
- `[US1]`/`[US2]`/`[US3]` labels map every user-story-phase task back to spec.md's prioritized
  stories for traceability.
- Every behavioral implementation task has a paired test task that precedes it and must be observed
  failing first (TDD, as explicitly requested).
- Existing `press_key`/`hotkey` regression coverage lives in T008 (routing/policy level) and is
  re-confirmed at the full-suite level in T001/T022 (execution level, via the pre-existing suite).
- Partial-execution-failure coverage lives in T016/T017 (unit level) end-to-end down to
  `KeyRepeatSendError`'s exact `completed_count` semantics.
- Avoid: expanding scope to key sequences, multi-action macros, or held-key timing — explicitly out
  of scope for this MVP per spec.md's Non-Goals and FR-010/FR-015.

### Remediation applied (post `/speckit-analyze`, 2026-07-24)

Three CRITICAL/HIGH findings from the analysis report were fixed directly in the task descriptions
above (no changes to spec.md or plan.md were needed):

- **F1 (CRITICAL — timeout can silently drop `requested_count`/`completed_count`)**: T007 and T012
  now add `compute_batch_repeat_timeout_seconds()` (execution/router.py), sized from
  `(repeat_count - 1) * repeat_interval_ms + margin`; T013 now calls `executor.execute(...,
  timeout_seconds=...)` with that computed value for `press_key_repeat` actions instead of relying on
  the static 10s default, so a spec-legal worst-case batch (count=50, interval=500ms → 24.5s) no
  longer risks a timeout that would have lost the partial-progress counts.
- **D1 (HIGH — hardcoded `action_kind="idempotent"`)**: T013 no longer sets `action_kind` on the
  bypass-constructed `SemanticAction`; it now routes through the same conservative
  `classify_action_kind()` default every Planner-produced action already gets, so `RepeatGuard`'s
  safety checks are not bypassed for non-idempotent keys (e.g. `enter`) on step retry.
- **E1 (HIGH — no test coverage for "zero Grounder calls / zero mid-batch screenshots")**: T009 now
  extends `FakeVNC` and asserts `grounder.calls == []`, directly proving half of FR-003/SC-002 instead
  of only proving the Planner wasn't called. (The screenshot-side half of this fix was itself buggy —
  see F2 below — and has since been corrected.)

E2 and E3 (MEDIUM) were intentionally left unchanged, per the user's explicit request to fix only
HIGH/CRITICAL findings.

### Second remediation round (post re-run of `/speckit-analyze`, 2026-07-24)

A re-analysis of the fixes above found one new HIGH-severity defect **in the E1 fix itself**, and one
MEDIUM-severity robustness refinement to the F1 fix. Only the HIGH item was fixed, per the same
HIGH/CRITICAL-only scope as the first round:

- **F2 (HIGH — the E1 fix's `drv.capture_calls == 2` assertion was itself wrong)**: `capture_calls`
  as a flat total-call counter cannot distinguish "2 captures because nothing extra happened" from "4
  captures because `StabilityEngine.wait_stable()`'s own internal polling loop (unrelated to this
  feature, called once after every action) issued 2 more of its own." T009 now uses an ordered
  `call_log` on `FakeVNC` instead, and asserts the 5 `"key:backspace"` entries are *contiguous* with
  no `"capture"` entry between the first and last — this proves the actual requirement (no screenshots
  *between* individual sends) without hardcoding a total that depends on `StabilityEngine`'s unrelated
  polling config.
- **G2 (MEDIUM — flat timeout margin doesn't scale with `repeat_count`)**: intentionally left
  unchanged — a robustness refinement, not a blocking defect, per the user's HIGH/CRITICAL-only
  scope.

### Implementation notes (`/speckit-implement`, 2026-07-24)

Two things discovered while executing T001–T019, neither requiring a spec/plan change:

- **Task-graph gap**: T013 (`agent_runtime.py`) reads `step.batch_repeat_key`, which T015
  (`domain/testcase.py`, nominally Phase 4/US2) defines — a dependency the Dependencies section above
  didn't capture (it says US2 is independent of Phase 3). T014/T015 were implemented ahead of their
  nominal phase position, immediately before T013, so T013's code has something to read. All of
  T014/T015's own tests were still written first and observed failing before T015's implementation —
  TDD was preserved, just the *phase ordering* shifted.
- **Regression found and fixed during T013**: the first version of T013's `executor.execute(...)` call
  always passed `timeout_seconds=...` as a keyword argument (`None` for non-batch actions). This broke
  three pre-existing e2e tests
  (`test_scenario_10_no_duplicate_action.py`, `test_scenario_13_pos_bag_regression.py`,
  `test_scenario_14_focus_path_runtime_wiring.py`) that monkey-patch `runtime.executor.execute` with a
  single-argument replacement — the new kwarg doesn't match that narrower signature, so the patched
  call raised `TypeError`, silently swallowed by the existing generic `except Exception` handler,
  producing 0 execute calls instead of the expected 1. Fixed by branching in `run_action_iteration()`:
  `press_key_repeat` actions call `execute(executable, timeout_seconds=...)`; every other operation
  calls `execute(executable)` with the exact original single-argument signature, byte-for-byte
  unchanged. Full suite re-run confirmed 0 regressions after the fix (395 passed, 1 skipped).
- **T020 side-fix**: `pos-scan-magazine-checkout.yaml`'s `clear_barcode` `action_tags` matcher was
  `action_type: press_key` — since the step's executed action is now `press_key_repeat`, that matcher
  would have silently stopped matching (breaking the tag's report count). Updated the matcher to
  `action_type: press_key_repeat` in the same edit.

## Phase 8: Convergence

**Purpose**: Close a gap found by `/speckit-converge` (2026-07-24) between what FR-009/SC-004 and
plan.md's Testing constraint require and what the existing test suite actually exercises.

- [X] T026 Add a test to `vnc_agent/tests/unit/test_execution_router_batch_repeat.py` proving
      `ExecutionRouter.execute()`'s actual timeout behavior for a `press_key_repeat` action — not just
      `compute_batch_repeat_timeout_seconds()` in isolation — per FR-009 / SC-004 (missing test
      coverage for the timeout interruption path noted in the F1 remediation, `partial`): (a) construct
      an `ExecutableAction(operation="press_key_repeat", repeat_count=50, repeat_interval_ms=500)`,
      stub `KeyboardExecutor.press_key_repeat` with a simulated duration that exceeds the router's
      *static* `default_timeout_seconds` (10s) but stays under the *dynamically computed* timeout
      (`compute_batch_repeat_timeout_seconds(50, 500, 10.0)`), call
      `router.execute(action, timeout_seconds=compute_batch_repeat_timeout_seconds(...))`, and assert
      it completes successfully (`success is True`) — proving the dynamic-timeout wiring actually
      prevents a timeout for the legal worst-case batch, not just that the helper function returns a
      larger number in isolation; (b) construct a second case whose simulated duration exceeds even
      the dynamically computed timeout, and assert `execute()` returns `ExecutionResult(success=False,
      timed_out=True, error_code="timeout")` with `requested_count is None` and `completed_count is
      None` — documenting and verifying the current, accepted behavior (a genuine hang past the sized
      timeout does not preserve partial-progress counts) rather than leaving it unverified.

## Phase 9: Convergence

**Purpose**: Close a gap found by `/speckit-converge` (2026-07-24) between FR-004's "...or is
interrupted" clause / Constitution Principle IV and what the test suite actually exercises at the
`AgentRuntime` level.

- [X] T027 Add an e2e test (new function in `vnc_agent/tests/e2e/test_scenario_16_batch_repeat_key.py`,
      or a new file following the same pattern) proving that when a declared `batch_repeat_key` step's
      execution is interrupted, the runtime still performs exactly one post-action stability wait and
      verification per FR-004 ("...after the batch repeat completes **or is interrupted**") and
      Constitution Principle IV (verification MUST be based on independently re-captured post-action
      evidence, never skipped just because the action reported failure) — `partial`, since this is
      already true structurally (`ExecutionRouter.execute()` catches `KeyRepeatSendError`/
      `asyncio.TimeoutError` internally and always returns a normal `ExecutionResult`, so
      `agent_runtime.py`'s `except Exception` early-return that skips WAITING/VERIFYING is never
      triggered for an interrupted batch) but is unverified by any test above the router/executor unit
      level. Using `build_runtime()`/`FakeVNC` (extend `FakeVNC.send_key` to raise after N calls, or
      reuse a similar fault-injection pattern to T016's), run a `TestCase`/`TestStep` declaring
      `batch_repeat_key` against a driver whose `send_key` fails partway through, then assert on the
      resulting single `ActionIteration`: `execution_result.success is False`,
      `execution_result.requested_count`/`.completed_count` match the injected failure point,
      `wait_result is not None` (the post-action stability wait ran), and `verification_result is not
      None` (post-action verification ran) — all within the same one iteration, not a retried second
      one. **Depends on**: existing `FakeVNC`/`build_runtime()` fixtures (`tests/e2e/conftest.py`,
      already extended by T009) and the fail-fast implementation (T018/T019, already complete).
