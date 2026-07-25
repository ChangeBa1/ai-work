# Confidence rules (producer guidance)

Every `Screen`, `Element`, `Transition`, `Flow`, and `Diagnostic` record MUST include a `confidence` object:

```json
{"level": "<one of four levels>", "score": 0.85}
```

## Four levels

| `level` | Meaning | When to use |
|---|---|---|
| `confirmed` | Observed in a real run | You (or the user) interacted with the live app and verified the fact |
| `statically_inferred` | Static analysis only | Derived from source, config, or design docs without runtime or visual proof |
| `visually_confirmed` | Visual evidence only | Confirmed from screenshots/mockups; interaction not verified |
| `requires_runtime_verification` | Needs live calibration | You suspect the fact but expect the consumer to verify in their environment |

## Score field

- Optional but recommended for all levels except when unknown (`null` is allowed).
- When present, MUST be a number in `[0.0, 1.0]`.
- Use `score` to rank certainty within the same level (higher = stronger evidence).

## Forbidden labeling (FR-026)

**Never** mark `confirmed` when the evidence is only static, visual, or uncertain.

### Bad → good examples

| Wrong | Why | Fix |
|---|---|---|
| `"level": "confirmed"` on a button found only in source | No runtime proof | `"level": "statically_inferred"` |
| `"level": "confirmed"` on layout from a screenshot | Visual only | `"level": "visually_confirmed"` |
| `"level": "confirmed"` on a guard you could not execute | Unknown at build time | `"level": "requires_runtime_verification"` |
| `"level": "confirmed"` on any `diagnostics.jsonl` row | Diagnostics are explicitly non-confirmed | Use one of the other three levels |

### Diagnostics

`diagnostics.jsonl` entries MUST NOT use `"level": "confirmed"`. The consumer rejects them with `invalid_diagnostic_confidence`.
