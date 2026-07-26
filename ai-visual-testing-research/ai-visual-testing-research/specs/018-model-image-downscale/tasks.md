# Tasks: Downscale Planner-Bound Screenshots Before Model Upload

**Input**: Design documents from `/specs/018-model-image-downscale/`

**Prerequisites**: plan.md, spec.md

**Organization**: grouped by user story; US1 (downscaled planner payload) is the MVP, US2 (grounder byte-identity) is the red line, US3 (kill switch) completes it. All paths relative to `vnc_agent/`.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

*(none — existing project, no new dependencies; opencv-python already present)*

## Phase 2: Foundational

- [X] T001 New module `src/vnc_agent/models/image_payload.py`: move `_image_url_content_part` verbatim from `planner_client.py`; add `planner_image_url_content_part(image_path, *, enabled=True, max_width=1024, jpeg_quality=80)` (cv2 read → INTER_AREA proportional shrink to max_width, never upscale, height ≥ 1 → JPEG imencode at quality → `data:image/jpeg;base64` part; disabled/decode-failure/encode-failure → byte-identical passthrough) (FR-001, FR-002)
- [X] T002 [P] Config: `PlannerModelConfig` += `planner_image_downscale_enabled: bool = True`, `planner_image_max_width: int = Field(1024, ge=1)`, `planner_image_jpeg_quality: int = Field(80, ge=1, le=100)` in `src/vnc_agent/config.py`; document the three keys under `planner:` in `config/models.yaml` (FR-005)

## Phase 3: User Story 1 — Planner vision calls upload a downscaled JPEG (P1) 🎯 MVP

- [X] T003 [US1] `src/vnc_agent/models/planner_client.py`: re-export `_image_url_content_part` from `image_payload` (grounder import untouched); `describe_screen()` builds its image part via `planner_image_url_content_part(...)` driven by the three cfg fields; `plan()` unchanged with a comment pointing future image parts at the helper (FR-003)
- [X] T004 [P] [US1] New tests in `tests/fixtures/test_planner_image_downscale.py`: helper geometry — 2048×1024 PNG → decoded JPEG is 1024×512 (proportional); 640×480 PNG → stays 640×480 (no upscale); data URI prefix `data:image/jpeg;base64,` and JPEG magic bytes
- [X] T005 [P] [US1] New tests: undecodable file (fake PNG bytes) → part byte-identical to passthrough `_image_url_content_part`; config defaults (1024 / 80 / enabled) on a bare `PlannerModelConfig`
- [X] T006 [US1] New test: `HttpPlannerClient.describe_screen()` through injected `httpx.MockTransport` with a real 2000-px-wide PNG → captured request's image part is a JPEG data URI decoded at width 1024, aspect preserved

## Phase 4: User Story 2 — Grounder payload stays byte-identical (P1, red line)

- [X] T007 [US2] New test: `MimoGrounderClient._build_payload(GroundingRequest(...))` against a real PNG → `image_url.url == "data:image/png;base64," + b64(raw file bytes)` exactly; `mimo_grounder.py` itself has zero edits (FR-004)

## Phase 5: User Story 3 — Kill switch restores pre-018 bytes (P2)

- [X] T008 [US3] New tests: `planner_image_url_content_part(path, enabled=False, ...)` returns a dict equal to `_image_url_content_part(path)`; `describe_screen()` with `planner_image_downscale_enabled=False` sends decoded bytes equal to the original PNG file bytes (SC-003)

## Phase 6: Polish & regression

- [X] T009 Full offline regression: `uv run pytest tests/unit tests/fixtures tests/e2e tests/integration -q` all green (1 pre-existing skip allowed) with zero modifications to existing tests — in particular `tests/fixtures/test_planner_client_describe_screen.py` (fake-bytes fixture) must pass via the passthrough fallback (SC-004)

## Dependencies

- T001 → T003/T004/T005/T008
- T002 → T003/T005/T006/T008
- T003 → T006/T007 (T007 verifies the re-export path feeding the grounder)
- everything → T009
