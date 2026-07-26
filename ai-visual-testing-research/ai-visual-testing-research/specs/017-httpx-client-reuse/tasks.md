# Tasks: Reuse httpx AsyncClient Across Model Calls

**Input**: Design documents from `/specs/017-httpx-client-reuse/`

**Prerequisites**: plan.md, spec.md

**Organization**: grouped by user story; US1 (reuse) is the MVP, US2 (lifecycle) and US3 (test seam) complete it. All paths relative to `vnc_agent/`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

*(none — existing project, no new dependencies)*

## Phase 2: Foundational

- [X] T001 Shared pool-limits constant `_KEEPALIVE_LIMITS` (`httpx.Limits(max_connections=10, max_keepalive_connections=5, keepalive_expiry=30.0)`) in `src/vnc_agent/models/planner_client.py`

## Phase 3: User Story 1 — Consecutive calls reuse one pool (P1) 🎯 MVP

- [X] T002 [US1] `HttpPlannerClient`: add `*, transport=None` ctor param, `_client` field, lazy `_get_client()` (client default timeout = `cfg.timeout_seconds`, limits = `_KEEPALIVE_LIMITS`); `plan()` uses shared client (drop `async with`), semantics unchanged in `src/vnc_agent/models/planner_client.py`
- [X] T003 [US1] `describe_screen()` uses shared client with per-request `timeout=self.cfg.describe_timeout()` in `src/vnc_agent/models/planner_client.py` (FR-005)
- [X] T004 [P] [US1] `MimoGrounderClient`: same lazy shared-client pattern (existing `transport=` handed to the long-lived client), `ground()` request semantics unchanged in `src/vnc_agent/models/mimo_grounder.py`
- [X] T005 [P] [US1] New test: two `ground()` calls on one instance → same underlying `AsyncClient` identity + MockTransport handler called twice, in `tests/fixtures/test_httpx_client_reuse.py`
- [X] T006 [P] [US1] New test: `plan()` + `describe_screen()` on one planner instance → exactly one AsyncClient constructed; describe request carries `describe_timeout()` while plan carries `timeout_seconds` (assert via `request.extensions["timeout"]`), in `tests/fixtures/test_httpx_client_reuse.py`

## Phase 4: User Story 2 — Teardown closes clients on every path (P1)

- [X] T007 [US2] `async def aclose()` on both classes: idempotent, no-op when never used, client re-creatable afterwards (`src/vnc_agent/models/planner_client.py`, `src/vnc_agent/models/mimo_grounder.py`)
- [X] T008 [US2] `api/cli.py::_execute` finally block: duck-typed `aclose()` of planner + grounder after driver disconnect, exceptions swallowed (FR-004) in `src/vnc_agent/api/cli.py`
- [X] T009 [P] [US2] New tests: `aclose()` twice after use; `aclose()` on virgin instance; request after `aclose()` lazily re-creates a fresh client, in `tests/fixtures/test_httpx_client_reuse.py`

## Phase 5: User Story 3 — Transport seam preserved (P2)

- [X] T010 [US3] New test: `HttpPlannerClient(cfg, transport=MockTransport)` serves `plan()` through the injected transport, in `tests/fixtures/test_httpx_client_reuse.py` (grounder seam already covered by existing `tests/fixtures/test_mimo_grounder.py`, which must stay green unchanged)

## Phase 6: Polish & regression

- [X] T011 Full offline regression: `uv run pytest tests/unit tests/fixtures tests/e2e tests/integration -q` all green (1 pre-existing skip allowed) with zero modifications to existing tests

## Dependencies

- T001 → T002/T004
- T002/T003/T004 → T005/T006 (tests exercise the new plumbing)
- T007 → T008/T009
- everything → T011
