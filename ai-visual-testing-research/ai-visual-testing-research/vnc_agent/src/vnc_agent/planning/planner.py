"""Planner orchestration — task_completed_hint is advisory only."""

from __future__ import annotations

from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.testcase import TestStep
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.models.provider import PlannerProvider, PlannerRequest, PlannerResponse
from vnc_agent.planning.plan_validator import PlanValidator
from vnc_agent.runtime.exceptions import PlanValidationError


class PlannerOrchestrator:
    def __init__(
        self,
        provider: PlannerProvider,
        validator: PlanValidator | None = None,
    ) -> None:
        self.provider = provider
        self.validator = validator or PlanValidator()

    async def plan(
        self,
        step: TestStep,
        screen: StructuredScreen,
        *,
        iteration_index: int,
        remaining_budget: int,
        previous_verification: VerificationResult | None = None,
    ) -> PlannerResponse:
        request = PlannerRequest(
            step_intent=step.intent,
            expected=step.expected,
            structured_screen=screen,
            iteration_index=iteration_index,
            remaining_iteration_budget=remaining_budget,
            previous_verification_result=previous_verification,
        )
        last_err: Exception | None = None
        for _ in range(2):
            try:
                raw = await self.provider.plan(request)
                return self.validator.validate(raw)
            except PlanValidationError as e:
                last_err = e
                if self.validator.exhausted_invalid():
                    break
        raise PlanValidationError(
            f"consecutive invalid planner responses: {last_err}"
        )
