# Contract: Internal Execution-Layer Interfaces

Audience: engineers implementing/reviewing this feature. Describes the new/extended internal
interfaces between `ActionPolicy`, `ExecutionRouter`, and `KeyboardExecutor`. All three classes keep
their existing public methods and signatures unchanged for every action type other than
`press_key_repeat`.

## `ActionPolicy.resolve()` — new branch

**Input**: `SemanticAction(action_type="press_key_repeat", keys=[<key>], repeat_count=<int>,
repeat_interval_ms=<int | None>)` — always already validated (see data-model.md).

**Output**: `PolicyResult(outcome="keyboard", executable=ExecutableAction(method="keyboard",
operation="press_key_repeat", keys=[<key>], repeat_count=<int>, repeat_interval_ms=<int>))`.

**Contract**:
- This branch is checked first (or at latest, before the existing "explicit keys/hotkey" branch),
  and returns unconditionally for `action_type == "press_key_repeat"` — it never falls through to
  focus-navigation, OCR/template matching, or Grounding.
- `repeat_interval_ms` on the outgoing `ExecutableAction` is never `None` — if the incoming
  `SemanticAction.repeat_interval_ms` is `None`, the branch substitutes
  `BATCH_REPEAT_INTERVAL_MS_DEFAULT` (50) before constructing the `ExecutableAction`.
- Every existing branch (explicit keys/hotkey, `type_text`, `wait`, `finish`, known-hotkey-by-keyword,
  focus navigation, OCR/template, Grounding) is untouched — none of them match
  `action_type == "press_key_repeat"`, and this new branch does not change their matching conditions.

## `ExecutionRouter._dispatch()` — new branch

**Input**: `ExecutableAction(method="keyboard", operation="press_key_repeat", keys=[<key>],
repeat_count=<int>, repeat_interval_ms=<int>)`.

**Behavior**: calls `await self.keyboard.press_key_repeat(action.keys[0], action.repeat_count,
action.repeat_interval_ms)` and returns its result (an `int`, the number of sends completed) up
through `_dispatch`'s return value so `execute()` can populate `ExecutionResult`.

**Contract**:
- `_dispatch()`'s return value is `None` for every operation except `press_key_repeat`, which is the
  only operation that returns the completed-send count. This is purely additive to `_dispatch()`'s
  return type (`None` → `int | None`); no existing caller inspects `_dispatch()`'s return value today.
- No screenshot, OCR, Planner, Grounder, or Verifier call is reachable from inside
  `KeyboardExecutor.press_key_repeat()` — it only calls `self.driver.send_key()` and, between sends,
  `asyncio.sleep()`.

## `ExecutionRouter.execute()` — result population

**Contract**:
- On success (`_dispatch()` returns without raising): if `action.operation == "press_key_repeat"`,
  `ExecutionResult.requested_count = action.repeat_count` and `.completed_count` = the value
  `_dispatch()` returned (equal to `requested_count` on full success). For every other operation, both
  fields stay `None` — identical to today's `ExecutionResult` shape.
- On `KeyRepeatSendError` (raised by `KeyboardExecutor.press_key_repeat()` — see below): caught
  alongside the existing generic `except Exception` handling; `ExecutionResult.success = False`,
  `.requested_count = e.requested_count`, `.completed_count = e.completed_count`,
  `.error_code = "key_repeat_partial"`, `.error_message` = a human-readable message built from
  `e.key`/`e.cause`.
- The existing `asyncio.TimeoutError` and generic-`Exception` branches are otherwise unchanged; a
  `KeyRepeatSendError` is a subtype of the existing exception handling path, not a new control-flow
  shape.

## `compute_batch_repeat_timeout_seconds()` — new pure function (execution/router.py)

```text
def compute_batch_repeat_timeout_seconds(repeat_count: int, repeat_interval_ms: int,
                                          default_timeout_seconds: float) -> float
```

Added as remediation for a CRITICAL gap found in `/speckit-analyze`: FR-006/FR-007's legal ranges
allow a worst-case batch (`count=50`, `interval_ms=500`) whose `(count - 1) * interval_ms / 1000.0`
duration (24.5s) exceeds the configured default per-action timeout (10s in
`vnc_agent/config/agent.yaml`). Without accounting for this, `ExecutionRouter.execute()`'s existing
`asyncio.TimeoutError` branch would fire mid-batch and — unlike the `KeyRepeatSendError` branch above
— does not populate `requested_count`/`completed_count`, silently violating FR-009 for a spec-legal
input.

**Contract**:
- `BATCH_REPEAT_TIMEOUT_MARGIN_SECONDS = 5.0` (module constant, execution/router.py).
- Returns `max(default_timeout_seconds, (repeat_count - 1) * (repeat_interval_ms / 1000.0) +
  BATCH_REPEAT_TIMEOUT_MARGIN_SECONDS)` — never smaller than the existing default, so short batches
  are unaffected.
- Pure function, no side effects, does not itself touch `ExecutionRouter.execute()`'s control flow.
- Callers (`AgentRuntime.run_action_iteration()`, see below) are responsible for passing the result as
  `execute(action, timeout_seconds=...)` for `press_key_repeat` actions; every other action type keeps
  passing `timeout_seconds=None` (today's behavior, router falls back to its own default).

## `AgentRuntime.run_action_iteration()` — batch declaration bypass

**Contract** (in addition to skipping the Planner call for a step with `batch_repeat_key` set):
- The bypass-constructed `SemanticAction` does **not** set `action_kind` explicitly. It is run through
  the same `if sa.action_kind is None: sa = sa.model_copy(update={"action_kind":
  classify_action_kind(sa)})` step the Planner path already applies, so it receives the same
  conservative `non_idempotent` default every other undeclared action gets — `RepeatGuard`'s safety
  checks are not weakened for a `press_key_repeat` action on step retry. (Remediation for a HIGH
  finding in `/speckit-analyze`: hardcoding `action_kind="idempotent"` for every declared key,
  including non-idempotent ones like `enter`, would have bypassed those checks.)
- `self.executor.execute(executable, timeout_seconds=...)` is called with
  `compute_batch_repeat_timeout_seconds(executable.repeat_count, executable.repeat_interval_ms,
  self.executor.default_timeout_seconds)` when `executable.operation == "press_key_repeat"`, and with
  `timeout_seconds=None` (today's behavior) otherwise.

## `KeyboardExecutor.press_key_repeat()` — new method

```text
async def press_key_repeat(self, key: str, count: int, interval_ms: int) -> int
```

**Contract**:
- Sends `key` via `self.driver.send_key(key)` exactly `count` times, each send a discrete
  press-and-release — no key-down/wait/key-up "held" mode (FR-010).
- Between consecutive sends (not after the last one), sleeps `interval_ms / 1000.0` seconds.
- **Fail-fast**: on the first exception raised by `self.driver.send_key()`, the loop stops
  immediately (no further sends, no retry of the failed send) and the method raises
  `KeyRepeatSendError(key=key, requested_count=count, completed_count=<sends completed so far>,
  cause=<original exception>)`.
- On full completion with no exception, returns `count`.
- Performs no screenshot, OCR, Planner, Grounder, or Verifier call — it is a pure
  driver-call-and-sleep loop, same execution-layer altitude as the existing `type_text`/`press_key`/
  `hotkey` methods on this class.
- Does not call `release_modifiers()` — batch-repeated keys are never modifier keys (enforced
  upstream by `SemanticAction`/`BatchRepeatKeyDeclaration` validation), so there is nothing to
  release.

## Compatibility contract (all three components)

- `KeyboardExecutor.type_text`, `.press_key`, `.hotkey`, `.focus_nav`, `.release_modifiers`: no
  signature or behavior change.
- `ExecutionRouter.execute()`'s behavior for `operation in {"type_text", "press_key", "hotkey",
  "click", "double_click", "right_click", "scroll", "drag", "wait", "finish"}`: byte-for-byte
  unchanged — verified by the existing test suite continuing to pass unmodified (`test_execution.py`,
  `test_action_policy_priority.py`, `test_scenario_02_keyboard_first.py`, and any other test currently
  exercising these operations).
