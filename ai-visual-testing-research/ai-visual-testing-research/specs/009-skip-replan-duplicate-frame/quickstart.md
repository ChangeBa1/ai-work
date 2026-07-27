# Quickstart: Skip Re-Plan on Duplicate Frame with Blocked Action

**Feature**: 009-skip-replan-duplicate-frame

## Run the tests

```bash
cd vnc_agent
uv sync
uv run pytest tests/unit/test_planner_skip_decision.py -q          # predicate unit tests
uv run pytest tests/e2e/test_scenario_11_skip_replan_duplicate_frame.py -q  # end-to-end
uv run pytest tests/unit tests/fixtures -q                          # regression
uv run pytest tests/e2e -q                                          # regression
```

## Observe the behavior on a run

After any run, inspect the JSON report:

- `steps[].iterations[].planner_skipped_reason` — `"duplicate_frame_blocked_action"` marks a short-circuited round; `null` everywhere else.
- `performance_summary.model_calls.planner` — counts only actual planner calls.
- `performance_summary.skipped_model_call_count` — grows by one per short-circuited round.
- Structured logs: one `model_call_skipped` event (`model_role="planner"`) per skipped round.

## When does it trigger?

Round N skips the planner iff round N-1's action was blocked by RepeatGuard with reason `blocked_effect_pending`(`_normalized_target`) or `ambiguous_fail_safe`, AND round N's observation has the same content hash as round N-1's, AND the step is not time-dependent (no `timeout_seconds` on the verification spec, previous action not wait-type), AND it is not a `batch_repeat_key` step.
