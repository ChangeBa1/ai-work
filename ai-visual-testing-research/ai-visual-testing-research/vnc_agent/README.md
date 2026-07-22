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

## Layout

See `specs/001-vnc-core-execution-loop/plan.md` for the full module map.
Also `specs/002-action-effect-verification/plan.md` for ActionEffect / RepeatGuard /
focus-path changes.
Also `specs/003-action-identity-grounding/plan.md` for identity, grounding, and
dangerous-drift changes.
