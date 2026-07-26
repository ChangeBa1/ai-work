# Data Model: Skip Re-Plan on Duplicate Frame with Blocked Action

**Feature**: 009-skip-replan-duplicate-frame | **Date**: 2026-07-26

## 1. ActionIteration (extended — `domain/run.py`)

| Field | Type | Default | Semantics |
|---|---|---|---|
| `planner_skipped_reason` | `str \| None` | `None` | Non-null iff this iteration's planner call was short-circuited. Only defined value in this feature: `"duplicate_frame_blocked_action"` (open string for future skip classes). |
| `before_content_hash` | `str \| None` | `None` | Pixel-content hash of this iteration's observation frame (`StructuredScreen.content_hash`), recorded at OBSERVING time on every iteration. Null when the capture layer could not compute a hash. |

Invariants:

- `planner_skipped_reason != None` ⇒ `semantic_action is None`, `executable_action is None`, `execution_result is None` (nothing was proposed or executed this round).
- `planner_skipped_reason != None` ⇒ `repeat_guard_decision` is a **carried copy** of the previous iteration's blocking decision (`allowed=false`), not a fresh guard evaluation. Distinguisher: the skip marker itself.
- Both fields are additive; absence (older records) deserializes as `None`.

## 2. Skip predicate (runtime-internal, stateless)

Inputs: current `StructuredScreen`, previous `ActionIteration | None`, current `TestStep`.

Returns `"duplicate_frame_blocked_action"` iff ALL:

1. previous iteration exists;
2. `previous.repeat_guard_decision` is not None, `allowed == False`, `reason ∈ {blocked_effect_pending, blocked_effect_pending_normalized_target, ambiguous_fail_safe}`;
3. `screen.content_hash` is not None AND `previous.before_content_hash` is not None AND equal;
4. NOT (previous `semantic_action` is wait-type: `action_type == "wait"` or `micro_action_purpose == "wait"`);
5. `step.expected.timeout_seconds is None`;
6. `step.batch_repeat_key is None` (checked at the call site — that path has no planner call).

Else returns `None` (plan normally).

## 3. Telemetry records per skipped iteration (pre-existing kinds, `runtime/telemetry.py` — unchanged)

- **CounterEvent** `kind="model_call_skipped"`, payload: `model_role="planner"`, `reason="duplicate_frame_blocked_action"`, `request_identity=<planner_identity or content-hash fallback>`.
- **ModelCallAudit**: `model_role="planner"`, `outcome="skipped"`, `reason="duplicate_frame_blocked_action"`, `source_ref=<previous-observation reference: duplicate-of frame id when available, else the previous round's observation evidence ref>`, sanitized request/response minimal (`{"step_intent": ..., "iteration_index": ...}` / `{}`).
- **No** planner `model_call` CounterEvent, **no** planner `StageMeasurement` (stage never ran; `record_unavailable_stage` is reserved for failures, not intentional skips).

Derived (`derive_performance_summary`, unchanged code): `model_calls["planner"]` counts only actual calls; `skipped_model_call_count` grows by 1 per skipped iteration.

## 4. JSON report iteration object (additive — `reporting/json_report.py`)

New key `"planner_skipped_reason"`: string or null, mirrored from the iteration record. All other keys byte-for-byte unchanged (features 001–007 backward-compatibility rule).

## 5. State transitions on a skipped iteration

`OBSERVING → UNDERSTANDING → PLANNING(entered, immediately short-circuited) → VERIFYING("planner_skip_duplicate_frame") → RECORDING` — the same externally visible states as the in-iteration repeat-guard block path (which forces VERIFYING with its own trigger tag); no new `AgentState` values.
