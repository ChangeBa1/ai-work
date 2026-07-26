# Contract: Planner Skip on Duplicate Frame with Blocked Action

**Feature**: 009-skip-replan-duplicate-frame | **Date**: 2026-07-26

Binding rules for `AgentRuntime.run_action_iteration` and downstream telemetry/report consumers.

## §1 Trigger (all conditions required)

| # | Condition | Source of truth |
|---|---|---|
| 1 | Previous ActionIteration exists in the current step | `StepRecord.iterations[-2]` at iteration time |
| 2 | Previous `repeat_guard_decision.allowed == false` with `reason` in `{blocked_effect_pending, blocked_effect_pending_normalized_target, ambiguous_fail_safe}` — own or carried (§4) | previous iteration record |
| 3 | Current observation `content_hash` non-null, previous `before_content_hash` non-null, equal | capture layer hashes, recorded per iteration |
| 4 | Previous planned action NOT wait-type (`action_type=="wait"` or `micro_action_purpose=="wait"`) | previous `semantic_action` |
| 5 | Step verification spec has `timeout_seconds == null` | `TestStep.expected` |
| 6 | Step has no `batch_repeat_key` declaration | `TestStep` |

Any condition failing ⇒ MUST plan normally. Missing evidence (nulls) MUST disable the skip, never enable it.

## §2 Behavior of a skipped iteration

- MUST NOT invoke the Planner provider, in any form (no cache, no replay).
- MUST follow the identical verdict path as the in-iteration RepeatGuard block: carried previous `ActionEffect` (or `effect_uncertain` fallback, reason `repeat_guard_block`), `resolve_step_result(..., escalate=True)` against the current observation with a re-observe callback, recovery routing via `FailureType.TARGET_NOT_FOUND` when the carried reason is `ambiguous_fail_safe` or `dangerous_drift`.
- MUST consume exactly one step-budget unit through `StepController.start_iteration()` (i.e., the normal outer-loop accounting; the skip adds no separate accounting).
- MUST NOT execute any action, produce a `semantic_action`, `executable_action`, or `execution_result`.
- MUST NOT introduce any new terminal state, retry loop, or recovery strategy.

## §3 Telemetry / report obligations per skipped iteration

- `ActionIteration.planner_skipped_reason = "duplicate_frame_blocked_action"` (MUST); normal iterations MUST keep `null`.
- Exactly one `CounterEvent kind="model_call_skipped"` with payload `model_role="planner"`, `reason="duplicate_frame_blocked_action"`, `request_identity` (planner canonical identity when computable, else the observation content hash) (MUST).
- Exactly one `ModelCallAudit` with `model_role="planner"`, `outcome="skipped"`, same `reason`, `source_ref` = previous-observation reference (the capture layer's duplicate-of frame id when available, else the previous round's recorded observation evidence ref) (MUST).
- MUST NOT emit: planner `model_call` CounterEvent, planner actual-outcome audit, planner `StageMeasurement` (neither completed nor unavailable).
- JSON report iteration objects MUST include key `planner_skipped_reason` (string/null). All pre-existing keys unchanged.
- Conservation: for any step, `count(planner model_call events) + count(planner model_call_skipped events) == count(iterations that reached the planning phase on a non-batch step)`.

## §4 Carried decision (chaining)

A skipped iteration MUST copy the previous iteration's blocking `RepeatGuardDecision` onto its own record so that §1.2 evaluates over chains of identical frames. Consumers MUST treat `repeat_guard_decision` on an iteration with non-null `planner_skipped_reason` as carried, not freshly evaluated.

Skipped iterations MUST be transparent to RepeatGuard itself: when a later round re-plans, the guard's previous-iteration reference MUST be the most recent iteration with a real planner proposal (`planner_skipped_reason == null`), so identity comparison semantics are identical to a run without skips.

## §5 Out of scope / forbidden

- No change to `execution/repeat_guard.py` decision logic, `verification/business_resolver.py`, `perception/cache.py`, `perception/ocr/`, capture/dedup semantics, or `StepController` budget semantics.
- The Planner remains excluded from the pixel-content analysis cache (perception-cache-contract.md); this contract is a *skip*, never a cached replay.
