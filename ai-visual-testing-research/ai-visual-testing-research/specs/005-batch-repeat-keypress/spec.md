# Feature Specification: Batch Repeat Key Press

**Feature Branch**: `005-batch-repeat-keypress`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "在现有 VNC Agent 键盘动作系统上追加批量重复按键能力。在同一个 ActionIteration 内连续发送指定按键若干次，完成后再统一执行一次稳定等待和动作后验证，首要场景是连续发送 Backspace 清空 Barcode 输入框。"

## Clarifications

### Session 2026-07-24

- Q: 批量重复按键的次数（repeat count）应如何限定取值范围与必填性？ → A: 必填，范围 1–50（无默认值，作者必须显式声明）
- Q: 可选的按键间隔（interval）应如何限定取值范围与默认值？ → A: 0–500ms，默认 50ms
- Q: 批量重复动作允许作用于哪些按键？是否排除修饰键？ → A: 沿用 press_key 全部按键，排除修饰键（ctrl/alt/shift/win）
- Q: 批量发送过程中某一次按键失败时，系统应立即中止，还是尽力发送完剩余次数？ → A: 立即中止（fail-fast），不做单键重试；单键重试仍由现有 Recovery Engine 负责
- Q: ScannerSimulator 的 Barcode 清空步骤，动作后验证应确认什么才算成功？ → A: 仅确认 Barcode 输入框为空（内容检查），不重复确认焦点状态

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clear a text field with one declared action (Priority: P1)

A test case author needs a test step that empties a text input field (e.g. the ScannerSimulator "Barcode" box) by pressing the same key multiple times in a row. Today they must write one test step per key press, and each step pays the full cost of a fresh screenshot, OCR read, planner call, and post-action check. The author wants to declare "press Backspace 20 times" as a single step and have the system carry it out as one unit of work, with observation and verification happening only once, before and after the whole burst.

**Why this priority**: This is the entire reason the feature exists — without it, there is no reduction in run time or model calls, and the ScannerSimulator use case cannot be simplified. It is also the only story required for a usable MVP.

**Independent Test**: Author a test step that repeats "backspace" 20 times against a populated input field and run it. The field ends up empty, and the run log shows exactly one pre-action observation and one post-action verification for that step, with no screenshots or model calls in between the individual key sends.

**Acceptance Scenarios**:

1. **Given** a Barcode input field containing 8 characters and focused, **When** a test step declares a batch repeat of "backspace" 20 times, **Then** the system sends the key 20 times in immediate succession within one action step, the field ends up empty, and only one post-action verification is performed for the step.
2. **Given** a batch repeat step with an optional delay between key sends, **When** the step executes, **Then** the system waits the declared delay between each key send and still performs only one pre-action observation and one post-action verification for the whole step.
3. **Given** a batch repeat step targeting a field, **When** the step runs to completion, **Then** the run's evidence record shows one action step (not one per key press) covering the whole burst.

---

### User Story 2 - Reject invalid batch requests before anything runs (Priority: P2)

A test case author mistypes the key name, sets the repeat count to zero, an extreme value, or a negative interval. The author expects the system to catch this before touching the screen, so a bad test case fails fast with a clear reason instead of partially executing or hanging.

**Why this priority**: Prevents wasted runs, unpredictable device state, and silent misbehavior (e.g. an unbounded repeat count). This is a safety rail around Story 1 and depends on the batch action existing, so it ranks after it, but it is required before the feature can be trusted in real test suites.

**Independent Test**: Author test steps with (a) an unsupported key name, (b) a repeat count of 0, (c) a repeat count above the allowed maximum, and (d) a negative interval. Run each independently and confirm each is rejected before any key is sent, with a message naming which value was invalid.

**Acceptance Scenarios**:

1. **Given** a batch repeat step naming a key that is not part of the accepted key set, **When** the test case is validated, **Then** the step is rejected with an error identifying the invalid key, and no key is sent.
2. **Given** a batch repeat step with a repeat count of 0 or a count above the documented maximum, **When** the test case is validated, **Then** the step is rejected with an error identifying the invalid count, and no key is sent.
3. **Given** a batch repeat step with a negative or otherwise out-of-range interval, **When** the test case is validated, **Then** the step is rejected with an error identifying the invalid interval, and no key is sent.

---

### User Story 3 - Get an accurate report when a batch is interrupted (Priority: P2)

A test run's batch key-send is interrupted partway through (e.g. the connection drops, the target device stops responding). The author reviewing the failed run needs to know how many key presses were planned, how many were actually sent before the interruption, and why it stopped — not just "step failed."

**Why this priority**: Without this, a partial failure mid-burst is indistinguishable from a full failure, making diagnosis slow. It matters as soon as the batch action exists in real runs, but it is a reporting/diagnostic concern layered on top of Story 1's core execution path.

**Independent Test**: Trigger an interruption partway through a batch repeat step (e.g. simulate a send failure after N of M key presses) and confirm the failure record states the planned count, the count actually sent, and the failure reason.

**Acceptance Scenarios**:

1. **Given** a batch repeat step planned for 20 key sends, **When** the underlying send fails after 7 successful sends, **Then** the step's failure record states a planned count of 20, a sent count of 7, and the reason the 8th send failed.
2. **Given** a batch repeat step that fails before any key is sent (e.g. the target loses focus first), **When** the failure is recorded, **Then** the sent count is reported as 0 along with the planned count and reason.

---

### Edge Cases

- What happens when the batch repeat targets a key already reachable via `press_key` today (e.g. "backspace", "delete", "enter")? The accepted key set for batch repeat MUST be drawn from the same single-key vocabulary already supported by `press_key`; key combinations (`hotkey`) are out of scope for batch repeat.
- What happens when the repeat count is 1? This is a degenerate but valid case: it behaves like a single `press_key` wrapped in the batch mechanism (one send, one pre/post observation cycle) and MUST NOT be rejected, since 1 is the documented minimum (FR-006).
- What happens if no interval is declared? The system MUST use a defined default spacing between sends rather than sending with zero delay by default, to avoid overwhelming the target device or losing key events.
- What happens when the field being cleared already has fewer characters than the declared repeat count (e.g. 20 Backspaces against a 5-character field)? The extra key sends beyond the field's content are harmless no-ops from the field's perspective; the step still completes as one action with one post-action verification, and verification judges the end state (field empty), not the exact character-by-character path.
- What happens if a batch repeat step is declared with an interval but the target device cannot keep up? This is treated the same as any other mid-burst send failure — captured under Story 3's interrupted-execution reporting.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow a test step to declare a single batch repeat action consisting of exactly one key, a repeat count, and an optional interval between sends.
- **FR-002**: The system MUST send the declared key the declared number of times, in immediate succession (subject only to the declared interval), entirely within one action step.
- **FR-003**: The system MUST NOT perform any screenshot capture, OCR read, planner call, grounding call, or verifier call between individual key sends within a batch repeat step.
- **FR-004**: The system MUST perform exactly one pre-action observation before the batch repeat begins and exactly one post-action stability wait and verification after the batch repeat completes (or is interrupted), matching the existing action-step lifecycle used by other action types.
- **FR-005**: The system MUST restrict the batch repeat key to the same single, non-combination key vocabulary already accepted by the existing single key-press action, EXCLUDING modifier keys (ctrl, alt, shift, win/super); a batch repeat step MUST NOT declare a modifier key as its target, and any key outside that non-modifier vocabulary MUST be rejected before sending begins.
- **FR-006**: The system MUST require an explicit repeat count between 1 and 50 inclusive, with no default value; the system MUST reject a declared repeat count of 0, negative, or above 50 before any key is sent, and the rejection reason MUST identify the invalid count.
- **FR-007**: The system MUST accept an optional interval between 0 and 500 ms inclusive, defaulting to 50 ms when not declared; the system MUST reject a declared interval outside that range before any key is sent, and the rejection reason MUST identify the invalid interval.
- **FR-008**: The system MUST perform all validation in FR-005, FR-006, and FR-007 prior to sending the first key of the batch, so an invalid declaration results in zero key sends.
- **FR-009**: When a single key send within a batch repeat step fails, the system MUST stop sending further keys immediately (fail-fast; the batch action itself MUST NOT retry the failed send), and MUST record the planned repeat count, the number of key sends actually completed before stopping, and the reason for the failure. Recovery/retry behavior beyond the batch action itself remains governed by the existing recovery mechanism used for other action types.
- **FR-010**: The system MUST NOT support a "held" or "long press" key mode as part of this feature; each repeated send is a discrete press-and-release of the declared key.
- **FR-011**: The system MUST NOT alter the observable behavior, evidence output, or verification flow of the existing single key-press, key-combination, and text-typing actions.
- **FR-012**: Existing test cases that use the existing single key-press, key-combination, and text-typing actions MUST continue to run and pass without modification after this feature is introduced.
- **FR-013**: The ScannerSimulator Barcode-clearing test case MUST be updated to declare one batch repeat step in place of the current multi-step, multi-retry Backspace sequence; that step's post-action verification MUST check only that the Barcode field is empty (a content-based check), without independently re-confirming input focus.
- **FR-014**: The system MUST NOT compute the batch repeat count automatically from the current on-screen content (e.g. counting recognized characters); the count is always an author-declared value.
- **FR-015**: The system MUST NOT support declaring more than one key or more than one distinct action within a single batch repeat step (no general-purpose multi-action macros).

### Key Entities

- **Batch Repeat Action**: A single declared action step consisting of one key identifier, a repeat count, and an optional inter-send interval. Produces one pre-action observation and one post-action verification regardless of the repeat count.
- **Batch Repeat Execution Outcome**: The recorded result of running a Batch Repeat Action, including the planned repeat count, the actually-completed send count, and — when execution did not fully complete — the reason it stopped.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A test step that clears a text field via 20 repeated key presses completes as a single action step, with exactly one pre-action observation and one post-action verification recorded for that step.
- **SC-002**: No screenshot, OCR, planner, grounding, or verification calls occur between the first and last key send within a batch repeat step, for any repeat count within the allowed range.
- **SC-003**: Test steps declaring an unsupported key, an out-of-range repeat count, or an out-of-range interval are rejected before any key is sent, in 100% of such cases.
- **SC-004**: When a batch repeat step is interrupted partway through, the reported outcome states the planned count and the actually-completed count, and the two values differ from each other whenever the interruption occurs before completion.
- **SC-005**: All test cases exercising the existing single key-press and key-combination actions continue to pass, unmodified, after this feature ships.
- **SC-006**: The ScannerSimulator Barcode-clearing scenario completes its field-clearing portion in one action step instead of the multiple retried steps it requires today.
- **SC-007**: Clearing a Barcode field of typical length (up to 20 characters) via batch repeat takes measurably less wall-clock time and fewer model calls than the equivalent one-press-per-step approach it replaces.

## Assumptions

- "Same single-key vocabulary already supported by `press_key`" (minus modifier keys, per FR-005) means the batch action reuses the existing accepted key-name list rather than introducing a new or separate list to maintain.
- Interruption reporting (Story 3) reuses the existing failure/evidence recording mechanism already in place for other action types, extended with the two additional fields (planned count, sent count) rather than a new reporting subsystem.
- This feature applies only to keyboard actions; no equivalent "batch repeat" is being requested for mouse actions (click, drag, scroll) or for `type_text`.
