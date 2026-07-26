# Implementation Plan: Slim the Planner `plan()` Request Payload at Serialization Time

**Branch**: `019-planner-request-slimming` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/019-planner-request-slimming/spec.md`

## Summary

Introduce `planning/request_slimming.py` — pure, total functions that transform
the JSON dict produced by `PlannerRequest.model_dump(mode="json")` before it is
`json.dumps`-ed into `plan()`'s user message: OCR items capped at
`prompt_ocr_items_max` (40; target-relevant text always survives, remainder by
confidence descending, output in original reading order; per item only `text` +
integer `bbox` + 2-decimal `confidence` + `normalized_text` iff it differs from
`text`), other list fields capped at `prompt_list_items_max` (10),
`recent_step_summaries` tail-truncated, all floats rounded (confidence 2 / rest
4 decimals), `null` and `[]` entries dropped recursively. The `PlannerRequest`
Pydantic model is untouched (slimming is serialization-time only), the system
prompt is untouched, and `prompt_slimming_enabled: false` restores byte-identical
pre-019 messages. A DEBUG log records before/after character lengths.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed project in `vnc_agent/`)

**Primary Dependencies**: pydantic (existing), httpx (existing) — the slimming module itself is stdlib-only

**Storage**: N/A

**Testing**: pytest + pytest-asyncio; wire-level assertions via `httpx.MockTransport`

**Target Platform**: same as project (Windows/Linux CLI)

**Performance Goals**: materially fewer prompt tokens per `plan()` call on real POS frames (30~60 OCR items → ≤ 40 slimmed items with ~half the per-item bytes), directly reducing the measured 4–5 s planning latency

**Constraints**: `PlannerRequest`/`PlannerResponse` models frozen; `describe_screen()`/grounder/runtime/perception untouched; disabled path byte-identical; no new dependencies; slimming functions total (never raise) and pure (never mutate input)

**Scale/Scope**: 1 new source module, 2 edited source files (`planner_client.py`, `config.py`) + 1 wiring block (`api/cli.py` duck-typed configure_planning call), 1 config yaml, 2 new test files, spec docs

## Constitution Check

*GATE: passed.*

- Principle I (deterministic runtime control): untouched — a deterministic, pure transformation on the model-boundary serialization; no control-flow change.
- Principle II (Planner/Grounder separation): reinforced — the planner still receives semantic text/structure only (no coordinates added/removed beyond redundancy); the grounder path is not touched.
- 资源约束（弱配置电脑 / avoid waste): directly served — fewer tokens per planning call, less upload and model latency.
- 凭据与隐私: unaffected — slimming only removes/rounds data already destined for the model; it never adds fields (e.g. no new paths/identifiers are exposed).

**Domain-Agnostic Core gate (Principle VI)**:

- [x] No business-specific fields/states/branches — generic JSON-payload reduction keyed on structural names (`ocr_items`, `confidence`), not business vocabulary.
- [x] Target-relevance matching uses only strings already present in the request (step intent / expected values) — no scenario semantics.
- [x] Validated by unit tests on synthetic payloads + provider-level fixture tests, not scenario fixtures.

## Phase 0 — Research (inline; no open unknowns)

- **Construction-site audit**: `PlannerRequest` is built in exactly one production place — `planning/planner.py::PlannerOrchestrator.plan()` — from `step.intent`, `step.expected` (`VerificationSpec`), the full `StructuredScreen`, iteration counters, `previous_verification_result`, and 007 `ui_index_hints`. `recent_step_summaries`/`risk_policy` stay at defaults. Offline tests also construct it with plain dicts (`expected={}`, `structured_screen={}`) — slimming must be total over those shapes.
- **Payload-weight audit**: `StructuredScreen.model_dump()` dominates: `ocr_items[]` each carry `text`, `bbox` (already ints), full-float `confidence`, and an always-populated `normalized_text` (`default_normalized` fills it with `text.strip().lower()` — for CJK POS text a byte-identical duplicate). Plus `template_matches[]`, `changed_regions[]`, `local_blobs[]`, `global_diff_ratio`, and frame-bookkeeping strings. `vision_understanding`, `content_hash`, `duplicate_of_frame_id`, `previous_verification_result` are frequently `null`; several lists are frequently empty.
- **Prompt audit**: `_PLANNER_SYSTEM_PROMPT` promises the model `step_intent`, `expected`, and `structured_screen` "含 OCR 文字、模板匹配、变化检测等" — no field inventory, no counts, no precision guarantees. Caps/rounding/empty-drop keep the prompt truthful; key renames would not, hence FR-009.
- **Wire-path audit**: only `HttpPlannerClient.plan()` serializes `PlannerRequest` (grep: single `model_dump` on the request). `StubPlanner.plan()` ignores payload content; the 008 answer cache and audit trails key off model objects/frames, never off `plan()`'s wire bytes → FR-006 holds by construction.
- **Config plumbing**: `HttpPlannerClient` is constructed in `provider.py::build_planner(models_cfg)` from `api/cli.py` with `cfg.models` only. Decision: optional `planning_cfg` constructor keyword + `configure_planning()` hook on `HttpPlannerClient`; the CLI calls the hook via duck-typing after `build_planner(cfg.models)`. Changing `build_planner`'s signature was tried and rejected: ~48 offline tests monkeypatch it with single-argument lambdas (full-suite regression caught it). Hiding planner-prompt knobs in `PlannerModelConfig` (models.yaml) was also rejected — the feature request explicitly places them in the `planning:` section, and they are planning-behavior knobs, not model-endpoint knobs.
- **Byte-identity check**: current code sends `json.dumps(request.model_dump(mode="json"), ensure_ascii=False)`. The disabled path reproduces exactly that expression — byte identity is trivially testable via `httpx.MockTransport`.

## Phase 1 — Design

### Slimming rules (single source of truth)

| # | Field | Rule |
|---|-------|------|
| 1 | `structured_screen.ocr_items` | ≤ `ocr_items_max` (40). Selection: target-relevant hits first (bidirectional case-insensitive substring vs `step_intent` + `expected.conditions[*].value`), then confidence descending; emit survivors in original order. Per item: `text`, `bbox` → `int(round())`, `confidence` → 2 dp, `normalized_text` only if ≠ `text`. |
| 2 | `structured_screen.template_matches` | ≤ `list_items_max` (10), top-confidence selection, original order; floats rounded by pass 5. |
| 3 | `structured_screen.changed_regions`, `structured_screen.local_blobs`, `ui_index_hints` | first `list_items_max` (10) entries. |
| 4 | `recent_step_summaries` | last `list_items_max` (10) entries (most recent). |
| 5 | all floats, recursively | key named `confidence` → round 2; any other float → round 4. |
| 6 | all dict entries, recursively | value `null` or `[]` → key omitted. |

### Changes by file

1. **NEW `vnc_agent/src/vnc_agent/planning/request_slimming.py`** (stdlib-only)
   - `DEFAULT_OCR_ITEMS_MAX = 40`, `DEFAULT_LIST_ITEMS_MAX = 10` (shared defaults).
   - `slim_planner_payload(payload, *, ocr_items_max, list_items_max) -> dict` — orchestrates rules 1–6; pure (deep-builds a new dict), total (malformed/missing sub-shapes pass through).
   - Internal helpers: `_collect_target_texts(payload)`, `_slim_ocr_items(...)`, `_slim_ocr_item(...)`, `_cap_by_confidence(...)`, `_cleanup(value, key)` (recursive rounding + null/[] drop).
2. **`vnc_agent/src/vnc_agent/models/planner_client.py`**
   - Module `logger = logging.getLogger(__name__)`.
   - `HttpPlannerClient.__init__` gains `planning_cfg: PlanningConfig | None = None` keyword; stores enabled/max values (module defaults when `None`).
   - `plan()`: `data = request.model_dump(mode="json")`; disabled → `content = json.dumps(data, ensure_ascii=False)` (byte-identical pre-019); enabled → slim, dump both, `logger.debug("planner request slimming: %d -> %d chars", ...)`, send slimmed.
3. **`vnc_agent/src/vnc_agent/config.py`**
   - `PlanningConfig` += `prompt_slimming_enabled: bool = True`, `prompt_ocr_items_max: int = Field(40, ge=1)`, `prompt_list_items_max: int = Field(10, ge=1)`.
4. **`vnc_agent/src/vnc_agent/api/cli.py`**
   - After `build_planner(cfg.models)` (call unchanged): duck-typed hook
     `getattr(planner, "configure_planning", None)` → `configure_planning(cfg.agent.planning)`
     when callable. Rationale: ~48 offline tests monkeypatch `build_planner`
     with single-argument `lambda models_cfg: StubPlanner(...)` factories, so
     the factory signature must not change; `StubPlanner` lacks the hook and
     is skipped by the `callable()` guard. `models/provider.py` is untouched.
5. **`vnc_agent/config/agent.yaml`** — document the three new `planning:` keys.
6. **NEW `vnc_agent/tests/unit/test_request_slimming.py`** — pure-function coverage (rules 1–6, purity, totality).
7. **NEW `vnc_agent/tests/fixtures/test_planner_request_slimming.py`** — wire-level via `httpx.MockTransport`: kill-switch byte identity, slimmed-on-by-default structure subset, target survival end-to-end, DEBUG length log, configure_planning hook, size shrink on a 60-item payload.

### Non-changes (explicit)

- `models/provider.py`: zero edits — schemas and `build_planner` signature untouched.
- `_PLANNER_SYSTEM_PROMPT`, `describe_screen()`, `mimo_grounder.py`, `runtime/`, `perception/`, `planning/planner.py` (orchestrator): untouched.
- `StubPlanner`, 008 answer cache, audit records: untouched (they never consume `plan()` wire bytes).

## Project Structure

### Documentation (this feature)

```text
specs/019-planner-request-slimming/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
vnc_agent/
├── config/
│   └── agent.yaml                        # + 3 documented planning keys
├── src/vnc_agent/
│   ├── config.py                         # PlanningConfig + 3 fields
│   ├── api/cli.py                        # duck-typed configure_planning wiring
│   ├── models/
│   │   └── planner_client.py             # plan() slimming + hook + debug log
│   └── planning/
│       └── request_slimming.py           # NEW: pure slimming functions
└── tests/
    ├── unit/test_request_slimming.py             # NEW
    └── fixtures/test_planner_request_slimming.py # NEW
```

**Structure Decision**: single-project layout as-is; the slimming module sits in
`planning/` (it encodes planning-prompt policy, not HTTP mechanics) with no
imports from `models/` or `config.py`, so `models/planner_client.py` importing
it introduces no cycle.

## Complexity Tracking

No constitution violations; table not needed. One boundary note: the feature
request scoped edits to "slimming module, `plan()` assembly, config, tests,
specs" — delivering the `planning:`-section config to `HttpPlannerClient`
additionally requires one guarded wiring block in `api/cli.py` (documented in
spec Clarifications; behavior-neutral defaults, no factory-signature change).
