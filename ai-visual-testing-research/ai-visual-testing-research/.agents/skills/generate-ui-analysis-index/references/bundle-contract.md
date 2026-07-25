# UI Analysis Bundle v1 — Producer contract

**Schema version**: `1.0` (`schema_version: "1.0"`)

This document is the producer-oriented view of `specs/007-ui-analysis-index-consumption/contracts/ui-analysis-bundle-v1.md`. Field names and file requirements MUST stay in sync with that authoritative contract.

## Directory layout

| File | Required |
|---|---|
| `manifest.yaml` | yes |
| `screens.jsonl` | yes |
| `elements.jsonl` | yes |
| `transitions.jsonl` | yes |
| `flows.jsonl` | no |
| `diagnostics.jsonl` | no |

- Filenames are case-sensitive; do not rename.
- Each `.jsonl` file is UTF-8, one JSON object per line.
- `manifest.yaml` top-level value MUST be a YAML mapping.

## `manifest.yaml` — top-level fields

| Field | Type | Required |
|---|---|---|
| `schema_version` | string | yes |
| `bundle_id` | string | yes |
| `project_id` | string | yes |
| `generated_at` | string (ISO 8601) | yes |
| `producer.name` | string | yes |
| `producer.version` | string | yes |
| `source_revision` | string | yes |
| `frameworks` | list[string] | yes (may be empty) |
| `coordinate_spaces` | list[string] | yes (≥1 item) |
| `default_viewports` | list[object] | no |
| `content_files` | map[string → object] | yes |
| `content_files.<name>.required` | boolean | yes |
| `content_files.<name>.sha256` | string \| null | no |
| `content_files.<name>.record_count` | int \| null | no |
| `metadata` | map \| null | no |

### Stable identifiers

- **`bundle_id`**: unique bundle instance (UUID or stable slug).
- **`project_id`**: owning project identifier.
- **`source_revision`**: traceability string (e.g. `git:<sha>`, `design:v3`).
- **`producer`**: `{name, version}` of the tool or team that generated the bundle.

## `screens.jsonl` — record fields

| Field | Type | Required |
|---|---|---|
| `screen_id` | string | yes |
| `name` | string | yes |
| `screen_type` | string | yes |
| `visible_titles` | list[string] | yes (may be empty) |
| `aliases` | list[string] | yes (may be empty) |
| `parent_screen_id` | string \| null | no |
| `source_evidence` | string \| null | no |
| `confidence` | Confidence object | yes |
| `metadata` | map \| null | no |

## `elements.jsonl` — record fields

| Field | Type | Required |
|---|---|---|
| `element_id` | string | yes |
| `screen_id` | string | yes |
| `parent_element_id` | string \| null | no |
| `name` | string | yes |
| `role` | string | yes |
| `visible_texts` | list[string] | yes (may be empty) |
| `aliases` | list[string] | yes (may be empty) |
| `supported_actions` | list[string] | yes (may be empty) |
| `state_conditions` | object | no |
| `region` | string | yes |
| `normalized_bounds` | object \| null | no |
| `anchors` | list[string] | no |
| `neighbors` | list[object] | no |
| `expected_effects` | list[string] | no |
| `source_evidence` | string \| null | no |
| `confidence` | Confidence object | yes |
| `metadata` | map \| null | no |

## `transitions.jsonl` — record fields

| Field | Type | Required |
|---|---|---|
| `transition_id` | string | yes |
| `from_screen_id` | string | yes |
| `trigger_element_id` | string | yes |
| `trigger_action` | string | yes |
| `guards` | list[object] | no |
| `to_screen_id` | string | yes |
| `transition_type` | string | yes |
| `expected_visible` | list[string] | no |
| `expected_hidden` | list[string] | no |
| `expected_state_changes` | list[string] | no |
| `source_evidence` | string \| null | no |
| `confidence` | Confidence object | yes |

## `flows.jsonl` — record fields (optional file)

| Field | Type | Required |
|---|---|---|
| `flow_id` | string | yes |
| `name` | string | yes |
| `start_screen_id` | string | yes |
| `steps` | list[object] | yes (≥1 item) |
| `completion_screen_id` | string | yes |
| `preconditions` | list[object] | no |
| `confidence` | Confidence object | yes |

## `diagnostics.jsonl` — record fields (optional file)

| Field | Type | Required |
|---|---|---|
| `diagnostic_id` | string | yes |
| `category` | string | yes |
| `target_ref` | object \| null | no |
| `reason` | string | yes |
| `confidence` | Confidence object | yes |
| `source_evidence` | string \| null | no |

## `Confidence` object (shared)

| Field | Type | Required |
|---|---|---|
| `level` | string | yes |
| `score` | number \| null | no |

Allowed `level` values: `confirmed`, `statically_inferred`, `visually_confirmed`, `requires_runtime_verification`.

See [confidence-rules.md](confidence-rules.md) for producer labeling guidance.
