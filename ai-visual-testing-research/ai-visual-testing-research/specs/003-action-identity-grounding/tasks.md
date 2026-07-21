# Tasks: 稳定动作身份与坐标空间定位纠正

**Input**: Design documents from `specs/003-action-identity-grounding/`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user
stories), [research.md](./research.md), [data-model.md](./data-model.md),
[contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Included and mandatory. Every implementation task is preceded by its own test
task(s); tests MUST be written and confirmed failing before the corresponding
implementation task begins (test-first, per explicit instruction). Real-VNC verification
is deliberately **excluded** from the automated test tasks and appears only as the final,
manual-only task (T062).

**Organization**: Tasks are grouped by user story (spec.md priorities). All file paths are
repository-root-relative (the project lives under `vnc_agent/`). No task in this file is
pre-marked complete — every checkbox starts unchecked.

**Renumbering note (2026-07-21, `/speckit-analyze` remediation)**: This file was fully
renumbered (T001–T056 → T001–T062) to insert 6 new tasks at their correct phase location
rather than appending them out of order after the manual acceptance task. This was judged
safe because zero tasks in this file had been started or checked off at the time of
renumbering (implementation had not yet begun) — see the CRITICAL/HIGH findings this
renumbering resolves, summarized inline where each new/changed task appears.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unmet dependency)
- **[Story]**: Maps the task to spec.md's US1–US7
- Every task names an exact file path and cites the FR-###/SC-###/USn it satisfies

## Path Conventions

Single project (`vnc_agent/`), per plan.md Project Structure:
- Domain models: `vnc_agent/src/vnc_agent/domain/`
- Execution/Planning/Models/Reporting: `vnc_agent/src/vnc_agent/{execution,planning,models,reporting}/`
- Tests: `vnc_agent/tests/{fixtures,unit,e2e}/`

---

## Phase 1: Setup

**Purpose**: Write failing contract tests for shared typed configuration before changing
the configuration implementation.

- [ ] T001 [P] Test-first: add failing typed-config tests in
      `vnc_agent/tests/fixtures/test_feature003_config.py` that require
      `PlanningConfig` (`result_display_keywords`, `dismissal_keywords`,
      `ocr_sanity_check_ratio`), `ReportingConfig.category_keywords`, and every
      `RecoveryPolicy` entry's six explicit fields; parameterize deletion of each recovery
      field and assert configuration loading fails rather than applying a default
      (FR-003/008/013/037, contracts/recovery-policy-contract.md)

**Checkpoint**: T001 exists and fails against the pre-feature configuration implementation.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Test, then implement shared configuration, domain types, and storage plumbing.

**⚠️ CRITICAL**: No user story implementation may begin until this phase is complete.

- [ ] T002 [P] Test-first: add failing schema/persistence tests in
      `vnc_agent/tests/fixtures/test_feature003_domain_schema.py` for
      `CanonicalActionIdentity`, `GroundingCandidate.coordinate_space/raw_bbox`, the new
      `RepeatGuardDecision.reason` values, `ActionIteration.canonical_identity`, repository
      round-trip, and `TestRun`'s `HumanStartStateConfirmation`/
      `ObservedStartState`/`StartStatePrecondition` fields (FR-001/002/007/012/025/026/038)
- [ ] T003 Implement the typed configuration required by T001 in
      `vnc_agent/src/vnc_agent/config.py` and `vnc_agent/config/agent.yaml`: add
      `PlanningConfig`, `ReportingConfig`, wire both into `AgentConfig`, and expand every
      `RecoveryPolicy` to six required fields with no model defaults for any field;
      run T001 until green (FR-003/008/013/037)
- [ ] T004 [P] Implement `CanonicalActionIdentity`, `ActionIteration.canonical_identity`,
      `HumanStartStateConfirmation`, `ObservedStartState`, `StartStatePrecondition`, and
      the corresponding `TestRun` fields in `vnc_agent/src/vnc_agent/domain/action_identity.py`
      and `vnc_agent/src/vnc_agent/domain/run.py`; add `canonical_identity_json` repository
      round-trip in `vnc_agent/src/vnc_agent/storage/repositories.py`; satisfy T002
      (FR-001/002/007/025/036/038)
- [ ] T005 [P] Add `coordinate_space: Literal["pixel","normalized_1000"] | None = None`
      and `raw_bbox: tuple[int,int,int,int] | None = None` to `GroundingCandidate` in
      `vnc_agent/src/vnc_agent/domain/grounding.py`; satisfy the grounding cases in T002
      (FR-012/026)
- [ ] T006 [P] Update `RepeatGuardDecision.reason` in
      `vnc_agent/src/vnc_agent/domain/repeat_guard.py`: remove `"different_action"`; add
      `"dangerous_drift"`, `"legitimate_micro_action"`, `"ambiguous_fail_safe"`, and the
      three `_normalized_target` variants defined by data-model.md §3; satisfy T002
      (FR-001~007)

**Checkpoint**: T001/T002 were observed failing before T003-T006, then pass; all new domain
types compile and existing 001/002 tests still pass. User story implementation can begin.

---

## Phase 3: User Story 1 - 措辞改写不应打断对同一非幂等业务动作的识别 (Priority: P1) 🎯 MVP

**Goal**: Fix the direct root cause from the real incident: `RepeatGuard` must treat
same-`action_id` retries as the same logical action regardless of Planner wording changes,
never producing the old `"different_action"` misclassification.

**Independent Test**: Feed the real incident's three literal `SemanticAction` records
(`action_id="act-1"` throughout, reworded `intent`/`target.description`) into
`RepeatGuard.check()` and assert iterations 2 and 3 are blocked — no real VNC required.

### Tests for User Story 1

- [ ] T007 [P] [US1] Test: `compute_identity()`/`identity_match()` — same `step_id` +
      same non-empty `action_id` + same `action_type` → `"action_id_match"` regardless of
      `intent`/`target.role`/`target.text`/`description` differences; different `step_id`
      (even with identical `action_id`) → `"different_step"`; same `action_id` but
      **differing `action_type`** → `"no_action_id_ambiguous"` (NOT `"action_id_match"` —
      `/speckit-analyze` CRITICAL remediation: an `action_id` reused across different
      action types MUST NOT be treated as a benign match, FR-007); `action_id` absent on
      at least one side but same `action_type` and OCR-tolerant equivalent
      `normalized_target` (e.g. `"レジ袋"` vs. `"ジ袋"`) → `"normalized_target_match"`
      (`/speckit-analyze` HIGH remediation: FR-005's OCR-noise tolerance previously had
      no code path that actually compared `normalized_target` values, see
      research.md §2); otherwise → `"no_action_id_ambiguous"` in
      `vnc_agent/tests/fixtures/test_action_identity.py` (FR-001/FR-002/FR-005/FR-007,
      contracts/action-identity-contract.md §1-2)
- [ ] T008 [P] [US1] Test: `RepeatGuard.check()` — using the real incident's three literal
      `SemanticAction` records (Run ID `cefe36a9-f5c3-4622-9998-ef06690a5ab6`,
      `action_id="act-1"` throughout, `intent`/`target.description` reworded each
      iteration) → iterations 2 and 3 return `allowed=False` with a `reason` other than
      the removed `"different_action"` in `vnc_agent/tests/fixtures/test_repeat_guard.py`
      (FR-002/FR-006, US1 AC1)
- [ ] T009 [P] [US1] Test: `RepeatGuard.check()` — previous `ActionEffect.status ==
      "expected_effect"` and previous `StepVerificationResult.status == "uncertain"` →
      `allowed=False`; the proposed (semantically-equivalent) action is never executed
      (repeat count 0) in `vnc_agent/tests/fixtures/test_repeat_guard.py` (FR-006, US1 AC2)
- [ ] T010 [P] [US1] Test: `RepeatGuard.check()` — previous `ActionEffect.status ==
      "effect_uncertain"` → `allowed=False` (repeat count 0), proving the block applies
      to `effect_uncertain` and not only `expected_effect` in
      `vnc_agent/tests/fixtures/test_repeat_guard.py` (FR-006, US1 AC7)
- [ ] T011 [P] [US1] Test: `RepeatGuard.check()` — previous `ActionEffect.status ==
      "no_effect"` reliably confirmed (after strengthened verification) and step retry
      budget remains → `allowed=True, reason="no_effect_confirmed"`, permitting exactly
      one retry — this is the *only* combination that allows re-execution in
      `vnc_agent/tests/fixtures/test_repeat_guard.py` (FR-006 sole retry condition)
- [ ] T012 [P] [US1] Test: two different `TestStep`s that coincidentally share the same
      `action_id` → `identity_match()` returns `"different_step"` and the new step's
      first iteration is always `allowed=True, reason="first_attempt"`, unaffected by the
      other step's history in `vnc_agent/tests/fixtures/test_action_identity.py`
      (FR-001, US1 AC5)
- [ ] T013 [P] [US1] Test: `evaluate_target_consistency()` — a legitimate step-internal
      micro-action (independent interactive purpose, e.g. dismissing a blocking popup,
      consistent with the step's declared `intent`) → `"legitimate_micro_action"`,
      `RepeatGuard.check()` → `allowed=True` in
      `vnc_agent/tests/fixtures/test_target_consistency.py` (FR-003, US1 AC8)
- [ ] T014 [P] [US1] Test: `RepeatGuard.check()` — identity/consistency genuinely
      ambiguous (no `action_id` match, consistency check inconclusive) and previous
      effect is not reliably `no_effect` → fail-safe `allowed=False,
      reason="ambiguous_fail_safe"` in `vnc_agent/tests/fixtures/test_repeat_guard.py`
      (FR-004, US1 AC7)
- [ ] T015 [P] [US1] Test: `evaluate_target_consistency()` —
      `previous_action.action_type != proposed_action.action_type` → unconditionally
      `"dangerous_drift"`, regardless of role/keyword signals (`/speckit-analyze`
      CRITICAL remediation: covers the `identity_match()` fall-through case where a
      same-`action_id` reuse across different action types must never be treated as a
      benign match, FR-007) in `vnc_agent/tests/fixtures/test_target_consistency.py`
      (FR-007, contracts/action-identity-contract.md §3)

### Implementation for User Story 1

- [ ] T016 [US1] Implement `compute_identity()` and `identity_match()` in
      `vnc_agent/src/vnc_agent/execution/action_identity.py` per
      contracts/action-identity-contract.md §1-2: `"action_id_match"` MUST additionally
      require `action_type` equality (FR-007 fix); `action_id` missing/differing but
      `action_type` equal and OCR-tolerant `normalized_target` match MUST return
      `"normalized_target_match"` (FR-005 fix) (depends on T004)
- [ ] T017 [US1] Implement `evaluate_target_consistency()` core structure in
      `vnc_agent/src/vnc_agent/execution/target_consistency.py`: `None`-previous-action →
      `"legitimate_micro_action"`; `action_type` mismatch → unconditional
      `"dangerous_drift"` (FR-007 fix, see T015); a minimal placeholder further
      `"dangerous_drift"` check (refined into both real drift directions in US2);
      remaining cases → `"ambiguous"` (contracts/action-identity-contract.md §3;
      depends on T003)
- [ ] T018 [US1] Rewrite `RepeatGuard.check()` in
      `vnc_agent/src/vnc_agent/execution/repeat_guard.py`: new signature
      `check(step_id, step_intent, proposed_action, previous_iteration)`; full decision
      combination per contracts/action-identity-contract.md §4 (action_id strong match →
      002's no_effect-only retry rule; `normalized_target_match` → the same rule with a
      `_normalized_target`-suffixed `reason` for audit distinction, FR-005; ambiguous →
      target consistency check → fail-safe); MUST NOT ever produce
      `reason="different_action"` (depends on T016, T017, T006)
- [ ] T019 [US1] Update the `RepeatGuard.check()` call site in
      `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` to pass `step.id`/`step.intent`
      (call timing itself unchanged — already before `RESOLVING_ACTION`, per
      research.md §1) (depends on T018)
- [ ] T020 [US1] Run T007–T015, fix implementation until all pass

**Checkpoint**: The reported duplicate-click bug (both the `action_id`-ignoring match and
the missing sole-retry-condition enforcement), plus the two design gaps found by
`/speckit-analyze` (`action_type` never checked, FR-005 never actually implemented), are
fixed and independently testable/demoable.

---

## Phase 4: User Story 2 - 识别并阻止从可交互控件到结果展示元素的危险目标漂移 (Priority: P1)

**Goal**: When a proposed target drifts away from what the step actually intends —
either to a non-interactive result-display element or to an unrelated interactive
control — block direct execution before it happens, in both directions.

**Independent Test**: Feed the real incident's second/third-iteration target
descriptions ("购物袋按钮" → "已添加的购物袋商品行") into `evaluate_target_consistency()`
and assert `"dangerous_drift"`, with no real mouse action ever produced.

### Tests for User Story 2

- [ ] T021 [P] [US2] Test: `evaluate_target_consistency()` — target drifts from
      "购物袋按钮"（可交互控件）to "已添加的购物袋商品行"（非交互结果展示元素）, using
      the real incident's literal 3rd-iteration `target.description` → `"dangerous_drift"`;
      `RepeatGuard.check()` → `allowed=False, reason="dangerous_drift"` in
      `vnc_agent/tests/fixtures/test_target_consistency.py` (FR-008 direction 1, US2 AC1)
- [ ] T022 [P] [US2] Test: `evaluate_target_consistency()` — target drifts from one
      interactive control to a *different* interactive control not matching the step's
      declared intent (e.g. "购物袋按钮" → "删除按钮") → `"dangerous_drift"` in
      `vnc_agent/tests/fixtures/test_target_consistency.py` (FR-008 direction 2, US2 AC5)
- [ ] T023 [P] [US2] Test: `evaluate_target_consistency()` — normal wording variation of
      the *same* interactive control (role/position/anchor text consistent or highly
      overlapping) → NOT `"dangerous_drift"` in
      `vnc_agent/tests/fixtures/test_target_consistency.py` (FR-011, US2 AC4)
- [ ] T024 [P] [US2] Test: dangerous-drift determination happens before any execution —
      driving a mocked iteration through `RepeatGuard`/`ActionPolicy` with a drifted
      target asserts no `ExecutableAction` with `method="mouse"` is ever produced, and
      the block does not depend on the drifted click's `ActionEffect` (which would only
      be known *after* execution) in `vnc_agent/tests/fixtures/test_target_consistency.py`
      (FR-009/FR-010, US2 AC2-3)

### Implementation for User Story 2

- [ ] T025 [US2] Implement full dangerous-drift detection (both directions) in
      `vnc_agent/src/vnc_agent/execution/target_consistency.py`, using
      `config.agent.planning.result_display_keywords`/`dismissal_keywords` and
      `target.role`/`target.text`/keyword-overlap-with-step-intent signals
      (research.md §4; depends on T017, T003)
- [ ] T026 [US2] Run T021–T024, fix implementation until all pass

**Checkpoint**: The reported wrong-element click (button → product row) is fixed for both
drift directions and independently testable without executing any real click.

---

## Phase 5: User Story 3 - Grounder 坐标必须遵循显式坐标空间协议 (Priority: P1)

**Goal**: Every Grounding candidate declares its coordinate space explicitly; the
system converts to pixel coordinates exactly once, at a single choke point, and rejects
— rather than guesses — when the declaration is missing, contradictory, unrecognized,
out of bounds, or contradicted by other evidence.

**Independent Test**: Feed the real incident's second-iteration candidate
`bbox=[251,402,405,459]` on a 1024×1568 resolution through `resolve_pixel_bbox()` under
both `"pixel"` and `"normalized_1000"` declarations and confirm the normalized
interpretation lands near the true click location (y≈678) while the pixel interpretation
does not — no real VNC or Grounder call required.

### Tests for User Story 3

- [ ] T027 [P] [US3] Test: `resolve_pixel_bbox()` — candidate declares
      `coordinate_space="normalized_1000"`, resolution `(1024, 1568)`, using the real
      incident's literal `raw_bbox=(251,402,405,459)` → converted bbox's Y range lands
      within ~630–720px (near the true y≈678 click), X/Y axes converted independently,
      result falls within `[0,1024)×[0,1568)` in
      `vnc_agent/tests/fixtures/test_coordinate_space.py` (FR-013/FR-017, US3 AC1)
- [ ] T028 [P] [US3] Test: `resolve_pixel_bbox()` — candidate declares
      `coordinate_space="pixel"` → returned unchanged (only bounds-checked, no numeric
      transform); feeding an already-resolved pixel bbox back through the same
      resolution path a second time produces byte-identical output (no double
      conversion) in `vnc_agent/tests/fixtures/test_coordinate_space.py` (FR-014, US3 AC2)
- [ ] T029 [P] [US3] Test: `resolve_pixel_bbox()` returns `None` for: (a) missing
      `coordinate_space` where both `"pixel"` and `"normalized_1000"` interpretations
      would be in-bounds (genuinely ambiguous); (b) declared `"pixel"` with values
      outside the actual resolution (contradictory); (c) an unrecognized
      `coordinate_space` value (neither `"pixel"` nor `"normalized_1000"`); confirm
      `MimoGrounderClient.ground()`/`StubGrounder` drop such candidates entirely so
      `ActionPolicy` never receives — and never produces an `ExecutableAction` for —
      them in `vnc_agent/tests/fixtures/test_coordinate_space.py` (FR-015/FR-016,
      US3 AC3-4)
- [ ] T030 [P] [US3] Test: a single Grounding response with candidate A declaring
      `"pixel"` and candidate B declaring `"normalized_1000"` → each converted
      independently per its own declaration, neither affecting the other in
      `vnc_agent/tests/fixtures/test_coordinate_space.py` (FR-012, US3 AC5)
- [ ] T031 [P] [US3] Test: `ActionPolicy` rejects an already-resolved candidate whose
      center point conflicts (beyond `ocr_sanity_check_ratio` tolerance) with a
      uniquely-matched OCR anchor for the same target → `stop_recover`, no
      `ExecutableAction` produced; absence of a comparable OCR anchor does NOT block
      (no new false rejections) in
      `vnc_agent/tests/fixtures/test_action_policy_sanity_check.py`
      (research.md §8, coordinate-space-contract.md §4)

### Implementation for User Story 3

- [ ] T032 [US3] Implement `resolve_pixel_bbox()` in
      `vnc_agent/src/vnc_agent/models/coordinate_space.py` per
      coordinate-space-contract.md §2 (depends on T005)
- [ ] T033 [US3] Update `_GROUNDING_SYSTEM_PROMPT` to require per-candidate
      `coordinate_space`, and wire `resolve_pixel_bbox()` as the single conversion point
      inside `MimoGrounderClient.ground()` (right after `_apply_crop_and_cap()`) in
      `vnc_agent/src/vnc_agent/models/mimo_grounder.py`; update `StubGrounder` in the
      same file to reuse the identical function for offline test doubles (depends on T032)
- [ ] T034 [US3] Add the OCR sanity-check rejection to
      `ActionPolicy._from_grounding()`/`_executable_from_candidate()` in
      `vnc_agent/src/vnc_agent/planning/action_policy.py` (depends on T032, T003)
- [ ] T035 [US3] Run T027–T031, fix implementation until all pass

**Checkpoint**: The likely root cause of the mis-clicked location (normalized-vs-pixel
confusion on a 1024×1568 screen) is fixed and independently testable without a real
Grounder call.

---

## Phase 6: User Story 4 - 将购物袋结算用例升级为可信业务验收标准 (Priority: P1)

**Goal**: `pos-buy-bag-checkout.yaml` uses `verification_mode: business` with
deterministic assertions grounded in the real incident's actual (noisy) OCR output, and
proves — end to end, offline — that the bag is added exactly once, subtotal is clicked
exactly once, and payment is never reached.

**Independent Test**: Drive a full offline `AgentRuntime.run()` of the updated YAML with
scripted frames reproducing the real incident's 0→1 item / 0→5-yen transition, and assert
the exact click/verification outcomes below.

### Tests for User Story 4

- [ ] T036 [P] [US4] Test: `pos-buy-bag-checkout.yaml` (post-update) declaring
      `verification_mode: business` for both steps loads successfully via
      `load_test_case()` — no `FieldValidationError`, because each step now has a real
      business assertion in `vnc_agent/tests/fixtures/test_testcase_loader.py`
      (FR-018, US4 AC1)
- [ ] T037 [P] [US4] Test: a fixed `StructuredScreen` whose `ocr_items` reproduce the
      real incident's actual noisy OCR output (e.g. bare `"1"`, a digit matching `"5"`,
      and `"袋"`, per research.md §9) evaluated against the updated add-shopping-bag
      step's `expected` spec via `VerificationEngine`/`business_resolver` →
      `StepVerificationResult.status == "passed"`, `weak_assertion_warning == False`,
      `basis` includes a business assertion — proving the new assertions actually match
      real-world OCR noise, not just an idealized full-string expectation, in
      `vnc_agent/tests/fixtures/test_pos_bag_assertions.py` (FR-019, research.md §9)
- [ ] T038 [P] [US4] Test: the second (小計) step's `expected` (declared
      `verification_mode: business`) evaluated against a fixed subtotal-confirmation
      `StructuredScreen` → `passed` via a deterministic text assertion alone, no
      `visual_question` condition present in the step (FR-020, FR-021 spirit: prefer
      deterministic assertions) in
      `vnc_agent/tests/fixtures/test_pos_bag_assertions.py` (FR-020)
- [ ] T039 [US4] E2E test: drive a full offline `AgentRuntime.run()` of the updated
      `pos-buy-bag-checkout.yaml` with a scripted frame sequence (cart 0 item/0 yen →
      1 item/5 yen → subtotal confirmation screen) → assert: `add-shopping-bag`'s
      fixed before/after frames produce `changed_pixel_ratio == pytest.approx(0.004669)`
      and `ActionEffect.status == "expected_effect"` (SC-007, not a coordinate test);
      `ExecutionRouter.execute()` call count == 1; `小計`'s click count == 1; zero
      payment-related actions across the whole run; zero extra mouse clicks or keyboard
      Tab presses; both steps' final `StepVerificationResult.status == "passed"` with
      `weak_assertion_warning == False` in
      `vnc_agent/tests/e2e/test_scenario_15_pos_bag_business_acceptance.py`
      (SC-001~008, US4 AC1-5, quickstart.md 场景 5b/10)

### Implementation for User Story 4

- [ ] T040 [US4] Rewrite `vnc_agent/testcases/pos-buy-bag-checkout.yaml`: both steps
      declare `verification_mode: business`; add-shopping-bag's `expected` asserts cart
      == 1 item, amount == 5 yen, and レジ袋-related text/`"袋"` appears (OCR-noise-
      tolerant per research.md §9), plus `screen_changed` as a secondary (non-sufficient)
      signal; 小計 step's `expected` asserts entry into the subtotal-confirmation screen
      via a deterministic text assertion; the use case ends at subtotal confirmation and
      does not include any payment step (FR-018~022)
- [ ] T041 [US4] Run T036–T039, fix the YAML content and any loader/`business_resolver`
      edge cases surfaced until all pass

### Legacy Compatibility (explicit requirement)

- [ ] T042 [P] [US4] Test: confirm existing legacy weak-assertion test cases/fixtures
      *other than* `pos-buy-bag-checkout.yaml` still load via `load_test_case()` and
      still resolve to `StepVerificationResult.status == "uncertain"` with
      `weak_assertion_warning == True` exactly as established by 002 — no regression
      introduced by 003's loader-adjacent or `business_resolver`-adjacent changes in
      `vnc_agent/tests/fixtures/test_testcase_loader.py` and
      `vnc_agent/tests/fixtures/test_business_resolver.py` (FR-023/FR-024)

**Checkpoint**: The use case that should have caught this incident during acceptance now
actually would — fully proven offline, independently of US1–US3's own tests.

---

## Phase 7: User Story 5 - 报告可审计动作身份与坐标空间换算 (Priority: P2)

**Goal**: Every report contains enough evidence — canonical action identity, RepeatGuard
reasoning, declared/raw/resolved coordinates, and (for real-VNC acceptance runs) human
start-state confirmation, observed start state, and per-category action counts — that a
reviewer can audit "why did this click happen" and "were the acceptance counts correct"
without re-running anything.

**Independent Test**: Inspect the JSON/HTML report produced by an offline run that
involves both a RepeatGuard block and a Grounding call, and confirm the new audit fields
are present and consistent.

### Tests for User Story 5

- [ ] T043 [P] [US5] Test: `build_report_dict()` output for a driven iteration
      (involving both a `RepeatGuard` block and a `Grounding` call) includes
      `canonical_action_identity` (`step_id`/`action_id`/`normalized_target`) and
      `coordinate_space_audit` (a list covering every evaluated candidate: declared
      space, `raw_bbox`, resolved `bbox`, whether accepted) in
      `vnc_agent/tests/fixtures/test_report_builder.py` (FR-025/FR-026, US5 AC1-2)
- [ ] T044 [P] [US5] Test: the HTML report's rendered output contains a collapsible
      "Action Identity / Coordinate Space" section sourced from the same
      `build_report_dict()` data (no separately re-derived data) in
      `vnc_agent/tests/fixtures/test_report_builder.py` (FR-025/FR-026, US5 AC1-2)

### Implementation for User Story 5

- [ ] T045 [US5] Add `canonical_action_identity` and `coordinate_space_audit` fields to
      `build_report_dict()` in `vnc_agent/src/vnc_agent/reporting/json_report.py`
      (depends on T004)
- [ ] T046 [US5] Add the corresponding collapsible section to the Jinja2 template in
      `vnc_agent/src/vnc_agent/reporting/html_report.py` (depends on T045)
- [ ] T047 [US5] Run T043–T044, fix implementation until all pass

**Checkpoint**: Reports are self-sufficient for auditing action-identity and
coordinate-space decisions, matching how 002 already made ActionEffect/RepeatGuard
auditable.

### FR-036/038、SC-012/013: 真实 VNC 起始门禁与实际发送动作审计

**`/speckit-analyze` HIGH remediation**: FR-036 (real-VNC report MUST additionally
include the human start-state confirmation record, its timestamp, the pre-run screenshot
reference, the observed starting state, and per-category action-count statistics) and
SC-012 (these counts must be directly readable from the report) previously had **zero**
implementation task — T045/T046 above only cover FR-025/026's per-iteration fields, and
the old T056 (manual acceptance, now T062) only *used* fields nothing ever built. The
four tasks below close that gap. See contracts/real-vnc-audit-contract.md and
data-model.md §8b.

- [ ] T048 [P] [US5] Test-first: `vnc-agent run --confirm-start-state --confirmed-cart-items 0
      --confirmed-cart-amount 0 --confirmed-screenshot <fixed test screenshot path>`
      populates `RunContext.test_run.human_start_state_confirmation`
      (`confirmed_cart_items`/`confirmed_cart_amount`/`screenshot_ref`/`confirmed_at`);
      omitting `--confirm-start-state` leaves it `None`; providing it without all three
      companion flags errors out before connecting to VNC in
      `vnc_agent/tests/unit/test_cli_start_state_confirmation.py` (FR-036/038,
      contracts/real-vnc-audit-contract.md §1)
- [ ] T049 [P] [US5] Test-first: in
      `vnc_agent/tests/fixtures/test_report_builder.py`, assert `build_report_dict()`
      serializes all three start-state fields plus `executed_action_log` and category
      counts; only iterations with `execution_result.success is True` count, while a
      RepeatGuard-blocked proposal remains auditable but contributes zero and an executed
      unclassified action remains in the log (FR-036/038, SC-012/013)
- [ ] T050 [US5] Implement `extract_cart_state()` in
      `vnc_agent/src/vnc_agent/verification/business_resolver.py`; add
      `--confirm-start-state`/`--confirmed-cart-items`/`--confirmed-cart-amount`/
      `--confirmed-screenshot` to the `vnc-agent run` command in
      `vnc_agent/src/vnc_agent/api/cli.py`, writing confirmation to
      `RunContext.test_run` through `vnc_agent/src/vnc_agent/runtime/run_context.py`;
      satisfy T048 and provide the typed inputs consumed by US6
      (FR-036/038, contracts/real-vnc-audit-contract.md §1-2; depends on T003/T004)
- [ ] T051 [US5] Add the three start-state fields, `executed_action_log`, and
      `action_category_counts` to `build_report_dict()` in
      `vnc_agent/src/vnc_agent/reporting/json_report.py`, and a corresponding section to
      `vnc_agent/src/vnc_agent/reporting/html_report.py`; aggregate only
      `execution_result.success is True`, preserve blocked proposals only in iteration
      audit, and retain executed unclassified actions in the log (FR-036/038, SC-012/013;
      depends on T003/T045/T050)
- [ ] T052 [US5] Run T048–T049, fix implementation until all pass

**Checkpoint**: T062 (manual real-VNC acceptance) can now actually find the audit fields
it is instructed to check — the gap `/speckit-analyze` found (a manual task referencing
fields nothing built) is closed.

---

## Phase 8: User Story 6 - 恢复路径不得盲目重试、额外点击或撤销已确认的业务结果 (Priority: P2)

**Goal**: The new failure modes introduced by US1–US3 (dangerous drift, coordinate
rejection) route through the existing recovery framework without ever introducing blind
Tab, extra clicks, or a "クリア" auto-clear action.

**Independent Test**: Simulate the new block/rejection scenarios and confirm the
resulting recovery strategy set never includes a destructive action.

### Tests for User Story 6

- [ ] T053 [P] [US6] Test-first: in
      `vnc_agent/tests/fixtures/test_recovery_no_destructive_actions.py`, verify
      `dangerous_drift`, `ambiguous_fail_safe`, and coordinate-space rejection route
      through a six-field `RecoveryPolicy`, consume step/global budgets exactly as
      declared, fail when budget is exhausted, and never produce blind `keys=["tab"]`,
      cart-clearing, item-deletion, or an unconfigured path; missing any policy field was
      already rejected by T001. In `vnc_agent/tests/e2e/test_start_state_precondition.py`,
      drive matching, mismatched, unreadable, and conflicting first-frame states; assert
      only the exact match reaches the first action and every other case stops before
      recovery with `start_state_precondition_failed` and zero execute calls
      (FR-028/029/031/037/038, SC-013, US6 AC1-6)
- [ ] T054 [P] [US6] Test: a static/grep-based scan confirms no code path in
      `vnc_agent/src/vnc_agent/` constructs an `ExecutableAction` that targets a
      "クリア"/clear-cart control automatically (i.e. the codebase contains no
      auto-invoked "クリア" click anywhere, matching FR-030's blanket prohibition) in
      `vnc_agent/tests/unit/test_no_auto_clear_action.py` (FR-030, SC-011)

### Implementation for User Story 6

- [ ] T055 [US6] Implement/adjust the existing recovery path so
      `dangerous_drift`/`ambiguous_fail_safe` outcomes in
      `vnc_agent/src/vnc_agent/execution/repeat_guard.py` route through the existing
      failure classification in `vnc_agent/src/vnc_agent/recovery/classifier.py` and the
      shared consumers in `vnc_agent/src/vnc_agent/recovery/engine.py` and
      `vnc_agent/src/vnc_agent/runtime/step_controller.py`; read all six fields from the typed policy, stop on missing
      authorization/model/human prerequisites or exhausted budgets, and add no new
      recovery loop outside the existing `ROUTING` table. In
      `vnc_agent/src/vnc_agent/runtime/agent_runtime.py`, feed T050's typed start-state
      inputs through a new pure `evaluate_start_state_precondition()` in
      `vnc_agent/src/vnc_agent/verification/business_resolver.py` after the first
      observation and before the first planned/input action;
      a failed precondition records the evidence and terminates without entering recovery
      (FR-031/037/038, SC-013; depends on T003/T019/T050)
- [ ] T056 [US6] Run T053–T054, fix implementation until all pass

**Checkpoint**: The new failure modes are provably as safe as 002's existing ones — no
new destructive recovery path exists anywhere in the codebase.

---

## Phase 9: User Story 7 - 新增场景均为离线回归测试，真实 VNC 仅作为独立人工批准环节 (Priority: P3)

**Goal**: Every new test in this feature is offline-only, and the full suite (001+002+003)
passes with zero regressions.

**Independent Test**: Run the full offline suite and the no-real-VNC static scan.

### Implementation for User Story 7

- [ ] T057 [P] [US7] Extend the no-real-VNC static scan (002's
      `vnc_agent/tests/unit/test_no_real_vnc_in_offline_tests.py`) to also cover the new
      003 test files (`test_action_identity.py`, `test_target_consistency.py`,
      `test_coordinate_space.py`, `test_action_policy_sanity_check.py`,
      `test_repeat_guard.py`, `test_pos_bag_assertions.py`, `test_feature003_config.py`,
      `test_feature003_domain_schema.py`, `test_start_state_precondition.py`,
      `test_scenario_15_pos_bag_business_acceptance.py`,
      `test_recovery_no_destructive_actions.py`, `test_no_auto_clear_action.py`,
      `test_cli_start_state_confirmation.py`) for direct `VNCDriver(`/`vncdotool` usage
      outside `MockVNCDriver`/`FakeVNC` (FR-032, SC-009)
- [ ] T058 [US7] Run the full suite (`pytest -q` from `vnc_agent/`) and confirm all
      001/002 existing tests plus all 003 tests pass with zero regressions (SC-010)

**Checkpoint**: The feature's own regression proof exists and is safe to run in CI
without touching real infrastructure.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Static checks and documentation that span multiple stories.

- [ ] T059 [P] Run `ruff check` (per `vnc_agent/pyproject.toml` `[tool.ruff]`) across all
      files touched by this feature and fix any findings (static check task)
- [ ] T060 [P] Document `CanonicalActionIdentity`, the `coordinate_space` protocol, and
      the dangerous-drift concept for test-case authors in `vnc_agent/README.md`
- [ ] T061 Execute every scenario documented in quickstart.md (1 through 12, including
      5b/11b/11c, dry-run) and confirm each pytest/CLI command's actual output matches its
      documented expected outcome (dry-run validation task)

---

## Phase 11: 真实 VNC 人工验收（独立环节，MUST NOT 在 pytest/CI 中运行）

**Purpose**: The one and only task in this feature that touches a real VNC environment;
gated on final human approval, per FR-035/SC-011 and explicit user instruction.

- [ ] T062 **[MANUAL — NOT run by pytest, NOT run by CI]** After T001–T061 all pass and
      final human approval is granted, execute quickstart.md's "真实 VNC 验收步骤"
      (5 steps) against the real target VNC environment: a human confirms and records
      the starting state (0 item/0 yen) before anything runs — the program MUST NOT
      auto-click "クリア"; run `pos-buy-bag-checkout.yaml` against the real target using
      the `--confirm-start-state`/`--confirmed-cart-items`/`--confirmed-cart-amount`/
      `--confirmed-screenshot` flags (T050); confirm the automatic
      `start_state_precondition` passes before the first input event (a mismatch must
      stop with zero sent actions, not be manually overridden); cross-check that the bag is added exactly
      once, the click never lands on the wrong element, subtotal is clicked exactly
      once, zero payment actions occur, and the generated report's audit fields
      (`human_start_state_confirmation`, `observed_start_state`,
      `start_state_precondition`, `executed_action_log`, `action_category_counts`,
      canonical action identity, coordinate-space audit — all
      built by T045/T051) make all of the above verifiable directly from the report.
      Record the acceptance outcome alongside the original incident report (Run ID
      `cefe36a9-f5c3-4622-9998-ef06690a5ab6`) for future reference
      (FR-035/036/038, US7 AC4, SC-001~006/SC-011~013,
      quickstart.md "真实 VNC 验收步骤")

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (T002–T006
  define the shared domain types every story imports)
- **User Story 1 (Phase 3)**: Depends on Foundational only — delivers the direct root-
  cause fix (`action_id` strong match, `action_type` guard, `normalized_target_match`);
  every later story that touches `RepeatGuard` builds on `execution/action_identity.py`
  and the rewritten `RepeatGuard.check()` from here
- **User Story 2 (Phase 4)**: Depends on Foundational + US1 (extends
  `execution/target_consistency.py`'s stub from T017 into full drift detection)
- **User Story 3 (Phase 5)**: Depends on Foundational only — independent of US1/US2's
  `execution/` work; touches `models/`/`planning/action_policy.py` instead
- **User Story 4 (Phase 6)**: Depends on US1 + US2 + US3 (the end-to-end acceptance test,
  T039, exercises the full fixed chain: identity matching, drift detection, and
  coordinate resolution together, in addition to the YAML's own business assertions)
- **User Story 5 (Phase 7)**: Depends on US1 + US3 for its first checkpoint (reports on
  `canonical_identity` from US1's domain field and `coordinate_space_audit` from US3's
  Grounder work); T048–T052's CLI/pure extraction/report aggregation paths are independent
  of US1–US4 after Foundational
- **User Story 6 (Phase 8)**: Depends on Foundational + US1 + US2 + T050 (verifies both the
  six-field recovery contract and that new failure modes cannot leak into destructive or
  off-budget recovery)
- **User Story 7 (Phase 9)**: Depends on US1–US6 (final regression + no-real-VNC proof
  over everything)
- **Polish (Phase 10)**: Depends on all desired stories being complete
- **Manual real-VNC acceptance (Phase 11)**: Depends on Phase 10 and final human
  approval; MUST NOT be run automatically at any point in this dependency chain

### Sequencing Note

**US3 is the one P1 story fully independent of US1/US2** (different files, different
root cause) and can be staffed in parallel by a different contributor once Foundational
is done. US1 → US2 must be sequential (US2 extends the `evaluate_target_consistency()`
stub US1 creates). US4's end-to-end test is deliberately the join point that proves US1,
US2, and US3 work together, so US4 cannot start meaningfully before all three land. The
FR-036/038 and SC-012 report tasks T048–T052 can proceed after Foundational in parallel
with US1–US4 because they touch CLI, run context, pure extraction, and reporting. The
US6 runtime enforcement in T055 waits for T019 and T050 because it modifies
`agent_runtime.py` and consumes the pure precondition function.

### Within Each User Story

- Tests are written first and MUST fail before their implementation task
- Domain/type tasks (Foundational) before story logic
- Story logic before its `agent_runtime.py`/reporting/`action_policy.py` wiring
- Story complete (its own tests green) before moving to the next priority

### Parallel Opportunities

- After failing tests T001/T002 exist, T003 can run in parallel with T004–T006; T004–T006
  touch separate implementation files and can run in parallel
- Within US1: T007–T014, T015 (tests) in parallel; T016→T018→T019 sequential (same
  `execution/` decision chain), T017 can start in parallel with T016 (different files)
- **US3 (Phase 5) can be staffed in parallel with US1+US2 (Phases 3-4)** by a different
  contributor once Foundational is done (see Sequencing Note)
- Within US3: T027–T031 (tests) in parallel; T032→T033→T034 sequential (same
  single-conversion-point chain)
- T048–T052 (FR-036/038 and SC-012 audit/data-flow work) can proceed after Foundational;
  T055 performs the SC-013 runtime enforcement after T019/T050
- Polish tasks T059/T060 in parallel

---

## Parallel Example: Foundational Phase

```bash
Task: "Implement typed planning/reporting/recovery config in vnc_agent/src/vnc_agent/config.py"
Task: "Define CanonicalActionIdentity and TestRun start-state fields in vnc_agent/src/vnc_agent/domain/action_identity.py and domain/run.py"
Task: "Add coordinate_space/raw_bbox fields to GroundingCandidate in vnc_agent/src/vnc_agent/domain/grounding.py"
Task: "Update RepeatGuardDecision.reason enum in vnc_agent/src/vnc_agent/domain/repeat_guard.py"
```

## Parallel Example: User Story 1 Tests

```bash
Task: "Test: compute_identity()/identity_match() step/action_id/action_type/normalized_target rules in vnc_agent/tests/fixtures/test_action_identity.py"
Task: "Test: RepeatGuard real-incident replay (action_id stable, text reworded) in vnc_agent/tests/fixtures/test_repeat_guard.py"
Task: "Test: RepeatGuard blocks on expected_effect+uncertain in vnc_agent/tests/fixtures/test_repeat_guard.py"
Task: "Test: RepeatGuard blocks on effect_uncertain in vnc_agent/tests/fixtures/test_repeat_guard.py"
Task: "Test: RepeatGuard allows retry on reliable no_effect in vnc_agent/tests/fixtures/test_repeat_guard.py"
Task: "Test: different TestStep never cross-blocked in vnc_agent/tests/fixtures/test_action_identity.py"
Task: "Test: legitimate micro-action not blocked in vnc_agent/tests/fixtures/test_target_consistency.py"
Task: "Test: ambiguous identity defaults to fail-safe in vnc_agent/tests/fixtures/test_repeat_guard.py"
Task: "Test: action_type mismatch always dangerous_drift in vnc_agent/tests/fixtures/test_target_consistency.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: run
   `pytest tests/fixtures/test_repeat_guard.py tests/fixtures/test_action_identity.py tests/fixtures/test_target_consistency.py -v`;
   confirm the real incident's three-iteration replay no longer produces a second click
5. This alone proves the direct root cause (ignoring `action_id`, plus the `action_type`
   and OCR-tolerance gaps found by `/speckit-analyze`) is fixed, even before drift
   detection, coordinate-space work, or the YAML upgrade land

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → direct root-cause fix demoable (MVP)
3. US2 → wrong-element click fixed (both drift directions)
4. US3 → likely coordinate-confusion root cause fixed, independent of US1/US2
5. US4 → the acceptance test that should have caught this incident now actually does,
   proving US1+US2+US3 together
6. US5 → reports become self-auditing, the start-state mismatch stops automatically, and
   only actually sent actions contribute to FR-036/038 and SC-012/013 counts
7. US6 → proves the Constitution six-field policy contract and no destructive/off-budget
   recovery path
8. US7 → full regression + no-real-VNC proof
9. Polish → lint, docs, quickstart dry-run
10. Manual real-VNC acceptance (T062) → only after everything above is green and
    approved

### Parallel Team Strategy

With two contributors: Developer A works US1 → US2 → US4 (needs US1/US2 finished first)
→ US5's US1/US3-dependent tasks (T043–T047) → US6; Developer B starts US3 as soon as
Foundational is done (fully independent), then helps with US4 once US1–US3 are all
ready, then US7. T048–T052 can be developed in parallel with the P1 stories; T055 is
sequenced after Developer A's T019 and T050 because it modifies `agent_runtime.py`.

---

## Notes

- [P] tasks touch different files with no unmet dependency
- [Story] label maps every story-phase task to spec.md's US1–US7 for traceability
- `execution/repeat_guard.py` is touched by both US1 (T018, full rewrite) and US6 (T055,
  verification only, no further rewrite) — do not parallelize edits to this file across
  those two stories
- `execution/target_consistency.py` is touched by both US1 (T017, stub — now including
  the `action_type`-mismatch rule) and US2 (T025, full implementation) — sequential by
  design, not parallelizable
- `vnc_agent/tests/fixtures/test_repeat_guard.py` and
  `vnc_agent/tests/fixtures/test_target_consistency.py` each accumulate assertions
  across multiple tasks within US1/US2 — do not parallelize edits to the same file within
  a story even where individual tasks are marked [P] for cross-task independence
- `vnc_agent/src/vnc_agent/reporting/json_report.py` is touched by both US5's first
  checkpoint (T045, per-iteration fields) and the FR-036/038/SC-012/013 task T051 (run-level
  fields) — sequential by design (T051 depends on T045), not parallelizable
- `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` is touched by T019 and T055; T055
  explicitly depends on T019 and MUST NOT be implemented in parallel with it
- T062 (manual real-VNC acceptance) is the only task in this file that is explicitly
  **not** part of the automated test suite — do not add it to any CI pipeline
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
- Avoid: vague tasks, same-file conflicts, skipping the Foundational phase, running T062
  automatically
