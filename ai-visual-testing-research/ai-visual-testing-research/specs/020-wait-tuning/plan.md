# Implementation Plan: Wait/Stability Default Tuning

**Branch**: `020-wait-tuning` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/020-wait-tuning/spec.md`

## Summary

Pure default-value tuning of the post-action stability wait: `stable_frame_count`
3→2, `capture_interval_ms` 500→300, `min_delay_ms` 300→200 in both
`config/agent.yaml` and `config.py::WaitConfig` (lockstep). `max_delay_ms` and
`pixel_diff_threshold` unchanged. No algorithm change — `perception/stability.py`
already enforces `max(2, stable_frame_count)` and declares stable at
`consecutive_stable >= stable_frame_count - 1`, so 2 frames = exactly one real
unchanged comparison. Risk (premature stability on slow animations) is argued
and given rollback order in spec.md. New tests pin the tuned defaults and the
2-sample stable path.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed project in `vnc_agent/`)

**Primary Dependencies**: pydantic (WaitConfig), yaml config loader, existing StabilityEngine/FrameCaptureService

**Storage**: N/A

**Testing**: pytest + pytest-asyncio; fixture-style SequenceDriver over synthetic frames

**Target Platform**: same as project (Windows/Linux CLI)

**Performance Goals**: instantly-stable wait floor ~1300 ms → ~500 ms per step (~62% cut of the fixed wait cost; telemetry bb9f039e showed ~3.2 s/step waiting)

**Constraints**: config-values-only change; no runtime/perception logic edits; no existing test modified

**Scale/Scope**: 2 config sources touched + 1 new test file + specs

## Constitution Check

*GATE: passed.*

- Principle I (deterministic runtime control): untouched — same deterministic wait algorithm, different constants.
- Principle II (Planner/Grounder separation): untouched.
- Resource constraint (弱配置电脑 / avoid waste): directly served — removes ~0.8 s of dead wait per step; dedup (004) keeps the denser capture cadence near-zero cost on static screens.
- Recovery/safety: `max_delay_ms` untouched (slow-page upper bound identical); premature-stable worst case is absorbed by the existing 002/014 recovery chain (spec Risk Analysis).

**Domain-Agnostic Core gate (Principle VI)**:

- [x] No business-specific fields/states/branches — numeric defaults only.
- [x] No scenario semantics introduced.
- [x] Generic capability validated by engine-level tests, not scenario fixtures.

## Phase 0 — Research (inline; no open unknowns)

- **Stability math**: `wait_stable()` stops at `consecutive_stable >= stable_frame_count - 1`; first own sample never increments (no comparison basis). `stable_frame_count=2` ⇒ 2 logical samples, 1 unchanged comparison. Constructor floor `max(2, …)` already present (`perception/stability.py:50`) — no code change needed.
- **Pass-through audit (FR-005)**: `api/cli.py` (StabilityEngine construction, lines ~234-241) passes all five `cfg.agent.wait.*` values explicitly. `WaitConfig` is populated from the yaml `wait:` section by `AppConfig`. **No hard-coded overrides, no wiring gap ⇒ stability.py stays untouched.**
- **Third default source**: `StabilityEngine.__init__` keyword defaults (300/20000/500/3/0.02) are unreachable from the CLI (always overridden) — left as-is per change boundary; recorded as spec assumption.
- **Affected-test sweep**: grep over `min_delay_ms|capture_interval_ms|stable_frame_count` in `tests/` — every hit passes explicit values (`tests/fixtures/test_stability.py`, `tests/fixtures/test_stability_deduplicated_frames.py`, `tests/e2e/conftest.py`, `tests/e2e/test_sensitive_masking.py`, `tests/integration/ui_index/test_no_index_vs_no_match_equivalence.py`, `tests/integration/ui_index/test_preflight_invalid_index.py`, `tests/unit/test_cli_capture_service_wiring.py`). `tests/e2e/test_scenario_06_wait_dynamic.py` asserts only `waited_ms >= 0` via conftest's explicit engine. `tests/fixtures/test_feature003_config.py` asserts section presence only. **Zero existing assertions to update.**
- **Risk & rollback**: argued in spec.md Risk Analysis; rollback order `stable_frame_count`→`capture_interval_ms`→(`min_delay_ms` last).

## Phase 1 — Design

### Changes by file

1. `vnc_agent/config/agent.yaml`
   - `wait.min_delay_ms: 300 → 200`
   - `wait.capture_interval_ms: 500 → 300`
   - `wait.stable_frame_count: 3 → 2`
   - comment pointing at specs/020 rationale + rollback order.
2. `vnc_agent/src/vnc_agent/config.py`
   - `WaitConfig` defaults mirrored: `min_delay_ms=200`, `capture_interval_ms=300`, `stable_frame_count=2` (max_delay_ms/pixel_diff_threshold untouched).
3. `vnc_agent/tests/fixtures/test_wait_tuning.py` (new)
   - `WaitConfig()` defaults pinned to FR-001 numbers.
   - Shipped `config/agent.yaml` wait section pinned to FR-001 numbers.
   - 2-sample stable path: engine with `stable_frame_count=WaitConfig().stable_frame_count` (fast CI timers) over identical frames → `stable` at `svc._sequence == 2`.
   - Floor: `StabilityEngine(..., stable_frame_count=1)` → effective 2.

### Non-changes (explicit)

- `perception/stability.py`: untouched (audit found no wiring gap; algorithm and constructor defaults as-is).
- `api/cli.py`: untouched (pass-through already correct).
- All existing tests: untouched.
- `max_delay_ms`, `pixel_diff_threshold`: untouched in both sources.

## Project Structure

### Documentation (this feature)

```text
specs/020-wait-tuning/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
vnc_agent/
├── config/agent.yaml                       # tuned wait defaults
├── src/vnc_agent/config.py                 # WaitConfig defaults in lockstep
└── tests/fixtures/test_wait_tuning.py      # new: default pins + 2-sample stable path + floor
```

**Structure Decision**: single-project layout as-is; new test lives beside the
other stability/config fixture tests.

## Complexity Tracking

No constitution violations; table not needed.
