# Feature Specification: Wrong-Click Detection (点错自愈 — Part 1: 判定信号)

**Feature Branch**: `022-wrong-click-detection`

**Created**: 2026-07-27

**Status**: Implemented

**Input**: User description: "The system can already detect '没点上' (action_no_effect) and obvious error popups (unexpected_effect), but not '点到了旁边的控件': the screen changes → `expected_effect` passes → the failure only surfaces at step verification with a vague `verification_failed` attribution, so recovery never learns the click was simply misplaced. A second root cause is stale frames: grounding runs on a T0 observation but execution happens at T0+seconds (a model call apart) — if the screen moved, the coordinates are 刻舟求剑 (`artifacts/_probe_stale_capture.py` is the historical probe of this failure). Build two deterministic defense lines with **zero new model calls**: (A) a pre-execution stale-frame guard for mouse actions, and (B) a WRONG_TARGET assessment/attribution upgrade that feature 023 (post-hoc diagnosis) consumes."

## Clarifications

### Session 2026-07-27 (self-resolved; fully automated run — decisions recorded here instead of asked)

- Q: What pixel infrastructure does the guard reuse? → A: The one shared `FrameCaptureService` (feature 004): the guard capture is a normal `capture()` with a new `capture_source="pre_click_guard"` (dedup + audit + `TestRun.frames` apply automatically; the `ScreenFrame.capture_source` Literal is extended additively). The ROI comparison reuses `perception/screen_diff.py::compute_diff` over the two safe-evidence PNGs (identically masked ⇒ mask handling is free) with `threshold=1.0` so only `local_blobs` + ratio are computed — the same trick `classify_action_effect` already uses. A content-hash fast path skips the diff entirely when the guard frame is logically identical to the observation frame.
- Q: Which actions does the guard cover? → A: Every `ExecutableAction` with `method == "mouse"` and a non-null `target_region` (grounding, OCR-direct, memory-direct paths all set it). Mouse actions without a `target_region` and all keyboard actions fail open — the guard never blocks what it cannot localize.
- Q: What happens on guard-internal failure (capture error, unreadable observation image)? → A: Fail open — execute as before. The guard is protective and MUST NOT introduce a new failure mode (mirrors the feature-014 observe_zoom fail-open convention).
- Q: How does a vetoed iteration terminate? → A: The action is NOT sent; the iteration fails with `VerificationResult(status="failed", reason="stale_frame: …")` after routing one recovery attempt through the existing `RecoveryEngine` with the new `FailureType.STALE_FRAME` (`ROUTING = ["recapture"]`; the next ActionIteration re-observes and re-grounds by construction, which IS the "re-observe + re-locate" remedy). RepeatGuard treats the vetoed iteration exactly like a never-executed proposal (`execution_result is None` and `action_effect is None` ⇒ `no_effect_confirmed` allow-path already in place since 002), so the retry is never blocked.
- Q: Where do WRONG_TARGET suspicion inputs come from? → A: Entirely from evidence that already exists after `classify_action_effect`: `evidence.local_blobs` + `evidence.global_diff_ratio` from the before/after diff, plus the executed action's `target_region`/`coordinates`. The assessment is a new pure function (`assess_wrong_target`) beside — never inside — `classify_action_effect`; existing classification semantics are untouched.
- Q: Why a screen-scale exemption? → A: A dialog popping up or a page navigating legitimately changes regions far from the click. `global_diff_ratio >= wrong_target_global_diff_ratio_max` (default 0.10) therefore vetoes suspicion.
- Q: When does suspicion change the verdict? → A: Never by itself. Only `suspected AND verification_result.status == "failed"` upgrades the iteration's attribution to `WRONG_TARGET` (reason prefixed `wrong_target:`, one recovery attempt routed through the `target_not_found`-equivalent chain `recapture → zoom_reground → re_ground`, reusing the feature-014 zoom plumbing). Suspected-but-passed iterations stay passed and only record evidence/telemetry (the response region may legitimately live elsewhere, e.g. a click that lights a distant status line).
- Q: How does feature 023 consume the signal? → A: Additive `ActionIteration.wrong_target_evidence` (full `WrongTargetEvidence`: suspected, thresholds applied, blob counts, max blob↔target IoU, nearest-blob bbox/distance/offset/8-way direction, click_point) + additive `ActionIteration.failure_attribution` ("stale_frame"/"wrong_target"/null) + the persisted `RecoveryAttempt.failure_type` + the experience row's `failure_type` (the runtime now passes `failure_attribution` into `ExperienceCollector.collect`, which always accepted the argument). All additive; JSON report mirrors both new iteration fields.
- Q: Feature 021 interplay? → A: Automatic — the hard-case miner already matches any configured `hard_case_failure_types` value against persisted recovery attempts and experience `failure_type`. `wrong_target`/`stale_frame` become matchable values; the shipped default set is deliberately unchanged (deployments opt in), only the stale yaml comment ("WRONG_TARGET does not exist in the enum") was refreshed.
- Q: Why are the legacy e2e scenarios run with the guard disabled? → A: The shared `FakeVNC` advances its scripted frame list on EVERY capture, so the (production-default-on) guard capture would consume frames that pre-022 scenarios scripted for later pipeline stages — a test-harness artifact, not a behavior question. The e2e conftest `app_config` fixture pins `stale_frame_check_enabled=False` with a comment; scenario 21 builds its own guard-enabled config and a click-driven `ClickScriptedVNC` whose frames advance on clicks (realistic causality). Spec FR-A03's "disabled == byte-identical pre-022 behavior" is exactly what keeps the legacy suite green unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story A - Stale-frame guard vetoes a doomed click (Priority: P1)

Grounding produced coordinates from a T0 frame; by execution time the UI drifted (async refresh, animation settling). Instead of clicking a ghost, the agent re-captures once, sees the target neighborhood changed, refuses to send the action, and retries from a fresh observation.

**Why this priority**: Sending a click at stale coordinates is the cheapest failure to prevent — one millisecond-scale ROI compare versus a wasted click + verification round (or worse, a click on whatever moved under the cursor).

**Independent Test**: e2e scenario 21a — scripted frame drift inside the target region between observation and execution; assert the click was never sent, the iteration failed as `stale_frame`, and the re-observed retry clicked the moved control and passed.

**Acceptance Scenarios**:

1. **Given** a mouse action whose `target_region` neighborhood (expand 0.25) changed between the observation frame and the guard capture, **When** the runtime reaches the execution stage, **Then** the action is NOT sent, the iteration records a `STALE_FRAME` recovery attempt (`recapture`) and fails with reason `stale_frame: …`, and the next iteration re-observes/re-grounds and may pass.
2. **Given** a guard capture logically identical to the observation frame (content hash equal / deduplicated), **When** the guard runs, **Then** the action executes exactly as without the guard (one extra audited frame is the only trace).
3. **Given** changes strictly outside the expanded neighborhood, **When** the guard runs, **Then** the action executes (distant churn — clocks, tickers — never vetoes).
4. **Given** `execution.stale_frame_check_enabled: false`, **When** any run executes, **Then** no `pre_click_guard` capture ever happens and behavior is byte-identical to pre-022.

---

### User Story B - Wrong-click attribution upgrade (Priority: P1)

A click lands beside the intended control: the screen changes (`expected_effect` — the neighbor reacted), step verification later fails, and pre-022 the failure was a vague `verification_failed`. Now the iteration is deterministically attributed `WRONG_TARGET` with distance/direction evidence, and recovery re-observes + re-locates instead of blindly re-verifying.

**Independent Test**: e2e scenario 21b — click produces only a far-away blob (global ratio < 0.10) and `text_appears` verification fails; assert `wrong_target_evidence.suspected`, attribution `wrong_target`, reason prefix `wrong_target:`, a `recapture` recovery attempt, and a passing re-located second iteration.

**Acceptance Scenarios**:

1. **Given** `expected_effect` whose change blobs ALL miss the x0.5 target neighborhood and `global_diff_ratio < 0.10`, **When** the iteration's verification fails, **Then** `failure_attribution == "wrong_target"`, the verification reason is prefixed `wrong_target:`, one `WRONG_TARGET` recovery attempt is recorded (chain `recapture → zoom_reground → re_ground`), and the experience row carries `failure_type="wrong_target"`.
2. **Given** the same suspicion but a PASSING verification, **When** the iteration completes, **Then** the step passes unchanged, `failure_attribution` stays null, no `WRONG_TARGET` recovery attempt exists, and only `wrong_target_evidence` + a `wrong_target_suspected` structured log record the suspicion.
3. **Given** a full-screen-scale change (`global_diff_ratio >= 0.10`, e.g. dialog/page transition), **When** assessed, **Then** the iteration is never suspected regardless of blob geometry.
4. **Given** any change blob touching the expanded target neighborhood, **When** assessed, **Then** the iteration is not suspected (the target did react).

---

### Edge Cases

- Guard capture fails / observation image unreadable → fail open, execute (Clarification 3).
- Mouse action without `target_region` (e.g. bare scroll) → guard and assessment both skip; `wrong_target_evidence` stays null.
- `no_effect` / `unexpected_effect` / `effect_uncertain` classifications → never suspected (only `expected_effect` is assessable); nearest-blob geometry is still recorded when computable.
- Blob exactly on the expanded-neighborhood boundary → exclusive edge (no intersection ⇒ suspected); pinned by unit test.
- STALE_FRAME Tier-2 budget exhausted (default max_retries 2) → the attempt is recorded unresolved and the step fails through the existing budget path — no new loop.
- Replay-mode runs (016) execute through `ReplayPlayer`, not `run_action_iteration` → deliberately untouched by both defense lines.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-A01**: Before EXECUTING any `method=="mouse"` ExecutableAction with a `target_region`, the runtime MUST (when enabled) capture one fresh frame via the shared FrameCaptureService with `capture_source="pre_click_guard"` and compare the target neighborhood against the observation frame that produced the coordinates, using existing diff facilities (`compute_diff`, content hash) — zero model calls, ROI-scoped verdict.
- **FR-A02**: If any change blob intersects the `target_region` expanded per-side by `execution.stale_frame_region_expand_ratio` (default 0.25), the action MUST NOT be sent; the iteration fails with the new `FailureType.STALE_FRAME` routed through the existing RecoveryEngine (`ROUTING: ["recapture"]`, budget from the config `recovery.stale_frame` section, default `max_retries: 2`). No change in the neighborhood ⇒ execute exactly as before.
- **FR-A03**: `execution.stale_frame_check_enabled` (default `true`) gates the entire guard; disabled ⇒ byte-identical pre-022 behavior (no guard capture, no new states, no new records).
- **FR-A04**: Guard captures flow through the existing capture contract (dedup, audit, `TestRun.frames`) — no parallel capture path.
- **FR-B01**: `FailureType.WRONG_TARGET = "wrong_target"` MUST exist (`domain/recovery.py`; overall_design.md §9.10 always listed this error type).
- **FR-B02**: A new pure function `perception/action_effect.py::assess_wrong_target` MUST mark `suspected=true` iff: status is `expected_effect` AND ≥1 change blob exists AND no blob intersects the `target_region` expanded by `perception.wrong_target_neighborhood_expand_ratio` (default 0.5) AND `global_diff_ratio < perception.wrong_target_global_diff_ratio_max` (default 0.10). It MUST attach nearest-blob distance/offset/8-way direction, max blob↔target IoU, blob counts, click point and the thresholds applied — consumable by 023. `classify_action_effect` semantics MUST NOT change.
- **FR-B03**: The runtime MUST upgrade the iteration's failure attribution to `WRONG_TARGET` **only** when `suspected` AND the iteration's independent verification failed: reason prefixed `wrong_target:`, one recovery attempt routed with the `target_not_found`-equivalent chain (`recapture → zoom_reground → re_ground`, budget from `recovery.wrong_target`, default `max_retries: 2`). Suspected + passed ⇒ verdict untouched, telemetry only.
- **FR-B04**: `ActionIteration` MUST gain additive `wrong_target_evidence` (full evidence model) and `failure_attribution` fields, mirrored additively in the JSON report; the upgraded attribution MUST reach the experience stream (`VisualExperience.failure_type`).
- **FR-B05**: Feature 021's exporter benefits with zero changes (`hard_case_failure_types` is already a configurable set matched against persisted recovery attempts / experience rows); the shipped default set stays unchanged.

### Success Criteria

- **SC-001**: e2e scenario 21 covers: (a) pre-execution drift → action not sent → re-observe → pass; (b) misplaced click + failed verification → `WRONG_TARGET` attribution → re-locate → pass; (c) suspected + passed verification → passes, telemetry only; (d) guard disabled → pre-022 capture vocabulary, no new records.
- **SC-002**: Unit coverage: stale ROI verdicts (inside / outside / expansion band / boundary / expand=0), wrong-target pure function (neighborhood in/out, screen-scale exemption, distance/direction, IoU, thresholds), enum members, ROUTING entries, recovery budgets, config defaults + shipped yaml lockstep.
- **SC-003**: Full offline regression `uv run pytest tests/unit tests/fixtures tests/e2e tests/integration -q` green (1 pre-existing skip); the only golden-snapshot change is the additive regeneration of `report_legacy_projection.json` (two new null iteration keys).
- **SC-004**: Zero new model calls on either defense line (guard = capture + cv2 diff; assessment = pure geometry over existing evidence).
