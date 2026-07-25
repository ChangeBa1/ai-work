---
name: generate-ui-analysis-index
description: Generate a language-agnostic ui-analysis-bundle-v1 directory (manifest.yaml + JSONL) for external UI projects so vnc-agent can validate/query it. Use whenever the user asks to produce a UI analysis index/bundle, export screen/element/transition knowledge for vnc-agent, or generate screens.jsonl/elements.jsonl/transitions.jsonl without implementing a source analyzer.
---

# Generate UI Analysis Index

Produce a **language- and framework-agnostic** `ui-analysis-bundle-v1` directory that vnc-agent can load, validate, and query. This skill defines **what to emit** and **how to label confidence** — not how to parse any particular source tree.

## Overview

An index bundle is a flat directory of one `manifest.yaml` plus UTF-8 JSONL files. Each line is one JSON object. Stable IDs, cross-file references, and normalized coordinates let vnc-agent assist testcase authoring without embedding business logic in the consumer.

**Do not** ship or invoke a source analyzer, AST parser, or framework-specific toolchain as part of this skill. Analyze the target project with whatever tools the user already has; map findings into the bundle contract below.

## Five recognition goals

When building a bundle, capture these dimensions for every meaningful UI surface:

1. **Screens** — distinct views, pages, dialogs, or modal layers (`screens.jsonl`).
2. **Elements** — interactive or semantically meaningful controls within a screen (`elements.jsonl`).
3. **Text & role** — visible labels, aliases, and control roles (button, text_field, icon_button, …).
4. **Relative position & neighbors** — `normalized_bounds` (0–1000 space), `region`, `anchors`, and directional `neighbors`.
5. **Actions, state, transitions & flows** — `supported_actions`, `state_conditions`, screen-to-screen `transitions.jsonl`, and optional ordered `flows.jsonl`.

## Workflow

1. Read [references/bundle-contract.md](references/bundle-contract.md) for file layout and field tables.
2. Read [references/confidence-rules.md](references/confidence-rules.md) before assigning any `confidence` object.
3. For framework-agnostic mapping intuition, see [references/framework-examples.md](references/framework-examples.md) (conceptual only).
4. Start from [assets/bundle-template/blank/](assets/bundle-template/blank/) or [assets/bundle-template/minimal-valid-example/](assets/bundle-template/minimal-valid-example/).
5. Fill records with stable IDs, consistent references, and honest confidence levels.
6. **Before delivery**, run validation:

```bash
cd vnc_agent
uv run vnc-agent ui-index validate <path-to-bundle-dir>
```

Fix every reported issue. A bundle that fails validation MUST NOT be handed off.

## References & assets

| Resource | Purpose |
|---|---|
| [references/bundle-contract.md](references/bundle-contract.md) | Authoritative producer field tables (aligned with repo contract) |
| [references/confidence-rules.md](references/confidence-rules.md) | Four confidence levels and forbidden `confirmed` misuse |
| [references/framework-examples.md](references/framework-examples.md) | Conceptual Screen/Element/Transition mapping examples |
| [assets/bundle-template/blank/](assets/bundle-template/blank/) | Empty-typed skeleton to copy |
| [assets/bundle-template/minimal-valid-example/](assets/bundle-template/minimal-valid-example/) | Smallest bundle that passes validation |
