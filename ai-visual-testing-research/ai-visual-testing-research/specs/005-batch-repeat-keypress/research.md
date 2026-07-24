# Phase 0 Research: Batch Repeat Key Press

All items below were resolved during `/speckit-specify` clarification (2026-07-24) and by reading the
current implementation (`domain/action.py`, `domain/testcase.py`, `planning/action_policy.py`,
`execution/router.py`, `execution/keyboard_executor.py`, `drivers/key_mapping.py`,
`runtime/agent_runtime.py::run_action_iteration`). No `NEEDS CLARIFICATION` markers remain in the
Technical Context.

## Decision: Where the batch declaration lives — TestStep field, not Planner output

**Decision**: Add an optional `batch_repeat_key: BatchRepeatKeyDeclaration | None` field to
`TestStep` (domain/testcase.py). When set, `AgentRuntime.run_action_iteration()` skips the Planner
call entirely for that `ActionIteration` and constructs the `SemanticAction` deterministically from
the declaration.

**Rationale**:
- The spec's non-goal is explicit: repeat count is always author-declared, never computed by a model
  (FR-014). The current per-key Backspace behavior in `pos-scan-magazine-checkout.yaml` exists
  *because* the step's `intent` prose already asks the Planner to loop ("本步骤可能通过多次重试连续
  Backspace 直到框空") and the Planner conservatively does one key per call anyway — asking an LLM to
  reliably emit "repeat_count=20" in one shot from a prose intent would just move the same
  unreliability into a new place, not remove it.
- Constitution Principle I requires the runtime control flow to be code-driven, not model-driven;
  bypassing the Planner for a fully-declared, bounded action is the more constitutional design, not
  less.
- The user's own plan brief lists exactly four layers to reuse — `StructuredAction`/`SemanticAction`,
  `ActionPolicy`, `ExecutionRouter`, `KeyboardExecutor` — and conspicuously omits the Planner. A
  declarative bypass is the only design consistent with that list.
- `plan_validator.py`'s `ALLOWED_ACTION_TYPES` whitelist (used only to validate *Planner LLM output*)
  never needs to learn about `press_key_repeat`, because the Planner is never asked to produce it —
  this alone removes an entire class of changes (prompt/schema/parser updates) that the "model
  decides" alternative would have required, directly serving the "minimal, no unrelated refactor"
  constraint.

**Alternatives considered**:
- *Let the Planner emit `press_key_repeat` from intent text.* Rejected: reintroduces LLM
  non-determinism for a value (count) the spec requires to be exact and author-controlled; would
  require touching `plan_validator.py`, the Planner prompt/schema, and `models/response_parser.py` —
  a much larger surface for no benefit.
- *A single generic "macro" step type that runs an arbitrary list of actions.* Rejected explicitly by
  spec non-goals ("不实现通用宏或多动作脚本") and FR-015.

## Decision: Single-key vocabulary source of truth

**Decision**: Add `is_batch_repeatable_key(name: str) -> bool` to `drivers/key_mapping.py`, built on
the existing `KEY_MAP` / `MODIFIERS` / `normalize_key`. Both the `SemanticAction` validator
(domain/action.py) and the `BatchRepeatKeyDeclaration` validator (domain/testcase.py) call this one
helper.

**Rationale**: The spec's Assumption states the batch action must reuse the existing accepted
key-name list rather than introduce a second one to maintain. `key_mapping.py` is already a
dependency-free leaf module (no imports from `domain`/`planning`/`execution`), so `domain/` importing
from it introduces no circular-import risk. Duplicating the modifier/key-name list inside `domain/`
instead was considered and rejected — it would drift the moment `KEY_MAP` gains a new key.

**Alternatives considered**: Duplicate a small modifier-only frozenset directly in `domain/action.py`
to avoid a domain→drivers import. Rejected: the spec assumption explicitly calls for one list, and
`key_mapping.py` has no dependencies of its own, so there is no layering hazard to avoid.

## Decision: Bounds enforcement — Pydantic validators at both the TestStep and SemanticAction layers

**Decision**: Two validation gates, sharing one set of constants
(`BATCH_REPEAT_COUNT_MIN/MAX = 1/50`, `BATCH_REPEAT_INTERVAL_MS_MIN/MAX/DEFAULT = 0/500/50`, defined
once in `domain/action.py` and imported by `domain/testcase.py`):
1. `BatchRepeatKeyDeclaration` (testcase-authoring surface) — validated the moment `load_test_case()`
   parses the YAML, before a run even starts.
2. `SemanticAction` (runtime object, action_type == "press_key_repeat") — validated again at
   construction time inside `run_action_iteration()`, before `ActionPolicy.resolve()` is called and
   therefore before any key is sent.

**Rationale**: FR-008 requires all of FR-005/006/007's validation to complete before the first key
send. Validating at YAML-load time catches authoring mistakes at the earliest possible point (long
before a VNC session even opens); re-validating at the `SemanticAction` boundary keeps that guarantee
true for any future caller that constructs a `SemanticAction` directly (tests, tooling) without going
through YAML loading. Both gates are cheap Pydantic model validators, not new runtime services.

**Alternatives considered**: Validate only once, in `KeyboardExecutor.press_key_repeat()`, right
before the loop starts. Rejected: this would still satisfy "before the first key is sent" literally,
but would push rejection past the entire Observe→Plan→Resolve pipeline of an `ActionIteration`
(wasting a screenshot and, if the bypass were not in place, a Planner call), and would not give
authors load-time feedback on a malformed test case.

## Decision: Fail-fast semantics and where partial-progress is captured

**Decision**: `KeyboardExecutor.press_key_repeat(key, count, interval_ms) -> int` sends keys in a
plain `for` loop; on the first `driver.send_key()` exception it stops immediately and raises a new
`KeyRepeatSendError(key, requested_count, completed_count, cause)` (runtime/exceptions.py). No
per-key retry happens inside this method. `ExecutionRouter.execute()` catches this exception
specifically (in addition to its existing generic `except Exception`) and populates
`ExecutionResult.requested_count` / `.completed_count` / `.error_code` / `.error_message` from it. On
full success, the method returns `count`, and `execute()` sets `requested_count == completed_count`.

**Rationale**: Matches the clarified decision (`Session 2026-07-24`): stop immediately, no per-key
retry inside the batch action; retries of a *whole* failed step remain the job of the existing
Recovery Engine / `TestStep.max_retries`, unchanged. Reusing the existing exception-based error
propagation pattern already used for `ActionTimeoutError` keeps `ExecutionRouter.execute()`'s
try/except structure intact — no new control-flow shape, matching "minimal, no unrelated refactor."

**Alternatives considered**: Return a result/outcome object from `press_key_repeat()` instead of
raising on failure, with `execute()` branching on it explicitly for both the success and failure
paths. Rejected as a viable *implementation* detail equally valid to the chosen one, but the
exception-based version was preferred because `execute()`'s existing `try/await asyncio.wait_for(...)
/ except` skeleton already exists for exactly this shape of "something in `_dispatch` failed
partway," minimizing the diff.

## Decision: `press_key`, `hotkey`, `type_text` compatibility

**Decision**: All new fields on `SemanticAction`, `ExecutableAction`, and `ExecutionResult` are
`Optional`, defaulting to `None`, and are only ever populated when `action_type`/`operation ==
"press_key_repeat"`. No existing branch in `ActionPolicy.resolve()` or
`ExecutionRouter._dispatch()`/`execute()` is modified — only new branches are added ahead of or
alongside them.

**Rationale**: Directly satisfies FR-011/FR-012/SC-005. Verified against the current code: none of
the three existing keyboard branches in `ActionPolicy.resolve()` (explicit keys/hotkey, `type_text`,
focus-navigation) or in `ExecutionRouter._dispatch()` reference `action_type`/`operation` values other
than their own literal string, so adding a new `elif`/early-return branch cannot change their
matching.

**Alternatives considered**: None — this is a straightforward additive-only change once the earlier
decisions are made.
