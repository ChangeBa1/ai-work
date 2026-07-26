# Implementation Plan: Wrong-Click Detection

**Branch**: `022-wrong-click-detection` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/022-wrong-click-detection/spec.md`

## Summary

Two deterministic, zero-model-call defense lines against misplaced clicks:

1. **Stale-frame guard (事前防)** — before EXECUTING a mouse action, one fresh
   capture (`capture_source="pre_click_guard"`, shared FrameCaptureService) is
   ROI-compared against the observation frame that produced the coordinates;
   a changed target neighborhood vetoes the send and fails the iteration into
   the new `STALE_FRAME` recovery (recapture → next iteration re-observes and
   re-grounds by construction).
2. **WRONG_TARGET attribution (事中判)** — a pure assessment over the existing
   `classify_action_effect` evidence marks `wrong_target_suspected` when an
   `expected_effect` happened entirely outside the target neighborhood at
   sub-screen scale; the iteration's attribution upgrades to `WRONG_TARGET`
   (re-observe/re-locate recovery chain identical to `target_not_found`)
   **only** when the independent verification also failed. Full geometric
   evidence (nearest-blob distance/direction, IoU, thresholds) is persisted
   additively for feature 023.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed project in `vnc_agent/`)

**Primary Dependencies**: existing only — OpenCV diff (`perception/screen_diff.py`), pydantic, FrameCaptureService (004), RecoveryEngine + zoom plumbing (014); no new dependencies

**Storage**: additive pydantic fields on `ActionIteration` (persisted through the existing JSON payload columns); no schema migration

**Testing**: pytest + pytest-asyncio; new unit files ×2, new e2e scenario 21 with a click-driven FakeVNC subclass; golden legacy-projection snapshot regenerated (additive)

**Target Platform**: unchanged (offline-capable, Windows/Linux)

**Performance Goals**: guard adds one capture + one full-frame gray absdiff (~ms at test/POS resolutions) per mouse action, only when enabled; assessment is pure arithmetic over already-computed blobs

**Constraints**: zero new model calls (SC-004); `stale_frame_check_enabled=false` byte-identical to pre-022; `classify_action_effect` semantics untouched; planning/verification/models/memory/replay untouched

**Scale/Scope**: 9 source files touched (all additive or insert-beside), 3 new test files, 1 regenerated snapshot, specs

## Constitution Check

*GATE: passed.*

- Principle I (deterministic runtime control): both defense lines are pure pixel/geometry decisions with config-declared thresholds; no model in the loop.
- Principle II (Planner/Grounder separation): untouched — the guard runs after resolution, the assessment after classification; neither emits or edits actions.
- Principle IV (independent verification): strengthened, never bypassed — WRONG_TARGET only upgrades an already-failed verification; suspected-but-passed never blocks a pass.
- Principle VI (domain-agnostic core): all new vocabulary is generic geometry/failure-mode language (stale frame, wrong target, blob distance/direction); thresholds live in config.
- Recovery constitution: both new FailureTypes get explicit `RecoveryPolicy` entries (shipped yaml + e2e fixture); strategies reuse the existing set (`recapture`/`zoom_reground`/`re_ground`) — no new strategy verbs, no destructive actions.
- FR-049 lineage: the guard compares the two *safe-evidence* images (identically masked) — no new exposure of unmasked pixels.

**Domain-Agnostic Core gate (Principle VI)**:

- [x] No business-specific fields/states/branches.
- [x] No scenario semantics (blob geometry + failure types only).
- [x] Validated with constructed frames/regions, not business fixtures.

## Phase 0 — Research (inline)

- **Stale-frame root cause**: grounding input frame at T0, execution at T0+Δ (planner+grounder calls in between); `artifacts/_probe_stale_capture.py` is the historical probe. The remedy needs to be cheap and pre-send — hence capture + ROI diff, not another grounding call.
- **Diff reuse**: `compute_diff(threshold=1.0)` returns `local_blobs` + ratio without triggering the global-change region path — the exact pattern `classify_action_effect` already uses; comparing the two safe PNGs makes mask handling free (identical masking on both sides).
- **RepeatGuard interplay (guard veto)**: a vetoed iteration has `execution_result is None` and `action_effect is None`; `RepeatGuard.check` already maps that to the `no_effect_confirmed` allow-path (002), so the follow-up identical proposal is never blocked. No RepeatGuard change needed.
- **Recovery chain reuse (WRONG_TARGET)**: `ROUTING[WRONG_TARGET] == ROUTING[TARGET_NOT_FOUND]` (`recapture → zoom_reground → re_ground`); the zoom escalation reuses feature 014's `_plan_zoom` refusal semantics untouched (no evidence ⇒ substitute next strategy).
- **021 interplay**: miner matches configured failure-type strings against persisted `recovery_attempts` + experience `failure_type`; passing `iteration.failure_attribution` into `ExperienceCollector.collect` (an argument it always accepted, previously never supplied) makes the upgrade visible there too. Shipped default hard-case set unchanged.
- **FakeVNC frame economics**: the shared e2e FakeVNC advances scripted frames on *every* capture ⇒ a default-on guard would consume frames legacy scenarios scripted for later stages. Resolution: conftest `app_config` pins the guard off for legacy scenarios (spec FR-A03 makes that byte-identical), scenario 21 uses a click-driven `ClickScriptedVNC` (frames advance on clicks — truthful causality) with the guard on.

## Phase 1 — Design

### Judgment rules & thresholds

| Signal | Rule | Threshold (config) | Default |
|---|---|---|---|
| STALE_FRAME | any guard-diff blob ∩ expand(target_region, r) ≠ ∅ | `execution.stale_frame_region_expand_ratio` | 0.25 |
| guard gate | run guard at all | `execution.stale_frame_check_enabled` | true |
| wrong_target_suspected | `expected_effect` ∧ blobs ≠ ∅ ∧ ∀blob ∉ expand(target_region, r) ∧ ratio < max | `perception.wrong_target_neighborhood_expand_ratio` / `perception.wrong_target_global_diff_ratio_max` | 0.5 / 0.10 |
| WRONG_TARGET upgrade | suspected ∧ verification failed | — (rule, not threshold) | — |
| budgets | Tier-2 retries | `recovery.stale_frame` / `recovery.wrong_target` `max_retries` | 2 / 2 |

### Changes by file

- `domain/recovery.py` — `FailureType.STALE_FRAME/WRONG_TARGET`; `WrongTargetDirection`; `WrongTargetEvidence` (additive model).
- `domain/observation.py` — `ScreenFrame.capture_source` Literal + `"pre_click_guard"` (additive).
- `domain/run.py` — `ActionIteration.wrong_target_evidence` / `.failure_attribution` (additive).
- `perception/action_effect.py` — pure helpers `expand_target_region`, `region_iou`, `blobs_intersecting_neighborhood`, `direction_8`, `assess_wrong_target`; `classify_action_effect` byte-identical.
- `recovery/strategies.py` — `ROUTING` entries for the two new FailureTypes (existing strategy verbs only).
- `runtime/agent_runtime.py` — `_pre_click_stale_check` helper; guard block inserted between RESOLVING and EXECUTING; assessment recorded after `classify_action_effect`; upgrade block after verification routing; `failure_attribution` passed to `ExperienceCollector.collect`. All inserted beside 008/009/014/015/016 wiring — none of it touched.
- `config.py` — `ExecutionConfig` (+`AgentConfig.execution`); `PerceptionConfig.wrong_target_*` fields.
- `config/agent.yaml` — `execution:` section, perception thresholds, `recovery.stale_frame`/`recovery.wrong_target` policies, refreshed (content-unchanged) evolution comment.
- `reporting/json_report.py` — two additive iteration keys (null when absent).
- Tests — `tests/unit/test_wrong_target_assessment.py`, `tests/unit/test_stale_frame_guard.py`, `tests/e2e/test_scenario_21_wrong_click_detection.py`; conftest fixture gains the two recovery policies + pinned-off guard; `_LEGACY_ITERATION_KEYS` extended (015/016 convention); `tests/snapshots/report_legacy_projection.json` regenerated (additive: two null keys).

### Interface handed to feature 023

`ActionIteration.wrong_target_evidence` (`WrongTargetEvidence`):

```
suspected: bool
target_region: (x1,y1,x2,y2) | null      click_point: (x,y) | null
neighborhood_expand_ratio: float          global_diff_ratio_max: float   # thresholds applied
global_diff_ratio: float                  blob_count: int
blobs_intersecting_neighborhood: int      max_blob_target_iou: float
nearest_blob_bbox: (x1,y1,x2,y2) | null   nearest_blob_distance_px: float | null
nearest_blob_offset: (dx,dy) | null       nearest_blob_direction: 8-way | "center" | null
reason: str
```

plus `ActionIteration.failure_attribution ∈ {"stale_frame","wrong_target",null}`,
`RecoveryAttempt.failure_type`, `VisualExperience.failure_type`, and the JSON
report mirrors of the two iteration fields.
