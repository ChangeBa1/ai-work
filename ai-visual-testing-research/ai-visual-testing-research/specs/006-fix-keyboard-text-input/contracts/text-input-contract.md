# Contract: Text Input Execution Path

Audience: engineers implementing/reviewing this fix. Describes (a) the public interfaces this feature
MUST leave unchanged (FR-013), and (b) the one internal method whose *body* changes, as the contract
regression tests target it directly.

## Public interfaces — preserved unchanged (no diff expected in these signatures)

| Interface | Signature | File |
|---|---|---|
| `VNCToolDriver.send_text` | `async def send_text(self, text: str) -> None` | `drivers/vncdotool_driver.py` |
| `KeyboardExecutor.type_text` | `async def type_text(self, text: str) -> None` | `execution/keyboard_executor.py` |
| `ExecutionRouter._dispatch` — `type_text` branch | `await self.keyboard.type_text(action.text or "")` for `action.method == "keyboard" and action.operation == "type_text"` | `execution/router.py` |
| `ExecutionRouter.execute` | Unchanged `try/except` structure; the fix relies on the existing generic `except Exception` branch, no new `except` clause added | `execution/router.py` |

A PR that touches any signature above (parameter names/types, return type, or the router's branch
condition) is out of contract for this fix and must be justified separately.

## Internal contract — `VNCToolDriver._sync_text` (private, body changes)

**Input**: `text: str` — the exact string declared by the `type_text` action (already normalized:
`None` → `""` upstream in the router, per the existing `action.text or ""`).

**Preconditions**: `self._client` is a connected vncdotool client exposing `keyPress(key: str)`
(plus `keyDown`/`keyUp`, used by other methods, not by this one). No precondition on focus state — the
caller (test step author, via a prior `click`/`double_click` step) is responsible for focus, per
spec Assumptions.

**Behavior**:
1. Iterate `text` character by character, in original order.
2. For `"\n"`: call `client.keyPress("enter")`.
3. For `"\t"`: call `client.keyPress("tab")`.
4. For any other character: call `client.keyPress(character)`.
5. On empty `text`: the loop body never executes — zero calls to the client (FR-006).
6. On any exception raised by a `keyPress` call: propagate immediately, without catching — no further
   characters are sent (FR-007), and the exception is not swallowed or converted (FR-008).

**Postconditions**:
- Success: every character was sent to `keyPress` in declared order; return value is `None` (matching
  the existing signature — no return-value contract change).
- Failure: the raised exception is whatever the client raised (e.g. connection error, protocol error);
  no partial-completion signal is added to the exception or elsewhere (research.md: no new
  `TextSendError`-style type; existing `ExecutionResult.error_message = str(exception)` path already
  carries whatever diagnostic string the underlying exception provides).

**Explicitly out of contract** (MUST NOT appear in `_sync_text` or anything it calls):
- No `client.type(...)` call (the removed defect).
- No `client.paste(...)` call (FR-010 — no clipboard usage).
- No reference to any business-specific string, field name, or branch (FR-014) — the method's
  behavior depends only on the characters of `text`, never on their business meaning.

## Regression test contract

A test MUST exist that:
1. Constructs a `VNCToolDriver` with a fake client object exposing `keyPress` (and, if convenient,
   `keyDown`/`keyUp`) but **not** `type` or `paste` — i.e. shaped like the real `VNCDoToolClient`
   surface (research.md).
2. Calls `_sync_text` (or the full `send_text` → driver path) with a string containing at least one
   character that is not `\n`/`\t`.
3. Asserts no `AttributeError` is raised and the fake client recorded a `keyPress` call for that
   character, in order.
4. Is demonstrably able to fail against the pre-fix implementation (i.e. reproduces the original
   `AttributeError` when run against `client.type`) — this is the FR-015 regression proof.

This test MUST NOT require a live VNC connection (Clarification Session 2026-07-24, Q1).
