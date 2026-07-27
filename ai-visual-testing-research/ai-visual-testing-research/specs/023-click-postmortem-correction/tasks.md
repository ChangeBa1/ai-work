# Tasks: Click Post-Mortem Correction

**Input**: Design documents from `/specs/023-click-postmortem-correction/`

**Prerequisites**: plan.md, spec.md

**Organization**: grouped by user story; US-A (diagnose & correct) is the backbone, US-B (undo) and US-C
(fail-safe refusals) layer onto the same diagnostician. All paths relative to `vnc_agent/`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

*(none — existing project, no new dependencies)*

## Phase 2: Foundational — domain vocabulary & config

- [X] T001 `src/vnc_agent/domain/recovery.py`: `RecoveryStrategy` += `postmortem`/`postmortem_undo`;
  `PostmortemOutcome` Literal; additive `PostmortemCorrectionPlan` + `PostmortemAudit` models (FR-007/FR-010)
- [X] T002 [P] `src/vnc_agent/domain/run.py`: additive `ActionIteration.postmortem` (FR-010)
- [X] T003 [P] `src/vnc_agent/config.py`: `WrongTargetPostmortemConfig` (enabled true / confidence_threshold
  0.7 / max_click_distance_ratio 0.4 / max_retries 1) as `AgentConfig.wrong_target_postmortem`, extracted
  from the yaml `recovery:` section (FR-009)
- [X] T004 [P] `config/agent.yaml`: `recovery.wrong_target_postmortem:` section in lockstep with T003 (FR-009)
- [X] T005 [P] `src/vnc_agent/runtime/telemetry.py`: `ModelRole` += `"postmortem"` (FR-010)

## Phase 3: User Story A — diagnosis client & correction plumbing (P1) 🎯

- [X] T006 [US-A] `src/vnc_agent/models/postmortem_client.py`: prompt, strict `PostmortemDiagnosis`,
  `parse_postmortem_diagnosis`, `resolve_corrected_bbox` (strict `resolve_pixel_bbox`),
  `HttpPostmortemClient` (grounder endpoint/model, two-image payload, 017 keep-alive), `StubPostmortemClient`
  (FR-001/FR-002)
- [X] T007 [US-A] `src/vnc_agent/recovery/postmortem.py`: `render_click_annotation` (original resolution),
  `annotation_png_bytes`, `build_evidence_summary`, `is_same_page_high` (015 fingerprint),
  distance helpers, `PostmortemDiagnostician.run` (undo→annotate→call→parse→gates; never raises)
  (FR-001~FR-004)
- [X] T008 [US-A] `src/vnc_agent/recovery/strategies.py`: `ROUTING[WRONG_TARGET]` leading `postmortem`;
  `StrategyContext.postmortem_capable`; `_run` branches (`postmortem` no-op, `postmortem_undo` = Esc)
  (FR-003/FR-007)
- [X] T009 [US-A] `src/vnc_agent/recovery/engine.py`: per-step cap + capability refusal substitution,
  disabled-chain restore in `strategies_for`, path-changing set, one-shot correction plan storage (FR-007/FR-008)
- [X] T010 [US-A] `src/vnc_agent/runtime/agent_runtime.py`: `postmortem_client` seam; WRONG_TARGET branch
  wiring (diagnostician run, artifacts, `ModelCallAudit` model_role="postmortem", fallback attempt on
  refusal); grounding-branch correction consumption (skip memory/grounder, `model_call_skipped` audit)
  (FR-001/FR-005/FR-008/FR-010)
- [X] T011 [P] [US-A] `src/vnc_agent/reporting/json_report.py`: additive `postmortem` iteration key (FR-010)

## Phase 4: Test coverage (US-A/B/C)

- [X] T012 [P] `tests/unit/test_postmortem_diagnosis.py`: strict parse matrix (valid pixel /
  normalized_1000 / missing fields / found-without-bbox / invalid bbox / non-JSON / envelope),
  annotation rendering (markers drawn, size == source), evidence summary, diagnostician gates
  (corrected / low_confidence / distance_exceeded / target_not_found / diagnosis_failed), undo decisions
  (same page skip / Esc restore / page_not_restored) (SC-002)
- [X] T013 [P] `tests/unit/test_postmortem_routing.py`: config defaults/bounds/yaml lockstep, ROUTING
  entry, disabled chain == 022, capability/per-step-cap substitution, budget consumption, correction plan
  one-shot semantics (SC-002)
- [X] T014 `tests/unit/test_stale_frame_guard.py`: routing expectations updated to the 023 chain
  (`postmortem` leading; disabled == 022) — supersedes the 022 chain-equality asserts (FR-007)
- [X] T015 `tests/e2e/conftest.py`: legacy scenarios pin `wrong_target_postmortem.enabled=false`
  (rationale comment; FR-007 disabled == 022 baseline)
- [X] T016 `tests/e2e/test_scenario_22_click_postmortem_correction.py`: `UndoScriptedVNC` + stub client;
  cases (a) misplaced click → postmortem corrected → verified pass → memory write-back + audit asserts,
  (b) dialog → Esc undo → corrected, (c) low confidence → recapture fallback, (d) disabled → 022
  baseline + zero diagnosis calls, (e) corrected click fails again → no second diagnosis, budget
  termination (SC-001)
- [X] T017 `tests/fixtures/test_json_report_compatibility.py`: `_LEGACY_ITERATION_KEYS` + `postmortem`;
  regenerate `tests/snapshots/report_legacy_projection.json` (additive: one null key) (SC-003)
- [X] T018 Full offline regression: `uv run pytest tests/unit tests/fixtures tests/e2e tests/integration -q`
  all green (1 pre-existing skip) (SC-003)

## Dependencies

- T001 → T002/T006/T007/T008/T009 (vocabulary first); T003/T004 lockstep → T009/T010
- T006/T007 → T010/T012; T008/T009 → T010/T013/T014
- T010 → T015/T016; T011 → T017
- everything → T018
