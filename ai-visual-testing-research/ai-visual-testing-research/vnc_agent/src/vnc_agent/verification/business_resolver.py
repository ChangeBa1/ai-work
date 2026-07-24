"""StepVerificationResult resolver — independent of ActionEffect (FR-001, data-model.md §4)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal

from vnc_agent.domain.action_effect import ActionEffect
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.run import FactEvaluation, PreconditionEvaluation, RunPrecondition
from vnc_agent.domain.verification import (
    VerificationResult,
    VerificationSpec,
    VerificationStatus,
    aggregate_conditions,
)
from vnc_agent.models.provider import PlannerProvider, VisionUnderstandingRequest
from vnc_agent.verification.engine import VerificationEngine

WEAK_TYPES = frozenset({"screen_changed", "region_changed"})
Basis = Literal["business_assertion", "action_effect_only", "mixed"]


async def evaluate_precondition(
    precondition: RunPrecondition | None,
    first_observed_screen: StructuredScreen,
    engine: VerificationEngine,
) -> PreconditionEvaluation:
    """Feature 003 (FR-024/025/026): evaluate a testcase's declared run-start
    facts against the first independently observed screen. No business-
    specific extraction — each fact's `spec` is evaluated with the exact same
    VerificationEngine used for step-level business assertions."""
    if precondition is None or not precondition.facts:
        return PreconditionEvaluation(status="not_required", fact_evaluations=[], checked_at=None)

    fact_evaluations: list[FactEvaluation] = []
    for fact in precondition.facts:
        result = await engine.verify(fact.spec, first_observed_screen)
        fact_evaluations.append(FactEvaluation(key=fact.key, result=result))

    status: Literal["passed", "failed"] = (
        "passed"
        if all(fe.result.status == "passed" for fe in fact_evaluations)
        else "failed"
    )
    return PreconditionEvaluation(
        status=status,
        fact_evaluations=fact_evaluations,
        checked_at=datetime.now(UTC),
    )


def _has_business_assertion(spec: VerificationSpec) -> bool:
    return any(c.type not in WEAK_TYPES for c in spec.conditions)


def _has_weak_only(spec: VerificationSpec) -> bool:
    return all(c.type in WEAK_TYPES for c in spec.conditions)


def _has_visual_question(spec: VerificationSpec) -> bool:
    return any(c.type == "visual_question" for c in spec.conditions)


def _has_deterministic_business(spec: VerificationSpec) -> bool:
    return any(
        c.type not in WEAK_TYPES and c.type != "visual_question"
        for c in spec.conditions
    )


def _partition_statuses(
    engine_result: VerificationResult,
    spec: VerificationSpec,
) -> tuple[list[VerificationStatus], list[VerificationStatus]]:
    """Map engine labels back to deterministic vs visual buckets by condition order."""
    det: list[VerificationStatus] = []
    vis: list[VerificationStatus] = []
    # Rebuild per-condition status from matched/failed/uncertain labels is brittle;
    # re-derive using condition type + presence in lists.
    for i, cond in enumerate(spec.conditions):
        label = f"{cond.type}:{cond.value or i}"
        if label in engine_result.matched_conditions:
            st: VerificationStatus = "passed"
        elif label in engine_result.failed_conditions:
            st = "failed"
        elif label in engine_result.uncertain_conditions:
            st = "uncertain"
        else:
            # Fallback: use overall if single condition
            st = engine_result.status
        if cond.type == "visual_question":
            vis.append(st)
        elif cond.type not in WEAK_TYPES:
            det.append(st)
    return det, vis


def _deterministic_wins(
    det: list[VerificationStatus],
    vis: list[VerificationStatus],
    fallback: VerificationStatus,
) -> VerificationStatus | None:
    """
    FR-010/SC-010: when deterministic and visual disagree, deterministic wins.
    Returns None if no decisive conflict rule applies.
    """
    if not det or not vis:
        return None
    det_agg = aggregate_conditions("all", det) if len(det) > 1 else det[0]
    vis_agg = aggregate_conditions("all", vis) if len(vis) > 1 else vis[0]
    if det_agg in ("passed", "failed") and vis_agg in ("passed", "failed", "uncertain"):
        if det_agg != vis_agg:
            return det_agg
        return det_agg
    if det_agg in ("passed", "failed"):
        return det_agg
    return None


async def resolve_step_result(
    spec: VerificationSpec,
    verification_mode: Literal["business", "effect_only"] | None,
    action_effect: ActionEffect,
    screen: StructuredScreen,
    *,
    planner: PlannerProvider | None = None,
    reobserve: Callable[[], Awaitable[StructuredScreen]] | None = None,
    engine: VerificationEngine | None = None,
    escalate: bool = True,
) -> VerificationResult:
    """
    Combine VerificationEngine condition eval with ActionEffect + verification_mode
    into the authoritative StepVerificationResult (data-model.md §4 table).

    MUST NOT emit ExecutableAction. Escalation: at most one reobserve + one optional
    describe_screen visual fallback per call (contracts §2).
    """
    ver = engine or VerificationEngine(planner)
    evidence_refs = [screen.image_path] if screen.image_path else []

    engine_result = await ver.verify(spec, screen, evidence_refs=evidence_refs)
    reobserve_calls = 0
    describe_calls = 0

    async def _maybe_escalate(current: VerificationResult) -> VerificationResult:
        nonlocal reobserve_calls, describe_calls, screen, engine_result
        if not escalate or current.status != "uncertain":
            return current
        if reobserve is not None and reobserve_calls == 0:
            reobserve_calls += 1
            screen = await reobserve()
            # Re-evaluate only non-visual conditions to avoid extra describe_screen
            # (visual_question already ran in the initial verify; escalation may
            # add one optional describe_screen below).
            det_conditions = [
                c for c in spec.conditions if c.type != "visual_question"
            ]
            if det_conditions:
                from vnc_agent.domain.verification import VerificationSpec as VS

                det_spec = VS(operator=spec.operator, conditions=det_conditions)
                engine_result = await ver.verify(
                    det_spec,
                    screen,
                    evidence_refs=evidence_refs
                    + ([screen.image_path] if screen.image_path else []),
                )
                if engine_result.status != "uncertain":
                    return engine_result
            # If only visual_question conditions, skip re-verify (escalation
            # describe_screen below covers the single optional model call)
        # Optional visual-model fallback once (not a loop)
        if planner is not None and describe_calls == 0 and current.status == "uncertain":
            describe_calls += 1
            try:
                resp = await planner.describe_screen(
                    VisionUnderstandingRequest(
                        mode="answer_question",
                        image_ref=screen.path_for_model() or screen.image_path or "stub",
                        structured_screen_hint=screen.to_hint_dict(),
                        question="Did the expected business result appear on screen?",
                    )
                )
                visual_answer = resp.answer or "uncertain"
                det, _vis = _partition_statuses(engine_result, spec)
                # Deterministic conclusive result always wins over visual (FR-010)
                if det and any(s in ("passed", "failed") for s in det):
                    det_agg = (
                        "failed"
                        if any(s == "failed" for s in det)
                        else "passed"
                    )
                    return engine_result.model_copy(
                        update={
                            "status": det_agg,
                            "reason": (
                                f"{engine_result.reason}; "
                                f"deterministic_overrides_visual={visual_answer}"
                            ),
                        }
                    )
                if visual_answer in ("passed", "failed", "uncertain"):
                    return VerificationResult(
                        status=visual_answer,
                        evidence_refs=engine_result.evidence_refs,
                        matched_conditions=engine_result.matched_conditions,
                        failed_conditions=engine_result.failed_conditions,
                        uncertain_conditions=(
                            []
                            if visual_answer != "uncertain"
                            else engine_result.uncertain_conditions
                        ),
                        reason=f"visual fallback: {resp.reason or visual_answer}",
                        weak_assertion_warning=False,
                        basis="business_assertion",
                    )
            except Exception as e:  # noqa: BLE001 — visual is optional fallback
                engine_result = engine_result.model_copy(
                    update={"reason": f"{engine_result.reason}; visual error: {e}"}
                )
        return engine_result

    has_business = _has_business_assertion(spec)
    weak_only = _has_weak_only(spec)
    ae_status = action_effect.status

    # --- Apply deterministic-over-visual conflict rule (FR-010) ---
    det, vis = _partition_statuses(engine_result, spec)
    conflict = _deterministic_wins(det, vis, engine_result.status)
    if conflict is not None and det and vis:
        engine_result = engine_result.model_copy(
            update={
                "status": conflict,
                "reason": (
                    f"{engine_result.reason}; deterministic_overrides_visual "
                    f"(det={det}, vis={vis})"
                ),
            }
        )

    # Business assertions present (rows 1–3)
    if has_business:
        # unexpected_effect does NOT blanket-reject when real business assertion matches
        # (FR-021): still evaluate assertion. Only weak evidence is blocked.
        if engine_result.status == "uncertain" and ae_status != "no_effect":
            engine_result = await _maybe_escalate(engine_result)
            det2, vis2 = _partition_statuses(engine_result, spec)
            conflict2 = _deterministic_wins(det2, vis2, engine_result.status)
            if conflict2 is not None and det2 and vis2:
                engine_result = engine_result.model_copy(
                    update={"status": conflict2}
                )

        # Feature 004 FR-021 / regression guard: when the action produced no
        # pixel change, text/visual matches against the *unchanged* screen are
        # not trusted as evidence that the action achieved the business result
        # (empty POS chrome commonly contains digits like "1"/"5" and button
        # labels like "袋"). Reject so Tier-1 retry / action_no_effect recovery
        # can run. unexpected_effect still follows FR-021 (feature 002) and is
        # not blanket-rejected here.
        if ae_status == "no_effect" and engine_result.status == "passed":
            failed = list(engine_result.failed_conditions)
            if "no_effect" not in failed:
                failed.append("no_effect")
            return VerificationResult(
                status="failed",
                evidence_refs=engine_result.evidence_refs,
                matched_conditions=engine_result.matched_conditions,
                failed_conditions=failed,
                uncertain_conditions=[],
                reason=(
                    "action produced no screen change (no_effect); "
                    "business assertions matching the unchanged screen are not trusted"
                ),
                weak_assertion_warning=False,
                basis="mixed",
            )

        status = engine_result.status
        # If only weak parts "passed" but business failed → failed already from engine
        basis: Basis = (
            "mixed"
            if any(c.type in WEAK_TYPES for c in spec.conditions)
            else "business_assertion"
        )
        return VerificationResult(
            status=status,
            evidence_refs=engine_result.evidence_refs,
            matched_conditions=engine_result.matched_conditions,
            failed_conditions=engine_result.failed_conditions,
            uncertain_conditions=engine_result.uncertain_conditions,
            reason=engine_result.reason,
            weak_assertion_warning=False,
            basis=basis,
        )

    # Weak-evidence-only paths
    effect_supports_pass = ae_status == "expected_effect" or (
        engine_result.status == "passed" and ae_status != "unexpected_effect"
    )

    # unexpected_effect never lets weak-only steps pass (FR-020)
    if ae_status == "unexpected_effect":
        return VerificationResult(
            status="failed",
            evidence_refs=engine_result.evidence_refs,
            matched_conditions=engine_result.matched_conditions,
            failed_conditions=engine_result.failed_conditions
            or ["unexpected_effect"],
            uncertain_conditions=[],
            reason="unexpected_effect (error popup) — weak evidence cannot pass",
            weak_assertion_warning=verification_mode != "effect_only",
            basis="action_effect_only",
        )

    if verification_mode == "effect_only":
        # Row 4: effect_only may pass on action effect alone
        if effect_supports_pass or engine_result.status == "passed":
            return VerificationResult(
                status="passed",
                evidence_refs=engine_result.evidence_refs,
                matched_conditions=engine_result.matched_conditions,
                failed_conditions=[],
                uncertain_conditions=[],
                reason="action effect only, not a verified business result",
                weak_assertion_warning=False,
                basis="action_effect_only",
            )
        if ae_status == "no_effect":
            return VerificationResult(
                status="failed",
                evidence_refs=engine_result.evidence_refs,
                matched_conditions=[],
                failed_conditions=["no_effect"],
                uncertain_conditions=[],
                reason="effect_only step: no action effect observed",
                weak_assertion_warning=False,
                basis="action_effect_only",
            )
        return VerificationResult(
            status="uncertain",
            evidence_refs=engine_result.evidence_refs,
            matched_conditions=engine_result.matched_conditions,
            failed_conditions=engine_result.failed_conditions,
            uncertain_conditions=engine_result.uncertain_conditions,
            reason="effect_only step: effect uncertain",
            weak_assertion_warning=False,
            basis="action_effect_only",
        )

    # Row 5: omitted / business default with only weak evidence → cap at uncertain
    if weak_only:
        return VerificationResult(
            status="uncertain",
            evidence_refs=engine_result.evidence_refs,
            matched_conditions=engine_result.matched_conditions,
            failed_conditions=engine_result.failed_conditions,
            uncertain_conditions=engine_result.uncertain_conditions
            or ["weak_assertion_only"],
            reason=(
                "仅凭 screen_changed 证据判定，业务结果未经验证 "
                f"(action_effect={ae_status})"
            ),
            weak_assertion_warning=True,
            basis="action_effect_only",
        )

    # Fallback
    return VerificationResult(
        status=engine_result.status,
        evidence_refs=engine_result.evidence_refs,
        matched_conditions=engine_result.matched_conditions,
        failed_conditions=engine_result.failed_conditions,
        uncertain_conditions=engine_result.uncertain_conditions,
        reason=engine_result.reason,
        weak_assertion_warning=False,
        basis="business_assertion",
    )
