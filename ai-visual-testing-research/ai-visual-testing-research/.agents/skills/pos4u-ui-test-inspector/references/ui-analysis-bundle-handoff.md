# POS4U evidence handoff to UI Analysis Bundle v1

Use this mapping only after collecting POS4U source/runtime evidence. Treat `generate-ui-analysis-index` and its `references/bundle-contract.md` as authoritative for filenames, required fields, confidence values, and validation.

## Artifact boundary

- Keep `source-ui.json`, runtime snapshots, `ui-inspection.json`, screenshots, and action logs outside the bundle directory.
- Put only contract-defined `manifest.yaml` and JSONL files in the flat bundle directory.
- Preserve POS4U-only details in allowed `metadata` or `source_evidence` fields when useful. Do not add undeclared top-level fields to bundle records.
- Exclude card data, PINs, credentials, personal data, and full receipt/customer information.

## Stable identity

- Derive `screen_id` from a stable window/page/dialog class or source identity.
- Derive `element_id` from `AutomationId`; otherwise use stable `sourceName` plus `screen_id`.
- Never derive a persistent ID solely from localized text, `RuntimeId`, physical coordinates, HWND, process ID, or collection index.
- Use the same ID for the same logical screen/control across captures and locales.

## Record mapping

| POS4U evidence | Bundle destination |
|---|---|
| Window/page/dialog identity and title | `screens.jsonl`: `screen_id`, `name`, `screen_type`, `visible_titles`, `aliases` |
| `automationId`, `sourceName`, `name` | `elements.jsonl`: stable `element_id`, `name`, `visible_texts`, `aliases` |
| `controlType`, `actionPatterns` | `role`, `supported_actions` |
| Runtime physical bounds plus screen client bounds | `normalized_bounds` in `normalized_1000` |
| Enabled/visible/selection conditions | `state_conditions` |
| Parent path, sibling layout, labels | `parent_element_id`, `region`, `anchors`, `neighbors` |
| `sourceFile`, `sourceLine`, handler/command/call chain | `source_evidence`; retain richer non-sensitive details in `metadata` when allowed |
| Verified action outcome or traced navigation | `transitions.jsonl` and optional `expected_effects` |
| `automationGaps`, unmapped nodes, unresolved mappings | Optional `diagnostics.jsonl` with non-`confirmed` confidence |

Map common action patterns semantically:

| Runtime/source pattern | Bundle action |
|---|---|
| `Invoke`, `Click` | `click` |
| `Value` on editable text | `type_text` and/or `set_value` |
| `Selection`, `SelectionItem` | `select` |
| `Toggle` | `toggle` |
| `ExpandCollapse` | `expand` and/or `collapse` |
| Focus support | `focus` |

Use neutral lowercase role/action names consistent with existing bundle records. Do not copy WPF or WinForms class names directly when a semantic role is known.

## Normalize runtime bounds

Normalize each element against the physical client rectangle of its owning `Screen`, not the whole desktop and not an unrelated top-level window. Treat a popup or dialog represented as a separate screen as having its own client rectangle.

Given:

```text
screen client physical = (screenX, screenY, screenWidth, screenHeight)
element physical       = (elementX, elementY, elementWidth, elementHeight)
```

Compute integer coordinates:

```text
x1 = clamp(round((elementX - screenX) / screenWidth * 1000), 0, 1000)
y1 = clamp(round((elementY - screenY) / screenHeight * 1000), 0, 1000)
x2 = clamp(round((elementX + elementWidth  - screenX) / screenWidth  * 1000), 0, 1000)
y2 = clamp(round((elementY + elementHeight - screenY) / screenHeight * 1000), 0, 1000)
```

Emit:

```json
{
  "coordinate_space": "normalized_1000",
  "x1": 400,
  "y1": 400,
  "x2": 600,
  "y2": 500
}
```

Require positive screen dimensions and `x1 < x2`, `y1 < y2`. If the owning screen rectangle is unknown, the element is clipped to an empty rectangle, or normalization collapses an edge, emit `normalized_bounds: null` and add a diagnostic instead of guessing. Recompute after layout, monitor, DPI, locale, window, popup, or modal changes.

## Translate confidence

Assign confidence independently to each bundle record using the four levels defined by `generate-ui-analysis-index`.

| Evidence | Bundle confidence |
|---|---|
| Observed and verified in a live run | `confirmed` |
| Derived only from XAML, Designer.cs, handlers, commands, or config | `statically_inferred` |
| Established only from screenshot/OCR/visual inspection | `visually_confirmed` |
| Plausible mapping, unexecuted transition, or environment-dependent geometry | `requires_runtime_verification` |

Do not mechanically convert `sourceMappingConfidence: high` to `confirmed`; that value measures source/runtime matching strength, not whether the bundle fact was exercised. A record with mixed evidence must use the level appropriate to the claimed fact. Diagnostics must never use `confirmed`.

## Transition evidence

- Emit a transition as `confirmed` only after executing the trigger in an authorized test/training instance and observing the destination screen.
- Use `statically_inferred` when a handler/command trace clearly establishes navigation but no live action was performed.
- Use `requires_runtime_verification` for branch-dependent, device-dependent, permission-dependent, or otherwise unresolved destinations.
- Reference existing stable `screen_id` and `element_id` values; do not create dangling references.
