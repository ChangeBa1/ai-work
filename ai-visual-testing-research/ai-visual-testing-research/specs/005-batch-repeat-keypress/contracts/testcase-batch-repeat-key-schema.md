# Contract: `TestStep.batch_repeat_key` YAML Schema

Audience: test-case authors writing/editing `vnc_agent/testcases/*.yaml`. This is the public,
declarative interface introduced by this feature — the only new surface an author needs to learn.

## Shape

```yaml
steps:
  - id: <existing required TestStep fields unchanged: id, name, intent, expected, ...>
    max_retries: <existing field — governs whole-step retry if the batch or its verification fails>
    batch_repeat_key:
      key: <string, required>          # single key name, same vocabulary as press_key's `keys[0]`
      count: <int, required>           # 1..50 inclusive, no default
      interval_ms: <int, optional>     # 0..500 inclusive; omitted → 50ms default
```

`batch_repeat_key` is optional on every `TestStep`. A step either has it (deterministic, Planner
bypassed for that step) or omits it (existing Planner-driven behavior, unchanged).

## Field contract

| Field | Required | Range | Rejected values | Rejection point |
|---|---|---|---|---|
| `key` | yes | one of the existing `press_key` single-key names, excluding modifiers (`ctrl`, `alt`, `shift`, `win`/`super`/`meta`/`cmd`) | unknown key name; any modifier key; more than one key | `load_test_case()` — before any run starts |
| `count` | yes | integer, `1..50` inclusive | `0`, negative, `> 50`, non-integer, omitted | `load_test_case()` |
| `interval_ms` | no | integer, `0..500` inclusive | negative, `> 500`, non-integer | `load_test_case()` |

A malformed `batch_repeat_key` block fails `load_test_case()` with a `FieldValidationError` whose
`errors` list identifies the offending field path (`steps[i].batch_repeat_key.<field>`), exactly like
every other structural validation error this loader already raises. **No key is ever sent to the
device for a test case that fails this validation.**

## Runtime contract

- When `batch_repeat_key` is set, the step's `intent` text is still required by the schema (for
  human-readable labeling/reporting) but is **not** sent to the Planner for this step — the Planner is
  not called at all for this step's action decision.
- Exactly one `ActionIteration`'s Act phase performs the whole burst of `count` sends of `key`,
  `interval_ms` apart (or the 50ms default apart if omitted). No screenshot, OCR, Planner, Grounder, or
  Verifier call happens between individual sends.
- Exactly one pre-action observation and one post-action wait-stable + verification still run for the
  step, unchanged from every other action type.
- If a send fails partway through, the step's this-iteration outcome reports how many sends actually
  completed (see `contracts/execution-layer-contract.md`); `TestStep.max_retries` still governs
  whether the whole step (i.e., the whole declared batch, retried from the top) gets another attempt.

## Compatibility contract

- A `TestStep` that omits `batch_repeat_key` behaves identically to today — this field's presence is
  the only trigger for any behavior change.
- Existing test cases (e.g. `pos-buy-bag-checkout.yaml`) that never set this field require zero
  changes and continue to load and run exactly as before (FR-012, SC-005).

## Example — the primary use case

```yaml
- id: clear-barcode-with-backspace
  name: 用Backspace清空Barcode框
  intent: 一次性清空 Barcode 输入框：连续发送 20 次 Backspace。
  batch_repeat_key:
    key: backspace
    count: 20
  max_retries: 2
  verification_mode: business
  expected:
    operator: all
    conditions:
      - type: visual_question
        value: >-
          请只看 ScannerSimulator 顶部「Barcode:」下方的输入框：
          框内是否已经完全空白（没有任何数字或字符）？
          仅当输入框明确为空时回答 passed。
```
