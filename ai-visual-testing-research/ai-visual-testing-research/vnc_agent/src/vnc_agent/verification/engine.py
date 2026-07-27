"""Verification engine with all/any aggregation (FR-031~034)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.verification import (
    VerificationCondition,
    VerificationResult,
    VerificationSpec,
    VerificationStatus,
    aggregate_conditions,
)
from vnc_agent.verification import ocr_verifier, screen_change_verifier, template_verifier
from vnc_agent.verification.answer_cache import CachedVisualAnswerer
from vnc_agent.verification.visual_verifier import verify_visual_question

if TYPE_CHECKING:
    from vnc_agent.models.provider import (
        PlannerProvider,
        VisionUnderstandingResponse,
    )


class VerificationEngine:
    def __init__(
        self,
        planner: PlannerProvider | None = None,
        *,
        answerer: CachedVisualAnswerer | None = None,
    ) -> None:
        self.planner = planner
        # Feature 008: shared cached-answer helper for every verification-path
        # answer_question call; the default (no cache) is byte-identical to a
        # direct planner call.
        self.answerer = answerer or CachedVisualAnswerer()

    async def answer_visual_question(
        self,
        screen: StructuredScreen,
        question: str,
        *,
        planner: PlannerProvider | None = None,
    ) -> VisionUnderstandingResponse:
        """Delegate used by business_resolver's escalation fallback so both
        verification call sites share one cache (FR-004)."""
        active = planner or self.planner
        if active is None:
            raise ValueError("no planner available for visual question")
        return await self.answerer.answer(active, screen, question)

    async def verify(
        self,
        spec: VerificationSpec,
        screen: StructuredScreen,
        *,
        evidence_refs: list[str] | None = None,
    ) -> VerificationResult:
        statuses: list[VerificationStatus] = []
        matched: list[str] = []
        failed: list[str] = []
        uncertain: list[str] = []
        reasons: list[str] = []

        for i, cond in enumerate(spec.conditions):
            label = f"{cond.type}:{cond.value or i}"
            status, reason = await self._eval_one(cond, screen)
            statuses.append(status)
            if status == "passed":
                matched.append(label)
            elif status == "failed":
                failed.append(label)
            else:
                uncertain.append(label)
            if reason:
                reasons.append(f"{label}: {reason}")

        overall = aggregate_conditions(spec.operator, statuses)
        refs = list(evidence_refs or [])
        if screen.image_path:
            refs.append(screen.image_path)

        return VerificationResult(
            status=overall,
            evidence_refs=refs,
            matched_conditions=matched,
            failed_conditions=failed,
            uncertain_conditions=uncertain,
            reason="; ".join(reasons) if reasons else overall,
        )

    async def _eval_one(
        self, cond: VerificationCondition, screen: StructuredScreen
    ) -> tuple[VerificationStatus, str]:
        t = cond.type
        if t in ("text_appears", "text_disappears"):
            return ocr_verifier.verify_text(cond, screen), ""
        if t in ("template_appears", "template_disappears"):
            return template_verifier.verify_template(cond, screen), ""
        if t in ("region_changed", "screen_changed"):
            return screen_change_verifier.verify_screen_change(cond, screen), ""
        if t == "visual_question":
            if self.planner is None:
                return "uncertain", "no planner for visual_question"
            return await verify_visual_question(
                cond, screen, self.planner, answerer=self.answerer
            )
        return "uncertain", f"unknown condition type {t}"
