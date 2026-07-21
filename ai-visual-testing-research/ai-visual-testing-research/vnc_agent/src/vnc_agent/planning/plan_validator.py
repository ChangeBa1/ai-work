"""Planner response four-layer validation (contracts/model-provider-contract.md)."""

from __future__ import annotations

from typing import Any

from vnc_agent.domain.action import ActionType, SemanticAction
from vnc_agent.models.provider import PlannerResponse
from vnc_agent.models.response_parser import parse_planner_response
from vnc_agent.runtime.exceptions import PlanValidationError

ALLOWED_ACTION_TYPES: frozenset[str] = frozenset(
    {
        "click",
        "double_click",
        "right_click",
        "type_text",
        "press_key",
        "hotkey",
        "scroll",
        "drag",
        "wait",
        "finish",
    }
)

ALLOWED_RISK = frozenset({"low"})


class PlanValidator:
    def __init__(self, *, max_invalid: int = 2) -> None:
        self.max_invalid = max_invalid
        self.consecutive_invalid = 0

    def reset(self) -> None:
        self.consecutive_invalid = 0

    def validate(self, raw: str | dict[str, Any] | PlannerResponse) -> PlannerResponse:
        try:
            if isinstance(raw, PlannerResponse):
                resp = raw
            else:
                resp = parse_planner_response(raw)
            self._whitelist(resp.semantic_action)
            self._risk(resp.semantic_action)
            self.consecutive_invalid = 0
            return resp
        except Exception as e:
            self.consecutive_invalid += 1
            raise PlanValidationError(str(e)) from e

    def exhausted_invalid(self) -> bool:
        return self.consecutive_invalid >= self.max_invalid

    def _whitelist(self, action: SemanticAction) -> None:
        if action.action_type not in ALLOWED_ACTION_TYPES:
            raise PlanValidationError(
                f"action_type {action.action_type!r} not in whitelist"
            )
        # Type-level already forbids coords; double-check dump
        dumped = action.model_dump()
        for forbidden in ("x", "y", "coordinates", "point"):
            if forbidden in dumped:
                raise PlanValidationError(f"coordinate field forbidden: {forbidden}")

    def _risk(self, action: SemanticAction) -> None:
        if action.risk_level not in ALLOWED_RISK:
            raise PlanValidationError(
                f"risk_level {action.risk_level!r} not allowed in this slice"
            )
