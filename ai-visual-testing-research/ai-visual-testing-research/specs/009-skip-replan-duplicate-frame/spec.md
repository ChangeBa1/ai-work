# Feature Specification: Skip Re-Plan on Duplicate Frame with Blocked Action

**Feature Branch**: `009-skip-replan-duplicate-frame`

**Created**: 2026-07-26

**Status**: Draft

**Input**: User description: "Skip planner re-plan when the current iteration's observation frame is the same logical frame as the previous iteration's and the previous iteration's action was rejected by the repeat guard — the round cannot produce new information, so the expensive cloud planner call is pure waste. Diagnosed from real run bb9f039e (add-shopping-bag step): it[1] blocked with reason=blocked_effect_pending, it[2] ambiguous_fail_safe, both observed frames deduplicated against the previous round, yet each round still made a full 4–5 s cloud planner call. Overall design §21.3 requires 'do not re-call the Planner when the page has not changed'."

## Clarifications

### Session 2026-07-26 (self-resolved; fully automated run — decisions recorded here instead of asked)

- Q: Which blocked reasons trigger the short-circuit? → A: Exactly the reasons observed in the diagnosed incident and named in the request: `blocked_effect_pending` (including its `_normalized_target` variant, which is the same semantics with a different identity-match basis) and `ambiguous_fail_safe`. `blocked_uncertain` / `blocked_uncertain_normalized_target` are deliberately **excluded** in this feature: an `effect_uncertain` previous effect means the observation itself was ambiguous, and giving the Planner a fresh chance to propose a *different* action (e.g., a corrective micro-action) on the same frame retains some information value. Conservative scope; can be widened later with evidence.
- Q: What is "the same logical frame"? → A: Pixel-content identity: the current observation's content hash is non-null and equal to the previous iteration's observation content hash (recorded per iteration). This subsumes the capture-layer `deduplicated` flag (which only relates a frame to the *immediately preceding capture*, possibly a stability-wait or post-action frame) and is robust to interleaved captures. When either hash is unavailable (capture optimization error), the system MUST NOT short-circuit — missing evidence never triggers an optimization.
- Q: What happens instead of planning? → A: The iteration follows the exact same verdict path an in-iteration repeat-guard block already follows today: carry the previous action effect, re-run the step-result resolution (which may re-observe and escalate verification), and route recovery for `ambiguous_fail_safe`-class reasons. No new verdict semantics are introduced.
- Q: Wait-semantics exception (requirement 4) — what is the criterion? → A: Do NOT short-circuit when the step is time-dependent, defined as any of: (a) the previous iteration's planned action was a wait-type action (`action_type == "wait"` or `micro_action_purpose == "wait"`); (b) the step's verification spec declares an explicit `timeout_seconds` (the author has stated the expected state may take time to appear, so an unchanged frame now does not imply an unchanged frame within budget). Rationale: in both cases the passage of time alone can change the next observation or its interpretation, so a re-plan on a visually identical frame can still produce a different, useful decision (e.g., keep waiting vs. act).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No wasted planner calls on a frozen screen with a blocked action (Priority: P1)

A test run reaches a step where the screen has stopped changing and the previous round's proposed action was rejected by the repeat guard (the same non-idempotent action must not be re-sent while its effect is pending or ambiguous). In subsequent rounds the system recognizes that nothing new can come out of asking the planner again on the identical screen, skips the planner call entirely, and proceeds directly to the existing verdict/recovery path for that round.

**Why this priority**: This is the core waste eliminated by the feature — each avoided call saves 4–5 seconds of cloud VLM latency and its cost, per iteration, in a situation that provably cannot produce a new outcome. It also implements design doc §21.3 ("do not re-call the Planner when the page has not changed") and the Constitution's resource constraint ("页面未变化不重复调用 Planner").

**Independent Test**: Drive a step with a static screen after one executed action, weak verification, and a non-idempotent action so the repeat guard blocks round 2; assert round 3+ makes no planner call while the step still terminates by budget.

**Acceptance Scenarios**:

1. **Given** iteration N-1's repeat-guard decision was `allowed=false` with reason `blocked_effect_pending` (or its normalized-target variant, or `ambiguous_fail_safe`), **When** iteration N's observation frame has the same content identity as iteration N-1's observation frame, **Then** iteration N makes no planner model call and proceeds directly to the verdict/recovery path.
2. **Given** the same setup, **When** iteration N's observation frame differs from iteration N-1's, **Then** the planner IS called normally.
3. **Given** iteration N-1's repeat-guard decision allowed the action (any allowed reason), **When** iteration N observes an identical frame, **Then** the planner IS called normally (the previous round executed something; a fresh plan may legitimately differ).

---

### User Story 2 - Short-circuited rounds still terminate the step by budget (Priority: P1)

When rounds are short-circuited on a frozen screen, the operator still sees the step finish deterministically: every short-circuited round consumes one iteration from the step budget exactly like a normal round, recovery escalation runs under its own configured caps, and the step ends in failure (or recovery success) within the same bounds as before the feature.

**Why this priority**: A short-circuit that loops forever or bypasses budget accounting would violate the "no infinite retry paths" gate; safety of the optimization is as important as the optimization.

**Independent Test**: Same scenario as Story 1 with `max_retries=N`; assert total iterations recorded is exactly N+1 and the step's final status is `failed` with the pre-existing budget-exhausted semantics.

**Acceptance Scenarios**:

1. **Given** a step whose remaining rounds all short-circuit, **When** the budget is exhausted, **Then** the step fails with the same failure semantics as today (no new terminal states, no extra iterations).
2. **Given** a short-circuited round whose carried blocked reason is `ambiguous_fail_safe`, **When** the round runs, **Then** recovery handling is invoked under its existing per-failure-type caps (a recovery strategy may change the screen and thereby end the short-circuit chain on the next round).

---

### User Story 3 - Skipped rounds are fully observable (Priority: P2)

A test author reviewing the run report or telemetry can see, for every short-circuited round: that the planner was skipped, why (`duplicate_frame_blocked_action`), and that the planner model-call counters did not grow, while a dedicated skipped-call counter did.

**Why this priority**: Telemetry is how this feature was diagnosed in the first place; an invisible optimization would make future diagnosis of planner behavior impossible and would violate the observability constraints.

**Independent Test**: Run the Story 1 scenario and inspect the run record/report: the skipped iteration carries the skip marker, `model_calls.planner` equals the number of non-skipped planning rounds, and the skipped-model-call count equals the number of short-circuited rounds.

**Acceptance Scenarios**:

1. **Given** a short-circuited round, **When** the run record and JSON report are produced, **Then** the iteration record carries `planner_skipped_reason = "duplicate_frame_blocked_action"` and non-skipped iterations carry a null marker.
2. **Given** a short-circuited round, **When** telemetry counters are derived, **Then** no planner `model_call` event exists for that round; instead one `model_call_skipped` event (role planner, reason `duplicate_frame_blocked_action`) and one skipped-outcome model-call audit record exist.

---

### User Story 4 - Time-dependent steps are never short-circuited (Priority: P2)

A test author writing a step that legitimately waits for a slow UI (an explicit verification timeout, or a planner-issued wait action) still gets a fresh planner decision each round, even when consecutive observations look identical — because for such steps an unchanged frame is expected, not evidence of a dead end.

**Why this priority**: Prevents the optimization from breaking a legitimate class of test steps; correctness exception to the P1 behavior.

**Independent Test**: Run the Story 1 scenario but with `timeout_seconds` declared on the step's verification spec; assert every round calls the planner.

**Acceptance Scenarios**:

1. **Given** a step whose verification spec declares `timeout_seconds`, **When** an identical frame follows a blocked round, **Then** the planner IS called.
2. **Given** the previous iteration's planned action was a wait-type action, **When** the current frame is identical, **Then** the planner IS called.

---

### Edge Cases

- **Chained skips**: after a short-circuited round, the next round may observe yet another identical frame. The short-circuited round carries forward the blocking decision (marked as carried), so the chain keeps short-circuiting until the frame changes, recovery changes the screen, or the budget ends. Without carry-forward, only every other round would be skipped.
- **Missing content hash** (capture optimization error path): either round's hash being null disables the short-circuit for that round — fail open to the normal (more expensive, safer) path.
- **First iteration of a step**: never short-circuited (no previous iteration).
- **Author-declared batch-repeat steps** (Feature 005): those steps never call the planner at all; the short-circuit logic does not apply and must not interfere with the batch bypass path.
- **VNC reconnect / capture session rotation**: rotation clears the dedup baseline, so hashes remain comparable only within a session; if a reconnect produced a new identical-looking frame, hash equality still holds only if pixel content is truly identical — acceptable, since the blocked-previous-round condition must also hold.
- **Precondition evaluation round**: precondition failure short-circuits the whole step before planning today; unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The step iteration loop MUST skip the planner invocation for an iteration when ALL of the following hold: (a) a previous iteration exists in the current step; (b) that previous iteration's repeat-guard decision (own or carried) has `allowed=false` with reason in {`blocked_effect_pending`, `blocked_effect_pending_normalized_target`, `ambiguous_fail_safe`}; (c) the current observation's content hash and the previous iteration's observation content hash are both non-null and equal; (d) no exception in FR-006 applies; (e) the step is not an author-declared batch-repeat step (which has no planner call to skip).
- **FR-002**: A short-circuited iteration MUST proceed through the same verdict path as an in-iteration repeat-guard block does today: carry the previous iteration's action effect (or the `effect_uncertain` fallback), resolve the step result with escalation against the current observation, and record the result on the iteration.
- **FR-003**: When the carried blocked reason is `ambiguous_fail_safe` (or `dangerous_drift`, defensively), a short-circuited iteration MUST route the same recovery handling as the in-iteration block path, under the recovery engine's existing per-failure-type caps.
- **FR-004**: A short-circuited iteration MUST consume exactly one unit of the step iteration budget via the existing controller, and MUST introduce no new loop: with a permanently frozen screen and blocked action, the step MUST terminate with the same budget-exhausted failure semantics as today.
- **FR-005**: A short-circuited iteration MUST carry forward the previous iteration's blocking repeat-guard decision onto its own record (so chained identical frames keep short-circuiting), and this carried decision MUST be distinguishable from a decision the guard actually made this round by the presence of the skip marker (FR-007). Conversely, short-circuited iterations MUST be transparent to the repeat guard when a later round does re-plan: the guard compares the fresh proposal against the most recent round that actually carried a proposal, preserving pre-feature comparison semantics exactly.
- **FR-006** (exceptions — never short-circuit): (a) the previous iteration's planned action is wait-type (`action_type == "wait"` or `micro_action_purpose == "wait"`); (b) the step's verification spec declares `timeout_seconds`. Rationale recorded in Clarifications: in both cases time alone can change the next observation or its interpretation, so a re-plan on an identical frame retains information value.
- **FR-007**: Every short-circuited iteration MUST record `planner_skipped_reason = "duplicate_frame_blocked_action"` on its iteration record, and this field MUST appear in the JSON report's iteration output (null for normal iterations).
- **FR-008**: A short-circuited iteration MUST NOT emit a planner `model_call` counter event, planner stage measurement, or actual-outcome planner audit record — the derived `model_calls.planner` count MUST NOT grow. Instead it MUST emit exactly one `model_call_skipped` counter event (`model_role="planner"`, `reason="duplicate_frame_blocked_action"`, with a request identity reference) and one model-call audit record with `outcome="skipped"` and the same reason, so `skipped_model_call_count` grows by one per skipped round.
- **FR-009**: Observation content identity MUST be recorded per iteration (from the observation frame's content hash) so the FR-001(c) comparison never depends on transient runtime state that a report consumer cannot see.
- **FR-010**: The change MUST be confined to the runtime step-iteration layer, its telemetry/report surfaces, and additive iteration-record fields. It MUST NOT alter `verification/business_resolver.py`, `perception/cache.py`, `perception/ocr/`, the repeat guard's decision logic, or the capture/dedup layer (owned by parallel features).

### Key Entities

- **ActionIteration (extended)**: gains `planner_skipped_reason` (nullable string; the skip marker) and `before_content_hash` (nullable string; the observation frame's content identity for this iteration). Both additive, defaulting to null — no existing consumer changes meaning.
- **Skip decision**: an internal predicate over (current observation, previous iteration record, step declaration) producing either "skip with reason" or "plan normally"; it never mutates state.
- **Carried RepeatGuardDecision**: a copy of the previous round's blocking decision attached to a short-circuited iteration; distinguishable via the skip marker.
- **`model_call_skipped` counter event / skipped-outcome ModelCallAudit**: pre-existing telemetry kinds (defined but previously unused for the planner) now emitted by the short-circuit.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the reproduced incident scenario (frozen screen + blocked non-idempotent action, budget ≥ 3 iterations), planner invocations per step drop from one-per-iteration to at most 2 (the initial plan and the one re-plan that got blocked); every further iteration in the chain is skipped.
- **SC-002**: Each skipped iteration removes one full planner round-trip (~4–5 s cloud latency in the diagnosed run) from the step's wall-clock time; no other stage gets slower.
- **SC-003**: Step outcomes are unchanged for every existing regression scenario: the full offline test suite passes without modification to any existing assertion.
- **SC-004**: 100% of skipped iterations are identifiable in both the run record and the JSON report by their skip marker, and conservation holds: actual planner calls + skipped planner rounds = planning rounds attempted.
- **SC-005**: Time-dependent steps (explicit verification timeout or wait-type previous action) show zero behavior change: every round still gets a planner decision.

## Assumptions

- The pixel-content hash produced by the capture layer is a trustworthy identity for "the page has not changed" at the fidelity the planner sees; two frames with equal hashes never carry different planner-relevant information.
- Planner prompt inputs that vary per iteration (iteration index, remaining budget) do not make a re-plan on an identical frame with a still-blocked action worthwhile — the design doc's §21.3 rule ("do not re-call the Planner when the page has not changed") takes precedence over the marginal chance that budget-awareness changes the plan. Recorded as an accepted trade-off.
- Recovery strategies remain the sanctioned mechanism for breaking a frozen-screen deadlock; the short-circuit intentionally does not add a new "force re-observe" mechanism of its own.
- The step-level verdict path invoked on the block/skip route may itself perform verification model calls; those are verification-role calls governed by existing rules and are out of scope here (only the planner call is skipped).
