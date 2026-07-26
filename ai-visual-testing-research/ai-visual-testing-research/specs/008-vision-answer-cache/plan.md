# Implementation Plan: Vision Answer Cache

**Branch**: `008-vision-answer-cache` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/008-vision-answer-cache/spec.md`

## Summary

Verification-path visual questions (`describe_screen(mode="answer_question")`) currently re-issue
a 5-6 s cloud VLM call on every iteration even when Feature 004 has already proven the post-action
frame pixel-identical. Add a `vision_answer` component to the existing bounded
`AnalysisResultCache`, keyed on frame content identity + question-text hash + request-side model
identity, and route both verification call sites (visual_question condition eval + business
resolver escalation) through one shared `CachedVisualAnswerer` helper. Surface hits as
`performance_summary.cache_hits["vision_answer"]`.

## Technical Context

**Language/Version**: Python 3.11+ (existing `vnc_agent` package, uv-managed)

**Primary Dependencies**: pydantic (domain models), existing Feature 004 cache/telemetry
infrastructure; no new dependencies

**Storage**: in-memory `AnalysisResultCache` only (bounded 3..5 frames); nothing persisted

**Testing**: pytest (+pytest-asyncio); call-count Spy oracle per telemetry-contract.md

**Target Platform**: same as project (cross-platform CLI agent)

**Project Type**: single Python package `vnc_agent/`

**Performance Goals**: N identical verification iterations ⇒ 1 real visual call (SC-001/002)

**Constraints**: minimal diff to `verification/business_resolver.py` (arbitration logic owned by a
parallel feature, FR-009); no behavior change when cache absent; never cache errors

**Scale/Scope**: ~6 source files touched, 1 new source module, 1 new test module

## Constitution Check

- **I. Deterministic runtime control** — PASS: cache decision is deterministic code (exact key
  equality + proven pixel identity); the model gains no control.
- **II. Separation of concerns** — PASS: helper lives in the verification package; perception
  cache stays a generic bounded store; Planner/Grounder untouched.
- **III. Model-call auditability** — PASS: every hit/real call lands as counter events; summary
  derivation stays event-sourced, never hand-patched.
- **IV. Independent observe-act-verify loop** — PASS with narrow, documented amendment (spec
  FR-008, contract): evidence is still freshly captured each iteration; only a capture proven
  pixel-identical by FrameCaptureService's dedup may reuse the *pure* visual answer; step-result
  resolution/arbitration always re-runs.
- **V. Controlled self-evolution** — PASS: no baselines, prompts, or models are modified at
  runtime; cache is per-run/session and cleared on reset.
- **VI. Domain-agnostic core** — PASS: no business fields; question text is opaque payload.
- **Screenshot/persistence constraints** — PASS: entries hold no pixels/paths/StructuredScreen;
  bounded window unchanged.

## Project Structure

### Documentation (this feature)

```text
specs/008-vision-answer-cache/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md
├── contracts/vision-answer-cache-contract.md
└── tasks.md
```

### Source Code (repository root)

```text
vnc_agent/
├── src/vnc_agent/
│   ├── perception/
│   │   ├── cache.py                 # Component Literal += "vision_answer"
│   │   └── structured_screen.py     # mirror capture_sequence + scope_key onto StructuredScreen
│   ├── domain/
│   │   └── observation.py           # StructuredScreen: additive capture_sequence/scope_key fields
│   ├── verification/
│   │   ├── answer_cache.py          # NEW: CachedVisualAnswerer (shared helper)
│   │   ├── engine.py                # owns answerer; answer_visual_question delegate
│   │   ├── visual_verifier.py       # routes through answerer when provided
│   │   └── business_resolver.py     # escalation call → engine delegate (minimal diff)
│   ├── runtime/
│   │   ├── agent_runtime.py         # wire answerer from pipeline.cache + capture_service
│   │   └── telemetry.py             # cache_hits defaults += "vision_answer"
└── tests/
    └── fixtures/test_vision_answer_cache.py   # NEW call-count oracle suite
```

**Structure Decision**: single existing package; one new module in `verification/`, everything
else is additive edits to existing files listed above.

## Phase summaries

- **Phase 0 (research.md)**: reuse decisions (existing cache, key shape, hint exclusion,
  contract amendment, telemetry oracle) — all resolved, no NEEDS CLARIFICATION.
- **Phase 1 (data-model.md, contracts/, quickstart.md)**: key/value schema, StructuredScreen
  mirror fields, CachedVisualAnswerer API, lookup/telemetry/error contracts.
- **Phase 2**: tasks.md via /speckit-tasks.

## Complexity Tracking

No constitution violations; the Principle IV amendment is narrow, documented in spec FR-008 and
the contract, and preserves fresh capture + proven pixel identity as preconditions.
