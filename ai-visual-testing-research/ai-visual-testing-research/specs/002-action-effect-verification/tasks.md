# Tasks: 自适应动作效果检测与可信业务验证

**Input**: Design documents from `specs/002-action-effect-verification/`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user stories), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included. spec.md explicitly requires offline regression tests reproducing the
production incident (FR-029~031, US8) and every P1/P2 user story's Independent Test is
phrased as a fixed-screenshot/mocked test; tests are written before their corresponding
implementation within each story.

**Organization**: Tasks are grouped by user story (spec.md priorities). All file paths are
repository-root-relative (the project lives under `vnc_agent/`).

> **Revision note (post `/speckit-analyze`)**: this version adds T015, T023, T039, T057
> (new coverage for the HIGH/MEDIUM findings F1–F4/F6) and edits T021, T026, T041, T063
> (F2/F5) relative to the previous draft. All task IDs after T014 have shifted; do not
> reuse old IDs from prior conversation history.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependency)
- **[Story]**: Maps the task to spec.md's US1–US8
- Every task names an exact file path

## Path Conventions

Single project (`vnc_agent/`), per plan.md Project Structure:
- Domain models: `vnc_agent/src/vnc_agent/domain/`
- Perception: `vnc_agent/src/vnc_agent/perception/`
- Planning/Execution/Verification/Recovery/Runtime/Reporting: `vnc_agent/src/vnc_agent/{planning,execution,verification,recovery,runtime,reporting}/`
- Tests: `vnc_agent/tests/{fixtures,unit,e2e}/`

---

## Phase 1: Setup

**Purpose**: Shared configuration surface needed by every later story; no new dependencies
are introduced (plan.md Technical Context).

- [x] T001 Add `error_keywords: list[str]` and `local_blob_min_ratio: float` fields (with
      defaults `["错误","エラー","Error","失败","失敗","Failed"]` and `0.0005`) to
      `PerceptionConfig` in `vnc_agent/src/vnc_agent/config.py`, and set matching defaults
      under `agent.perception` in `vnc_agent/config/agent.yaml`

**Checkpoint**: Config surface exists for later ActionEffect/error-popup work to read from.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: New domain types and field additions that every user story (US1–US8) imports.
No story-specific behavior lives here — only data shapes and load/storage plumbing.

**⚠️ CRITICAL**: No user story implementation may begin until this phase is complete.

- [x] T002 [P] Define `ActionEffectStatus` (`no_effect`/`expected_effect`/
      `unexpected_effect`/`effect_uncertain`), `ActionEffectEvidence`, and `ActionEffect`
      Pydantic models in `vnc_agent/src/vnc_agent/domain/action_effect.py` per
      data-model.md §3
- [x] T003 [P] Define `VerifiedFocusNavigationPath` Pydantic model in
      `vnc_agent/src/vnc_agent/domain/focus_path.py` per data-model.md §8
- [x] T004 [P] Define `RepeatGuardDecision` Pydantic model in
      `vnc_agent/src/vnc_agent/domain/repeat_guard.py` per data-model.md §6
- [x] T005 [P] Add optional `action_kind: Literal["idempotent","non_idempotent"] | None`
      field to `SemanticAction` in `vnc_agent/src/vnc_agent/domain/action.py` per
      data-model.md §5
- [x] T006 [P] Add `weak_assertion_warning: bool = False` and
      `basis: Literal["business_assertion","action_effect_only","mixed"]` fields to
      `VerificationResult` in `vnc_agent/src/vnc_agent/domain/verification.py` per
      data-model.md §4
- [x] T007 Add optional `verification_mode: Literal["business","effect_only"] | None`
      field to `TestStep` in `vnc_agent/src/vnc_agent/domain/testcase.py` per
      data-model.md §1 (schema only, no validation logic yet)
- [x] T008 Implement load-time validation in `load_test_case()` in
      `vnc_agent/src/vnc_agent/domain/testcase.py`: when a step's `verification_mode ==
      "business"` and `expected.conditions` contains only `screen_changed`/
      `region_changed` types, raise `FieldValidationError` pointing at
      `steps[i].expected.conditions` (FR-008, contracts/test-case-schema-delta.md);
      `verification_mode == "effect_only"` or omitted MUST NOT be rejected (depends on T007)
- [x] T009 Add `action_effect: ActionEffect | None` and
      `repeat_guard_decision: RepeatGuardDecision | None` fields to `ActionIteration` in
      `vnc_agent/src/vnc_agent/domain/run.py` per data-model.md §6 (depends on T002, T004)
- [x] T010 Add nullable `action_effect_json` and `repeat_guard_decision_json` columns for
      the `ActionIteration` persistence mapping in
      `vnc_agent/src/vnc_agent/storage/repositories.py` (plan.md Technical Context
      §Storage; depends on T009)

**Checkpoint**: All new domain types compile and import cleanly; existing 001 tests still
pass (`pytest -q` from `vnc_agent/`). User story implementation can now begin.

---

## Phase 3: User Story 1 - 发现任意位置的局部画面变化以确认动作已产生效果 (Priority: P1) 🎯 MVP

**Goal**: Decouple "local evidence exists" from "global pixel ratio meets threshold" so
that the original incident's 0.424% global-change click is correctly classified as
`expected_effect`, anywhere on screen, without pre-configured ROIs.

**Independent Test**: Fixed before/after screenshot pairs (including the original incident's
~0.424% global / local cart-region case) drive `classify_action_effect()` directly and
assert `expected_effect`, with no VNC connection required.

### Tests for User Story 1

- [x] T011 [P] [US1] Test: 1024×1568 frame pair with ~0.424% global diff ratio but a local
      cart-badge region change → `classify_action_effect(...).status == "expected_effect"`
      (also assert `global_diff_ratio < 0.02` to prove the incident condition is
      reproduced) in `vnc_agent/tests/fixtures/test_action_effect.py`
- [x] T012 [P] [US1] Test: local change injected at each of nine grid positions (none
      pre-configured as ROI) → all nine classify as `expected_effect` (SC-005) in
      `vnc_agent/tests/fixtures/test_action_effect.py`
- [x] T013 [P] [US1] Test: list-update, form-update, and page-navigation frame pairs (three
      of the four SC-006 scenarios; dialog-appear is covered under US4) →
      `expected_effect` in `vnc_agent/tests/fixtures/test_action_effect.py`
- [x] T014 [P] [US1] Test: identical before/after frames → `no_effect`; and a frame pair
      with only OCR text change (no pixel blob above threshold, no template change) →
      `expected_effect` via the OCR-diff signal in
      `vnc_agent/tests/fixtures/test_action_effect.py`
- [x] T015 [P] [US1] Test (F4, FR-005/Edge Cases §1): local pixel change confined entirely
      within a configured dynamic-noise-mask region (e.g. the taskbar clock area) →
      `classify_action_effect(...).status == "no_effect"`, not `expected_effect`,
      proving noise exclusion applies to the new local-evidence path (not just to the
      pre-001 stability-wait masking) in `vnc_agent/tests/fixtures/test_action_effect.py`

### Implementation for User Story 1

- [x] T016 [US1] Modify `compute_diff()` in `vnc_agent/src/vnc_agent/perception/screen_diff.py`
      so contour/connected-component detection runs unconditionally (not gated behind
      `ratio >= threshold`); return an additional `local_blobs: list[Region]` value
      filtered only by a per-blob minimum size, independent of the global `threshold`;
      confirm the existing `mask_regions` zeroing (already applied to `thresh` before
      contour extraction) now also gates `local_blobs`, not just the global ratio
      (research.md §1; covers T015)
- [x] T017 [US1] Update `assemble_structured_screen()` in
      `vnc_agent/src/vnc_agent/perception/structured_screen.py` to keep
      `StructuredScreen.changed_since_last`/`changed_regions` as the existing global weak
      signal while separately threading through the new `local_blobs` for downstream
      ActionEffect use (depends on T016)
- [x] T018 [US1] Implement `classify_action_effect(before, after, *, intent, mask_regions,
      local_blob_min_ratio, error_keywords)` core combination logic (local blobs + OCR
      added/removed + template added/removed + structured-state diff, excluding dynamic
      noise regions reusing `perception/stability.py`'s masking) in
      `vnc_agent/src/vnc_agent/perception/action_effect.py` per research.md §2 steps
      2/4/5 and contracts/action-effect-contract.md §1 (error-popup step 3 stubbed to
      always return `"none"`, implemented in US4); depends on T002, T017
- [x] T019 [US1] Run T011–T015, fix `classify_action_effect()`/`compute_diff()` until all
      pass

**Checkpoint**: `classify_action_effect()` correctly reproduces the incident's core
misjudgment fix, including dynamic-noise exclusion. Independently testable and demoable
without any other story.

---

## Phase 4: User Story 2 - 效果已确认但业务结果未定时，先加强验证，不重复执行非幂等动作 (Priority: P1)

**Goal**: Stop the runtime from sending a second "add to bag" click when the first click's
effect is already known and the business result is merely undetermined; escalate to
re-observation and (if needed) a visual-model question instead. Also settles what happens
when a deterministic assertion and a visual-model answer disagree.

**Independent Test**: A mocked `PlannerProvider` proposes the same semantic click twice in a
row against a fixed frame sequence showing bag-count 0→1; assert the execution router's
`execute()` is invoked exactly once for that action, with escalation taking its place the
second time.

### Tests for User Story 2

- [x] T020 [P] [US2] Test: `classify_action_kind()` recognizes default keywords (加入/添加/
      レジ袋/add, 删除/remove, 提交/submit, 支付/pay) as `non_idempotent`, an unrelated
      intent with no keyword match also defaults to `non_idempotent` (conservative
      fallback, research.md §3) in `vnc_agent/tests/unit/test_action_kind_classification.py`
- [x] T021 [P] [US2] Test: `RepeatGuard.check()` — first iteration always `allowed=True`;
      same non-idempotent semantic action after `expected_effect`/`effect_uncertain` with
      `uncertain` verification is `allowed=False`; an idempotent action is never blocked;
      a *different* target/intent is never blocked; **and** (F2, FR-016) when the
      previous iteration's `ActionEffect` has been reliably re-confirmed as `no_effect`
      (after strengthened verification) and the step's retry budget remains, `check()`
      returns `allowed=True, reason="no_effect_confirmed"` — this positive branch MUST be
      exercised, not just the blocking branches — in
      `vnc_agent/tests/fixtures/test_repeat_guard.py`
- [x] T022 [P] [US2] Test: `resolve_step_result()` escalation — when the business result is
      `uncertain` after the first evaluation, `reobserve` and (mocked)
      `describe_screen` are each called at most once before a final `uncertain` is
      returned, and no `ExecutableAction` is triggered by the resolver itself in
      `vnc_agent/tests/fixtures/test_business_resolver.py`
- [x] T023 [P] [US2] Test (F1, FR-010/SC-010): `resolve_step_result()` — a step whose
      `expected` contains both a deterministic business assertion (e.g. `text_appears`)
      and a `visual_question` condition: when the deterministic assertion evaluates to
      `failed` and the mocked visual model answers `passed`, the final `status` is
      `failed` (deterministic wins); when the deterministic assertion evaluates to
      `passed` and the mocked visual model answers `failed`/`uncertain`, the final
      `status` is still `passed` — the visual model's conflicting answer MUST NOT
      override an already-conclusive deterministic result, in
      `vnc_agent/tests/fixtures/test_business_resolver.py`

### Implementation for User Story 2

- [x] T024 [US2] Implement `classify_action_kind()` in
      `vnc_agent/src/vnc_agent/planning/action_classification.py` (configurable keyword
      table + conservative `non_idempotent` fallback, research.md §3); depends on T005
- [x] T025 [US2] Implement `RepeatGuard.check()` in
      `vnc_agent/src/vnc_agent/execution/repeat_guard.py` per
      contracts/action-effect-contract.md §3, including the `no_effect_confirmed`
      positive-permission branch (F2) (depends on T002, T004, T024)
- [x] T026 [US2] Implement `resolve_step_result()`'s escalation path (reobserve +
      deterministic re-evaluation, optional `describe_screen` visual-question fallback)
      **and** the deterministic-over-visual conflict-resolution rule (F1) — when a
      deterministic assertion and a visual-model answer are both present and disagree,
      the deterministic assertion's result MUST be returned unchanged — in
      `vnc_agent/src/vnc_agent/verification/business_resolver.py` per research.md §5/§8
      and contracts/action-effect-contract.md §2 (depends on T002, T006)
- [x] T027 [US2] Update `classify_action_no_effect()` in
      `vnc_agent/src/vnc_agent/recovery/classifier.py` to accept an `ActionEffect`
      instead of a bare `bool`: `no_effect` → `FailureType.ACTION_NO_EFFECT`,
      `unexpected_effect` → `FailureType.UNEXPECTED_DIALOG`, `effect_uncertain` → no
      classification (left to RepeatGuard/business_resolver) per data-model.md §10;
      depends on T002
- [x] T028 [US2] Wire `RepeatGuard.check()` and
      `business_resolver.resolve_step_result()` into `run_action_iteration()` in
      `vnc_agent/src/vnc_agent/runtime/agent_runtime.py`, replacing the old
      `not after.changed_since_last` → `ACTION_NO_EFFECT` shortcut, per
      contracts/action-effect-contract.md §5 call-order invariant; depends on T018 (US1),
      T025, T026, T027
- [x] T029 [US2] Run T020–T023, fix implementation until all pass
- [x] T030 [US2] E2E test: fixed frame sequence where bag count goes 0→1 on the first
      click; a mocked Planner proposes the identical "click レジ袋" action again on the
      next iteration → assert the mocked `ExecutionRouter.execute()` for that action is
      called exactly once across the whole run in
      `vnc_agent/tests/e2e/test_scenario_10_no_duplicate_action.py` (depends on T028)

**Checkpoint**: The reported duplicate-add bug is fixed, the RepeatGuard's positive
re-permission branch is verified, and the deterministic/visual conflict rule is
independently demoable/testable.

---

## Phase 5: User Story 3 - 正式业务步骤要求独立的业务结果断言，screen_changed 不能单独通过 (Priority: P1)

**Goal**: `screen_changed`-only formal business steps are rejected at load when explicitly
opted into strict mode, and never silently resolve to a trusted `passed` at runtime.

**Independent Test**: A newly authored step declaring `verification_mode: business` with
only `screen_changed` is rejected by `load_test_case()` before any execution begins; the
same step with an added business assertion loads and only passes when that assertion passes.

### Tests for User Story 3

- [x] T031 [P] [US3] Test: `verification_mode: business` step whose `expected.conditions`
      contains only `screen_changed`/`region_changed` → `load_test_case()` raises
      `FieldValidationError` naming `steps[i].expected.conditions` in
      `vnc_agent/tests/fixtures/test_testcase_loader.py`
- [x] T032 [P] [US3] Test: `verification_mode: business` step with `screen_changed` plus a
      `text_appears` business assertion → loads successfully in
      `vnc_agent/tests/fixtures/test_testcase_loader.py`
- [x] T033 [P] [US3] Test: `resolve_step_result()` — business assertion `passed` +
      `screen_changed` also `passed` → final `status="passed"`, `basis="mixed"`; business
      assertion `failed` (even with `screen_changed` `passed`) → final `status="failed"`,
      i.e. ActionEffect/weak evidence never overrides a failed business assertion in
      `vnc_agent/tests/fixtures/test_business_resolver.py`

### Implementation for User Story 3

- [x] T034 [US3] Implement the business-assertion-present branches of
      `resolve_step_result()`'s status/`basis` table (data-model.md §4 rows 1–3) in
      `vnc_agent/src/vnc_agent/verification/business_resolver.py` (depends on T026)
- [x] T035 [US3] Replace the direct `VerificationEngine.verify()` result with
      `business_resolver.resolve_step_result()` as the authoritative
      `StepVerificationResult` source inside `run_action_iteration()` in
      `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` (depends on T028, T034)
- [x] T036 [US3] Run T031–T033, fix implementation until all pass

**Checkpoint**: Formal business steps can no longer pass on `screen_changed` alone;
independently testable via the loader and `business_resolver` in isolation.

---

## Phase 6: User Story 4 - 错误弹窗不得因画面变化而使业务步骤通过 (Priority: P1)

**Goal**: An error popup — regardless of how much screen area it changes — is classified as
`unexpected_effect` and can never make a business step pass by itself; but a step whose
*actual business assertion* legitimately expects an error message must still evaluate
normally.

**Independent Test**: Fixed "click produced an error popup" screenshots (large global
change) classify as `unexpected_effect`, and an end-to-end run with such a popup never
resolves the step to `passed` on weak evidence alone — while a step that explicitly asserts
"error text appears" still evaluates and can pass on that assertion.

### Tests for User Story 4

- [x] T037 [P] [US4] Test: frame pair with an injected error-popup pattern (OCR keyword
      hit, large global diff ratio) → `classify_action_effect(...).status ==
      "unexpected_effect"` regardless of diff ratio magnitude in
      `vnc_agent/tests/fixtures/test_error_popup_classification.py`
- [x] T038 [P] [US4] Test: a legitimate large-change scenario (e.g. full page navigation
      after submit, no error keyword/template hit) → NOT classified as
      `unexpected_effect` (completes SC-006's fourth "dialog-appear"/navigation case) in
      `vnc_agent/tests/fixtures/test_error_popup_classification.py`
- [x] T039 [P] [US4] Test (F3, FR-021): a formal business step whose declared business
      assertion is itself `text_appears: "<error message>"` (the step legitimately
      expects an error dialog) — even though the after-frame's `ActionEffect` classifies
      as `unexpected_effect`, `resolve_step_result()` still evaluates that assertion
      normally and returns `status="passed"` when the error text is present, proving the
      `unexpected_effect` override does not blanket-reject steps with a real matching
      business assertion, in `vnc_agent/tests/fixtures/test_business_resolver.py`

### Implementation for User Story 4

- [x] T040 [US4] Implement `_classify_error_popup()` (OCR keyword list from
      `perception.error_keywords` + optional template match via
      `perception/template/matcher.py`) and wire it as step 3 of
      `classify_action_effect()` in `vnc_agent/src/vnc_agent/perception/action_effect.py`
      per research.md §6 (depends on T001, T018)
- [x] T041 [US4] Ensure `resolve_step_result()` treats `unexpected_effect` as
      `failed`/`uncertain` and never `passed` **only when weak evidence
      (`screen_changed`/`region_changed`) is the deciding factor** — a `text_appears` (or
      other) business assertion that actually matches the error content on screen MUST
      still be evaluated and MAY return `passed` (F3, FR-021) — in
      `vnc_agent/src/vnc_agent/verification/business_resolver.py` (FR-020/021; depends
      on T034, T040)
- [x] T042 [US4] Run T037–T039, fix implementation until all pass
- [x] T043 [US4] E2E test: fixed frame sequence where the action-after frame shows an
      error popup with a large global diff ratio → final `StepVerificationResult.status`
      is `failed` or `uncertain`, never `passed` in
      `vnc_agent/tests/e2e/test_scenario_11_error_popup_not_passed.py` (depends on T035,
      T041)

**Checkpoint**: The second half of the original incident (error popup wrongly passing) is
fixed, the legitimate-error-assertion edge case is verified, and both are independently
testable.

---

## Phase 7: User Story 5 - 鼠标点击只有在存在可验证的焦点导航路径时才允许退化为键盘操作 (Priority: P1)

**Goal**: Recovery can no longer blindly convert a click into `keys=["tab"]`; it must have
a `VerifiedFocusNavigationPath` (recorded sequence + a way to confirm it is still valid).

**Independent Test**: With `prefer_keyboard=True` and no focus-path evidence,
`ActionPolicy.resolve()` must not emit a Tab-press executable — verified with no real
keyboard/mouse execution.

### Tests for User Story 5

- [x] T044 [P] [US5] Test: `ActionPolicy.resolve(..., prefer_keyboard=True, focus_path=None)`
      for a `click` action does NOT return `outcome="focus"`/`keys=["tab"]`; it falls back
      to whatever the action would otherwise resolve to (OCR/template/grounding/
      `stop_recover`) in `vnc_agent/tests/unit/test_focus_path_gate.py`
- [x] T045 [P] [US5] Test: `ActionPolicy.resolve(..., prefer_keyboard=True, focus_path=<valid
      VerifiedFocusNavigationPath>)` returns `outcome="focus"` with
      `executable.keys == focus_path.tab_sequence` exactly in
      `vnc_agent/tests/unit/test_focus_path_gate.py`

### Implementation for User Story 5

- [x] T046 [US5] Change `ActionPolicy.resolve()`'s signature and `prefer_keyboard` branch
      in `vnc_agent/src/vnc_agent/planning/action_policy.py` to accept
      `focus_path: VerifiedFocusNavigationPath | None`, per
      contracts/action-effect-contract.md §4 (depends on T003)
- [x] T047 [US5] Implement focus-path construction (`structural_diff_confirmed` /
      `prior_successful_replay`) as part of the `switch_to_keyboard` side effect in
      `vnc_agent/src/vnc_agent/recovery/engine.py` and
      `vnc_agent/src/vnc_agent/recovery/strategies.py`; construction failure MUST leave
      `focus_path=None` for the next `ActionPolicy.resolve()` call (depends on T003)
- [x] T048 [US5] Update the `ActionPolicy.resolve()` call site in
      `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` to pass the recovery-constructed
      `focus_path` through (depends on T046, T047)
- [x] T049 [US5] Run T044–T045, fix implementation until all pass

**Checkpoint**: The recovery-triggered blind-Tab bug is fixed and independently testable
without executing any real key events.

---

## Phase 8: User Story 6 - 显式声明 effect-only 测试步骤 (Priority: P2)

**Goal**: Steps explicitly declaring `verification_mode: effect_only` may legitimately pass
on action-effect evidence alone, clearly labeled as such in reports.

**Independent Test**: An `effect_only` step with only `screen_changed` loads without
rejection and passes on `expected_effect` alone, with its report entry visibly distinct
from a business-assertion-backed pass.

### Tests for User Story 6

- [x] T050 [P] [US6] Test: `verification_mode: effect_only` step with only
      `screen_changed`, `expected_effect` observed → `resolve_step_result()` returns
      `status="passed"`, `weak_assertion_warning=False`, `basis="action_effect_only"` in
      `vnc_agent/tests/fixtures/test_business_resolver.py`
- [x] T051 [P] [US6] Test: `verification_mode: effect_only` step with only
      `screen_changed`/`region_changed` conditions loads successfully via
      `load_test_case()` (no rejection, unlike US3's `business` case) in
      `vnc_agent/tests/fixtures/test_testcase_loader.py`

### Implementation for User Story 6

- [x] T052 [US6] Implement the `effect_only` branch of `resolve_step_result()`'s
      status/`basis` table (data-model.md §4 row 4) in
      `vnc_agent/src/vnc_agent/verification/business_resolver.py` (depends on T034)
- [x] T053 [US6] Render `effect_only`-`passed` steps with an explicit "action effect only,
      not a verified business result" label, visually distinct from
      business-assertion-backed passes, in
      `vnc_agent/src/vnc_agent/reporting/json_report.py` and
      `vnc_agent/src/vnc_agent/reporting/html_report.py` (FR-013; depends on T035)
- [x] T054 [P] [US6] Run T050–T051, fix implementation until all pass
- [x] T055 [P] [US6] Add one example `verification_mode: effect_only` step to a new
      sample file `vnc_agent/testcases/pos-hover-probe.yaml` illustrating the authoring
      pattern from contracts/test-case-schema-delta.md

**Checkpoint**: Legitimate effect-only probes work end to end and are clearly labeled.

---

## Phase 9: User Story 7 - 旧用例保持可加载，仅 screen_changed 的旧业务用例产生弱断言警告且判定为 uncertain (Priority: P2)

**Goal**: `pos-buy-bag-checkout.yaml` and any other pre-existing test case with only
`screen_changed` (and no `verification_mode`) keeps loading, but its `StepVerificationResult`
is capped at `uncertain` with a weak-assertion warning — never a silent trusted `passed` —
and that warning is actually visible in both report formats.

**Independent Test**: The unmodified `pos-buy-bag-checkout.yaml` loads via
`load_test_case()` and, run offline end to end, its `add-shopping-bag` step resolves to
`uncertain` with `weak_assertion_warning=True`, rendered distinctly in the report.

### Tests for User Story 7

- [x] T056 [P] [US7] Test: step with `verification_mode` omitted and only
      `screen_changed`, `expected_effect` observed → `resolve_step_result()` returns
      `status="uncertain"`, `weak_assertion_warning=True`, `basis="action_effect_only"`
      (row 5 of data-model.md §4) in `vnc_agent/tests/fixtures/test_business_resolver.py`
- [x] T057 [P] [US7] Test: unmodified `vnc_agent/testcases/pos-buy-bag-checkout.yaml`
      loads successfully via `load_test_case()` with no changes to the file in
      `vnc_agent/tests/fixtures/test_testcase_loader.py`
- [x] T058 [P] [US7] Test (F6, FR-027): `json_report`/`html_report` output for a step with
      `weak_assertion_warning=True` contains a visibly distinct warning marker/section,
      and that marker is **absent** for both a business-assertion-backed `passed` step
      and an `effect_only`-backed `passed` step (i.e. the three outcomes — trusted pass,
      effect-only pass, weak-assertion uncertain — are each rendered distinguishably) in
      `vnc_agent/tests/fixtures/test_report_builder.py`

### Implementation for User Story 7

- [x] T059 [US7] Implement the "omitted `verification_mode`, weak-evidence-only" branch of
      `resolve_step_result()`'s status/`basis` table (data-model.md §4 row 5) in
      `vnc_agent/src/vnc_agent/verification/business_resolver.py` (depends on T052)
- [x] T060 [US7] Render `weak_assertion_warning=True` results with a prominent warning,
      distinct from both a business-assertion `passed` and an `effect_only` `passed`
      (per the three-way distinction tested in T058), in
      `vnc_agent/src/vnc_agent/reporting/json_report.py` and
      `vnc_agent/src/vnc_agent/reporting/html_report.py` (FR-027; depends on T053)
- [x] T061 [US7] Run T056–T058, fix implementation until all pass
- [x] T062 [US7] E2E test: run the unmodified `vnc_agent/testcases/pos-buy-bag-checkout.yaml`
      offline end to end (mocked driver + fixed frames showing bag 0→1) → the
      `add-shopping-bag` step's final status is `uncertain` with
      `weak_assertion_warning=True`, never `passed` in
      `vnc_agent/tests/e2e/test_scenario_12_legacy_weak_assertion.py` (depends on T035,
      T059, T060)

**Checkpoint**: Old test suites keep running without modification, can no longer silently
masquerade as trustworthy business passes, and the distinction is actually visible in
generated reports.

---

## Phase 10: User Story 8 - 针对购物袋重复添加问题的离线回归测试，不操作真实 VNC (Priority: P3)

**Goal**: A single stitched offline regression proves the full original incident is fixed,
and no automated test in this feature touches a real VNC connection.

**Independent Test**: Run the regression suite; it reproduces the incident's frame sequence
end to end and asserts every one of the incident's three failure points is now correct,
entirely offline.

### Implementation for User Story 8

- [x] T063 [US8] Build the stitched fixed-frame fixture and end-to-end test
      reproducing the original incident sequence (click → ~0.424% global/local cart
      change → `expected_effect` → duplicate click blocked → simulated recovery
      escalation to `switch_to_keyboard` without focus-path evidence → simulated error
      popup → step never `passed`) in
      `vnc_agent/tests/e2e/test_scenario_13_pos_bag_regression.py`; assert within it that
      the mocked `ExecutionRouter.execute()` for the add-bag action is called exactly
      once across the whole run, and that no `tab`-only `ExecutableAction` is ever sent
      without an attached `VerifiedFocusNavigationPath` (depends on T019, T030, T043,
      T049)
- [x] T064 [P] [US8] Add a check confirming no test added by this feature instantiates a
      real `VNCDriver`/`vncdotool` connection (SC-009) in
      `vnc_agent/tests/unit/test_no_real_vnc_in_offline_tests.py` (F5: filed under
      `tests/unit/` to match plan.md's documented three-tier test taxonomy, not as a
      loose top-level file — a static scan over `tests/fixtures/`, `tests/unit/`, and
      the new `tests/e2e/test_scenario_1{0,1,2,3}_*` files for direct `VNCDriver(`
      instantiation outside of `MockVNCDriver`)
- [x] T065 [US8] Run the full suite (`pytest -q` from `vnc_agent/`) and confirm all 001
      existing tests plus all tests added in this feature pass with zero regressions
      (SC-008)

**Checkpoint**: The feature's own regression proof exists and is safe to run in CI without
touching real infrastructure.

---

## Phase 11: Polish & Cross-Cutting Concerns

**Purpose**: Documentation and final validation that spans multiple stories.

- [x] T066 [P] Document the `ActionEffect` vs `StepVerificationResult` separation and
      `verification_mode: business`/`effect_only` authoring guidance for test-case authors
      in `vnc_agent/README.md`
- [x] T067 [P] Run `ruff check` (per `vnc_agent/pyproject.toml` `[tool.ruff]`) across all
      files touched by this feature and fix any findings
- [x] T068 Execute every scenario documented in quickstart.md (1, 1b, 2, 3, 3b, 3c, 4, 4b,
      5, 6, 7, 7b, 8, 9) individually against the finished implementation and confirm each
      pytest command's actual output matches its documented expected outcome

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (T002–T010 define
  the shared domain types every story imports)
- **User Story 1 (Phase 3)**: Depends on Foundational only — delivers the root-cause fix;
  every later story consumes `classify_action_effect()`/`compute_diff()` from here
- **User Story 2 (Phase 4)**: Depends on Foundational + US1 (`classify_action_effect`,
  T018)
- **User Story 3 (Phase 5)**: Depends on Foundational + US2 (`resolve_step_result`
  scaffolding, T026, and the `agent_runtime.py` integration point, T028)
- **User Story 4 (Phase 6)**: Depends on Foundational + US1 (T018) + US3 (T034, T035)
- **User Story 5 (Phase 7)**: Depends on Foundational only (`domain/focus_path.py`, T003)
  — independent of US2–US4, could be developed in parallel with them by a different
  contributor once Foundational is done
- **User Story 6 (Phase 8)**: Depends on US3 (`resolve_step_result` table + `agent_runtime`
  wiring, T034/T035)
- **User Story 7 (Phase 9)**: Depends on US3 (T034/T035) + US6 (T052, T053 — extends the
  same `resolve_step_result`/reporting files)
- **User Story 8 (Phase 10)**: Depends on US1, US2, US4, US5 (stitches their fixtures/
  fixes into one regression)
- **Polish (Phase 11)**: Depends on all desired stories being complete

### Sequencing Note

Unlike a typical feature where P1 stories are mutually independent, US2/US3/US4 in this
feature form a genuine implementation chain through `business_resolver.py` and the single
`agent_runtime.py` integration point (each extends the previous story's table/wiring rather
than duplicating it) — this mirrors spec.md's own priority rationale (US1's bug is the
direct root cause; US2–US4 build the guarantees on top of it). **US5 is the one P1 story
that is fully independent** of US2–US4 and can be staffed in parallel once Foundational is
done. Note that the FR-010/SC-010 conflict-resolution rule (T023/T026) and the FR-016
positive re-permission branch (T021/T025) both landed inside US2 rather than as separate
stories, since both extend logic US2 already owns (`business_resolver.py` and
`RepeatGuard`, respectively).

### Within Each User Story

- Tests are written first and MUST fail before their implementation task
- Domain/type tasks (Foundational) before story logic
- Story logic before its `agent_runtime.py`/reporting wiring
- Story complete (its own tests green) before moving to the next priority

### Parallel Opportunities

- All Foundational tasks marked [P] (T002–T006) can run in parallel — different files
- Within US1: T011–T015 (tests) in parallel; T016→T017→T018→T019 sequential (same
  perception pipeline, each depends on the last)
- Within US2: T020–T023 (tests) in parallel; T024/T025/T026/T027 touch different files and
  can proceed in parallel once their Foundational deps are met, but T028 needs all four
- **US5 can be staffed in parallel with US2/US3/US4** by a different contributor once
  Foundational is done (see Sequencing Note)
- Polish tasks T066/T067 in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together (writing them first, expected to fail):
Task: "Test: ~0.424% global/local cart-region change → expected_effect in vnc_agent/tests/fixtures/test_action_effect.py"
Task: "Test: nine-grid arbitrary-position local change → expected_effect in vnc_agent/tests/fixtures/test_action_effect.py"
Task: "Test: list/form/navigation scenarios → expected_effect in vnc_agent/tests/fixtures/test_action_effect.py"
Task: "Test: no-change → no_effect; OCR-only change → expected_effect in vnc_agent/tests/fixtures/test_action_effect.py"
Task: "Test: local change confined to a masked dynamic-noise region → no_effect in vnc_agent/tests/fixtures/test_action_effect.py"
```

*(These five all append to the same test file, so in practice they are best run as one
sequential authoring pass even though they are logically independent test cases — mark [P]
reflects "no code dependency between them", not "safe to edit the file concurrently".)*

## Parallel Example: Foundational Phase

```bash
Task: "Define ActionEffect models in vnc_agent/src/vnc_agent/domain/action_effect.py"
Task: "Define VerifiedFocusNavigationPath in vnc_agent/src/vnc_agent/domain/focus_path.py"
Task: "Define RepeatGuardDecision in vnc_agent/src/vnc_agent/domain/repeat_guard.py"
Task: "Add action_kind field to SemanticAction in vnc_agent/src/vnc_agent/domain/action.py"
Task: "Add weak_assertion_warning/basis fields to VerificationResult in vnc_agent/src/vnc_agent/domain/verification.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run `pytest tests/fixtures/test_action_effect.py -v`; confirm the
   0.424% incident screenshot now classifies as `expected_effect`
5. This alone proves the root-cause misjudgment is fixed, even before RepeatGuard/business
   assertions/error-popup/focus-path work lands

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → root-cause fix demoable (MVP)
3. US2 → duplicate-add bug fixed, RepeatGuard's retry-permission branch verified,
   deterministic/visual conflict rule settled
4. US3 → business assertions enforced
5. US4 → error-popup false-pass fixed (closes the second half of the original incident),
   legitimate-error-assertion edge case verified
6. US5 → blind-Tab recovery bug fixed (independent, may land any time after Foundational)
7. US6 → effect-only declarations supported
8. US7 → legacy test cases downgraded to `uncertain` instead of silently passing, with the
   distinction actually visible in reports
9. US8 → stitched regression + no-real-VNC guarantee proves the whole incident is closed
10. Polish → docs, lint, quickstart validation

### Parallel Team Strategy

With two contributors: Developer A works the US1→US2→US3→US4 chain sequentially (it must
be sequential, see Sequencing Note); Developer B can start US5 as soon as Foundational is
done and finish independently, then help with US6/US7/US8 once US3 lands.

---

## Notes

- [P] tasks touch different files with no unmet dependency
- [Story] label maps every story-phase task to spec.md's US1–US8 for traceability
- `verification/business_resolver.py` and `runtime/agent_runtime.py` are each touched by
  multiple stories (US2→US3→US4→US6→US7) — later stories' tasks explicitly extend the
  earlier story's table/wiring rather than re-implementing it; do not parallelize edits to
  these two files across stories
- `tests/fixtures/test_business_resolver.py` accumulates assertions across US2/US3/US4/
  US6/US7 (T022/T023, T033, T039, T050, T056) — same caution as above
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
- Avoid: vague tasks, same-file conflicts, skipping the Foundational phase

---

## Phase 12: Convergence

**Purpose**: Close a gap found by `/speckit-converge` between the implementation and
spec.md/plan.md/tasks.md after `/speckit-implement` completed all tasks through T068.

- [x] T069 Implement real `VerifiedFocusNavigationPath` construction inside the
      `switch_to_keyboard` side effect in
      `vnc_agent/src/vnc_agent/recovery/engine.py`'s `_apply_side_effects()` — it
      currently calls `try_build_focus_path(self._last_screen, to_hint=...)` in
      `vnc_agent/src/vnc_agent/recovery/strategies.py` without ever supplying a
      `tab_sequence`, and `try_build_focus_path()` unconditionally returns `None` when
      `tab_sequence` is falsy, so `switch_to_keyboard` is a permanent no-op in every real
      run — the positive/MAY branch is only exercised by `tests/unit/test_focus_path_gate.py`
      constructing a `VerifiedFocusNavigationPath` by hand and calling
      `ActionPolicy.resolve()` directly, never through the actual recovery pipeline.
      Derive a genuine `tab_sequence` from OCR/template anchor ordering between the last
      remembered focus context (`self._last_screen`/`self._last_target_hint`) and the
      target (`verification_method="structural_diff_confirmed"`), or from a recorded
      successful within-run replay (`verification_method="prior_successful_replay"`);
      construction MUST still leave `focus_path=None` when no reliable sequence can be
      derived (do not weaken FR-022's no-blind-Tab guarantee while fixing this). Add a
      test exercising the full `RecoveryEngine.handle()` → `switch_to_keyboard` →
      non-`None` `focus_path` path (not just direct `ActionPolicy.resolve()` calls) to
      `vnc_agent/tests/unit/test_focus_path_gate.py` or
      `vnc_agent/tests/fixtures/test_repeat_guard.py` per FR-023 / US5 AC2 (partial)

---

## Phase 13: Convergence

**Purpose**: Close a gap found by a second `/speckit-converge` pass after T069 was
implemented. T069 added a real tab-sequence derivation algorithm to
`recovery/strategies.py`/`recovery/engine.py`, but the production caller in
`runtime/agent_runtime.py` was never updated to feed it — so the gap moved one layer
deeper instead of closing.

- [x] T070 Wire `vnc_agent/src/vnc_agent/runtime/agent_runtime.py`'s
      `run_action_iteration()` to actually populate the "current focus" signal that
      `RecoveryEngine._build_focus_path_for_keyboard()` (`recovery/engine.py`) requires —
      today neither `RecoveryEngine.remember_focus()` nor
      `RecoveryEngine.remember_screen(..., known_focus_hint=...)` nor
      `RecoveryEngine.record_successful_focus_path()` is ever called from
      `agent_runtime.py` (only the two existing
      `self.recovery.remember_screen(screen, target_hint=target_hint)` calls at lines
      ~342/~470, neither passing `known_focus_hint`), so
      `self._last_known_focus_hint` stays `""` forever and
      `_build_focus_path_for_keyboard()` always returns `None` in real runs regardless
      of how correct the T069 derivation algorithm is — `switch_to_keyboard` is still a
      permanent no-op end-to-end, only exercised by
      `tests/unit/test_focus_path_gate.py` calling `RecoveryEngine` methods directly.
      Concretely: (a) after a click/keyboard `ExecutableAction` executes and its
      `ActionEffect`/`StepVerificationResult` confirms the action landed as intended,
      call `self.recovery.remember_focus(<normalized label of the element just acted
      on, e.g. from `sa.target.text`/`sa.target.description`>)` so the *next*
      `ActionIteration`'s `switch_to_keyboard` side effect has a genuine `from_hint`;
      (b) when a `switch_to_keyboard`-produced `focus_path` is subsequently confirmed
      successful (business result no longer blocked / `ActionEffect` resolves), call
      `self.recovery.record_successful_focus_path(iteration.executable_action-derived
      VerifiedFocusNavigationPath)` so `prior_successful_replay` can populate within a
      run. Add an end-to-end (not just `RecoveryEngine`-direct) test — e.g. extending
      `vnc_agent/tests/e2e/test_scenario_13_pos_bag_regression.py` or a new focused
      scenario — that drives a full `AgentRuntime.run()` through a sequence where a
      click fails, recovery escalates to `switch_to_keyboard`, and asserts the
      resulting `ExecutableAction.keys` came from a real derived `tab_sequence` (not
      that it stayed on the OCR/grounding fallback because `focus_path` was `None`),
      proving the wiring — not just the algorithm — works end to end per FR-023 /
      US5 AC2 (partial)
