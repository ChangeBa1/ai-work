# Contract: vision_answer cached component

Amends (narrowly) the Feature 004 perception-cache contract's "Explicit exclusions". The Feature
004 contract file itself is historical and unchanged; this contract governs the `vision_answer`
component.

## Cacheable unit

The pure visual answer function:

```
(frame pixel content, exact question text, request-side model identity) → (answer, reason, confidence, model_name)
```

Only `describe_screen(mode="answer_question")` responses. Never cached: Verifier conclusions
(StepVerificationResult), ActionEffect combination, escalation decisions,
deterministic-overrides-visual arbitration, Planner decisions, Grounder locations — these always
re-run per iteration on independently captured evidence (Constitution Principle IV preserved:
evidence is still freshly captured; only a capture proven pixel-identical by the Feature 004
dedup gate may reuse the model answer).

## Key identity

- `component="vision_answer"`, `algorithm_revision="vision-answer-v1"`;
- content: `content_hash` + `scope_key` (scope identity hash);
- question: sha256 of exact utf-8 question text — any textual change (including whitespace) is a
  different key;
- model: request-side provider name + requested model + prompt/schema revision. Response-side
  `model_name` alone MUST NOT complete a lookup (Feature 004 rule).
- The advisory `structured_screen_hint` is excluded from identity (precedent: `vision_describe`).

## Lookup contract

1. No cache configured, `content_hash` null, or `scope_key` empty ⇒ no lookup, direct call.
2. Current screen not `deduplicated=true` with a direct-predecessor `duplicate_of_frame_id` ⇒
   miss (A→B→A never hits; strict adjacency is FrameCaptureService's proven decision).
3. Key fingerprint mismatch (content, scope, question, model, revision) ⇒ miss.
4. Last reference older than `cache_max_frames` (3..5) in capture sequence ⇒ evict + miss.
5. Hit ⇒ return stored response unchanged; MUST NOT issue HTTP; MUST append the current sequence
   to the entry's reference window.

## Call sites (both MUST route through the shared helper)

1. `visual_question` condition evaluation (`verification/engine.py` → `visual_verifier.py`).
2. Step-result escalation fallback (`verification/business_resolver.py`), via the engine
   delegate — the resolver's arbitration logic is out of scope (FR-009) and its diff is limited to
   how the model answer is obtained.

With no cache configured both sites behave byte-identically to the pre-feature code.

## Telemetry contract

- hit ⇒ `CounterEvent(kind="analysis_cache_hit", payload={component:"vision_answer", frame_id,
  source_ref})`;
- real call ⇒ `CounterEvent(kind="analysis_invocation", payload={component:"vision_answer",
  invocation_id, status:"completed"})`;
- `performance_summary.cache_hits` MUST contain `vision_answer` (0 when unused) alongside
  ocr/template/vision;
- Test oracle is call counting on the planner double — never durations, never report-side counts
  alone.

## Error behavior

- Model call raises ⇒ propagate to caller unchanged; nothing stored.
- Cache lookup/store raises ⇒ log-and-degrade to a real call / no-op; verification never fails
  because of the cache.
- Run/session reset, disconnect ⇒ `clear()` drops all entries (shared cache instance).
