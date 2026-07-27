# Feature Specification: Slim the Planner `plan()` Request Payload at Serialization Time

**Feature Branch**: `019-planner-request-slimming`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "`models/planner_client.py::plan()` dumps the entire `PlannerRequest` (`request.model_dump(mode='json')`) into the user message — every OCR item (a real POS screen yields 30~60, mostly numeric-keypad noise, each carrying full-precision bbox/confidence plus a `normalized_text` that duplicates `text`), all template matches, changed regions, etc. The wasted tokens directly slow the planner (~4–5 s measured for the planning stage). Add a serialization-time slimming layer (pure functions) applied only when `plan()` assembles the user message: cap OCR items (config, default 40, keep by confidence descending, always prefer target-relevant text hits), keep only `text` / integer bbox / 2-decimal confidence per item, drop `normalized_text` when it equals `text`, cap other list fields (default 10), round all floats, drop null/empty-list fields, truncate history/summary fields. The Pydantic `PlannerRequest` model MUST NOT change — 008~016 consumers (audit, cache identity) are untouched. `prompt_slimming_enabled: false` restores byte-identical pre-019 output."

## Clarifications

### Session 2026-07-27 (self-resolved; fully automated run — decisions recorded here instead of asked)

- Q: Where is `PlannerRequest` actually constructed, and out of what? → A: Audited. The single production construction site is `planning/planner.py::PlannerOrchestrator.plan()`: `step_intent` (step's intent string), `expected` (the step's `VerificationSpec`), `structured_screen` (the **full** `StructuredScreen`), `iteration_index`, `remaining_iteration_budget`, `previous_verification_result`, `ui_index_hints` (feature 007). `recent_step_summaries` and `risk_policy` are never set by production code today (model defaults `[]` / `{"max_risk_level": "low"}`). The dominant payload weight is `structured_screen`: `ocr_items[]` (each `text` + `bbox` + full-float `confidence` + `normalized_text`, where `OCRItem.default_normalized` guarantees `normalized_text` is **always** populated — for CJK text it is byte-identical to `text.strip()`, pure duplication), `template_matches[]`, `changed_regions[]`, `local_blobs[]`, plus frame-bookkeeping fields (`frame_id`, `content_hash`, `scope_key`, `image_path`, `model_image_path`, `analysis_source_refs`, …) that exist for runtime identity, not for planning.
- Q: What does the model actually get told it receives? → A: `_PLANNER_SYSTEM_PROMPT` says the model receives `step_intent`, `expected`, and `structured_screen` "含 OCR 文字、模板匹配、变化检测等". It names **no** individual sub-field, no counts, no float precision, no `normalized_text`. Therefore capping list lengths, rounding floats, and dropping empty/null fields keeps every statement in the prompt true — the semantic red line holds by construction.
- Q: Where does the slimming live? → A: New pure-function module `src/vnc_agent/planning/request_slimming.py` (no imports from `models/` or `config.py` → no cycle), applied by `HttpPlannerClient.plan()` between `model_dump(mode="json")` and `json.dumps(...)`. The `PlannerRequest` Pydantic model is untouched, so every other consumer of the model object (008 cache identity, audits, `StubPlanner`, validator paths) sees exactly what it saw before — slimming exists only in the wire serialization of `plan()`.
- Q: What counts as "target-relevant" for the keep-priority rule? → A: Case-insensitive bidirectional substring match between an OCR item's text (`text.strip().lower()`, falling back to `normalized_text`) and any of: `step_intent`, every `expected.conditions[*].value` string. These are the only target descriptions that exist in the request itself; matched items are retained ahead of the confidence ranking so the planner never loses sight of the text it is being asked about.
- Q: Ordering of the surviving OCR items? → A: Selection is by priority (target hits first, then confidence descending), but the **output order preserves the original reading order** of the survivors — OCR order is top-to-bottom layout information and reordering it would alter meaning (red-line violation). Same rule for `template_matches` (selected by confidence, emitted in original order).
- Q: `normalized_text` drop rule — literal equality or normalized equality? → A: Literal: emit `normalized_text` only when it differs from `text` as a string. (Default normalization is `text.strip().lower()`; for CJK/POS content these are almost always equal, which is exactly the duplication being removed. When they differ — e.g. Latin case folding — the difference is information and is kept.)
- Q: Where do the knobs live, and how do they reach `HttpPlannerClient`? → A: `PlanningConfig` (config `agent.yaml`, `planning:` section) gains `prompt_slimming_enabled` (default `true`), `prompt_ocr_items_max` (default `40`), `prompt_list_items_max` (default `10`). `HttpPlannerClient` gains an optional `planning_cfg` constructor keyword plus a `configure_planning(planning_cfg)` hook (both default to module defaults, which equal the config defaults). The CLI composition root calls the hook via duck-typing (`getattr(planner, "configure_planning", None)`) after `build_planner(cfg.models)` — **`build_planner`'s signature is deliberately unchanged** because ~48 offline tests monkeypatch it with single-argument `lambda models_cfg: StubPlanner(...)` factories, and `StubPlanner` (no hook) is skipped by the `callable()` guard. `runtime/`, orchestrator, and provider factories are otherwise untouched.
- Q: What about `recent_step_summaries` ("history/summary" truncation)? → A: Production never populates it today, but the rule is implemented anyway (defensive, spec'd behavior): the list is capped to the **most recent** `prompt_list_items_max` entries (tail, since summaries append chronologically). No extra config key is introduced for per-string length — no such content exists today to size it against.
- Q: Float rounding precision? → A: Fields named `confidence` → 2 decimals (spec'd). All other floats (e.g. `global_diff_ratio`) → 4 decimals, applied by a recursive pass. Integers and booleans are untouched (`True`/`False` are not floats).
- Q: `plan()` is also exercised by offline tests with `structured_screen={}` / `expected={}` (plain dicts). → A: The slimming functions are total over arbitrary JSON-shaped dicts: missing keys, non-dict `structured_screen`, non-list `ocr_items` etc. degrade to pass-through of that sub-value. Slimming never raises; a malformed field is simply left as-is (minus the generic null/empty/rounding pass).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Planner user message sheds OCR noise but keeps decision-relevant text (Priority: P1)

On a real POS frame with 30~60 OCR items, `plan()`'s user message carries at most `prompt_ocr_items_max` (40) items, each reduced to `text`, integer `bbox`, 2-decimal `confidence` (plus `normalized_text` only when it differs from `text`). Items whose text relates to the step's intent or expected-condition values are always retained, the rest are kept by confidence descending, and the survivors appear in their original reading order.

**Why this priority**: This is the payload's dominant weight and the whole point — fewer prompt tokens, faster planning, no lost decision signal.

**Independent Test**: Feed a payload with 60 OCR items (numeric-keypad noise at high confidence, one low-confidence item matching a `text_appears` condition value) through the slimming function; assert the cap, the guaranteed survival of the target-relevant item, the per-item field set, and the original relative order of survivors.

**Acceptance Scenarios**:

1. **Given** 60 OCR items and `prompt_ocr_items_max=40`, **When** `plan()` assembles the user message, **Then** exactly 40 items are serialized and every dropped item has confidence ≤ every kept non-target item.
2. **Given** an OCR item whose text matches `step_intent` or an `expected` condition value but ranks below the confidence cut, **When** slimming runs, **Then** that item is still present in the serialized message.
3. **Given** an OCR item `{"text": "小計", "bbox": [10.6, 20.4, 99.5, 40.0], "confidence": 0.987654, "normalized_text": "小計"}`, **When** slimmed, **Then** it serializes as `{"text": "小計", "bbox": [11, 20, 100, 40], "confidence": 0.99}` — no `normalized_text` key; **Given** `text="Login"`/`normalized_text="login"`, **Then** `normalized_text` is kept.

---

### User Story 2 - Other list fields and floats are bounded, empties disappear (Priority: P2)

`template_matches`, `changed_regions`, `local_blobs`, `ui_index_hints` are each capped at `prompt_list_items_max` (10); `recent_step_summaries` keeps its most recent 10 entries; every float is rounded (confidence 2 decimals, others 4); keys whose value is `null` or an empty list are omitted from the serialized message.

**Acceptance Scenarios**:

1. **Given** 25 template matches, **When** slimmed, **Then** the 10 highest-confidence matches survive in original order.
2. **Given** `previous_verification_result: null`, `vision_understanding: null`, and empty `template_matches`/`changed_regions`/`ui_index_hints` lists, **When** slimmed, **Then** none of those keys appear in the serialized JSON.
3. **Given** `global_diff_ratio: 0.123456789`, **When** slimmed, **Then** it serializes as `0.1235`.

---

### User Story 3 - Kill switch restores byte-identical pre-019 output (Priority: P1)

With `prompt_slimming_enabled: false`, the user message `plan()` sends is byte-for-byte `json.dumps(request.model_dump(mode="json"), ensure_ascii=False)` — exactly today's bytes — for debugging and A/B comparison against production behavior.

**Acceptance Scenarios**:

1. **Given** `prompt_slimming_enabled: false` and any `PlannerRequest`, **When** `plan()` sends the request (captured via `httpx.MockTransport`), **Then** the user message content equals the pre-019 serialization byte-for-byte.

---

### User Story 4 - Field names and structure the planner relies on are preserved (Priority: P1)

For every field that survives slimming, the key names and nesting are identical to the unslimmed dump — `step_intent`, `expected`, `structured_screen.ocr_items[*].text/bbox/confidence`, `structured_screen.template_matches`, etc. — so every statement in `_PLANNER_SYSTEM_PROMPT` about the input remains true and the planner model needs no prompt change.

**Acceptance Scenarios**:

1. **Given** a fully-populated `PlannerRequest`, **When** slimmed, **Then** the slimmed JSON's key set at every level is a subset of the original dump's key set at that level (no renamed or restructured keys), and `step_intent` / `expected` / `structured_screen` / non-empty list fields are all present under their original names.

### Edge Cases

- `structured_screen={}` or `expected={}` (offline-test dicts) → slimming passes them through untouched (minus the generic cleanup); never raises.
- `ocr_items` fewer than the cap → all items kept (still per-item slimmed).
- More target-relevant hits than `prompt_ocr_items_max` → highest-confidence hits fill the whole budget.
- `bbox` already integers (the normal case — `OCRItem.bbox` is `tuple[int, ...]`) → `int(round(...))` is the identity; float bboxes from dict-shaped payloads are rounded.
- Empty-string values (e.g. `image_path: ""`, `scope_key: ""`) are **not** dropped — the drop rule covers only `null` and `[]` (spec'd scope; empty strings are cheap and dropping them is a different semantic statement).
- Slimming failure of any kind must never break planning: functions are total by construction (no I/O, no model access); there is deliberately no try/except-wrapped "fallback" path to hide bugs — tests cover the malformed shapes that exist in the codebase.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A new pure-function module `planning/request_slimming.py` MUST provide `slim_planner_payload(payload, *, ocr_items_max=40, list_items_max=10) -> dict` operating on the JSON-shaped dict produced by `PlannerRequest.model_dump(mode="json")`, never mutating its input and never raising on missing/malformed sub-structures.
- **FR-002**: OCR slimming: at most `ocr_items_max` items survive; selection keeps every target-relevant item first (case-insensitive bidirectional substring match against `step_intent` and all `expected.conditions[*].value`), then fills by confidence descending; if hits alone exceed the cap, the highest-confidence hits win; survivors are emitted in original order. Each surviving item carries exactly `text`, `bbox` (ints, `int(round(...))`), `confidence` (2 decimals), and `normalized_text` only when it differs from `text` as a string.
- **FR-003**: `template_matches` (top-`list_items_max` by confidence, original order), `changed_regions`, `local_blobs`, and `ui_index_hints` (each first `list_items_max`) MUST be capped; `recent_step_summaries` MUST keep only its last `list_items_max` entries.
- **FR-004**: A recursive cleanup pass MUST round every float (`confidence`-named keys to 2 decimals, all others to 4) and drop every dict entry whose value is `null` or an empty list, at all nesting levels. No key is renamed, no nesting is changed, no non-empty non-null value is removed beyond the list caps of FR-002/FR-003.
- **FR-005**: `HttpPlannerClient.plan()` MUST apply the slimming between `model_dump(mode="json")` and `json.dumps(...)` when enabled; with `prompt_slimming_enabled: false` the serialized user message MUST be byte-identical to `json.dumps(request.model_dump(mode="json"), ensure_ascii=False)`. `describe_screen()`, the grounder, and all non-wire consumers of `PlannerRequest` MUST be untouched.
- **FR-006**: The `PlannerRequest` / `PlannerResponse` Pydantic models MUST NOT change in any way (no new fields, no serializers) — features 008~016 consumers (cache identity, audit, orchestrator, stubs) are provably unaffected because they never see the slimmed dict.
- **FR-007**: `PlanningConfig` MUST gain `prompt_slimming_enabled: bool = true`, `prompt_ocr_items_max: int = 40` (≥ 1), `prompt_list_items_max: int = 10` (≥ 1), loadable from `config/agent.yaml` `planning:` section; the CLI composition root MUST deliver it to `HttpPlannerClient` via the duck-typed `configure_planning()` hook (skipped for planners without the hook), leaving `build_planner()`'s signature unchanged so existing monkeypatched single-argument factories keep working.
- **FR-008**: Observability: when slimming runs, `plan()` MUST emit a DEBUG log with the serialized character length before and after slimming (`len()` of each JSON string), so real-run savings are measurable from logs.

### Semantic red line (restated as a requirement)

- **FR-009**: Slimming removes redundancy only — it MUST NOT rename fields, reorder surviving OCR/template items relative to each other, invent values, or drop any populated field that `_PLANNER_SYSTEM_PROMPT` describes to the model (`step_intent`, `expected`, `structured_screen` with its OCR/template/change content). Every sentence of the existing system prompt MUST remain true of the slimmed payload; the system prompt itself is not modified.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a synthetic 60-OCR-item POS-like payload, the serialized user message shrinks substantially (measured in the fixture test via the FR-008 debug log / direct `len()` comparison; the exact ratio is data-dependent and asserted only as "strictly smaller with the cap binding").
- **SC-002**: Target-relevant OCR text survives slimming in 100% of cases where it was present in the unslimmed payload (asserted by test).
- **SC-003**: `prompt_slimming_enabled: false` produces byte-identical pre-019 user messages (asserted by test through `httpx.MockTransport`).
- **SC-004**: Key-structure preservation: slimmed JSON key sets are subsets of the original at every level, with all non-empty prompt-described fields present (asserted by test).
- **SC-005**: Full offline regression `uv run pytest tests/unit tests/fixtures tests/e2e tests/integration -q` green with no existing test modified (1 pre-existing skip allowed).

## Assumptions

- The planner model does not depend on seeing dozens of near-duplicate numeric OCR items, full-precision floats, `null` markers, or empty lists; the system prompt never promises them.
- `plan()` is the only wire path that serializes `PlannerRequest`; audited: `PlannerOrchestrator` passes the model object, `StubPlanner` ignores content, no other serializer exists.
- Config defaults (`40` / `10` / enabled) match the module-level defaults, so an unwired `HttpPlannerClient` (tests constructing it directly) behaves identically to a default-configured one.
- Out of scope: prompt-text changes, image payloads (018 territory), `describe_screen()`, grounder payloads, `PlannerRequest` schema evolution, persistent measurement/metrics beyond the DEBUG log.
