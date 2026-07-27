# Research: Skip Re-Plan on Duplicate Frame with Blocked Action

**Feature**: 009-skip-replan-duplicate-frame | **Date**: 2026-07-26

## R1. Where the waste happens (incident bb9f039e, add-shopping-bag)

Observed sequence in the real-run telemetry:

- it[0]: planner call → click proposed → executed; verification uncertain (weak `screen_changed`-class assertion).
- it[1]: planner call (4–5 s cloud VLM) → identical action → RepeatGuard `allowed=false, reason=blocked_effect_pending` → blocked-verdict path.
- it[2]: observation frame `deduplicated` (identical to it[1]'s), planner call again → RepeatGuard `ambiguous_fail_safe` → blocked-verdict path.

it[1] and it[2] can never produce a new outcome: the planner input screen is pixel-identical and any identical proposal will be blocked again. Design doc §21.3 and the Constitution's resource constraint both already mandate "页面未变化时不重复调用 Planner"; the runtime simply has no code path implementing it for this case.

**Decision**: implement the rule as a pre-planning short-circuit in `AgentRuntime.run_action_iteration`, scoped to exactly the provably-informationless case (identical frame AND previously blocked action).

**Alternatives considered**:
- *Skip planner on any identical frame* (pure §21.3 reading): rejected — after an *executed* action with an identical frame, a fresh plan can legitimately differ (e.g., propose a corrective action); the repeat-guard-blocked precondition is what makes the skip provably safe.
- *Cache planner responses by content hash* (perception-cache style): rejected — the Planner is a context-sensitive role explicitly excluded from the pixel-content cache (perception-cache-contract.md, feature 004); a skip decision in the runtime keeps that exclusion intact.

## R2. Duplicate-frame identity: content hash vs. `deduplicated` flag

`ScreenFrame.deduplicated` relates a frame to the *immediately preceding capture in the capture session* — which between two observation frames is usually a stability-wait or post-action-verification frame. Relying on it would make the skip depend on interleaved capture ordering.

**Decision**: compare `StructuredScreen.content_hash` of the current observation against the previous iteration's recorded observation hash (`ActionIteration.before_content_hash`, new additive field). Non-null equality required; any null → no skip (fail open to the normal path). This subsumes the dedup flag (dedup implies equal content hash along the chain) and is stable under interleaved captures and reconnect session rotation.

## R3. Trigger reason set

`RepeatGuardReason` blocked values: `blocked_effect_pending`, `blocked_effect_pending_normalized_target`, `blocked_uncertain`, `blocked_uncertain_normalized_target`, `dangerous_drift`, `ambiguous_fail_safe`.

**Decision**: trigger set = {`blocked_effect_pending`, `blocked_effect_pending_normalized_target`, `ambiguous_fail_safe`} — exactly the incident's reasons as requested. Excluded:
- `blocked_uncertain(!_normalized_target)`: previous effect was `effect_uncertain`; a re-plan on the same frame may propose a *different* corrective action, so skipping loses information. Conservative exclusion, revisit with telemetry evidence.
- `dangerous_drift`: the previous *proposal* drifted; the next planner proposal may be different and safe — must be re-planned. (Defensively, if a carried decision ever holds `dangerous_drift`, the verdict helper still routes recovery the same way the block path does.)

## R4. What a skipped iteration does instead

The existing in-iteration RepeatGuard block branch already defines the "no action this round" verdict path: carry previous `ActionEffect` (or `effect_uncertain` fallback with reason `repeat_guard_block`), call `resolve_step_result(..., escalate=True)` with a re-observe callback, and route `recovery.handle(TARGET_NOT_FOUND, detail=reason)` for `dangerous_drift`/`ambiguous_fail_safe`.

**Decision**: refactor that branch body into a private helper (`_blocked_iteration_verdict`) and call it from both the real block branch and the new skip branch. This guarantees FR-002/FR-003 ("same verdict path") by construction rather than by duplication. `business_resolver.py` itself is untouched (FR-010).

Note: `resolve_step_result` escalation may issue *verification-role* model calls; that is pre-existing behavior on the block path and out of scope — only the planner call is skipped.

## R5. Chain behavior and loop safety

A skipped iteration produces no new RepeatGuard decision (no proposal to check). If its record carried `repeat_guard_decision=None`, the *next* identical frame would re-plan (condition (b) fails), yielding an alternating plan/skip pattern.

**Decision**: copy the previous blocking decision onto the skipped iteration's record (carried decision), so chains of identical frames keep skipping until the frame changes, recovery changes the screen, or the budget ends. The carried copy is distinguishable via `planner_skipped_reason != null` (FR-005). Loop safety is inherited: every skipped iteration passes through `StepController.start_iteration()` (budget consumption identical to today), and recovery reuse is capped by the per-failure-type `RecoveryPolicy.max_retries` — no new loop or terminal state (FR-004).

**Corollary — RepeatGuard transparency**: a skipped iteration proposed and executed nothing, so when a later round *does* re-plan (frame changed), RepeatGuard must compare the fresh proposal against the most recent iteration that actually carried a planner proposal, not against the skipped iteration (whose `semantic_action` is null and would trigger the guard's `ambiguous_fail_safe` null-action fallback, changing pre-feature behavior). The runtime therefore walks back past skipped iterations when selecting the guard's reference iteration; with zero skips the reference is the immediate previous iteration, byte-for-byte as before.

## R6. Wait-semantics exception criterion (FR-006)

The skip's premise — "same pixels ⇒ same information" — fails when time itself is an input. Two observable, declaration-level signals identify that:

1. Previous iteration's planned action was wait-type: `semantic_action.action_type == "wait"` or `micro_action_purpose == "wait"`. (In practice wait actions classify as idempotent and are never blocked, but the guard's classification is config/planner-influenced; the explicit check documents intent and is cheap.)
2. The step's verification spec declares `timeout_seconds` (`VerificationSpec.timeout_seconds is not None`): the author has stated the expected state may take time to materialize, so an unchanged frame is an expected intermediate, not a dead end.

**Decision**: both are hard exceptions — no skip. Rejected alternative: inferring time-dependence from condition types (e.g., `text_appears`) — too broad, would disable the optimization for most steps.

## R7. Telemetry: reuse feature-004 contract kinds

`CounterEvent` kind `model_call_skipped` (payload keys `model_role`, `reason`, `request_identity`) and `ModelCallAudit.outcome="skipped"` (requires `reason`) already exist in `runtime/telemetry.py` — defined by feature 004's telemetry contract but never emitted for the planner. `derive_performance_summary` already counts them into `skipped_model_call_count` and leaves `model_calls.planner` untouched.

**Decision**: emit exactly one of each per skipped iteration, with `reason="duplicate_frame_blocked_action"`, `source_ref` = previous observation frame id, and `request_identity` from `planner_identity(...)` when computable (same construction as the actual-call audit), falling back to the observation content hash. No `StageMeasurement` is written for the planner stage — `record_unavailable_stage` would mark the run summary `completeness="partial"`, which is for measurement *failures*, not intentional skips; absence of the stage plus the skip events is the truthful record.

## R8. Report surface

**Decision**: additive-only: `ActionIteration.planner_skipped_reason` serialized into the JSON report iteration object (null for normal iterations), matching the additive-field convention used by features 004/007 (`ui_index_audit` precedent). `before_content_hash` stays a run-record/domain field (frame hashes are already visible in the report's `frames[]` section; duplicating per-iteration in the report is unnecessary). HTML report untouched.

## R9. Test strategy

- **Unit** (`tests/unit/test_planner_skip_decision.py`): the pure predicate — every trigger reason, excluded reasons, null hashes, hash mismatch, wait-type previous action, `timeout_seconds` exception, missing previous iteration, carried-decision chaining.
- **E2E** (`tests/e2e/test_scenario_11_skip_replan_duplicate_frame.py`, Stub infra from `conftest.py` per scenarios 05/10): frozen screen after one executed non-idempotent click with weak verification → assert `StubPlanner.plan_calls` stops growing after the block, skipped iterations carry the marker, `model_calls.planner` conservation, budget-exhausted step failure with full iteration count, and the `timeout_seconds` exception keeps planning every round. Second unrelated scenario uses a keyboard-flow step to satisfy the two-scenario rule.
