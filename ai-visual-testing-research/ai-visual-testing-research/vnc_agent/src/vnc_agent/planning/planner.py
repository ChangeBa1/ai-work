"""Planner orchestration — task_completed_hint is advisory only."""

from __future__ import annotations

from typing import Any

from vnc_agent.config import UiIndexConfig
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.testcase import TestStep
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.models.provider import PlannerProvider, PlannerRequest, PlannerResponse
from vnc_agent.planning.plan_validator import PlanValidator
from vnc_agent.runtime.exceptions import PlanValidationError
from vnc_agent.ui_index.repository import UiIndexBundle
from vnc_agent.ui_index.runtime_adapter import build_hints


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
        ui_index_bundle: UiIndexBundle | None = None,
        ui_index_config: UiIndexConfig | None = None,
        ui_index_audit_sink: Any | None = None,
    ) -> PlannerResponse:
        hints: list[Any] = []
        cfg = ui_index_config or UiIndexConfig()
        # Call build_hints whenever an explicit bundle is passed (including None
        # via not_configured path only when caller asks). Existing callers omit
        # ui_index_bundle → no behavior change.
        if ui_index_bundle is not None or ui_index_config is not None:
            hints, _candidates, audit = build_hints(ui_index_bundle, screen, cfg)
            if ui_index_audit_sink is not None:
                from vnc_agent.ui_index.audit import record_index_usage

                record_index_usage(ui_index_audit_sink, audit)
        request = PlannerRequest(
            step_intent=step.intent,
            expected=step.expected,
            structured_screen=screen,
            iteration_index=iteration_index,
            remaining_iteration_budget=remaining_budget,
            previous_verification_result=previous_verification,
            ui_index_hints=hints,
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
