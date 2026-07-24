# Phase 0 Research: Fix Keyboard Text Input (`type_text` Driver Defect)

All items below were resolved by reading the currently installed `vncdotool` package source
(`vnc_agent/.venv/Lib/site-packages/vncdotool/client.py`), the project's own driver
(`vnc_agent/src/vnc_agent/drivers/vncdotool_driver.py`), `execution/router.py`,
`execution/keyboard_executor.py`, `drivers/key_mapping.py`, the dependency lock (`vnc_agent/uv.lock`,
installed `vncdotool-1.3.0.dist-info`), and existing test conventions
(`tests/integration/test_vncdotool_driver_lifecycle.py`, `tests/unit/test_keyboard_executor_repeat.py`,
`tests/unit/test_execution_router_batch_repeat.py`). No `NEEDS CLARIFICATION` markers remain in the
Technical Context.

## Decision: Confirmed dependency version and client API surface

**Decision**: The resolved/installed dependency is `vncdotool==1.3.0` — confirmed both via
`pip show vncdotool` (Version: 1.3.0) and via `vnc_agent/.venv/Lib/site-packages/vncdotool-1.3.0.dist-info`,
which is what `vnc_agent/uv.lock` pins for the `vnc-agent` project (`pyproject.toml` itself only
declares the unpinned `"vncdotool"` dependency; the lock file is the source of truth for the resolved
version). Reading `vncdotool/client.py` directly confirms the `VNCDoToolClient` class (line 152)
defines `keyPress` (line 194), `keyDown` (line 208), `keyUp` (line 216), and `paste` (line 428) —
and defines **no** `type` method anywhere in the file or its base class `rfb.RFBClient`.

**Rationale**: This is the exact root cause of the accident. `VNCToolDriver._sync_text` (line 187-195)
calls `client.type(ch)` for every non-newline/non-tab character. `api.connect()` returns a
`ThreadedVNCClientProxy` whose `__getattr__` forwards unknown attributes to
`self.factory.protocol` — the `VNCDoToolClient` **class** object (Twisted protocol-class attribute,
not yet an instance) — which has no `type` attribute, producing exactly
`AttributeError: type object 'VNCDoToolClient' has no attribute 'type'`.

**Alternatives considered**: None — this is a direct source read, not a design choice.

## Decision: `paste()` is not usable for this fix

**Decision**: `VNCDoToolClient.paste(message)` (client.py line 428) sends the given text as the
**remote clipboard content** (an RFB `ClientCutText` message) and does not simulate keystrokes into
the currently focused control. It is not used to implement `type_text`.

**Rationale**: Using `paste()` would functionally depend on the target application supporting/reacting
to a clipboard-paste action (e.g. Ctrl+V or an app-specific paste gesture) to actually land the text in
a focused field — which is exactly the "remote clipboard / Ctrl+V" mechanism the spec's FR-010
prohibits. It also would not satisfy FR-001's "keyboard input" framing consistently with
FR-004/FR-005's existing newline/Tab-as-keypress semantics, which already rely on `keyPress`, not
clipboard operations.

**Alternatives considered**: `paste()` was the only other plausible built-in text-sending primitive on
`VNCDoToolClient`; rejected per FR-010 and per the constitution's keyboard-first execution priority
(Principle III) — clipboard injection is not a keyboard action.

## Decision: Per-character `keyPress(character)` for the supported character set

**Decision**: For every character in the declared text that is not `\n` or `\t`, call
`client.keyPress(character)` (a single-character string), preserving order via a plain `for` loop.
Newline continues to map to `client.keyPress("enter")`, and Tab continues to map to
`client.keyPress("tab")` — both unchanged from the current (already-working) branches in
`_sync_text`.

**Rationale**: `VNCDoToolClient._decodeKey` (client.py line 177-187) handles this correctly today for
every printable ASCII character without any code change: for a single-character key, it does
`KEYMAP.get(k) or ord(k)`. `KEYMAP` (client.py line 31) only contains multi-character named keys
(`"bsp"`, `"tab"`, `"return"`, `"enter"`, `"esc"`, arrow names, etc.) — no single-character entries —
so any single ASCII character (digit, letter, punctuation) falls through to `ord(k)`, which is the
correct RFB/X11 keysym for printable ASCII (keysym value equals the character's code point for the
whole printable ASCII range). This was verified by reading `client.py` directly; no `force_caps`
configuration is required for uppercase letters or shifted punctuation (`force_caps` defaults to
`False` on `VNCDoToolFactory`, and is only relevant for local-physical-Shift-key emulation, not for
keysym correctness) — the driver does not set it today and does not need to.

**Alternatives considered**:
- *Batch/bulk send via a single API call.* Rejected: `VNCDoToolClient` has no such method (confirmed
  above), and per-character `keyPress` already satisfies FR-001 (ordered, complete delivery) with no
  new dependency.
- *Route through `keyDown`/`keyUp` pairs per character instead of `keyPress`.* Rejected: `keyPress`
  already does exactly `keyDown` then `keyUp` internally (client.py line 194-206) for a single key;
  using it directly is the minimal-diff choice and matches the existing `_sync_key` method's own use
  of `keyPress` for named keys.

## Decision: Fail-fast propagation — no new exception type

**Decision**: `_sync_text` performs no its own try/except around the per-character `keyPress` calls.
Any exception raised by `client.keyPress(...)` propagates unmodified out of `_sync_text` →
`send_text` → `KeyboardExecutor.type_text` → `ExecutionRouter._dispatch`, where the existing
`execute()` method's generic `except Exception as e` clause (router.py line 106-117) already
constructs `ExecutionResult(success=False, error_code="error", error_message=str(e), ...)`.

**Rationale**: This directly satisfies FR-007/FR-008/FR-009 with zero new control-flow shapes,
matching the user's explicit minimal-fix instruction. Unlike Feature 005's batch-repeat-key fix
(which introduced `KeyRepeatSendError` to carry `requested_count`/`completed_count` because the
router needed to report partial progress for a *counted* repeat action), `type_text` has no
count-based progress contract to report — FR-008 only requires that a mid-send failure not be
reported as success, which the existing generic exception path already guarantees today (it is only
the specific `AttributeError` from the nonexistent `.type()` call that currently reaches this path;
the fix does not change how the router handles it, only removes the wrong method call that triggers
it in the one working case and would otherwise still trigger it for every other non-mapped
character).

**Alternatives considered**: A dedicated `TextSendError` mirroring `KeyRepeatSendError`. Rejected:
there is no partial-count or structured recovery data to carry (`ExecutionResult` has no equivalent
"characters sent so far" field, and FR-016/spec explicitly scope this to a minimal fix); adding one
would be an unrequested public-contract change to `ExecutionResult` with no acceptance criterion
requiring it.

## Decision: Regression test layer — stand-in/fake client, no live VNC required

**Decision** (confirmed by Clarification Session 2026-07-24, Q1): The automated regression test for
FR-015 uses a fake client object that exposes only `keyPress` (deliberately omitting `type`, `paste`,
etc.) injected as `driver._client` on a real `VNCToolDriver` instance (matching the existing
`tests/integration/test_vncdotool_driver_lifecycle.py` pattern of monkeypatching driver internals
rather than connecting to a live VNC server). This test must fail against the pre-fix `_sync_text`
(reproducing `AttributeError: ... has no attribute 'type'` when a fake client without `.type` is used)
and pass after the fix.

**Rationale**: Matches existing project test conventions exactly (no new test infrastructure needed);
runs fast and deterministically in CI; live-VNC confirmation is a separate, already-distinct concern
covered by SC-001 (real `pos-scan-magazine-checkout.yaml` run against `win10-test-01`).

**Alternatives considered**: Mocking at the `KeyboardExecutor`/`ExecutionRouter` layer only (as
`test_keyboard_executor_repeat.py` / `test_execution_router_batch_repeat.py` do with `AsyncMock`
drivers). Rejected as the *sole* regression test: those layers are trivial pass-throughs
(`KeyboardExecutor.type_text` is a one-line `await self.driver.send_text(text)`); the actual bug lives
inside `VNCToolDriver._sync_text`'s interaction with the vncdotool client object, so the regression
test must exercise that exact boundary to have caught the original defect. Router/executor-level tests
are still added as secondary coverage (see below), not as the sole regression proof.

## Decision: Second unrelated scenario for FR-016 — synthetic contract test, not a second live testcase

**Decision** (confirmed by Clarification Session 2026-07-24, Q2): The two required "unrelated
scenarios" are (1) the real accident testcase `pos-scan-magazine-checkout.yaml` step
`type-barcode-45127366`, confirmed via a live VNC run (SC-001), and (2) a synthetic/contract-level
scenario at the fake-client test tier — e.g. asserting the same `_sync_text` code path against a
different character set (mixed letters/punctuation) and a different simulated control context — with
no core-code branching on which scenario is active.

**Rationale**: Satisfies constitution Principle VI's "at least two unrelated GUI scenarios" gate
without requiring a second live-VNC business testcase, keeping the fix's test cost proportional to a
minimal driver-layer fix. The generic/business-agnostic proof is that the *same* unmodified
`_sync_text` code, driven only by its `text: str` parameter, is exercised successfully under two
independent inputs/contexts — not that two different business YAMLs exist.

**Alternatives considered**: Require a second full live-VNC business testcase (e.g. a login or cart
flow). Rejected per the clarification answer: disproportionate cost for a fix whose core code has no
business awareness to begin with; the synthetic contract test already proves genericity at the layer
where genericity actually lives (the driver method takes a plain string, not a business object).

## Decision: Public contract — no signature or call-site changes

**Decision**: `VNCToolDriver.send_text(text: str) -> None`, `KeyboardExecutor.type_text(text: str) ->
None`, and `ExecutionRouter._dispatch`'s existing `type_text` branch
(`await self.keyboard.type_text(action.text or "")`, router.py line 124) are unchanged. Only the body
of the private `_sync_text` method changes.

**Rationale**: Directly satisfies FR-013. Verified against the current code: `send_text`,
`type_text`, and the router's `type_text` dispatch branch contain no reference to `.type(...)` or
anything else internal to `_sync_text` — the fix is fully contained within one private method.

**Alternatives considered**: None — this is the only change consistent with FR-012/FR-013's
minimal-surface constraint.

## Technical Context (resolved)

- **Language/Version**: Python 3.12 (`pyproject.toml` `requires-python = ">=3.12"`).
- **Primary Dependencies**: `vncdotool==1.3.0` (locked, see above); no new dependency introduced.
- **Storage**: N/A — this fix touches no persistence layer.
- **Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`), existing `tests/unit/`,
  `tests/integration/`, `tests/e2e/` layout.
- **Target Platform**: Windows VNC target (`win10-test-01`, `vnc_agent/config/vnc-targets.yaml`) for
  live confirmation; cross-platform for the offline regression suite.
- **Project Type**: Single project (`vnc_agent/`), no frontend/backend split.
- **Performance Goals**: N/A beyond existing per-character send behavior already in place for
  newline/Tab; no new performance target introduced.
- **Constraints**: No third-party (`site-packages`) edits (FR-012); no public contract changes
  (FR-013); no business-specific branching in core code (FR-014, constitution Principle VI).
- **Scale/Scope**: Single private method (`_sync_text`) in one file
  (`vnc_agent/src/vnc_agent/drivers/vncdotool_driver.py`); new/updated tests in
  `tests/integration/` and `tests/unit/`.
