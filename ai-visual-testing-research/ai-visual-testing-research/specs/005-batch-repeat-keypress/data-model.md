# Phase 1 Data Model: Batch Repeat Key Press

All entities below are additive extensions of existing Pydantic models in the `vnc_agent` domain
layer. No existing field is renamed, removed, or repurposed.

## Shared bound constants (`domain/action.py`)

| Constant | Value | Used by |
|---|---|---|
| `BATCH_REPEAT_COUNT_MIN` | `1` | `SemanticAction`, `BatchRepeatKeyDeclaration` |
| `BATCH_REPEAT_COUNT_MAX` | `50` | `SemanticAction`, `BatchRepeatKeyDeclaration` |
| `BATCH_REPEAT_INTERVAL_MS_MIN` | `0` | `SemanticAction`, `BatchRepeatKeyDeclaration` |
| `BATCH_REPEAT_INTERVAL_MS_MAX` | `500` | `SemanticAction`, `BatchRepeatKeyDeclaration` |
| `BATCH_REPEAT_INTERVAL_MS_DEFAULT` | `50` | Applied when `interval_ms` is omitted |

## Shared timeout constant (`execution/router.py`)

| Constant | Value | Used by |
|---|---|---|
| `BATCH_REPEAT_TIMEOUT_MARGIN_SECONDS` | `5.0` | `compute_batch_repeat_timeout_seconds()` |

Added post-`/speckit-analyze` remediation (finding F1, CRITICAL): the bound constants above allow a
worst-case batch (`count=50`, `interval_ms=500`) whose send duration (24.5s) exceeds the configured
default per-action timeout (10s, `vnc_agent/config/agent.yaml`). `compute_batch_repeat_timeout_seconds
(repeat_count, repeat_interval_ms, default_timeout_seconds)` returns
`max(default_timeout_seconds, (repeat_count - 1) * (repeat_interval_ms / 1000.0) +
BATCH_REPEAT_TIMEOUT_MARGIN_SECONDS)`, and `AgentRuntime.run_action_iteration()` passes this as an
explicit `timeout_seconds` override to `ExecutionRouter.execute()` for `press_key_repeat` actions only
— every other action type keeps using the router's static default, unchanged. This lives in the
execution layer (not alongside the count/interval *validation* bounds above) because it is a timing
concern, not a value-legality concern — the two are validated/sized independently.

## `BatchRepeatKeyDeclaration` (new — `domain/testcase.py`)

The test-case-authoring surface. One instance = one batch repeat declaration on a `TestStep`.

| Field | Type | Constraints | Notes |
|---|---|---|---|
| `key` | `str` | must satisfy `is_batch_repeatable_key()` (drivers/key_mapping.py) — i.e. a recognized, non-modifier single key | e.g. `"backspace"`, `"delete"`, `"tab"` |
| `count` | `int` | `BATCH_REPEAT_COUNT_MIN..BATCH_REPEAT_COUNT_MAX` inclusive, required | no default — author must state it (FR-006, FR-014) |
| `interval_ms` | `int \| None` | `None`, or `BATCH_REPEAT_INTERVAL_MS_MIN..BATCH_REPEAT_INTERVAL_MS_MAX` inclusive | `None` means "use the default" (FR-007) |

Validation runs at `load_test_case()` time (Pydantic `model_validator`), i.e. before a run starts.

## `TestStep` (extended — `domain/testcase.py`)

| Field | Type | Notes |
|---|---|---|
| `batch_repeat_key` | `BatchRepeatKeyDeclaration \| None = None` | **New, optional.** When set, `AgentRuntime.run_action_iteration()` bypasses the Planner call for this step's iterations and constructs the `SemanticAction` directly from this declaration. `intent` and `expected`/`max_retries` remain required and behave as today (label + post-action verification + whole-step retry budget). |

No other `TestStep` field changes. `TestCase.steps` validation is unaffected.

## `ActionType` (extended — `domain/action.py`)

Literal union gains one new member: `"press_key_repeat"`, alongside the existing `click`,
`double_click`, `right_click`, `type_text`, `press_key`, `hotkey`, `scroll`, `drag`, `wait`, `finish`.
`plan_validator.ALLOWED_ACTION_TYPES` (Planner-output whitelist) is **not** extended — the Planner is
never asked to produce this action type (see research.md).

## `SemanticAction` (extended — `domain/action.py`)

| Field | Type | Notes |
|---|---|---|
| `repeat_count` | `int \| None = None` | **New.** Required (and bound-checked) when `action_type == "press_key_repeat"`; MUST be `None` for every other `action_type`. |
| `repeat_interval_ms` | `int \| None = None` | **New.** Optional even when `action_type == "press_key_repeat"` (defaults to `BATCH_REPEAT_INTERVAL_MS_DEFAULT` downstream); MUST be `None` for every other `action_type`. |

New `model_validator` (in addition to the existing `reject_coords`) enforces, when
`action_type == "press_key_repeat"`:
- `keys` has exactly one entry, and that entry satisfies `is_batch_repeatable_key()`.
- `repeat_count` is set and within `[BATCH_REPEAT_COUNT_MIN, BATCH_REPEAT_COUNT_MAX]`.
- `repeat_interval_ms`, if set, is within `[BATCH_REPEAT_INTERVAL_MS_MIN, BATCH_REPEAT_INTERVAL_MS_MAX]`.

And, for every other `action_type`:
- `repeat_count` and `repeat_interval_ms` are both `None` (keeps existing action types provably
  untouched — FR-011/FR-012).

## `ExecutableAction` (extended — `domain/action.py`)

| Field | Type | Notes |
|---|---|---|
| `repeat_count` | `int \| None = None` | **New.** Carried through 1:1 from `SemanticAction.repeat_count` by `ActionPolicy.resolve()`. |
| `repeat_interval_ms` | `int \| None = None` | **New.** Carried through from `SemanticAction.repeat_interval_ms`, or the default if that was `None`. |

## `ExecutionResult` (extended — `domain/action.py`)

| Field | Type | Notes |
|---|---|---|
| `requested_count` | `int \| None = None` | **New.** Set only when `operation == "press_key_repeat"`; the declared repeat count. |
| `completed_count` | `int \| None = None` | **New.** Set only when `operation == "press_key_repeat"`; number of key sends actually completed before success or the first failure. Existing `error_code`/`error_message` fields carry the failure reason — no new failure-reason field needed. |

For every other `operation`, both fields remain `None`, matching today's `ExecutionResult` shape
exactly (FR-011/FR-012/SC-005).

## `KeyRepeatSendError` (new — `runtime/exceptions.py`)

Not persisted directly; caught by `ExecutionRouter.execute()` and translated into the
`ExecutionResult` fields above.

| Attribute | Type | Notes |
|---|---|---|
| `key` | `str` | the key being sent when the failure occurred |
| `requested_count` | `int` | the declared total |
| `completed_count` | `int` | how many sends succeeded before the failure |
| `cause` | `Exception` | the underlying driver error (chained via `raise ... from cause`) |

## State / lifecycle notes

- A `Batch Repeat Action` (spec's Key Entity) corresponds 1:1 to one `SemanticAction` with
  `action_type == "press_key_repeat"`, which resolves to exactly one `ExecutableAction`, which is
  executed by exactly one `ExecutionRouter.execute()` call — never more than one `ExecutableAction`
  per declared batch (FR-001, FR-002).
- A `Batch Repeat Execution Outcome` (spec's Key Entity) corresponds 1:1 to the `ExecutionResult`
  produced by that one `execute()` call: `success`, `requested_count`, `completed_count`,
  `error_code`, `error_message`.
- No new persisted database table or migration — `ExecutionResult` is already part of
  `ActionIteration` and flows through the existing storage/reporting path unchanged in shape (two
  additional optional columns picked up structurally, same as any other optional Pydantic field
  already on that model).
