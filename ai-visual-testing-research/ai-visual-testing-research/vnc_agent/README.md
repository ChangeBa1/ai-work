# vnc-agent

VNC black-box GUI automation testing core execution loop (feature `001-vnc-core-execution-loop`).

## Install

```bash
cd vnc_agent
pip install -e ".[dev]"
```

## Configure

1. Edit `config/vnc-targets.yaml` host/port.
2. Set secrets via environment variables (never in YAML plaintext):
   - `VNC_AGENT_VNC_PASSWORD`
   - `VNC_AGENT_PLANNER_API_KEY`
   - `VNC_AGENT_GROUNDER_API_KEY`
3. Point Planner/Grounder endpoints in `config/models.yaml`.

### Using OpenCode Go for both Planner and Grounder

`config/models.yaml` ships pointed at OpenCode Go (`https://opencode.ai/zen/go/v1`,
`/chat/completions`, OpenAI-compatible) for **both** roles, both defaulted to `mimo-v2.5`
(confirmed vision-capable, so `describe_screen()` gets real answers instead of degrading to
low-confidence/uncertain). Set `VNC_AGENT_PLANNER_API_KEY` and `VNC_AGENT_GROUNDER_API_KEY`
to the same OpenCode Go API key unless you want separate quotas. FR-046 still holds — this
is a config-only choice; `HttpPlannerClient` is a generic OpenAI-compatible client, no code
change was needed to point it at OpenCode Go instead of another provider. Before a real run,
verify the exact `model` id string your account accepts via `GET {base_url}/models` (bare
`mimo-v2.5` vs. an `opencode-go/mimo-v2.5` prefixed form — see
`specs/001-vnc-core-execution-loop/contracts/model-provider-contract.md`).

## CLI

```bash
# Validate test case only
vnc-agent run testcases/smoke-connect.yaml --dry-run

# Full run
vnc-agent run testcases/smoke-connect.yaml --config config

# Re-render report
vnc-agent report <run-id> --format both
```

## Tests

```bash
pytest
```

## ActionEffect vs StepVerificationResult (feature 002)

Feature `002-action-effect-verification` splits two independent outcomes on every action
iteration:

| Result | Meaning | Produced by |
|---|---|---|
| **ActionEffect** | Did the UI *respond* to the action? (`no_effect` / `expected_effect` / `unexpected_effect` / `effect_uncertain`) | `perception.action_effect.classify_action_effect` |
| **StepVerificationResult** (`VerificationResult`) | Did the *business* assertion pass? (`passed` / `failed` / `uncertain` + `basis` / `weak_assertion_warning`) | `verification.business_resolver.resolve_step_result` |

They MUST NOT be collapsed into a single pass/fail. Local pixel blobs, OCR/template diffs
drive ActionEffect; business conditions (`text_appears`, templates, `visual_question`, …)
drive StepVerificationResult.

### Authoring `verification_mode`

```yaml
# Formal business step (recommended for new cases) — load-time requires a real assertion
verification_mode: business
expected:
  operator: all
  conditions:
    - type: screen_changed
    - type: text_appears
      value: "1点"

# Effect-only probe — may pass on ActionEffect alone; report labels it clearly
verification_mode: effect_only
expected:
  operator: all
  conditions:
    - type: screen_changed

# Omitted (legacy) — still loads; runtime caps at uncertain + weak_assertion_warning
expected:
  operator: all
  conditions:
    - type: screen_changed
```

See sample `testcases/pos-hover-probe.yaml` and
`specs/002-action-effect-verification/quickstart.md` for offline regression commands.

## Action identity and grounding safety (feature 003)

Every proposed action is reduced to a `CanonicalActionIdentity` containing `step_id`,
`action_id`, `action_type`, and `normalized_target`. Authors should give a stable
`action_id` to retries of the same logical action; rewording the intent or target does not
create a new action. An action from another step is independent. If an `action_id` is not
stable, normalized target text is matched with OCR-tolerant comparison and then checked
against the step intent.

Grounder candidates must declare their `coordinate_space` explicitly:

- `pixel`: `bbox` is already in screenshot pixels and is never scaled.
- `normalized_1000`: each coordinate is in `[0, 1000]` and is converted exactly once
  against the observed screenshot resolution.

Missing, unknown, contradictory, or out-of-bounds coordinate declarations are rejected;
the runtime never guesses between pixel and normalized coordinates. Reports retain the
declared space, source box, resolved pixel box, and whether conversion occurred.

The target-consistency gate blocks `dangerous_drift` before grounding or input dispatch.
Examples include changing action type, moving from an interactive control to a result row,
or moving to another control whose label no longer matches the step intent. Legitimate
preparatory micro-actions must have an independently recognizable purpose (for example,
closing a step-requested modal). Ambiguous proposals fail safe and are recorded as
`ambiguous_fail_safe`; test-case authors should improve `action_id`, `target.role`, target
text, and step-intent wording instead of relying on retries.

## Screenshot dedup, analysis reuse, performance telemetry, zh-CN reports (feature 004)

### Logical frames vs. physical images

Every capture (observation, stability wait, retry, recovery, or post-action verification)
creates exactly one **logical `ScreenFrame`** — a new id, timestamp, and entry in
`TestRun.frames`, always. Whether it also writes a **new physical PNG** is a separate
decision: `FrameCaptureService` compares the current capture against the immediately
preceding logical frame in the same run/VNC session and only treats it as a duplicate when
*all* of these match exactly:

- run id and VNC session id
- capture kind (`full_screen`/`roi`), coordinates, resolution, pixel format
- security mask identity and `private_persistence_allowed`
- a SHA-256 over the normalized, unmasked pixel bytes (`content_hash`)
- `np.array_equal` on the decoded arrays (the hash only filters candidates — pixel equality
  is the final verdict, so a hash collision can never cause a false dedup)

A duplicate frame reuses the prior frame's safe (and, if applicable, private) physical
file — no new write, no new analysis, no new model call. Physical images are written
through a `FrameArtifactBundle`: safe/private files + a manifest are staged, fsynced, and
published via one same-filesystem directory rename — never a partial multi-file publish.
Startup/reconnect reconciles staging leftovers and quarantines any published-but-
unreferenced bundle (an orphan), which never counts as a successful physical write or
becomes report evidence.

### Analysis cache safety

`perception/cache.py`'s `AnalysisResultCache` reuses OCR/template/vision-describe pure
results **only** when the current frame is `deduplicated=true` — i.e. proven pixel-identical
to its immediate predecessor. The cache key also includes scope, pixel format, mask
identity, and a component-specific identity (OCR backend/version, template-set content
fingerprint, vision requested-model/prompt/schema), so a duplicate frame under changed
analysis configuration still misses. `A → B → A` never hits: the third capture isn't
adjacent to the first. The cache window is bounded by `perception.cache_max_frames`
(default 5, only 3-5 accepted) and never holds raw pixels, evidence paths, or a full
`StructuredScreen` — only pure per-component results, released on eviction or session
reset. Planner/Grounder/Verifier decisions are **never** in this cache —
`runtime/context_identity.py` builds their canonical request/context identity purely for
audit trail (`ModelCallAudit`), and every post-action Verifier execution always runs on
fresh, independently captured evidence.

### Performance summary

`runtime/telemetry.py::derive_performance_summary()` computes `total_capture_count`,
`unique_frame_count`, `duplicate_frame_count`, `physical_image_count`,
`avoided_write_count`/`avoided_write_bytes`, cache hit/analysis/model-call counts, and
`completeness` purely from `TestRun.frames` + `TestRun.counter_events` — never hand-patched.
A `physical_image_written` event for a frame that isn't in `TestRun.frames` (a
staging/quarantined/orphan artifact) is flagged in `consistency_errors` and excluded, never
silently counted. The same event objects that land in `TestRun` are mirrored into
structured JSON Lines logs (`stage_measurement`, `frame_dedup_decision`,
`analysis_cache_event`, `model_call_event`, `physical_image_event`,
`artifact_bundle_recovery`, `performance_summary`) — one event source, multiple outputs,
never independently recomputed per output. `report_build` times safe-evidence resolution +
machine-dict/HTML-draft assembly only; the final JSON/HTML encode + atomic write is the
separate `report_output` stage.

### zh-CN reports and zero-copy evidence

`reporting/localization.py` is the single zh-CN resource registry (`reporting.locale:
zh-CN` by default in `config/agent.yaml`; an unregistered locale fails config load, never a
silent fallback). HTML output is fully localized with autoescape on; the only English
allowed in visible text is raw error codes/details, explicit machine enum/data-marker
values, model/provider identifiers, and diagnostic file/path fragments. JSON keeps every
feature 001-003 field byte-for-byte unchanged (see
`specs/001-vnc-core-execution-loop/contracts/report-schema.md`'s feature 004 addendum) and
only *additively* appends `frames`, `stage_measurements`, `performance_summary`,
`display_status`, `localized_message`.

`reporting/safe_evidence.py` resolves each frame's safe image to a validated,
already-published path — purpose, run-root bounds, manifest, byte size, SHA-256, and
decodability are all checked — and returns "unavailable" (never a private path, never a
guess) on any mismatch. No report entry point (normal execution, offline `report`
re-render, partial-failure report, or the compat CLI path) ever copies, hardlinks, or
symlinks evidence; duplicate logical frames referencing the same physical file resolve to
the exact same path in both JSON and HTML.

### Offline acceptance commands

```bash
# Regenerate the deterministic fixture set (idempotent — must show no diff twice in a row)
uv run python tests/fixtures/images/frame_dedup/generate_fixtures.py --check

# Full offline regression (performance-marked tests excluded by default)
uv run pytest -q

# Fixed-workload performance gate (100 identical captures -> 1 write, 1 analysis each)
uv run pytest -q -m performance tests/performance/test_frame_dedup_performance.py

# Two structurally unrelated GUI scenarios sharing the same capture->observe->act->verify->report contract
uv run pytest -q tests/e2e/test_frame_dedup_cross_scenario.py

# Static core business-agnosticism scan (now also covers perception/ and storage/)
uv run pytest -q tests/unit/test_no_business_keywords_in_core.py

# Static lint
uv run ruff check src tests
```

### Safety fallbacks

Decode/mask-encode failures abort the capture outright — no `ScreenFrame`, no downstream
analysis or verification, and (when masking is required) never a raw-bytes write to the
safe path. Hash/pixel-compare/cache-get/cache-put failures degrade to "treat as unique" /
"full analysis" without raising and without fabricating a dedup/cache-hit/avoided/skipped
event. `private_persistence_allowed=false` means the unmasked pixels only exist in memory
for the current analysis and are never written or reused as a physical file — `model_image`
stays `null` for that frame; the safe evidence path is unaffected.

## Layout

See `specs/001-vnc-core-execution-loop/plan.md` for the full module map.
Also `specs/002-action-effect-verification/plan.md` for ActionEffect / RepeatGuard /
focus-path changes.
Also `specs/003-action-identity-grounding/plan.md` for identity, grounding, and
dangerous-drift changes.
Also `specs/004-frame-dedup-observability/plan.md` for screenshot dedup, analysis-cache
reuse, performance telemetry, and zh-CN report changes.
