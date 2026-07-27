# Feature Specification: Wait/Stability Default Tuning

**Feature Branch**: `020-wait-tuning`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "Every post-action stability wait pays a fixed floor cost: `config/agent.yaml` wait section `min_delay_ms: 300` + `stable_frame_count: 3` (requires 2 consecutive unchanged comparisons) × `capture_interval_ms: 500` → ~1.3 s even when the screen is instantly stable. Real-run telemetry (run bb9f039e) shows ~3.2 s/step spent in the waiting phase. The system under test is a fast local native POS application, and frame dedup (feature 004) already makes duplicate-frame comparisons near-zero cost — so the defaults can be more aggressive: `stable_frame_count: 3→2`, `capture_interval_ms: 500→300`, `min_delay_ms: 300→200`. `max_delay_ms` and `pixel_diff_threshold` stay unchanged."

## Clarifications

### Session 2026-07-27 (self-resolved; fully automated run — decisions recorded here instead of asked)

- Q: Does `stable_frame_count: 2` still perform a real stability comparison, or does it degenerate into "first frame wins"? → A: A real comparison remains. `StabilityEngine.wait_stable()` declares stable when `consecutive_stable >= stable_frame_count - 1`; with `stable_frame_count=2` that is exactly **1 unchanged comparison between 2 logical samples**. The first sample of a wait never increments `consecutive_stable` (no local comparison basis), so an instantly-stable screen needs 2 captures minimum. The engine additionally enforces `max(2, stable_frame_count)` in its constructor, so no configuration can reduce this below one real comparison.
- Q: Which files carry the defaults, and do they all need the change? → A: Two places define the tuned values: `config/agent.yaml` (the shipped runtime config) and `config.py::WaitConfig` (the pydantic defaults used when a yaml omits keys). Both are updated in lockstep. `StabilityEngine.__init__` keyword defaults are **not** a third source of truth at runtime — the only composition root (`api/cli.py`) always passes all five wait values explicitly from `cfg.agent.wait` — so they are deliberately left untouched (out of the change boundary; changing them would alter constructor behavior for direct test instantiations for no runtime benefit).
- Q: Is the yaml→engine pass-through actually real, or could the tuning be silently ignored? → A: Audited. `api/cli.py` builds `StabilityEngine(capture_service, min_delay_ms=cfg.agent.wait.min_delay_ms, max_delay_ms=..., capture_interval_ms=..., stable_frame_count=..., pixel_diff_threshold=...)` — all five values transit from yaml through `WaitConfig` into the engine with no hard-coded overrides. No wiring gap; no stability.py change needed.
- Q: Which existing tests depend on the old defaults? → A: None. Every existing test that constructs a `StabilityEngine` (or a runtime containing one) passes explicit wait parameters: `tests/fixtures/test_stability.py` (explicit 3/0.02 etc.), `tests/fixtures/test_stability_deduplicated_frames.py` (explicit `stable_frame_count=3`), `tests/e2e/conftest.py::build_runtime` (5/50/5/2/0.5), `tests/e2e/test_sensitive_masking.py`, `tests/integration/ui_index/test_no_index_vs_no_match_equivalence.py`, `tests/integration/ui_index/test_preflight_invalid_index.py`, `tests/unit/test_cli_capture_service_wiring.py` (yaml literal 1/20/1/2/0.5). `tests/e2e/test_scenario_06_wait_dynamic.py` only asserts `waited_ms >= 0` through `build_runtime`'s explicit values. `tests/fixtures/test_feature003_config.py` asserts the `wait` section exists, not its values. Therefore zero assertion updates are required; new tests pin the new defaults instead.

## Risk Analysis *(mandatory for this feature)*

**Risk**: more aggressive waiting can declare "stable" prematurely on slow gradual animations (e.g. a progress bar repainting slower than 300 ms per visible change, or a fade-in whose inter-frame delta stays under `pixel_diff_threshold`). A premature stable verdict hands a half-rendered screen to perception/verification.

**Why the risk is acceptable**:

1. **The system under test is a fast local native POS app** — screens settle in well under 300 ms; long animations are not part of its UI vocabulary. Telemetry (run bb9f039e, ~3.2 s/step waiting) shows the wait floor, not real screen activity, dominates the phase.
2. **Existing safety nets catch a premature verdict downstream**: if a half-rendered screen causes the action to look ineffective or verification to fail, the established recovery chain from features 002 (action-effect verification → `action_no_effect` retry/recovery) and 014 (target-not-found zoom recovery) re-observes the screen on a fresh capture and retries. A too-early "stable" therefore degrades to one extra recovery iteration, not a wrong test verdict.
3. **`max_delay_ms: 20000` is untouched** — genuinely slow pages keep the same upper wait bound; nothing times out earlier than before.
4. **The `max(2, stable_frame_count)` floor guarantees at least one real unchanged comparison** — the tuning can never reach "declare stable on the first frame".

**Rollback guidance (if real-environment regression shows premature stability)**: revert **`stable_frame_count` 2→3 first** — it is the parameter that directly controls how much sustained evidence of quiescence is required (3 restores two consecutive unchanged comparisons and is the strongest single lever against gradual animations). If flapping persists on slow repaints, additionally raise **`capture_interval_ms` 300→500** so consecutive samples straddle a wider time window and slow deltas become visible to the comparison. `min_delay_ms` (200) is the last resort — it only shifts the sampling start and does not affect the evidence requirement.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Instantly-stable screens stop paying the old ~1.3 s floor (Priority: P1)

After a fast action on the local POS app the screen is already stable; the wait phase should conclude after `min_delay_ms` (200 ms) + 2 captures 1 interval apart (~300 ms) instead of the previous ~1.3 s (300 ms + 2 × 500 ms intervals across 3 captures).

**Why this priority**: This is the entire feature — the wait floor is paid on every step of every run (~3.2 s/step observed), and it is pure dead time on a fast application.

**Independent Test**: Build a `StabilityEngine` with the shipped `WaitConfig()` defaults (fast timers scaled for CI) over a static frame sequence and assert it returns `stable` after exactly 2 logical samples (1 unchanged comparison).

**Acceptance Scenarios**:

1. **Given** the shipped defaults (`stable_frame_count=2`), **When** the screen never changes, **Then** `wait_stable()` returns `end_reason="stable"` after its 2nd logical sample.
2. **Given** the shipped `config/agent.yaml`, **When** it is loaded through `AppConfig`, **Then** `wait.min_delay_ms == 200`, `wait.capture_interval_ms == 300`, `wait.stable_frame_count == 2`, and `wait.max_delay_ms == 20000` / `wait.pixel_diff_threshold == 0.02` are unchanged.

---

### User Story 2 - Config floor still guarantees one real comparison (Priority: P2)

An operator who sets `stable_frame_count: 1` (or 0) in yaml must still get at least one unchanged comparison before "stable" — the tuning must not open a path to zero-evidence stability.

**Acceptance Scenarios**:

1. **Given** `StabilityEngine(..., stable_frame_count=1)`, **When** constructed, **Then** the effective `stable_frame_count` is 2 (the `max(2, …)` floor).

### Edge Cases

- Slow gradual animation on the POS app: covered by Risk Analysis above — recovery chain (002/014) + untouched `max_delay_ms` are the backstop; rollback order documented.
- Screen still actively changing: unchanged behavior — every changed comparison resets `consecutive_stable` to 0 and the wait continues up to `max_delay_ms` (20 s) exactly as before; only the sampling cadence is denser (300 ms vs 500 ms), which if anything detects change *more* reliably.
- Frame-dedup interplay (004): duplicate frames count as unchanged without any pixel comparison, so the denser 300 ms cadence adds near-zero CPU cost on a static screen.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `config/agent.yaml` `wait` section MUST ship `min_delay_ms: 200`, `capture_interval_ms: 300`, `stable_frame_count: 2`; `max_delay_ms: 20000` and `pixel_diff_threshold: 0.02` MUST remain unchanged.
- **FR-002**: `config.py::WaitConfig` pydantic defaults MUST match FR-001 exactly (yaml and code defaults stay in lockstep).
- **FR-003**: With `stable_frame_count=2`, `StabilityEngine.wait_stable()` MUST return `stable` after exactly one unchanged comparison (2nd logical sample) on a static screen — verified by test.
- **FR-004**: The `max(2, stable_frame_count)` constructor floor MUST remain in force (no configuration reaches zero-comparison stability).
- **FR-005**: The yaml→`WaitConfig`→`StabilityEngine` pass-through in `api/cli.py` MUST carry all five wait values with no hard-coded overrides (audit; wiring fix only if a gap is found — none was).
- **FR-006**: No runtime/perception logic changes beyond configuration values; `perception/stability.py` algorithm untouched.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Theoretical instantly-stable wait floor drops from ~1300 ms (300 + 2×500) to ~500 ms (200 + 1×300) — a ~62% reduction, asserted structurally by SC-002/SC-003 (not wall-clock measured in CI).
- **SC-002**: New test proves `stable` is reached on the 2nd logical sample with `stable_frame_count=2` (exactly 1 stability comparison).
- **SC-003**: New tests pin the shipped yaml values and the `WaitConfig` defaults to the FR-001 numbers.
- **SC-004**: Full offline regression (`tests/unit tests/fixtures tests/e2e tests/integration`) passes with no existing test modified (1 pre-existing skip allowed).

## Assumptions

- The POS system under test is a local native app with sub-300 ms screen settle times; deployments against slower systems should follow the rollback guidance in Risk Analysis (raise `stable_frame_count` first, then `capture_interval_ms`).
- `StabilityEngine.__init__` keyword defaults are dead at runtime (composition root always passes explicit values) and stay as-is; only yaml + `WaitConfig` are sources of truth.
- Out of scope: adaptive/dynamic wait tuning, per-step wait overrides, changes to `max_delay_ms`, `pixel_diff_threshold`, or the dedup/capture pipeline.
