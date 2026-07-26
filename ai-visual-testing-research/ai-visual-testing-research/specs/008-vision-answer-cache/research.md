# Research: Vision Answer Cache

## R1. Diagnosed waste (telemetry, run bb9f039e)

One step ran 3 iterations; each iteration's `after_frame` was the same image and the frame-dedup
mechanism (Feature 004, `ScreenFrame.deduplicated` + `duplicate_of_frame_id` + `content_hash`)
already recognized it. Yet each iteration's verification re-issued
`planner.describe_screen(mode="answer_question")` — a 5-6 s cloud VLM HTTP call — with the same
frame and the same question. Observe-phase `vision_describe` is already cached
(`src/vnc_agent/perception/pipeline.py::_vision_describe_or_cache`); the verification path has no
cache.

## R2. Existing cache infrastructure to reuse (Feature 004)

**Decision**: Reuse `AnalysisResultCache` / `AnalysisCacheKey`
(`src/vnc_agent/perception/cache.py`) unchanged except for widening the `Component` Literal with
`"vision_answer"`.

**Rationale**:
- `AnalysisCacheKey` already carries `content_hash`, `scope_identity`, `pixel_format`,
  `mask_identity`, `perception_config_fingerprint`, `algorithm_revision`, and a free-form
  `component_identity` dict — the question hash and model identity fit `component_identity`
  exactly the way `vision_describe` puts provider/model/prompt revisions there.
- `lookup()` already enforces the strict-adjacency dedup gate (`frame_deduplicated=true` +
  `duplicate_of_frame_id` present) and the bounded window
  (`current_sequence - last_reference >= max_frames` ⇒ evict, miss).
- `store()` + `_prune()` already implement the 3..5 `cache_max_frames` window and run-reset
  `clear()`.

**Alternatives considered**: a separate dict cache inside the verification package — rejected:
would duplicate window/eviction/telemetry semantics and violate Feature 004's single bounded-cache
constraint (weak-hardware memory budget).

## R3. Where the verification path calls the model

Two call sites issue `describe_screen(mode="answer_question")`:

1. `src/vnc_agent/verification/visual_verifier.py::verify_visual_question` — evaluation of
   `visual_question` conditions, dispatched from
   `src/vnc_agent/verification/engine.py::VerificationEngine._eval_one`.
2. `src/vnc_agent/verification/business_resolver.py::resolve_step_result::_maybe_escalate`
   (~lines 175-185) — the one-shot visual escalation fallback with the fixed question
   "Did the expected business result appear on screen?".

**Decision**: introduce one shared helper, `CachedVisualAnswerer`
(`src/vnc_agent/verification/answer_cache.py`), owned by `VerificationEngine`. Site (1) receives
it through `verify_visual_question(..., answerer=...)`; site (2) calls a thin
`VerificationEngine.answer_visual_question(...)` delegate so the `business_resolver.py` diff stays
minimal (FR-009: the arbitration logic ~lines 225-250 belongs to a parallel feature and is not
touched).

## R4. Frame identity available to the verification path

Verification operates on `StructuredScreen`, not `ScreenFrame`. `StructuredScreen` already mirrors
the dedup identity (`content_hash`, `deduplicated`, `duplicate_of_frame_id`, Feature 004
data-model §7) but lacks the two values the cache API needs at lookup/store time:

- `capture_sequence` (window arithmetic),
- the scope identity string (key field).

**Decision**: extend the Feature 004 mirror with two additive, defaulted fields on
`StructuredScreen`: `capture_sequence: int = 0` and `scope_key: str = ""` (the
`scope_identity(frame.scope)` hash, already computed in
`assemble_structured_screen_from_pixels`). Both assemblers populate them from the owning frame.
No consumer of `StructuredScreen` is affected (defaults preserve construction in tests).

**Alternatives considered**:
- Passing the `ScreenFrame` into the verification path — rejected: churns many signatures
  (`VerificationEngine.verify`, `resolve_step_result`, runtime call sites) for two scalar values.
- Keying without scope — rejected: every other cached component includes scope identity; keeping
  the key shape uniform costs one mirrored string.

`AnalysisCacheKey.pixel_format` / `mask_identity` are set to `""` for `vision_answer` keys:
`scope_key` is a hash that already includes both (see `scope_identity()`), and key fingerprints
are compared only against other `vision_answer` entries (component is part of the fingerprint), so
the encoding is internally consistent and non-colliding.

## R5. What exactly is cached; hint exclusion

**Decision**: cache the full successful `VisionUnderstandingResponse` (pydantic, pure data:
answer/reason/description/confidence/model_name) — never exceptions, never `None`.

**Decision**: the `structured_screen_hint` is NOT part of the key. Precedent: `vision_describe`'s
`component_identity` (provider/model/mode/prompt/schema revisions) omits the hint too. The hint is
derived from the same pixels; its diff-adjacency fields (`changed_since_last`, `changed_regions`)
differ between an original frame and its duplicate by construction and would otherwise defeat the
cache for provably identical content. Recorded in spec Assumptions.

## R6. Contract amendment vs Feature 004 "Explicit exclusions"

Feature 004's perception-cache contract excludes "Verifier 结论" and answers carrying run context
from the content cache, and Constitution Principle IV requires verification on freshly captured
evidence.

**Decision** (spec FR-008): amend narrowly. The cacheable unit is the pure function
(pixel content, question text, model identity) → (answer, reason). Everything contextual — step
result resolution, ActionEffect combination, escalation policy, deterministic-vs-visual
arbitration — still runs fresh every iteration; evidence is still freshly captured every
iteration, and only a capture *proven* pixel-identical by the Feature 004 dedup gate may reuse the
answer. Model identity comes from request-side configuration, honoring the Feature 004 rule that
response-side `model_name` cannot complete a lookup. The amendment lives in this feature's own
contract (`contracts/vision-answer-cache-contract.md`); Feature 004's historical contract file is
left untouched.

## R7. Telemetry

**Decision**: mirror the `vision_describe` pattern with counter events as the oracle:
- hit → `CounterEvent(kind="analysis_cache_hit", payload.component="vision_answer")`;
- miss/real call → `CounterEvent(kind="analysis_invocation", payload.component="vision_answer")`
  plus the existing `model_call` accounting stays untouched at its current emission points.
- `derive_performance_summary` adds `"vision_answer"` to the always-present `cache_hits` defaults
  (`ocr`/`template`/`vision`/`vision_answer`).

Stage measurements are not added for the answer path in this feature (the verification stage is
already measured at the step level in `agent_runtime`); call counts, not durations, are the test
oracle (telemetry-contract.md "Test oracle").

`test_run` is obtained lazily (`FrameCaptureService.test_run` at call time) because the CLI
attaches it after construction.

## R8. Test oracle infrastructure

Reuse the Spy/call-count style of `tests/fixtures/test_analysis_call_counts.py`
(`SequenceDriver` over `tests/fixtures/images/frame_dedup` fixtures + counting fake planner).
New tests drive real `FrameCaptureService`/`ObservationPipeline` captures so
`deduplicated`/`capture_sequence`/`scope_key` are produced by the production path, then run
`VerificationEngine.verify` with a counting planner and assert exact call counts for: same
frame+question (1 call), different question (2 calls), changed frame (re-call), window eviction
(re-call), and escalation-path reuse via `resolve_step_result`.
