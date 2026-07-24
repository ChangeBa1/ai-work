---

description: "Task list template for feature implementation"
---

# Tasks: 修复键盘文本输入能力（type_text 驱动缺陷）

**Input**: Design documents from `/specs/006-fix-keyboard-text-input/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/text-input-contract.md,
quickstart.md

**Tests**: Explicitly requested (TDD) by the user for this feature — test tasks are included and
MUST be written and confirmed failing before the implementation task.

**Organization**: Tasks are grouped by user story (US1/US2/US3 from spec.md), in priority order.

**Path note**: The regression test file lives at
`vnc_agent/tests/integration/test_vncdotool_text_input.py`. It was originally requested at
`vnc_agent/tests/unit/test_vncdotool_text_input.py`, but during implementation
`tests/unit/test_no_real_vnc_in_offline_tests.py` (a pre-existing Feature 003 guard test) was found
to statically forbid importing/constructing the real `VNCToolDriver`/`vncdotool` in
`tests/unit/`, `tests/fixtures/`, or `tests/e2e/` — only `tests/integration/` is exempt. Since this
test must construct a real `VNCToolDriver` (the bug lives inside its `_sync_text` method; a
mock/fake driver would not exercise the actual defect), it was moved to `tests/integration/` to
comply with that existing rule rather than weakening the guard test. No live VNC connection is
required either way — a fake client is still injected, per research.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Tasks touching the same file are never marked `[P]`, even if otherwise independent, to avoid
  edit conflicts.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the one shared test fixture every subsequent test task appends to.

- [X] T001 Create `vnc_agent/tests/integration/test_vncdotool_text_input.py` with a `FakeKeyPressClient`
      test double that implements and records `keyPress(key: str)` calls (append each call's `key`
      argument, in order, to a `self.calls: list[str]` attribute) and **deliberately does not
      define `type` or `paste`**, matching the real `VNCDoToolClient` surface confirmed in
      `research.md` (`keyPress`/`keyDown`/`keyUp`/`paste` exist, `type` does not). Add a helper to
      build a `VNCToolDriver("test-host")` with `driver._client = <FakeKeyPressClient instance>` and
      `driver._connected = True` set directly (bypassing `connect()`), since `_ensure()` in
      `vnc_agent/src/vnc_agent/drivers/vncdotool_driver.py` requires both to be set before returning
      the client. No test functions yet — this task only creates the file, imports, and the fixture
      helper(s).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented.

No additional foundational tasks for this fix — T001's fake client harness is the only shared
prerequisite, and it already lives in Setup. Proceed directly to Phase 3.

**Checkpoint**: Foundation ready — user story test-writing can begin.

---

## Phase 3: User Story 1 - 已聚焦输入控件的普通文本输入按序正确送达 (Priority: P1) 🎯 MVP

**Goal**: `type_text` sends the declared text to the focused control in original character order,
correctly handling the exact accident payload (`"45127366"`) and mixed ASCII content.

**Independent Test**: Run `pytest vnc_agent/tests/integration/test_vncdotool_text_input.py -k US1 -v` — the
fake client's recorded `keyPress` calls must equal the declared text's characters, in order, with no
`AttributeError`.

### Tests for User Story 1 (write first — MUST fail against the current implementation)

- [X] T002 [US1] In `vnc_agent/tests/integration/test_vncdotool_text_input.py`, add
      `test_types_pure_digit_string_sends_ordered_keypresses`: call `_sync_text("45127366")` on the
      driver built in T001, then assert `fake_client.calls == ["4", "5", "1", "2", "7", "3", "6",
      "6"]`. This reproduces the exact accident payload from run
      `18ba967a-822c-4860-a90d-d8e849205a75` and MUST currently fail with
      `AttributeError: 'FakeKeyPressClient' object has no attribute 'type'` (or equivalent), matching
      the original `ExecutionResult.error_message`.
- [X] T003 [US1] In the same file, add `test_types_mixed_ascii_letters_digits_punctuation_in_order`:
      call `_sync_text("Ab12-_.@")` and assert `fake_client.calls == ["A", "b", "1", "2", "-", "_",
      ".", "@"]`, in that exact order. MUST currently fail the same way as T002.

### Implementation for User Story 1

- [X] T004 [US1] Fix `_sync_text` in `vnc_agent/src/vnc_agent/drivers/vncdotool_driver.py` (currently
      lines 187-195): replace the `else: client.type(ch)` fallback branch with
      `else: client.keyPress(ch)`. Do not change the `if ch == "\n": client.keyPress("enter")` or
      `elif ch == "\t": client.keyPress("tab")` branches — leave them exactly as-is. Do not add any
      try/except around the loop (research.md: exceptions must propagate unmodified). Depends on
      T002 and T003 existing and failing first.
- [X] T005 [US1] Run `pytest vnc_agent/tests/integration/test_vncdotool_text_input.py -v` and confirm T002
      and T003 now pass with no `AttributeError`.

**Checkpoint**: User Story 1 is fully functional — ordered, complete text delivery works for the
accident payload and for general ASCII content. This is the MVP.

---

## Phase 4: User Story 2 - 换行与 Tab 的既有语义保持不变 (Priority: P2)

**Goal**: Prove the newline→Enter / Tab→next-control semantics (already correct before this fix)
remain correct after T004's change, including at boundaries and with consecutive occurrences.

**Independent Test**: Run `pytest vnc_agent/tests/integration/test_vncdotool_text_input.py -k US2 -v` — all
newline/Tab cases resolve to named `keyPress("enter")`/`keyPress("tab")` calls, never a literal
character.

### Tests for User Story 2 (regression guards — should already pass once T004 lands)

- [X] T006 [US2] In `vnc_agent/tests/integration/test_vncdotool_text_input.py`, add
      `test_newline_maps_to_enter_keypress`: call `_sync_text("a\nb")` and assert
      `fake_client.calls == ["a", "enter", "b"]`.
- [X] T007 [US2] In the same file, add `test_tab_maps_to_tab_keypress`: call `_sync_text("a\tb")`
      and assert `fake_client.calls == ["a", "tab", "b"]`.
- [X] T008 [US2] In the same file, add
      `test_consecutive_and_trailing_newline_tab_trigger_each_occurrence` (spec.md Edge Cases): call
      `_sync_text("\n\n\t\t")` and assert `fake_client.calls == ["enter", "enter", "tab", "tab"]`
      (covers both "consecutive" and "no trailing occurrence is dropped").

**Checkpoint**: Run T006-T008 — all pass without further code changes (they exercise branches T004
did not touch), confirming no regression was introduced in the already-correct newline/Tab paths.

---

## Phase 5: User Story 3 - 空文本与中途失败的结果必须真实可信 (Priority: P2)

**Goal**: Empty text is a true no-op success; a mid-send driver failure stops immediately and is
reported as failure with a diagnosable message — never partial success.

**Independent Test**: Run `pytest vnc_agent/tests/integration/test_vncdotool_text_input.py -k US3 -v` and
`pytest vnc_agent/tests/unit/test_execution_router_type_text.py -v`.

### Tests for User Story 3

- [X] T009 [US3] In `vnc_agent/tests/integration/test_vncdotool_text_input.py`, add
      `test_empty_string_sends_no_keypress_calls`: call `_sync_text("")` and assert
      `fake_client.calls == []` (zero calls). This already passes both before and after T004 — add
      it as an explicit, permanent regression guard for FR-006/SC-003.
- [X] T010 [US3] In the same file, add `test_mid_send_exception_stops_immediately_and_propagates`:
      extend `FakeKeyPressClient` (or add a second fake in this test) so `keyPress` raises
      `RuntimeError("simulated driver failure")` on its 3rd call; call `_sync_text("abcdef")` inside
      `pytest.raises(RuntimeError, match="simulated driver failure")`; after the exception, assert
      `fake_client.calls == ["a", "b"]` (exactly two successful calls before the raise, nothing sent
      after — no 3rd/4th/... character reaches `keyPress`). MUST currently fail against the
      unfixed code (it hits the `AttributeError` from `client.type(ch)` on the very first non-mapped
      character instead of the intended injected `RuntimeError`, so the `pytest.raises` match fails)
      — this is the mid-send fail-fast proof required by FR-007/FR-008.
- [X] T011 [P] [US3] Create `vnc_agent/tests/unit/test_execution_router_type_text.py` (new file,
      following the pattern of `vnc_agent/tests/unit/test_execution_router_batch_repeat.py`): build
      an `ExecutionRouter` with an `AsyncMock` driver whose `send_text` is configured with
      `side_effect=RuntimeError("driver keyPress failed")`; call
      `await router.execute(ExecutableAction(method="keyboard", operation="type_text",
      text="45127366"))`; assert `result.success is False`, `result.error_code == "error"`, and
      `"driver keyPress failed" in result.error_message` (diagnosable, not empty/generic). This
      confirms `ExecutionRouter`'s existing generic-exception path correctly reports a driver-level
      text-send failure — the router itself needs no code change, only this new coverage.
- [X] T012 [P] [US3] Create `vnc_agent/tests/unit/test_keyboard_executor_type_text.py` (new file,
      following the pattern of `vnc_agent/tests/unit/test_keyboard_executor_repeat.py`): with an
      `AsyncMock` driver, assert `KeyboardExecutor.type_text("")` calls `driver.send_text("")` exactly
      once and does not raise; and separately, with `driver.send_text` configured to raise
      `RuntimeError("boom")`, assert `await executor.type_text("x")` propagates that same
      `RuntimeError` unmodified out of `type_text` (confirms the pass-through contract in
      `contracts/text-input-contract.md` is unchanged by this fix).

**Checkpoint**: Run T009-T012 — all pass. Empty-input and mid-send-failure behavior is now both
correct and covered at the driver, executor, and router layers.

---

## Phase 6: Cross-Scenario Contract Coverage (constitution Principle VI / FR-016 / SC-006)

**Goal**: Prove the fix is a generic capability, not adapted to the barcode scenario specifically,
via a second, unrelated scenario at the same fake-client test tier (Clarification Session
2026-07-24, Q2) — the live-VNC confirmation of the first (real) scenario happens later, in Phase 7.

- [X] T013 [US1] In `vnc_agent/tests/integration/test_vncdotool_text_input.py`, add
      `test_generic_text_input_in_unrelated_synthetic_context`: call `_sync_text("user.name-01@test")`
      (a value unrelated to any barcode/scanner context — e.g. representing a generic
      email-like/account field) on a **freshly constructed** driver/fake-client pair (not reusing
      state from other tests), and assert `fake_client.calls` equals that string's characters in
      order. This must be the same, unmodified `_sync_text` code path used by T002/T003/T010 — no
      branching on which text/context is passed.

**Checkpoint**: Two unrelated scenarios now pass at this tier (T002/T003's barcode-accident payload,
T013's unrelated synthetic payload), satisfying FR-016/SC-006 pending the live-VNC leg in Phase 7.

---

## Phase 7: Full Regression, Dry-Run, and Live Verification

**Purpose**: Confirm no regressions elsewhere, and close the loop on the original accident with a
real VNC run. Sequential — each task depends on the previous succeeding.

- [X] T014 Run the new/changed test files together:
      `cd vnc_agent && pytest tests/integration/test_vncdotool_text_input.py
      tests/unit/test_execution_router_type_text.py tests/unit/test_keyboard_executor_type_text.py -v`
      — confirm all tests from T002-T013 pass.
- [X] T015 Run the full existing test suite: `cd vnc_agent && pytest tests/unit tests/integration
      tests/e2e -q` — confirm no pre-existing test regresses, in particular
      `tests/e2e/test_scenario_02_keyboard_first.py`, `tests/unit/test_keyboard_executor_repeat.py`,
      and `tests/unit/test_execution_router_batch_repeat.py` (the pre-existing `press_key`/`hotkey`/
      `press_key_repeat` paths sharing the same driver/router/executor files).
- [X] T016 Dry-run validate the untouched testcase:
      `cd vnc_agent && vnc-agent run testcases/pos-scan-magazine-checkout.yaml --dry-run` — confirm
      it prints `OK: test case ... is valid` and exits successfully, and confirm via
      `git diff --stat vnc_agent/testcases/pos-scan-magazine-checkout.yaml` that the file shows no
      changes (FR-011: the formal testcase is never modified to work around the driver defect).
- [X] T017 (Requires a live Windows VNC target reachable per
      `vnc_agent/config/vnc-targets.yaml`, target `win10-test-01`, with `VNC_AGENT_VNC_PASSWORD` set,
      and ScannerSimulator showing the default barcode `2000900010268`) Run:
      `VNC_AGENT_VNC_PASSWORD=*** vnc-agent run testcases/pos-scan-magazine-checkout.yaml --target
      win10-test-01`. Inspect the generated HTML/JSON report and confirm all of:
      (a) `focus-barcode-field` passed (double-click full-select of the original barcode);
      (b) `type-barcode-45127366` passed, with its own independent post-action visual verification
      confirming the Barcode field shows exactly `45127366` — not merely
      `execution_result.success == true` (SC-001);
      (c) `click-scan-button` was reached and executed (previously never run because the case
      aborted at the prior step);
      (d) subsequent steps in the case continued to execute rather than stopping;
      (e) no step's final Barcode-field evidence shows the stale `2000900010268` value.

      **Executed** (run `46c898a4-9f83-4f46-a449-1614a012eac7` against `win10-test-01`,
      2026-07-24): (a)-(d) all confirmed — `open-task-view`, `select-scanner-simulator`,
      `focus-barcode-field`, `type-barcode-45127366`, `click-scan-button`, and
      `return-to-pos-via-task-view` all `passed`; `type-barcode-45127366`'s
      `execution_result.success == true` AND its independent OCR-based verification separately
      confirmed the Barcode field text is exactly `45127366` (position-anchored OCR match, not a
      self-reported flag). (e) confirmed — the field's own OCR match shows only `45127366`, not the
      stale `2000900010268` (that string only appears in unrelated Favorite-list OCR diff noise
      elsewhere on screen, not in the Barcode field itself). The case's final step,
      `select-pos-main`, failed for an unrelated reason (ScannerSimulator window remained in
      foreground instead of returning to the POS main screen) — a window-navigation issue outside
      this feature's scope (this fix only concerns the `type_text` execution path), not a
      regression from this change.
- [X] T018 Confirm business-agnostic core (constitution Principle VI, FR-014): run
      `grep -rniE "barcode|scannersimulator|45127366|\bpos\b" vnc_agent/src/vnc_agent/drivers/vncdotool_driver.py
      vnc_agent/src/vnc_agent/execution/router.py vnc_agent/src/vnc_agent/execution/keyboard_executor.py
      vnc_agent/src/vnc_agent/runtime/exceptions.py` and confirm it returns no matches — the fix
      introduced no business-specific field, keyword, or branch into any core module.

      **Executed**: 0 matches (word-boundary-safe `\bpos\b` added per the `/speckit-analyze` G1
      finding, to actually check "POS" as originally requested rather than only
      barcode/scannersimulator/45127366). Also confirmed `git status --porcelain vnc_agent/.venv`
      shows no changes (FR-012 — site-packages untouched; only `Read`, never `Edit`/`Write`, was used
      on any file under `.venv/Lib/site-packages` during this implementation).

**Checkpoint**: All phases complete. The original accident (run
`18ba967a-822c-4860-a90d-d8e849205a75`) is reproduced as a failing test (T002/T010 pre-fix) and
resolved end-to-end, both offline (T014-T015) and live (T017), with the business-agnostic-core
constraint verified (T018).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Empty for this feature — no gate beyond Setup.
- **User Story 1 (Phase 3)**: Depends on T001. Tests (T002, T003) before implementation (T004)
  before confirmation (T005) — strict TDD order, all same-file/same-method so fully sequential.
- **User Story 2 (Phase 4)**: Depends on T004 (the fix) having landed, so the regression guards run
  against final code; T006-T008 are otherwise independent of Phase 3's specific assertions.
- **User Story 3 (Phase 5)**: T009-T010 depend on T004 (same file, sequential edits). T011 and T012
  depend only on `ExecutionRouter`/`KeyboardExecutor` already existing (unchanged) — no dependency on
  T004, so they may start as soon as Phase 1 is done, but are listed here for grouping by story.
- **Phase 6 (T013)**: Depends on T004 (same file as T002/T003/T010, sequential edits) and logically
  extends US1.
- **Phase 7 (T014-T018)**: Depends on all of Phases 3-6 being complete; strictly sequential
  (T014 → T015 → T016 → T017 → T018).

### Within Each User Story

- Tests MUST be written and confirmed failing before T004 (the only implementation task).
- All test-writing tasks in `test_vncdotool_text_input.py` (T002, T003, T006-T010, T013) touch the
  same file and are therefore sequential, not parallel, regardless of story grouping.
- Story complete before moving to full-suite verification (Phase 7).

### Parallel Opportunities

- T011 and T012 are in different, new files with no dependency on each other or on the
  `test_vncdotool_text_input.py` edits — they can be done in parallel with each other and with any
  of T002/T003/T006-T010/T013.
- No other pair of tasks is safely parallel: every other test task edits the same file
  (`test_vncdotool_text_input.py`), and T004/T005 have a hard TDD ordering dependency on T002/T003.

---

## Parallel Example: User Story 3

```bash
# T011 and T012 touch different, independent new files and can be done in parallel:
Task: "Create vnc_agent/tests/unit/test_execution_router_type_text.py"
Task: "Create vnc_agent/tests/unit/test_keyboard_executor_type_text.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001).
2. Complete Phase 2: none required.
3. Complete Phase 3 (T002-T005) — this alone fixes the reported accident for the general
   printable-ASCII/digit case.
4. **STOP and VALIDATE**: `pytest vnc_agent/tests/integration/test_vncdotool_text_input.py -v`.

### Incremental Delivery

1. Phase 1 → Phase 3 (US1, MVP) → Phase 4 (US2 regression guards) → Phase 5 (US3 no-op/fail-fast
   guarantees) → Phase 6 (cross-scenario contract proof) → Phase 7 (full regression, dry-run, live
   confirmation, business-agnostic-core check).
2. Each phase adds verification value without requiring the next phase to be considered "done" for
   its own acceptance scenarios.

---

## Notes

- `[P]` tasks = different files, no dependencies. All other tasks either share a file
  (`test_vncdotool_text_input.py`) or have an explicit TDD ordering dependency, so they are marked
  sequential even where the underlying logic is otherwise independent.
- Verify T002, T003, and T010 actually fail before starting T004 — this is the TDD proof requested
  for this feature (and doubles as SC-005's "regression test reproduces the original failure mode").
- Commit after each checkpoint (end of each phase), not after every single task.
- Only one production file changes in this entire task list:
  `vnc_agent/src/vnc_agent/drivers/vncdotool_driver.py` (T004). No other `src/` file is touched.
