# Tasks: Slim the Planner `plan()` Request Payload at Serialization Time

**Input**: Design documents from `/specs/019-planner-request-slimming/`

**Prerequisites**: plan.md, spec.md

**Organization**: grouped by user story; US1 (OCR slimming) is the MVP, US3 (kill switch) and US4 (structure preservation) are the red lines, US2 completes the reduction. All paths relative to `vnc_agent/`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

*(none — existing project, no new dependencies; slimming module is stdlib-only)*

## Phase 2: Foundational

- [X] T001 New module `src/vnc_agent/planning/request_slimming.py`: `DEFAULT_OCR_ITEMS_MAX=40` / `DEFAULT_LIST_ITEMS_MAX=10`; `slim_planner_payload(payload, *, ocr_items_max, list_items_max)` implementing rules 1–6 of plan.md (OCR cap w/ target-hit priority + confidence ranking + original-order emission + per-item field reduction; template/region/blob/hint caps; summary tail-truncation; recursive confidence-2/other-4 float rounding; recursive null/[] drop); pure and total over arbitrary JSON dicts (FR-001..FR-004)
- [X] T002 [P] Config: `PlanningConfig` += `prompt_slimming_enabled: bool = True`, `prompt_ocr_items_max: int = Field(40, ge=1)`, `prompt_list_items_max: int = Field(10, ge=1)` in `src/vnc_agent/config.py`; document the three keys under `planning:` in `config/agent.yaml` (FR-007)

## Phase 3: User Story 1 — OCR noise shed, decision text kept (P1) 🎯 MVP

- [X] T003 [US1] `src/vnc_agent/models/planner_client.py`: module logger; `HttpPlannerClient.__init__(..., planning_cfg=None)`; `plan()` applies `slim_planner_payload` between `model_dump(mode="json")` and `json.dumps` when enabled, emits `logger.debug("planner request slimming: %d -> %d chars", ...)`; disabled path byte-identical `json.dumps(data, ensure_ascii=False)` (FR-005, FR-008)
- [X] T004 [US1] Wiring: `HttpPlannerClient.configure_planning(planning_cfg)` hook; `src/vnc_agent/api/cli.py` calls it via duck-typing (`getattr(..., "configure_planning", None)`) after the unchanged `build_planner(cfg.models)` — factory signature untouched because offline tests monkeypatch it with single-argument stub factories (FR-007)
- [X] T005 [P] [US1] Unit tests in `tests/unit/test_request_slimming.py`: 60→40 cap with confidence-descending survival; low-confidence target-hit (step_intent and expected-condition-value variants) survives; hits-exceed-cap → top-confidence hits win; survivors in original order; bbox float→int rounding; confidence → 2 dp; `normalized_text == text` dropped / differing kept; input dict not mutated (FR-002)

## Phase 4: User Story 2 — Other lists bounded, floats rounded, empties dropped (P2)

- [X] T006 [P] [US2] Unit tests: template_matches 25→10 top-confidence in original order; changed_regions/local_blobs/ui_index_hints first-10; recent_step_summaries keeps last 10; `global_diff_ratio` → 4 dp; null and `[]` keys dropped at all levels; empty strings kept; `structured_screen={}`/`expected={}`/non-list `ocr_items` pass through without raising (FR-003, FR-004)

## Phase 5: User Story 3 — Kill switch byte identity (P1, red line)

- [X] T007 [US3] Fixture test in `tests/fixtures/test_planner_request_slimming.py`: `HttpPlannerClient` with `prompt_slimming_enabled=False` through `httpx.MockTransport` → captured user message content `== json.dumps(request.model_dump(mode="json"), ensure_ascii=False)` byte-for-byte (FR-005, SC-003)

## Phase 6: User Story 4 — Structure preservation + observability (P1, red line)

- [X] T008 [US4] Fixture tests: default-enabled client with a fully-populated `PlannerRequest` (real `StructuredScreen`, `VerificationSpec`, hints) → captured JSON key sets are subsets of the unslimmed dump at every level; `step_intent`/`expected`/`structured_screen` + non-empty lists present under original names; target text present; caplog captures the DEBUG before/after length line with before > after on a 60-item payload (FR-008, FR-009, SC-001/002/004)

## Phase 7: Polish & regression

- [X] T009 Full offline regression: `uv run pytest tests/unit tests/fixtures tests/e2e tests/integration -q` all green (1 pre-existing skip allowed) with zero modifications to existing tests — in particular `tests/fixtures/test_httpx_client_reuse.py` (dict-shaped `PlannerRequest`s now flowing through the default-enabled slimming path) must stay green via totality (SC-005)

## Dependencies

- T001 → T003/T005/T006
- T002 → T003/T004/T007/T008
- T003 → T004/T007/T008
- everything → T009
