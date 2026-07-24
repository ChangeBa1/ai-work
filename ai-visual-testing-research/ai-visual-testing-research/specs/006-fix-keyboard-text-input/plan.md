# Implementation Plan: 修复键盘文本输入能力（type_text 驱动缺陷）

**Branch**: `006-fix-keyboard-text-input` | **Date**: 2026-07-24 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-fix-keyboard-text-input/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

`VNCToolDriver._sync_text` (`drivers/vncdotool_driver.py`) currently calls `client.type(ch)` for
every non-newline/non-tab character, but the installed `vncdotool==1.3.0` client
(`VNCDoToolClient`) has no `type` method — only `keyPress`/`keyDown`/`keyUp`/`paste`. This is the
exact defect that failed run `18ba967a-822c-4860-a90d-d8e849205a75` on the
`pos-scan-magazine-checkout.yaml` `type-barcode-45127366` step. The fix replaces the broken
fallback branch with `client.keyPress(character)` per character (verified correct for the full
printable-ASCII range via `VNCDoToolClient._decodeKey`'s `ord()` fallback), leaves the already-working
newline→`keyPress("enter")` / Tab→`keyPress("tab")` branches untouched, and changes nothing else —
no new exception type, no public signature changes to `VNCDriver.send_text`,
`KeyboardExecutor.type_text`, or `ExecutionRouter`. Regression coverage uses a fake vncdotool client
(no `type`/`paste`) at the driver boundary — the only layer where the original bug actually lived —
plus existing-pattern unit tests at the `KeyboardExecutor`/`ExecutionRouter` layers, all running
without a live VNC session; a live-VNC rerun of the original testcase is the separate, final
confirmation (SC-001).

## Technical Context

**Language/Version**: Python 3.12 (`vnc_agent/pyproject.toml` `requires-python = ">=3.12"`)

**Primary Dependencies**: `vncdotool==1.3.0` (resolved/locked via `vnc_agent/uv.lock`; installed at
`vnc_agent/.venv/Lib/site-packages/vncdotool-1.3.0.dist-info`) — no new dependency added

**Storage**: N/A — this fix touches no persistence layer

**Testing**: `pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`, `vnc_agent/pyproject.toml`),
existing `tests/unit/`, `tests/integration/`, `tests/e2e/` layout

**Target Platform**: Windows VNC target (`win10-test-01`, `vnc_agent/config/vnc-targets.yaml`) for
the live confirmation run; cross-platform for the offline automated regression suite

**Project Type**: Single project (`vnc_agent/`) — no frontend/backend split

**Performance Goals**: N/A — no new performance target; per-character send rate is unchanged from
today's already-correct newline/Tab branches

**Constraints**: No edits to `.venv/Lib/site-packages/vncdotool` (FR-012); no change to
`VNCDriver.send_text`/`KeyboardExecutor.type_text`/`ExecutionRouter` public signatures (FR-013); no
business-specific keyword/branch in core code (FR-014, constitution Principle VI); no clipboard/
Ctrl+V usage (FR-010)

**Scale/Scope**: One private method (`VNCToolDriver._sync_text`) in one file; new tests in
`tests/integration/` (the real-driver regression, per the `test_no_real_vnc_in_offline_tests.py`
guard) and `tests/unit/` (mocked-driver coverage); no schema, migration, or API surface change

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Deterministic Runtime Control (Principle I)**: Not implicated — this fix is entirely inside the
Executor layer's driver implementation; it does not touch the state machine, retry logic, or
pass/fail judgment. PASS.

**Planner/Grounder/Executor/Verifier separation (Principle II)**: Not implicated — no Planner,
Grounder, or Verifier code is touched (spec Assumptions explicitly exclude them). PASS.

**Keyboard-First Execution Priority (Principle III)**: Directly reinforced — the fix replaces a
broken call with `keyPress`, and explicitly rejects `paste()`/clipboard as an alternative (FR-010,
research.md), keeping `type_text` on the keyboard-only path. PASS.

**Independent Observe-Act-Verify Loop (Principle IV)**: Preserved — the fix does not change how or
when post-action verification runs; `quickstart.md` §4 explicitly requires the live confirmation to
check the independent screen-content verification, not just `execution_result.success`. PASS.

**Controlled Self-Evolution (Principle V)**: Not implicated — no replay/self-heal/memory code is
touched. PASS.

**Domain-Agnostic Core gate (Principle VI)**:

- [x] No business-specific fields, keywords, states, action categories, expected
      values, or flow branches are being added to core modules (domain, runtime,
      planning, grounding, execution, verification, reporting, recovery, config).
      `_sync_text`'s fixed body depends only on `text: str` and its individual characters — no
      reference to Barcode/ScannerSimulator/`45127366` anywhere in `drivers/`, `execution/`, or any
      other core module (FR-014).
- [x] All business/scenario semantics introduced by this feature live only in
      testcase YAML, example/offline-regression fixtures, or an optional scenario
      profile registered through a generic interface — never as fixed core fields.
      The only place `45127366`/`pos-scan-magazine-checkout.yaml` appear is the existing testcase
      YAML (already committed, unmodified per FR-011) and this planning documentation — never in
      `src/`.
- [x] Any capability claimed to be generic/reusable is validated against at least
      two unrelated scenarios, and a cross-scenario contract test is planned/listed
      (not just a single-scenario regression fixture).
      Two scenarios per Clarification Session 2026-07-24 Q2: (1) the real accident testcase,
      confirmed live (SC-001), and (2) a synthetic/contract-level character-set scenario in
      `vnc_agent/tests/integration/test_vncdotool_text_input.py`, both exercising the identical
      unmodified `_sync_text` code path (see research.md, contracts/text-input-contract.md).

**Engineering & Safety Constraints**: 黑盒边界 unaffected (still VNC-only pixels/keyboard/mouse);
资源约束 unaffected (no new model calls, no new screenshot cadence); 动作安全分级 unaffected
(`type_text` is not a high-risk action category); PowerShell 黑盒配方 unaffected (no PowerShell
involvement); 凭据与隐私 unaffected (this fix does not change how sensitive text is masked/logged,
only how it is transmitted to the VNC session).

**Quality Gates**: 验证独立性门禁 — satisfied, see Principle IV above. 恢复与重试门禁 — not
implicated, no retry policy changes. 测试覆盖门禁 — satisfied via a test at the real driver
boundary (`vnc_agent/tests/integration/test_vncdotool_text_input.py` — lives under `tests/integration/`
per the pre-existing `test_no_real_vnc_in_offline_tests.py` guard, which forbids constructing a real
`VNCToolDriver` under `tests/unit/`/`tests/fixtures/`/`tests/e2e/`) plus the
`KeyboardExecutor`/`ExecutionRouter` layers (`vnc_agent/tests/unit/test_keyboard_executor_type_text.py`,
`vnc_agent/tests/unit/test_execution_router_type_text.py`), per research.md and tasks.md.

No violations requiring Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/006-fix-keyboard-text-input/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/
│   └── text-input-contract.md   # Phase 1 output (/speckit-plan command)
├── checklists/
│   ├── requirements.md          # /speckit-specify quality checklist
│   └── pr-review.md             # /speckit-checklist PR review checklist
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
vnc_agent/
├── src/vnc_agent/
│   ├── drivers/
│   │   ├── vncdotool_driver.py   # FIX: _sync_text body only (this feature's sole production change)
│   │   └── key_mapping.py        # unchanged — no new keys needed, "enter"/"tab" already handled
│   ├── execution/
│   │   ├── router.py             # unchanged — existing generic except Exception path already correct
│   │   └── keyboard_executor.py  # unchanged — pass-through type_text already correct
│   └── runtime/exceptions.py     # unchanged — no new exception type (research.md)
├── tests/
│   ├── integration/
│   │   └── test_vncdotool_text_input.py          # NEW — fake-client regression + 2nd unrelated scenario
│   └── unit/
│       ├── test_keyboard_executor_type_text.py   # NEW — pass-through + fail-fast at this layer
│       └── test_execution_router_type_text.py    # NEW — ExecutionResult population on failure
└── testcases/
    └── pos-scan-magazine-checkout.yaml   # UNCHANGED (FR-011) — used only for the live confirmation run
```

**Structure Decision**: Single project (`vnc_agent/`), matching the existing repository layout used by
features 001-005. No new top-level directory, package, or test tier is introduced. The driver-level
test (`test_vncdotool_text_input.py`) lives under `tests/integration/`, following both the
fake-client-injection fixture pattern of the existing `test_vncdotool_driver_lifecycle.py` in that
same directory, and — more importantly — the directory placement itself is required by the
pre-existing `tests/unit/test_no_real_vnc_in_offline_tests.py` guard test (Feature 003), which
statically forbids constructing a real `VNCToolDriver` under `tests/unit/`/`tests/fixtures/`/
`tests/e2e/`; only `tests/integration/` is exempt. This test still requires no live VNC connection —
only the directory, not the network behavior, is constrained. The two other new test files
(`test_keyboard_executor_type_text.py`, `test_execution_router_type_text.py`) use mocked drivers, not
the real `VNCToolDriver`, so they remain under `tests/unit/`, following the existing
`tests/unit/test_*_repeat.py` naming convention.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — the Constitution Check above passed with no gate marked unmet. This table is
intentionally empty.
