# Quickstart: Vision Answer Cache

## What it does

Verification-phase `visual_question` answers (`describe_screen(mode="answer_question")`) are now
cached in the same bounded `AnalysisResultCache` used by ocr/template/vision_describe. When the
post-action capture is proven pixel-identical to its predecessor (Feature 004 dedup) and the
question + model are unchanged, the cached answer is returned with no HTTP call.

## No configuration change

Uses the existing `agent.perception.cache_max_frames` (3..5) window. No new config keys. Runs
without a cache (bare `VerificationEngine()`) behave exactly as before.

## Verify it works

```bash
cd vnc_agent
uv run pytest tests/fixtures/test_vision_answer_cache.py -q   # call-count oracle
uv run pytest tests/unit tests/fixtures -q
uv run pytest tests/e2e -q
```

Expected oracle behavior:

- N identical frames + same question ⇒ exactly 1 planner `answer_question` call;
- second question on the same frame ⇒ its own call;
- changed frame ⇒ new call;
- entry older than `cache_max_frames` references ⇒ evicted, new call.

## Observe in a real run

In the run report JSON, `performance_summary.cache_hits` now contains `"vision_answer"`; repeated
identical verification frames show hits > 0 and correspondingly fewer 5-6 s visual calls in the
verification stage.
