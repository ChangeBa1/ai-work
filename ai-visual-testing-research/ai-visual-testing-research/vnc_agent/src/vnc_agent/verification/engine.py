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
from vnc_agent.verification.visual_verifier import verify_visual_question

if TYPE_CHECKING:
    from vnc_agent.models.provider import PlannerProvider


class VerificationEngine:
    def __init__(self, planner: PlannerProvider | None = None) -> None:
        self.planner = planner

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
            return await verify_visual_question(cond, screen, self.planner)
        return "uncertain", f"unknown condition type {t}"
