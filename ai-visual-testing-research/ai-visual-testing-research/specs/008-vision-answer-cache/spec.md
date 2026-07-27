# Feature Specification: Vision Answer Cache

**Feature Branch**: `008-vision-answer-cache`

**Created**: 2026-07-26

**Status**: Draft

**Input**: User description: "Telemetry from run bb9f039e shows a step whose 3 iterations produced the
same after_frame (frame dedup from Feature 004 already proved pixel identity), yet the verification
phase's `visual_question` evaluation re-issued the same 5-6 s cloud VLM HTTP call every iteration —
same frame, same question, 3 times. The observe-phase `vision_describe` already goes through the
AnalysisCache, but the verification path has no caching at all. Add a `vision_answer` cached
component so that an identical frame + identical question + identical model returns the cached
answer without a network call, and surface the hit count in the run's performance summary."

## Clarifications (self-answered, autonomous run)

- **Q: Does caching the visual answer violate Feature 004's "Explicit exclusions" (Verifier
  conclusions must not be cached) and Constitution Principle IV (verification must use freshly
  captured evidence)?** → A: No, with a narrow amendment. The cached unit is the *pure visual
  answer function* — (frame pixel content, question text, model identity) → (answer, reason) — not
  the Verifier's `StepVerificationResult`. Verification still runs on a freshly captured
  post-action frame every iteration; the capture service must still rigorously prove (via the
  Feature 004 dedup mechanism: `deduplicated=true` + direct-predecessor `duplicate_of_frame_id` +
  content hash) that the new capture is pixel-identical before any cache lookup is allowed. Step
  result resolution (ActionEffect combination, escalation policy, deterministic-vs-visual
  arbitration) is never cached and re-runs every iteration. Feature 004's exclusion targeted
  answers keyed on *run context* (step intent, retry state, history); the `vision_answer` key
  contains the full request semantics that reach the model (image content + question + model), so
  reuse is deterministic-safe. This spec amends the Feature 004 perception-cache contract
  accordingly (see FR-008).
- **Q: The `structured_screen_hint` sent with the request differs between an original frame
  (`changed_since_last=true`, changed regions listed) and its deduplicated successor
  (`changed=false`). Does the hint belong in the cache key?** → A: No. Precedent: the existing
  `vision_describe` cached component already excludes the hint from its key. The hint is advisory
  context derived from the same pixel content; diff-related hint fields describe capture adjacency,
  not screen content, and must not defeat caching for provably identical pixels. Recorded as an
  explicit assumption.
- **Q: Should error/exception responses be cached?** → A: Never. Only successfully returned model
  answers are stored. Failures propagate to the caller's existing error handling and the next
  attempt issues a real call.
- **Q: Scope of wiring?** → A: Both verification-path call sites that ask the model a visual
  question about a screen: (1) `visual_question` condition evaluation, (2) the one-shot visual
  escalation fallback in step-result resolution. The observe-phase `vision_describe` path is
  untouched. The deterministic-overrides-visual arbitration logic in step-result resolution is
  owned by a parallel feature and is explicitly out of scope — this feature only swaps the model
  invocation for a cached invocation, with minimal diff.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Identical frame + identical question answered from cache (Priority: P1)

A test step's verification asks the visual model "did X appear on screen?" on each of several
iterations. The screen has not changed between iterations — the capture service has already proven
each new capture pixel-identical to its predecessor. The first iteration issues one real model
call; every subsequent iteration on the identical frame reuses that answer instantly, with no
network round trip.

**Why this priority**: This is the diagnosed production waste: 3 identical 5-6 s cloud calls per
step in run bb9f039e. Eliminating repeats directly cuts wall-clock time and API cost of every
retry-heavy run.

**Independent Test**: Drive a capture sequence of N identical frames, evaluate the same
`visual_question` condition after each; assert via call counting that the model was invoked exactly
once and the verification verdict is identical each time.

**Acceptance Scenarios**:

1. **Given** a frame proven pixel-identical to its predecessor (dedup mechanism), **When** the same
   visual question is evaluated against it with the same model, **Then** the cached answer is
   returned and no model call is made.
2. **Given** the same identical-frame sequence, **When** the verification verdicts are compared,
   **Then** the cached-answer verdict and reason equal the original call's verdict and reason.
3. **Given** a run where such reuse occurred, **When** the run report is produced, **Then** the
   performance summary's cache-hit counts include a `vision_answer` entry with the hit count.

---

### User Story 2 - Different question or changed screen always re-asks (Priority: P2)

A verification asks two different questions about the same screen, or the screen content changes
between iterations. Each distinct (frame content, question, model) combination gets its own real
model call — the cache never returns an answer for a different question or different pixels.

**Why this priority**: Correctness guardrail — a cache that conflates questions or frames would
corrupt verification verdicts, which is worse than the latency it saves.

**Acceptance Scenarios**:

1. **Given** a cached answer for question A on frame F, **When** question B is evaluated on the
   same frame F, **Then** a real model call is made for B (and both answers are independently
   cached).
2. **Given** a cached answer for question A on frame F, **When** the screen changes and question A
   is evaluated on the new frame G, **Then** a real model call is made.
3. **Given** a cached answer produced by model M1, **When** the same frame and question are
   evaluated under model identity M2, **Then** a real model call is made.

---

### User Story 3 - Bounded retention identical to existing analysis cache (Priority: P3)

Cached visual answers live in the same bounded window as other cached analysis components
(`perception.cache_max_frames`, 3..5 frames). An answer not referenced within the window is
evicted; a later identical frame + question issues a fresh model call.

**Why this priority**: Keeps memory bounded on weak hardware and keeps behavior consistent with
the established Feature 004 cache semantics; without it the cache would grow unbounded across a
long run.

**Acceptance Scenarios**:

1. **Given** a cached answer whose last reference is more than `cache_max_frames` captures old,
   **When** the same frame content + question recurs, **Then** the entry has been evicted and a
   real model call is made.
2. **Given** a run/session reset or disconnect, **When** the cache is cleared, **Then** no visual
   answer survives into the next run.

---

### Edge Cases

- Frame not deduplicated (first occurrence, or A→B→A non-adjacent recurrence): lookup is not even
  eligible — real call. Same strict-adjacency gate as every other cached component.
- Frame has no content hash (hash unavailable): caching is skipped entirely — real call every time,
  never a wrong-key hit.
- Model call raises: error propagates exactly as today; nothing is stored; next evaluation retries
  with a real call.
- Cache infrastructure itself raises on lookup/store: treated as a miss / no-op — verification
  never breaks because of the cache (matches Feature 004 error behavior).
- No cache configured (e.g. unit tests constructing the engine bare): behavior is byte-identical to
  today — direct model call.
- Question text differing only by surrounding whitespace: treated as a different question (no
  normalization beyond exact text; conservative, never conflates).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The analysis cache MUST support a new cached component `vision_answer` alongside the
  existing `ocr`, `template`, `diff`, and `vision_describe` components.
- **FR-002**: The `vision_answer` cache key MUST include: frame content identity (the existing
  content-hash / pixel-identity mechanism), a hash of the exact question text, and the model
  identity (provider name + requested model, plus mode/prompt/schema revisions via the existing
  algorithm-revision mechanism).
- **FR-003**: A cache lookup MUST be eligible only under the existing strict-adjacency dedup gate:
  the current frame is `deduplicated=true` with a direct-predecessor `duplicate_of_frame_id`, and
  the stored entry's key fingerprint matches exactly. Same frame content + same question + same
  model → cached answer, no network call. Any change in frame content, question text, or model
  identity → miss and real call.
- **FR-004**: All verification-path visual-question model calls MUST route through one shared
  cached-answer helper: (a) `visual_question` condition evaluation, and (b) the one-shot visual
  escalation fallback in step-result resolution. Both call sites MUST behave identically to today
  when no cache is configured.
- **FR-005**: `vision_answer` entries MUST obey the existing bounded window
  (`perception.cache_max_frames`, 3..5): entries not referenced within the window are evicted, and
  run/session reset clears them.
- **FR-006**: Every `vision_answer` cache hit MUST be recorded in run telemetry, and the run's
  performance summary `cache_hits` map MUST report a `vision_answer` count (present even when 0,
  next to the existing ocr/template/vision counts). Every real (miss) call MUST continue to be
  observable as an analysis invocation.
- **FR-007**: Only successful model answers are cached. Errors are never cached and MUST propagate
  exactly as they do today. Cache-infrastructure failures MUST degrade to a real call, never fail
  verification.
- **FR-008**: The Feature 004 perception-cache contract's "Explicit exclusions" is amended
  narrowly: the pure visual answer (frame content + question + model → answer) becomes a cacheable
  content component; Verifier *conclusions* (step verification results, ActionEffect combination,
  escalation and arbitration decisions) remain excluded and MUST still be resolved fresh every
  iteration on independently captured evidence.
- **FR-009**: The deterministic-overrides-visual arbitration logic in step-result resolution is out
  of scope and MUST NOT be modified; the escalation call site changes only the way the model answer
  is obtained, with minimal diff to that file.

### Key Entities

- **Vision Answer Cache Entry**: A stored pure result of asking the visual model one question about
  one screen content: verdict (passed/failed/uncertain), reason text, model name, confidence.
  Keyed by (component=`vision_answer`, content identity, question-text hash, model identity,
  revisions). Holds no pixels, no image paths, no run context.
- **Performance Summary cache_hits**: Existing per-component hit-count map; gains a
  `vision_answer` entry.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a step with N iterations whose post-action screens are pixel-identical and whose
  visual question is unchanged, exactly 1 real model call is made (was N); verified by call-count
  oracle in tests.
- **SC-002**: In the diagnosed scenario shape (3 identical iterations, ~5-6 s per visual call),
  per-step verification wall time attributable to visual questions drops by roughly two thirds;
  cached answers return without any network round trip.
- **SC-003**: Distinct questions on the same frame, the same question on changed frames, and
  evaluations after window eviction each produce their own real model call — zero wrong-key hits
  in the test suite.
- **SC-004**: Run reports show `vision_answer` hit counts in the performance summary; existing
  ocr/template/vision counts and all existing tests remain unchanged and green.

## Assumptions

- The Feature 004 dedup mechanism (content hash + strict adjacency) is the sole authority on
  "same frame content"; this feature adds no new pixel comparison.
- The advisory structured-screen hint sent alongside the question is derived from the same pixel
  content and is intentionally excluded from the cache key (precedent: `vision_describe`).
  Diff-adjacency hint fields may differ between an original frame and its duplicate without
  affecting the answer's validity.
- Question text is compared exactly (hash of exact text); no normalization.
- Model identity is taken from run configuration (provider name + requested model + prompt/schema
  revision), not from the response's self-reported model name (matches the Feature 004 rule that
  response-side `model_name` alone cannot complete a lookup).
- The escalation fallback's fixed question ("Did the expected business result appear on screen?")
  benefits from the same cache when the frame is unchanged between the condition evaluation and
  escalation only if the question text matches; different questions are separate entries by design.
- A parallel feature owns the arbitration (deterministic-overrides-visual) logic in step-result
  resolution; this feature's diff there is limited to the model-invocation line(s).
