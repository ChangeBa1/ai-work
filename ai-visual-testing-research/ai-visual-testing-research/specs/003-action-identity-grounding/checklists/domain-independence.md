# Domain Independence Checklist: 通用动作身份、目标一致性与坐标空间安全

**Purpose**: Validate that this feature's requirements AND the design artifacts derived
from them (plan.md, data-model.md, contracts/, tasks.md) remain domain-agnostic per
Constitution v1.1.0 Principle VI (业务无关核心与声明式场景隔离) — i.e., that no tested-
application-specific field, keyword, category, or expected value has leaked into what is
supposed to be reusable core (domain/runtime/planning/grounding/execution/verification/
reporting/recovery/config), and that POS content is confined to testcase/example/fixture/
scenario-profile locations only. Any confirmed business leakage causes the corresponding
item to be marked **not passing** (`[ ]`), per explicit instruction.

**Created**: 2026-07-22
**Feature**: [spec.md](../spec.md) | [plan.md](../plan.md) | [data-model.md](../data-model.md) | [tasks.md](../tasks.md)

**Scope note**: spec.md was rewritten on 2026-07-22 to be fully domain-agnostic (see
`checklists/requirements.md`). This checklist checks whether that rebaseline actually
holds **across the whole current artifact set** for 003 — not spec.md in isolation.
Several items below fail precisely *because* plan.md/data-model.md/contracts/tasks.md
were generated against the **pre-rebaseline** spec and have not been regenerated since.

## Requirement Completeness

- [x] **CHK001** - Do the domain/runtime/config/reporting design artifacts define their
      fields exclusively through generic types (no fixed per-business fields), matching
      what FR-001～041 of spec.md require? [Completeness, Spec §FR-002/012/024/027, data-model.md §8b]
      **Evidence (RESOLVED, 2026-07-22 /speckit-plan rewrite)**: `data-model.md` §8 now
      defines `DeclaredFact(key, spec: VerificationSpec)`/`RunPrecondition`/
      `FactEvaluation`/`PreconditionEvaluation`/`HumanConfirmedFact` — generic
      key+reused-assertion types, replacing the old `HumanStartStateConfirmation.
      confirmed_cart_items`/`ObservedStartState.cart_items` fixed fields entirely
      (see data-model.md §10 removal-mapping table). `rg` for the forbidden tokens
      across plan.md/data-model.md/research.md/contracts/*.md (2026-07-22) returns
      matches only inside explicitly-labeled "重新基线说明"/"业务泄漏清单" removal
      documentation, never in a current schema definition.
- [x] **CHK002** - Are the "at least two unrelated offline scenarios" required by
      FR-040/SC-012 (form-submit dedup, icon-only menu grounding, popup/scroll legitimate
      micro-action) reflected as concrete tasks in tasks.md, or does the task breakdown
      still cover only the single POS incident scenario? [Completeness, Gap, Spec §FR-040/SC-012, tasks.md]
      **Evidence (RESOLVED, 2026-07-22 /speckit-tasks)**: `tasks.md` Phase 10 (US8)
      T040/T041/T042 create `test_scenario_form_submit.py`/`test_scenario_icon_menu.py`/
      `test_scenario_popup_scroll.py` as standalone, business-agnostic scenarios; T045
      asserts genericity evidence independent of the POS fixture (T043/T044). Re-verified
      by the 2026-07-22 `/speckit-analyze` pass (0 CRITICAL/HIGH).

## Requirement Consistency

- [x] **CHK003** - Does `contracts/action-identity-contract.md`'s `action_id_match`
      handling remain consistent with spec.md FR-003/FR-004 (Safety Issue A: an
      `action_id` match proves only "same logical action attempt," and MUST NOT exempt
      a substantially conflicting new target from the step-intent-consistency check)?
      [Conflict, Spec §FR-003/FR-004, contracts/action-identity-contract.md]
      **Evidence (RESOLVED)**: `action-identity-contract.md` §4 now requires
      `RepeatGuard.check()` to **unconditionally** call `has_target_evidence_conflict()`
      (§3.1, new) regardless of `identity_match()`'s result; §6 invariant 1 states this
      explicitly. `data-model.md` §1/§4/§9 updated to match. Re-verified clean by the
      2026-07-22 `/speckit-analyze` pass.
- [x] **CHK004** - Does the design's `no_effect`-based retry-permission logic remain
      scoped only to "same, unchanged target" re-execution, or does it (as currently
      documented) implicitly also bypass the FR-003 consistency check for a *changed*
      target, contradicting FR-004? [Conflict, Spec §FR-004, data-model.md §3, contracts/action-identity-contract.md]
      **Evidence (RESOLVED)**: `action-identity-contract.md` §4 explicit invariant:
      "第 3 步的'直接放行/拦截'分支 MUST NOT 在 `conflict is True` 时被采用，即使
      前一轮 `ActionEffect` 已被可靠判定为 `no_effect`". tasks.md T005(b) tests this
      exact invariant.
- [x] **CHK005** - Are report/config category fields expressed as arbitrary user-declared
      tags/matchers (FR-027/028), or does the design still hardcode a fixed four-category
      business enum? [Conflict, Spec §FR-027/FR-028, data-model.md §8b, contracts/real-vnc-audit-contract.md]
      **Evidence (RESOLVED)**: `data-model.md` §8b now defines `ActionMatcher`/
      `ActionTagRule` (structured, testcase/profile-declared predicates) and
      `ReportingConfig.action_tags: list[ActionTagRule] = []` — core default empty,
      no required-category validator. `contracts/real-vnc-audit-contract.md` §4 was
      rewritten to match (fully replaces the old fixed four-category requirement).
- [x] **CHK006** - Is the "no undeclared state-mutating recovery action" requirement
      (FR-032) expressed in business-neutral terms in all contract artifacts, or does any
      contract still name a specific business action? [Consistency, Spec §FR-032, contracts/recovery-policy-contract.md]
      **Evidence (RESOLVED)**: `contracts/recovery-policy-contract.md`'s "路由与预算
      不变量" now reads "任何策略不得构造任何不在该测试步骤已声明动作范围内、会改变
      被测应用状态的操作（FR-032；本条 MUST NOT 依赖任何具体业务动作名词...）" —
      "清空购物车" only remains in the file's "重新基线说明" header documenting the edit.

## Acceptance Criteria Quality

- [x] **CHK007** - Can "at least two unrelated scenarios prove a generic capability"
      (FR-040/SC-012) be objectively verified against the *current* task/contract
      artifact set, or does verifying it today require artifacts that don't yet exist?
      [Measurability, Spec §FR-040/SC-012, tasks.md]
      **Evidence (RESOLVED)**: T040/T041/T042 (new scenario test files) + T045
      (cross-scenario coverage assertion, extended by the 2026-07-22 `/speckit-analyze`
      pass to also assert SC-006/SC-007 across the scenario set) now give SC-012 a
      concrete, produceable evidence trail — no longer dependent on artifacts that
      don't exist.
- [x] **CHK008** - Are the SC-001～013 measurable outcomes stated in spec.md themselves
      free of business-specific expected values (e.g., no fixed item/amount counts, no
      named business UI text)? [Measurability, Spec §SC-001~013]
      **Evidence**: SC-001～013 use only generic counts ("提交动作被重复执行的次数仍为
      0", "点击动作严格执行 1 次") and scenario references (US8's three generic
      scenarios); SC-013 explicitly denies the POS fixture sole-evidence status.
      spec.md-level Success Criteria pass in isolation.

## Scenario Coverage

- [x] **CHK009** - Is the requirement that "a matching `action_id` still requires the
      target-safety consistency check when target evidence conflicts" (FR-003) reflected
      as an explicit scenario/state transition in data-model.md's `IdentityMatch` →
      `RepeatGuardDecision` flow, or does that flow only branch on `action_id`/
      `action_type` equality? [Coverage, Gap, Spec §FR-003, US1/AC9-10, data-model.md §9]
      **Evidence (RESOLVED)**: `data-model.md` §9's state-flow diagram now shows
      `has_target_evidence_conflict(previous, proposed)` computed unconditionally
      ("无论 IdentityMatch 结果如何都计算") before the combination decision branches on
      `IdentityMatch ∈ {action_id_match, normalized_target_match} AND NOT conflict`.
      tasks.md T004/T005 test this path directly.
- [x] **CHK010** - Is the risk-signal-driven, three-factor `dangerous_drift` combination
      rule (FR-013: purpose ∧ risk-level ∧ consistency, AND semantics) reflected in
      `TargetConsistencyResult`, or does the design still classify purely on
      `action_type` inequality? [Coverage, Conflict, Spec §FR-012/FR-013, data-model.md §2]
      **Evidence (RESOLVED)**: `data-model.md` §2/§3 now define the AND(purpose ∈
      legitimate-micro-action-enum, step-intent-consistency, risk ≤ threshold) rule with
      no `action_type`-inequality short-circuit; `action-identity-contract.md` §3.2
      explicitly states "不再有任何分支因为...`action_type` 不同...就无条件返回
      `dangerous_drift`". tasks.md T011 tests the AND semantics plus the `"ambiguous"`
      branch (added 2026-07-22 by `/speckit-analyze` remediation).

## Dependencies & Assumptions

- [x] **CHK011** - Does spec.md's Assumptions section correctly scope "场景 profile" as
      fully optional, with core required to function with zero registered profiles (per
      the 2026-07-22 `/speckit-clarify` resolution)? [Assumption, Spec §Assumptions]
      **Evidence**: Assumptions bullet added by the clarify pass states this explicitly;
      no contract or design artifact currently introduces a profile registration
      interface, so no inconsistency exists here yet.
- [x] **CHK012** - Is the dependency of downstream design artifacts (plan.md, data-
      model.md, contracts/, tasks.md) on the *current* (2026-07-22 rebaselined) spec.md
      explicitly re-validated, or do they still reflect the pre-rebaseline, POS-specific
      spec? [Assumption, Dependency, Gap]
      **Evidence (RESOLVED)**: plan.md/research.md/data-model.md/contracts/tasks.md were
      fully regenerated on 2026-07-22 via `/speckit-plan` + `/speckit-tasks` against the
      current spec.md, and independently re-verified via `/speckit-analyze` (0
      CRITICAL/HIGH findings). plan.md's own Constitution Check now carries a per-CHK
      cross-reference table recording this dependency explicitly.

## Ambiguities & Conflicts

- [x] **CHK013** - Is there a clear, single source of truth stating that POS-specific
      identifiers (`confirmed_cart_items`, `cart_items`, `add_to_bag`, `subtotal`,
      `clear_or_reset`, `extract_cart_state`) MUST NOT appear in core-scoped
      requirements? [Traceability, Spec §checklists/requirements.md]
      **Evidence**: `checklists/requirements.md`'s "Business-Agnostic Core" section and
      Notes make this an explicit, mandatory, itemized check with a runnable `rg`
      command; spec.md passes it. This checklist (domain-independence.md) extends the
      same rule to plan/data-model/contracts/tasks, where it currently fails (CHK001–010).
- [x] **CHK014** - Are the conflicts identified above (CHK003/CHK005/CHK010, where a
      contract or data-model artifact directly contradicts a spec.md requirement)
      recorded anywhere as a blocking follow-up before `/speckit-implement` proceeds, or
      would implementation currently be free to follow the stale, contradictory design?
      [Conflict, Gap]
      **Evidence (RESOLVED)**: the follow-up was executed, not just recorded — `/speckit-
      plan` (2026-07-22) regenerated `data-model.md`, `contracts/action-identity-
      contract.md`, `contracts/real-vnc-audit-contract.md`, and `/speckit-tasks`
      regenerated `tasks.md`, all against the rebaselined spec.md. `/speckit-analyze`
      then independently re-verified 0 CRITICAL/HIGH remain before `/speckit-implement`
      was invoked.

## Notes

- **Result (2026-07-22, re-validated after /speckit-plan + /speckit-tasks +
  /speckit-analyze): 14/14 items passing.** All 11 items that failed at this
  checklist's creation time described defects in the **pre-rewrite** plan.md/
  data-model.md/contracts/tasks.md; those artifacts were fully regenerated the same
  day against the rebaselined spec.md, and the fixes were independently re-verified by
  a subsequent `/speckit-analyze` read-only pass (0 CRITICAL, 0 HIGH; the one HIGH
  finding it did surface — a missing test for `evaluate_target_consistency()`'s
  `"ambiguous"` branch — was a tasks.md test-coverage gap, not a design-artifact
  business-leakage or safety-bypass issue, and was fixed in tasks.md T011).
- This checklist is now safe to treat as a passed prerequisite gate for
  `/speckit-implement`.
- **Post-implementation confirmation (2026-07-22, T049)**: `/speckit-implement`
  completed all 49 tasks (T001–T049). `tests/unit/test_no_business_keywords_in_core.py`
  (T002/T046) and the generalized `tests/unit/test_no_real_vnc_in_offline_tests.py`
  (T003/T047) both pass against the actual implementation; the full offline suite
  (T048) is 202 passed, 1 skipped, 0 failed. The `has_target_evidence_conflict()`
  front-door gate (CHK003/004/009) and the AND-semantics `dangerous_drift`
  combination (CHK005/010) are implemented exactly as this checklist's evidence
  described, not just planned. `tests/fixtures/test_cross_scenario_coverage.py`
  (T045) directly re-verifies SC-006/SC-007 hold across all three generic
  scenarios independent of the POS fixture.
