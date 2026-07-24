# Phase 1 Data Model: Fix Keyboard Text Input

This feature adds **no new fields, models, or public types**. Per FR-013 (public contract stability)
and the research.md decision that the fix is fully contained in the private `_sync_text` method, no
existing Pydantic model (`SemanticAction`, `ExecutableAction`, `ExecutionResult`, `TestStep`, etc.)
changes shape. This document records the existing entities the fix touches and the one conceptual
classification rule the fixed code applies — for traceability, not schema change.

## `type_text` action (existing — `domain/action.py`, unchanged)

| Field | Type | Notes |
|---|---|---|
| `action_type` / `operation` | `"type_text"` | Existing literal, unchanged. |
| `text` | `str \| None` | Existing field carrying the declared text. `ExecutionRouter._dispatch` already normalizes `None` to `""` (`action.text or ""`, router.py line 124) — unchanged by this fix. |

## `ExecutionResult` (existing — unchanged)

| Field | Type | Notes |
|---|---|---|
| `success` | `bool` | `False` for any exception raised during `_sync_text` (FR-008), including the fixed character-send path. |
| `timed_out` | `bool` | Unaffected — governed by the existing `asyncio.wait_for` wrapper in `execute()`, not by `_sync_text` itself. |
| `error_code` | `str \| None` | `"error"` for a mid-send driver exception (existing generic `except Exception` branch, router.py line 106-117) — unchanged path, just no longer reachable via the wrong trigger (`AttributeError` on `.type`) for ordinary characters. |
| `error_message` | `str \| None` | `str(exception)` from whatever the fixed `client.keyPress(...)` call raises — no new formatting introduced. |

No new `error_code` value, no new `requested_count`/`completed_count`-style progress field is
introduced (research.md: "no partial-count contract exists for `type_text`, unlike the batch-repeat
key feature").

## Internal character classification rule (private to `_sync_text`, not a public type)

Applied per character of the declared text, in original order, unchanged in shape from before the fix
except for the fallback branch:

| Character class | Action | Status |
|---|---|---|
| `"\n"` | `client.keyPress("enter")` | Unchanged (already correct before this fix). |
| `"\t"` | `client.keyPress("tab")` | Unchanged (already correct before this fix). |
| Any other single character (printable ASCII per FR-003) | `client.keyPress(character)` | **Fixed** — was `client.type(character)`, a nonexistent method. |
| Empty string input | Loop body never executes; zero `keyPress`/`keyDown`/`keyUp` calls | Unchanged (already correct — an empty `for` loop is inherently a no-op), now explicitly required by FR-006. |

This is not a stored/serialized entity — it exists only as control flow inside one method — and is
documented here solely so the implementation and its regression tests can be traced back to FR-001
through FR-009.
