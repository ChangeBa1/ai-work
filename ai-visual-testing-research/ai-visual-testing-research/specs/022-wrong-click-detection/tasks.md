# Tasks: Wrong-Click Detection

**Input**: Design documents from `/specs/022-wrong-click-detection/`

**Prerequisites**: plan.md, spec.md

**Organization**: grouped by user story; US-A (stale-frame guard) and US-B (WRONG_TARGET attribution) are both P1 — B depends on A only for the shared geometry helpers. All paths relative to `vnc_agent/`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

*(none — existing project, no new dependencies)*

## Phase 2: Foundational — domain vocabulary & config

- [X] T001 `src/vnc_agent/domain/recovery.py`: add `FailureType.STALE_FRAME` / `FailureType.WRONG_TARGET` (FR-A02/FR-B01) + `WrongTargetDirection` + additive `WrongTargetEvidence` model (FR-B04)
- [X] T002 [P] `src/vnc_agent/domain/observation.py`: extend `ScreenFrame.capture_source` Literal with `"pre_click_guard"` (FR-A04)
- [X] T003 [P] `src/vnc_agent/config.py`: `ExecutionConfig` (`stale_frame_check_enabled` default true, `stale_frame_region_expand_ratio` default 0.25) wired as `AgentConfig.execution`; `PerceptionConfig.wrong_target_neighborhood_expand_ratio` (0.5) + `.wrong_target_global_diff_ratio_max` (0.10) (FR-A03/FR-B02)
- [X] T004 [P] `config/agent.yaml`: `execution:` section, perception wrong-target thresholds, `recovery.stale_frame` / `recovery.wrong_target` policies (max_retries 2), refreshed evolution comment — shipped values in lockstep with T003 defaults
- [X] T005 `src/vnc_agent/recovery/strategies.py`: `ROUTING[STALE_FRAME] = ["recapture"]`, `ROUTING[WRONG_TARGET] = ["recapture","zoom_reground","re_ground"]` (mirror of target_not_found; FR-A02/FR-B03)

## Phase 3: User Story A — pre-execution stale-frame guard (P1) 🎯

- [X] T006 [US-A] `src/vnc_agent/perception/action_effect.py`: pure geometry helpers `expand_target_region` / `_regions_intersect` / `region_iou` / `blobs_intersecting_neighborhood` (shared by both stories; existing classification untouched)
- [X] T007 [US-A] `src/vnc_agent/runtime/agent_runtime.py`: `_pre_click_stale_check` (guard capture via shared FrameCaptureService `capture_source="pre_click_guard"`, content-hash fast path, `compute_diff(threshold=1.0)` over the two safe PNGs, fail-open) + guard block between RESOLVING and EXECUTING (veto ⇒ `failure_attribution="stale_frame"`, STALE_FRAME recovery attempt, `VerificationResult failed "stale_frame: …"`) (FR-A01/FR-A02/FR-A03)
- [X] T008 [P] [US-A] `tests/unit/test_stale_frame_guard.py`: neighborhood verdicts (inside/outside/band/boundary/expand=0), `ExecutionConfig` defaults + bounds, shipped-yaml lockstep, enum members, ROUTING entries, STALE_FRAME/WRONG_TARGET Tier-2 budget stop + zoom-refusal substitution

## Phase 4: User Story B — WRONG_TARGET assessment & attribution upgrade (P1) 🎯

- [X] T009 [US-B] `src/vnc_agent/perception/action_effect.py`: `direction_8` + pure `assess_wrong_target` (suspicion rule, screen-scale exemption, nearest-blob distance/offset/direction, IoU summary, threshold echo) (FR-B02)
- [X] T010 [US-B] `src/vnc_agent/domain/run.py`: additive `ActionIteration.wrong_target_evidence` / `.failure_attribution` (FR-B04)
- [X] T011 [US-B] `src/vnc_agent/runtime/agent_runtime.py`: record assessment after `classify_action_effect` for every executed mouse action with a target_region (+ `wrong_target_suspected` log_event); upgrade block — suspected ∧ verification failed ⇒ attribution `wrong_target`, reason prefix, WRONG_TARGET recovery attempt with zoom-capable StrategyContext; pass `failure_attribution` into `ExperienceCollector.collect` (FR-B03/FR-B04)
- [X] T012 [US-B] `src/vnc_agent/reporting/json_report.py`: additive `wrong_target_evidence` / `failure_attribution` iteration keys (FR-B04)
- [X] T013 [P] [US-B] `tests/unit/test_wrong_target_assessment.py`: suspicion in/out of neighborhood, boundary exclusivity, custom ratios, global-ratio exemption (0.10 inclusive-exempt / 0.099 suspected), non-expected statuses, non-assessable inputs, nearest-blob selection, direction sectors, expansion clamping, IoU

## Phase 5: E2E scenario 21 & regression

- [X] T014 `tests/e2e/conftest.py`: recovery fixture gains `stale_frame` (no path change) + `wrong_target` (path change) policies; guard pinned off for legacy scenarios (FakeVNC capture-advances-frames harness artifact; FR-A03 makes disabled byte-identical) with rationale comment
- [X] T015 `tests/e2e/test_scenario_21_wrong_click_detection.py`: click-driven `ClickScriptedVNC` + `SeqGrounder` + color-keyed OCR stub; cases (a) drift → veto → re-observe → pass, (b) misplaced click + failed `text_appears` → WRONG_TARGET → re-locate → pass (incl. experience `failure_type` assert), (c) suspected + passed → telemetry only, (d) disabled → pre-022 capture vocabulary (SC-001)
- [X] T016 `tests/fixtures/test_json_report_compatibility.py`: `_LEGACY_ITERATION_KEYS` + the two additive keys (015/016 convention); regenerate `tests/snapshots/report_legacy_projection.json` (additive diff: two null keys only) (SC-003)
- [X] T017 Full offline regression: `uv run pytest tests/unit tests/fixtures tests/e2e tests/integration -q` all green (1 pre-existing skip) (SC-003)

## Dependencies

- T001 → T005/T006/T009/T010 (vocabulary first)
- T003/T004 in lockstep; T003 → T007/T011
- T006 → T007 and T009
- T007 → T014/T015 (guard behavior under test)
- T009/T010/T011/T012 → T013/T015/T016
- everything → T017
