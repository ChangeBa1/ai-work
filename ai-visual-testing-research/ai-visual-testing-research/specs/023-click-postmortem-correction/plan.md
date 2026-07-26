# Implementation Plan: Click Post-Mortem Correction

**Branch**: `023-click-postmortem-correction` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/023-click-postmortem-correction/spec.md`

## Summary

Give the WRONG_TARGET recovery (feature 022) a first-choice **post-mortem tier** that actually uses the
misclick evidence: (1) confirm/restore the pre-click page (015 fingerprint tier-high check; at most one
safe Esc undo), (2) ask a VLM — pre-click frame + annotated post-click frame (click marker + intended
target rectangle at original resolution) + evidence summary — for `{clicked_element, target_found,
corrected_bbox, coordinate_space, confidence, reason}` in strict JSON, (3) after strict bbox resolution
plus confidence and distance gates, re-click `safe_click_point(corrected_bbox)` through the completely
unchanged execution+verification loop, and (4) let the existing 015 write path persist the corrected
region on a verified pass. Every refusal falls back to the 022 chain inside existing budgets; disabled ⇒
022 byte-identical.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed project in `vnc_agent/`)

**Primary Dependencies**: existing only — httpx (OpenAI-compatible channel, 017 keep-alive client
pattern), OpenCV (annotation drawing), pydantic; no new dependencies

**Storage**: additive pydantic fields (`ActionIteration.postmortem`); diagnosis artifacts via the
existing `ArtifactStore.save_json/save_bytes` under `runs/<run>/model/`; no schema migration

**Testing**: pytest + pytest-asyncio; 2 new unit files, 1 new e2e scenario (22) with a stub postmortem
client and an undo-capable FakeVNC subclass; golden legacy-projection snapshot regenerated (additive)

**Target Platform**: unchanged (offline-capable, Windows/Linux)

**Performance Goals**: zero extra model calls unless a WRONG_TARGET upgrade fires AND postmortem is
enabled AND the per-step cap allows; then exactly one diagnosis call (plus at most one Esc + one recovery
observation)

**Constraints**: fail-safe everywhere (every refusal degrades to the 022 chain); no verification
exemption; `planning/`, `verification/`, `perception/`, `memory/` internals, `replay/`, MiMo grounding
chain untouched; annotated image at original resolution (no downscale — 018's planner path deliberately
not reused)

**Scale/Scope**: 2 new source modules, 8 existing source files touched (additive / insert-beside), 2 new
unit files + 1 e2e file, 2 updated test files, 1 regenerated snapshot, specs

## Constitution Check

*GATE: passed.*

- Principle I (deterministic runtime control): the model only *proposes* a corrected bbox; acceptance is
  deterministic (strict parse, strict coordinate resolution, config-declared confidence + distance
  gates), execution geometry is the deterministic `safe_click_point`, and the undo decision is the pure
  015 fingerprint math with config thresholds.
- Principle II (Planner/Grounder separation): the diagnosis is a new, third read-only role
  (`model_role="postmortem"`); it never emits actions — the runtime builds the ExecutableAction itself.
  The grounding chain is untouched.
- Principle IV (independent verification): the corrected click runs the full execute/wait/verify loop;
  nothing is exempted. Memory write-back happens only after a verified pass, through the existing path.
- Principle VI (domain-agnostic core): all new vocabulary is generic (post-mortem, corrected bbox,
  undo); prompts describe GUI geometry, not business semantics; thresholds live in config.
- Recovery constitution: `postmortem`/`postmortem_undo` are explicit strategy verbs inside the existing
  engine (budgets, RecoveryAttempt records); the undo key is Esc only — the destructive-action ban holds.
- FR-049 lineage: the model receives unmasked frames (existing convention); everything persisted locally
  (annotated artifact) is rendered from the masked-safe evidence image.

**Domain-Agnostic Core gate (Principle VI)**:

- [x] No business-specific fields/states/branches.
- [x] No scenario semantics (click geometry + failure vocabulary only).
- [x] Validated with constructed frames/regions, not business fixtures.

## Phase 0 — Research (inline)

- **Why the engine selects but the runtime executes**: `execute_strategy` only sees a driver; the
  post-mortem needs pipeline observations, the artifact store, model client and the iteration record.
  Feature 014 already split zoom the same way (engine plans/one-shots, runtime consumes) — reuse the
  idiom: `postmortem` is a no-op in `_run()`, the runtime does the work right after `handle()` returns
  and downgrades `attempt.resolved` when the diagnosis refuses.
- **Refusal ⇒ substitution**: `_plan_zoom`-style capability check (`StrategyContext.postmortem_capable`
  + per-step cap) substitutes the next chain entry inside `handle()`, so budget-exhausted or
  incapable-runtime cases never leak a phantom `postmortem` attempt that did nothing.
- **Disabled ⇒ chain restore**: dropping `postmortem` in `strategies_for()` (not in `ROUTING`) keeps the
  static table single-source while making the *effective* chain — and `_step_strategy_index` indexing —
  literally the 022 list when disabled.
- **Undo check economics**: the post-click frame (`after`) already exists with OCR — the first "same
  page?" comparison costs zero captures. Only a detected page change pays for one Esc + one recovery
  observation.
- **Fingerprint reuse**: `build_page_fingerprint(image, ocr_items, resolution)` + `page_similarity` +
  `classify_page_match(..., high/medium/low from memory config)`; resolution mismatch already caps the
  tier below high inside `classify_page_match` — cross-resolution frames can never count as "same page".
- **Correction consumption point**: the grounding branch already consumes one-shot recovery plans (zoom)
  and pre-grounder shortcuts (memory hit). The correction slots in as the highest-priority shortcut for
  click-type actions, skipping memory and grounder for that iteration; a pending plan facing a
  non-click proposal is dropped (fail-open to the normal path).
- **FakeVNC harness**: legacy e2e scenarios pin `wrong_target_postmortem.enabled=false` in the shared
  `app_config` fixture (exactly like the 022 guard pin — spec-defined byte-identical baseline);
  scenario 22 builds its own enabled config, an `UndoScriptedVNC` whose Esc reverts the dialog frame,
  and stubs the diagnosis client.

## Phase 1 — Design

### Judgment rules & thresholds

| Signal | Rule | Threshold (config) | Default |
|---|---|---|---|
| postmortem gate | strategy available at all | `recovery.wrong_target_postmortem.enabled` | true |
| per-step cap | diagnoses per TestStep | `recovery.wrong_target_postmortem.max_retries` | 1 |
| same page | `classify_page_match(...) == "high"` | `memory.page_match_high/medium/low` (reused) | 0.88/0.72/0.55 |
| accept diagnosis | strict parse ∧ target_found ∧ bbox resolves | — (rule) | — |
| confidence gate | `confidence >= threshold` | `wrong_target_postmortem.confidence_threshold` | 0.7 |
| distance gate | `dist(corrected_pt, click_point) <= ratio × screen_w` | `wrong_target_postmortem.max_click_distance_ratio` | 0.4 |
| budgets | Tier-2 / global | `recovery.wrong_target` (unchanged) | 2 |

### Changes by file

- `src/vnc_agent/models/postmortem_client.py` (new) — system prompt; `PostmortemDiagnosis` strict model
  (target_found+confidence required; found⇒bbox required); `parse_postmortem_diagnosis` (chat.completion
  envelope → strict JSON, raising `PostmortemParseError`); `resolve_corrected_bbox` →
  `coordinate_space.resolve_pixel_bbox`; `HttpPostmortemClient` (grounder config endpoint/model, 017
  keep-alive pattern, two-image payload: before path + annotated PNG bytes inlined base64);
  `StubPostmortemClient`.
- `src/vnc_agent/recovery/postmortem.py` (new) — `render_click_annotation` (cv2 marker+rect, size
  preserved), `annotation_png_bytes`, `build_evidence_summary` (022 evidence → text),
  `is_same_page_high` (015 fingerprint tier check), `click_distance_px` / `max_click_distance_px`;
  `PostmortemDiagnostician.run(...)` — the full undo→annotate→call→parse→gate pipeline returning
  `(PostmortemAudit, PostmortemCorrectionPlan | None, undo RecoveryAttempt | None)`; every failure maps
  to a distinct audit outcome and never raises.
- `src/vnc_agent/domain/recovery.py` — `RecoveryStrategy` += `postmortem`/`postmortem_undo`;
  `PostmortemOutcome` Literal; additive `PostmortemCorrectionPlan` + `PostmortemAudit` models.
- `src/vnc_agent/domain/run.py` — additive `ActionIteration.postmortem: PostmortemAudit | None`.
- `src/vnc_agent/config.py` — `WrongTargetPostmortemConfig` (enabled/confidence_threshold/
  max_click_distance_ratio/max_retries) wired as `AgentConfig.wrong_target_postmortem`; the existing
  before-validator extracts it from the yaml `recovery:` section (zoom_reground precedent).
- `config/agent.yaml` — `recovery.wrong_target_postmortem:` section (lockstep defaults + rationale).
- `src/vnc_agent/recovery/strategies.py` — `ROUTING[WRONG_TARGET]` gains leading `postmortem`;
  `StrategyContext.postmortem_capable`; `_run()` no-op `postmortem` branch + `postmortem_undo` = single
  Esc.
- `src/vnc_agent/recovery/engine.py` — per-step postmortem counter (+ reset), capability/cap refusal
  substitution in `handle()`, `postmortem` counted as path-changing, one-shot
  `set_/take_postmortem_correction`, `strategies_for()` drops `postmortem` when disabled.
- `src/vnc_agent/runtime/agent_runtime.py` — optional `postmortem_client` seam + lazy HTTP build;
  WRONG_TARGET branch: capability flag → engine routing → diagnostician run → audit/artifacts/
  ModelCallAudit(model_role="postmortem") → correction storage or 022 fallback attempt; grounding branch:
  one-shot correction consumption for click actions (skip memory+grounder, `model_call_skipped` audit).
  All inserted beside 008/009/014/015/016/022 wiring.
- `src/vnc_agent/runtime/telemetry.py` — `ModelRole` += `"postmortem"` (additive Literal member).
- `src/vnc_agent/reporting/json_report.py` — additive `postmortem` iteration key (null when absent).
- Tests — `tests/unit/test_postmortem_diagnosis.py`, `tests/unit/test_postmortem_routing.py`,
  `tests/e2e/test_scenario_22_click_postmortem_correction.py`; `tests/e2e/conftest.py` pins
  `wrong_target_postmortem.enabled=false` for legacy scenarios (rationale comment);
  `tests/unit/test_stale_frame_guard.py` routing expectations updated to the 023 chain (022's
  chain-equality assertions are superseded by FR-007); `tests/fixtures/test_json_report_compatibility.py`
  `_LEGACY_ITERATION_KEYS` + `postmortem`; `tests/snapshots/report_legacy_projection.json` regenerated
  (additive: one null key).

### Post-mortem data contract

`ActionIteration.postmortem` (`PostmortemAudit`):

```
outcome: corrected | page_not_restored | diagnosis_failed | target_not_found
         | low_confidence | distance_exceeded
clicked_element: str | null            target_found: bool | null
confidence: float | null               corrected_bbox: (x1,y1,x2,y2) | null
corrected_click_point: (x,y) | null    distance_px: float | null
max_distance_px: float | null          confidence_threshold: float
undo_performed: bool                   undo_restored_page: bool | null
page_similarity: float | null          annotated_image_ref: str | null
request_ref: str | null                response_ref: str | null
reason: str
```

plus the one-shot `PostmortemCorrectionPlan {corrected_bbox, click_point, confidence, clicked_element,
source_iteration_index}` (engine-held, consumed by the next iteration's grounding branch) and the
`RecoveryAttempt` records (`postmortem`, `postmortem_undo`).
