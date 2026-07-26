# Data Model: Vision Answer Cache

## 1. Component Literal (extended)

`vnc_agent.perception.cache.Component`:

```
Literal["ocr", "template", "diff", "vision_describe", "vision_answer"]
```

## 2. vision_answer cache key

Reuses `AnalysisCacheKey` (frozen dataclass, Feature 004) with:

| Field | Value for vision_answer |
|---|---|
| `component` | `"vision_answer"` |
| `algorithm_revision` | `"vision-answer-v1"` |
| `content_hash` | `StructuredScreen.content_hash` (mirrors owning `ScreenFrame`) |
| `scope_identity` | `StructuredScreen.scope_key` (sha of `CaptureScope`, includes pixel format + mask identity) |
| `pixel_format` | `""` (subsumed by `scope_key`; uniform within component) |
| `mask_identity` | `""` (subsumed by `scope_key`; uniform within component) |
| `perception_config_fingerprint` | `""` (perception toggles do not change the answer to a question about fixed pixels; uniform within component) |
| `component_identity` | see below |

`component_identity`:

```json
{
  "provider": "<vision provider name, e.g. planner-provider>",
  "requested_model": "<configured model>",
  "mode": "answer_question",
  "prompt_revision": "vision-answer-v1",
  "schema_revision": "vision-answer-v1",
  "question_sha256": "<sha256 of exact question text (utf-8)>"
}
```

Question text is hashed exactly (no normalization). The `structured_screen_hint` is intentionally
NOT part of the identity (research.md R5).

## 3. Cached value

The successful `VisionUnderstandingResponse` (pydantic BaseModel, pure data):
`mode="answer_question"`, `answer` ∈ {passed, failed, uncertain}, `reason`, `description`,
`confidence`, `model_name`. Errors and `None` are never stored (FR-007).

Entries live in the shared `AnalysisResultCache` instance (`AnalysisCacheEntry`): same
`source_frame_id` audit field, same `referencing_sequences` window bookkeeping, same
`max_frames` (3..5) eviction, same `clear()` on run/session reset.

## 4. StructuredScreen (additive mirror fields, Feature 004 §7 extension)

| Field | Type | Default | Source |
|---|---|---|---|
| `capture_sequence` | `int` | `0` | `ScreenFrame.capture_sequence` |
| `scope_key` | `str` | `""` | `scope_identity(ScreenFrame.scope)` |

Populated by both assemblers (`assemble_structured_screen_from_pixels`,
`assemble_structured_screen`). Defaults keep all existing constructions valid; an empty
`scope_key` or absent `content_hash` disables caching for that screen (eligibility guard), never a
wrong-key hit.

## 5. CachedVisualAnswerer (new, verification package)

```
CachedVisualAnswerer(
    cache: AnalysisResultCache | None,
    test_run_provider: () -> TestRun | None,
    provider_name: str,
    model: str,
)
async answer(planner, screen: StructuredScreen, question: str) -> VisionUnderstandingResponse
```

Behavior:
- eligibility: cache present AND `screen.content_hash` AND `screen.deduplicated` AND
  `screen.duplicate_of_frame_id` — else direct model call (byte-identical to today);
- hit → emit `analysis_cache_hit(component="vision_answer", frame_id, source_ref)`, return stored
  response, no HTTP;
- miss → real `describe_screen(mode="answer_question")`, emit
  `analysis_invocation(component="vision_answer")`, store on success;
- lookup/store exceptions → treated as miss / no-op (Feature 004 error behavior);
- model exceptions → propagate, nothing stored.

Ownership: one instance per `VerificationEngine`; `AgentRuntime` wires it from
`pipeline.cache`, `capture_service.test_run` (lazy), and the pipeline's vision provider/model
identity. `VerificationEngine.answer_visual_question(screen, question, planner=None)` is the
delegate used by `business_resolver` (minimal diff, FR-009).

## 6. PerformanceSummary

`cache_hits` gains an always-present `"vision_answer"` key (default 0), derived from
`analysis_cache_hit` counter events exactly like ocr/template/vision. No schema change —
`cache_hits` is already `dict[str, int]`.
