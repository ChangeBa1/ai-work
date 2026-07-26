# Feature Specification: Click Post-Mortem Correction (点错自愈 — Part 2: 事后诊断与修正)

**Feature Branch**: `023-click-postmortem-correction`

**Created**: 2026-07-27

**Status**: Implemented

**Input**: User description: "Feature 022 delivered the deterministic WRONG_TARGET attribution (suspected ∧
verification failed) with full geometric evidence (`ActionIteration.wrong_target_evidence`: click_point,
target_region, nearest_blob bbox/distance/offset/direction) and routes recovery through the generic
re-observe/re-locate chain (`recapture → zoom_reground → re_ground`). That recovery throws the evidence
away — it just searches again from scratch. Add a **click post-mortem** tier: show a VLM the pre-click
frame plus an *annotated* post-click frame (actual click point marked, intended target region framed) and
the 022 evidence summary; the model answers what was actually clicked and where the intended target really
is (`corrected_bbox`); after undoing any accidental page change (Esc, at most once), the agent re-clicks
the corrected location through the unchanged execution+verification loop and, on a verified pass, writes
the corrected region back into page-element memory so the mistake becomes next time's direct hit."

## Clarifications

### Session 2026-07-27 (self-resolved; fully automated run — decisions recorded here instead of asked)

- Q: Where does the post-mortem sit in the WRONG_TARGET recovery chain? → A: As the *first* strategy:
  `ROUTING[WRONG_TARGET] = ["postmortem", "recapture", "zoom_reground", "re_ground"]`. The strategy verb
  `postmortem` goes through the existing `RecoveryEngine.handle` path unchanged (Tier-2 budget, global
  retry budget consumption, `RecoveryAttempt` record); the engine only *selects* it — the actual
  undo/diagnose/correct work runs in the runtime's WRONG_TARGET branch right after `handle()` returns,
  mirroring how `zoom_reground` selection (engine) and the zoom observation (runtime, next iteration) are
  already split. When `recovery.wrong_target_postmortem.enabled: false`, `strategies_for(WRONG_TARGET)`
  drops `postmortem` entirely — the chain is byte-identical to 022.
- Q: How is the "postmortem 每步最多 1 次" red line enforced? → A: A per-step counter in the
  RecoveryEngine (`reset_iteration()` clears it at TestStep start, exactly like the feature-014
  `_zoom_attempts_step` cap). When the counter has reached `wrong_target_postmortem.max_retries`
  (default 1) — or the runtime signalled it cannot diagnose (`StrategyContext.postmortem_capable=False`)
  — the engine substitutes the next strategy in the chain, the same refusal semantics `zoom_reground`
  uses. A corrected re-click whose verification fails again therefore re-enters WRONG_TARGET routing and
  deterministically gets `recapture` (`_step_strategy_index` already advanced past `postmortem`), never a
  second diagnosis.
- Q: What exactly does the model see? → A: Two images at **original resolution** (no downscale — the
  answer must map 1:1 back to frame pixels, so the 018 planner-downscale path is deliberately not used):
  (1) the pre-click observation frame (model-facing unmasked path, FR-049 convention), (2) the post-click
  frame with the actual `click_point` marked (red circle + crosshair) and the intended `target_region`
  framed (orange rectangle), drawn with OpenCV. The annotated image sent to the model is rendered from the
  model-facing (unmasked) post-click frame and inlined as base64 — never persisted; the artifact copy
  under `runs/<run>/model/` is rendered from the masked-safe evidence frame (same masking rules as every
  other locally persisted image).
- Q: What must the model answer? → A: One strict JSON object:
  `{"clicked_element": str, "target_found": bool, "corrected_bbox": [x1,y1,x2,y2] | null,
  "coordinate_space": "pixel" | "normalized_1000", "confidence": 0~1, "reason": str}`.
  Parsing is strict fail-safe: JSON decode failure, missing `target_found`/`confidence`,
  `target_found=true` without a bbox, unknown coordinate space, or a bbox rejected by the single-point
  strict converter `models/coordinate_space.resolve_pixel_bbox` (never clamp, never guess — 014/018
  lineage) each individually fail the diagnosis and fall back to the 022 chain.
- Q: Which model/endpooint serves the diagnosis? → A: The existing OpenAI-compatible channel with the
  **grounder's** endpoint/model config (`models.grounder`) — a separate lightweight
  `HttpPostmortemClient` (own system prompt, two-image user message), so the MiMo grounding chain
  (`mimo_grounder.py`) is untouched. Offline tests inject a `StubPostmortemClient` through the new
  optional `AgentRuntime(postmortem_client=...)` seam.
- Q: How is "还在点击前的页面吗" decided? → A: Feature 015's pure fingerprint functions
  (`memory/fingerprint.py`: `build_page_fingerprint` + `page_similarity` + `classify_page_match`) over
  the pre-click observation frame vs. the post-click frame (each with its own OCR items), thresholds
  straight from the existing `memory.page_match_high/medium/low` config; only tier `"high"` counts as
  "same page". Not-high ⇒ one safe undo: the `postmortem_undo` strategy verb sends a single Esc (the
  same non-destructive key the `unexpected_dialog` chain's `press_escape` uses; Alt+F4 and friends remain
  banned), then one fresh `capture_source="recovery"` observation is compared again. Still not high ⇒ the
  post-mortem aborts (`page_not_restored`) and the 022 chain takes over. The undo is recorded as its own
  `RecoveryAttempt` (strategy `postmortem_undo`, resolved = page restored) and happens at most once per
  diagnosis.
- Q: How does the corrected click execute? → A: The diagnosis produces a one-shot
  `PostmortemCorrectionPlan` (corrected_bbox + click point from `planning/click_point.safe_click_point`
  with empty siblings — the exact geometry every other mouse path uses) stored on the RecoveryEngine like
  the 014 zoom plan. The next ActionIteration's grounding branch consumes it *before* memory/grounder for
  coordinate-producing click actions: the grounder call is skipped (audited as `model_call_skipped`,
  reason `postmortem_correction`, mirroring the 015 memory-hit shape), the ExecutableAction is built with
  `target_region=corrected_bbox`, and execution/wait/verify/RepeatGuard run entirely unchanged — no
  verification is exempted (Constitution IV).
- Q: What guards against a hallucinated bbox? → A: Three independent gates, each falling back to the 022
  chain: (1) strict parse + `resolve_pixel_bbox` in-bounds validation; (2)
  `confidence >= wrong_target_postmortem.confidence_threshold` (default 0.7); (3) the corrected click
  point must lie within `wrong_target_postmortem.max_click_distance_ratio` × screen width (default 0.4)
  of the original click point — a "correction" flung across the screen is treated as untrustworthy.
- Q: How does the memory write-back happen? → A: With zero new write code. The corrected ExecutableAction
  carries `target_region=corrected_bbox`, so the existing 015 runtime write path ("verified-passed mouse
  action with a resolved target_region ⇒ `PageElementMemory.record_success`") persists the corrected
  region under the same target label. Stale entries for the old (wrong) region decay through 015's
  existing failure counters — nothing is deleted.
- Q: Budget accounting? → A: `postmortem` consumes the WRONG_TARGET Tier-2 budget and the global retry
  budget through the existing `RecoveryPolicy` (`recovery.wrong_target`, unchanged) — no separate budget
  pool. A failed diagnosis additionally routes one normal fallback attempt (`recapture`) inside the same
  budgets, so a diagnose-and-fail iteration ends exactly where a 022 iteration would.
- Q: Observability? → A: Diagnosis request summary + raw response JSON + the safe annotated image are
  persisted under the run's `model/` directory (`ArtifactStore.save_json`/`save_bytes`); a new additive
  `ActionIteration.postmortem` audit (outcome, clicked_element, corrected_bbox, corrected click point,
  distance, thresholds, artifact refs, undo flags) mirrors into the JSON report; the model call itself is
  audited via the existing `ModelCallAudit` convention with the new `model_role="postmortem"` (which also
  increments `performance_summary.model_calls["postmortem"]`), plus `postmortem_*` structured log events.
- Q: Why are legacy e2e scenarios pinned `wrong_target_postmortem.enabled=false`? → A: Same reasoning as
  the 022 guard pin: pre-023 scenarios (incl. scenario 21) script FakeVNC frames and recovery
  expectations around the 022 chain and have no postmortem model stub; `enabled: false` is spec-defined
  to reproduce the 022 chain byte-identically. Scenario 22 builds its own postmortem-enabled config with
  an injected stub client.

## User Scenarios & Testing *(mandatory)*

### User Story A - Diagnose and correct a misplaced click (Priority: P1)

A click lands beside the intended control (022 attributes WRONG_TARGET). Instead of blindly re-searching,
the agent shows the model where it clicked, what responded and what it wanted, gets the corrected target
region, re-clicks it through the normal verified pipeline, and — on a verified pass — remembers the
corrected region for next time.

**Why this priority**: This is the entire point of the two-part feature — 022's evidence finally *drives*
the recovery instead of being reporting garnish.

**Independent Test**: e2e scenario 22a — misplaced click, stub diagnosis returns a corrected bbox; assert
the corrected re-click, the passing verification, the memory write-back of the corrected region and the
full recovery/audit trail.

**Acceptance Scenarios**:

1. **Given** a WRONG_TARGET-upgraded iteration with a postmortem-capable runtime, **When** recovery
   routes, **Then** the first attempt's strategy is `postmortem`, the diagnosis artifacts exist
   (annotated image at the post-click frame's exact resolution, request/response JSON under `model/`),
   and `iteration.postmortem.outcome == "corrected"`.
2. **Given** a stored correction plan, **When** the next ActionIteration resolves a click action, **Then**
   the grounder is NOT called (one `model_call_skipped` audit, reason `postmortem_correction`), the
   executable's `target_region` equals the corrected bbox and its coordinates equal
   `safe_click_point(corrected_bbox, siblings=[])`, and verification runs unchanged.
3. **Given** the corrected click passes verification, **Then** `PageElementMemory` holds the target label
   with the corrected bbox (existing 015 write path).

---

### User Story B - Undo an accidentally opened dialog before diagnosing (Priority: P1)

The wrong click opened a dialog/new surface. Before diagnosing, the agent detects the page changed
(fingerprint tier < high vs. the pre-click frame), presses Esc once, confirms the page is back, then
diagnoses and corrects as in Story A.

**Independent Test**: e2e scenario 22b — dialog appears on the wrong click; assert one Esc, a
`postmortem_undo` RecoveryAttempt (resolved), then the corrected click passes.

**Acceptance Scenarios**:

1. **Given** a post-click frame whose fingerprint match vs. the pre-click frame is below tier high,
   **When** the post-mortem starts, **Then** exactly one Esc is sent, one fresh recovery observation is
   compared, and on restoration the diagnosis proceeds (`postmortem.undo_performed=true`,
   `undo_restored_page=true`).
2. **Given** the page still does not match after the single Esc, **Then** the post-mortem aborts with
   outcome `page_not_restored`, no model call happens, and the same iteration falls back to the 022
   chain (`recapture`) within existing budgets.

---

### User Story C - Fail-safe refusal paths (Priority: P2)

Anything questionable about the diagnosis (parse failure, `target_found=false`, low confidence, invalid
bbox, correction too far away) abandons the post-mortem and the 022 chain proceeds — the feature can only
add a better recovery, never a worse one.

**Independent Test**: e2e scenario 22c (low confidence → recapture fallback) + unit matrix over every
refusal reason.

**Acceptance Scenarios**:

1. **Given** a diagnosis below the confidence threshold, **Then** `postmortem.outcome=="low_confidence"`,
   the `postmortem` attempt is recorded unresolved, and a `recapture` attempt follows in the same
   iteration (022 chain, existing budgets).
2. **Given** `wrong_target_postmortem.enabled: false`, **Then** routing, attempts and report fields are
   byte-identical to the 022 baseline (no `postmortem` strategy, no `postmortem` iteration field content,
   zero diagnosis calls).
3. **Given** a corrected re-click whose verification fails again, **Then** no second diagnosis happens in
   that step (per-step cap 1) — the retry terminates through the existing chain/budgets.

---

### Edge Cases

- Diagnosis model unreachable / raises → diagnosis fails (`diagnosis_failed`), 022 fallback; the run
  never crashes on the post-mortem path.
- `corrected_bbox` valid but `coordinate_space="normalized_1000"` → resolved through the same strict
  converter the grounder uses; out-of-range values (>1000 or resolving out of frame) reject.
- Post-click frame unreadable / annotation render fails → `diagnosis_failed` before any model call.
- Correction plan pending but the next iteration's planner proposes a keyboard action → the plan is
  consumed and dropped (never applied to a non-click), grounding proceeds normally.
- WRONG_TARGET budget exhausted before postmortem selection → existing unresolved-attempt path, no
  diagnosis.
- Replay-mode runs (016) never enter `run_action_iteration` → untouched.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A post-mortem diagnosis MUST send the pre-click frame plus an annotated post-click frame
  (actual click point marker + intended target region rectangle, OpenCV-drawn, exact original
  resolution) and the 022 evidence summary to the existing OpenAI-compatible channel (grounder
  endpoint/model config) with a dedicated prompt requiring the strict JSON answer
  `{clicked_element, target_found, corrected_bbox, coordinate_space, confidence, reason}`.
- **FR-002**: Response handling MUST be strict fail-safe: any parse/validation failure — including
  `resolve_pixel_bbox` rejection (no clamping, no guessing) — fails the diagnosis and falls back to the
  022 recovery chain.
- **FR-003**: Before diagnosing, the runtime MUST verify the page still matches the pre-click frame via
  feature 015's fingerprint functions at tier `high` (thresholds from `memory.*`). On mismatch it MUST
  perform at most ONE safe undo (Esc — never a destructive key), re-observe, re-compare; still-mismatched
  ⇒ abort post-mortem (`page_not_restored`) and fall back. The undo MUST be recorded as a
  `RecoveryAttempt` with strategy `postmortem_undo`.
- **FR-004**: A diagnosis is accepted only when `target_found`, the bbox passes strict resolution AND
  `confidence >= wrong_target_postmortem.confidence_threshold` (default 0.7) AND the corrected click
  point (from `safe_click_point(corrected_bbox, siblings=[])`) lies within
  `wrong_target_postmortem.max_click_distance_ratio` (default 0.4) × screen width of the original click
  point. Any gate failure falls back to the 022 chain.
- **FR-005**: An accepted correction MUST execute as a normal ExecutableAction
  (`target_region=corrected_bbox`, safe-click-point coordinates) through the unchanged
  execution/wait/verification loop on the next ActionIteration — no verification bypass. The skipped
  grounder call MUST be audited (`model_call_skipped`, reason `postmortem_correction`).
- **FR-006**: After the corrected click passes independent verification, the corrected region MUST reach
  `PageElementMemory.record_success` through the existing runtime write path (corrected_bbox as
  target_region); old wrong entries decay via existing failure counters only.
- **FR-007**: `ROUTING[WRONG_TARGET]` MUST become `["postmortem", "recapture", "zoom_reground",
  "re_ground"]`; with `wrong_target_postmortem.enabled: false` the effective chain MUST be byte-identical
  to 022 (`["recapture", "zoom_reground", "re_ground"]`).
- **FR-008**: The post-mortem (undo + diagnosis + correction) MUST run at most
  `wrong_target_postmortem.max_retries` (default 1) times per TestStep, consume the existing WRONG_TARGET
  Tier-2 and global retry budgets, and a corrected click that fails verification again MUST NOT trigger a
  second diagnosis in that step.
- **FR-009**: Config section `recovery.wrong_target_postmortem` MUST expose `enabled` (default true),
  `confidence_threshold` (0.7), `max_click_distance_ratio` (0.4), `max_retries` (1); shipped yaml in
  lockstep with model defaults.
- **FR-010**: Observability: diagnosis request/response artifacts + safe annotated image under the run's
  `model/` directory; additive `ActionIteration.postmortem` audit (outcome, clicked_element,
  corrected_bbox, corrected click point, distance, artifact refs, undo flags) mirrored in the JSON
  report; `ModelCallAudit` with `model_role="postmortem"` for every actual diagnosis call (counted in
  `performance_summary.model_calls`).

### Success Criteria

- **SC-001**: e2e scenario 22 covers: (a) misplaced click → postmortem → corrected click → verified pass
  → memory write-back + full audit; (b) dialog undo (Esc) → diagnosis → correction; (c) low confidence →
  recapture fallback; (d) disabled → 022-identical behavior with zero diagnosis calls; (e) corrected
  click fails again → no second diagnosis, budget-terminated.
- **SC-002**: Unit coverage: strict parse matrix (valid pixel / valid normalized_1000 / missing fields /
  invalid bbox / non-JSON), confidence gate, distance gate, annotation rendering (markers drawn, size ==
  source), undo decision (same page skip / mismatch Esc / not restored abort), routing + per-step budget +
  disabled chain, config defaults/bounds/yaml lockstep.
- **SC-003**: Full offline regression `uv run pytest tests/unit tests/fixtures tests/e2e
  tests/integration -q` green (1 pre-existing skip); golden snapshot change limited to the additive null
  `postmortem` iteration key (regenerated).
- **SC-004**: `planning/`, `verification/`, `perception/`, `memory/` internals, `replay/` and the MiMo
  grounding chain untouched (public call sites only).
