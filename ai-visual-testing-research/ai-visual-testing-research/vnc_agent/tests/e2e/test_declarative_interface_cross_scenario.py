"""Feature 003 T051 (/speckit-converge): a second, unrelated end-to-end
scenario proving the declarative precondition/action-tag PUBLIC INTERFACE
(TestCase.precondition/action_tags loaded via load_test_case(), executed via
AgentRuntime.run(), reported via build_report_dict()) — not just the
underlying Python functions — independent of the POS fixture
(test_scenario_15_pos_bag_business_acceptance.py), which was previously the
only end-to-end proof of this interface (FR-024~028, Constitution v1.1.0
Principle VI ≥2-unrelated-scenario requirement)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.e2e.conftest import FakeVNC, build_runtime
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.domain.testcase import load_test_case
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.models.provider import PlannerRequest, PlannerResponse
from vnc_agent.reporting.json_report import build_report_dict

FIXTURE_CASE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "testcases"
    / "generic-declarative-interface-example.yaml"
)


class StepPlanner(StubPlanner):
    async def plan(self, request: PlannerRequest) -> PlannerResponse:
        self.plan_calls += 1
        if "escape" in request.step_intent:
            action = SemanticAction(
                action_id="confirm-default",
                intent=request.step_intent,
                action_type="press_key",
                keys=["escape"],
                action_kind="idempotent",
            )
        else:
            action = SemanticAction(
                action_id="open-panel",
                intent=request.step_intent,
                action_type="click",
                target=TargetDescription(role="button", text="Open"),
                action_kind="idempotent",
            )
        return PlannerResponse(semantic_action=action)


class ScriptedPipeline:
    def __init__(self, screens: list[StructuredScreen]) -> None:
        self.screens = screens
        self.index = 0

    async def observe(self, **_kwargs) -> StructuredScreen:
        screen = self.screens[min(self.index, len(self.screens) - 1)]
        self.index += 1
        return screen


def _screen(texts: list[str], *, changed: bool) -> StructuredScreen:
    return StructuredScreen(
        frame_id="frame",
        resolution=(300, 200),
        captured_at=datetime.now(UTC),
        changed_since_last=changed,
        ocr_items=[
            OCRItem(text=t, bbox=(i * 50, 0, i * 50 + 40, 20), confidence=0.99)
            for i, t in enumerate(texts)
        ],
    )


@pytest.mark.asyncio
async def test_declarative_interface_end_to_end_on_a_non_pos_scenario(
    tmp_path: Path, app_config
) -> None:
    case = load_test_case(FIXTURE_CASE)
    assert case.precondition is not None
    assert case.action_tags

    screens = [
        _screen(["ready"], changed=False),  # step1 before + precondition source
        _screen(["ready", "open"], changed=True),  # step1 after
        _screen(["ready", "open"], changed=False),  # step2 before
        _screen(["ready", "open", "confirmed"], changed=True),  # step2 after
    ]

    driver = FakeVNC()
    runtime, _ = await build_runtime(tmp_path, app_config, driver=driver, planner=StepPlanner())
    runtime.pipeline = ScriptedPipeline(screens)  # type: ignore[assignment]

    ctx = await runtime.run(case)

    assert ctx.test_run.status == "passed"
    assert ctx.test_run.precondition_evaluation.status == "passed"
    assert ctx.test_run.precondition_evaluation.fact_evaluations[0].key == "panel_state"

    report = build_report_dict(ctx.test_run, action_tags=case.action_tags)
    assert report["precondition_evaluation"]["status"] == "passed"
    assert report["declared_tag_counts"] == {"primary_action": 1, "keyboard_action": 1}
    assert len(report["executed_action_log"]) == 2
