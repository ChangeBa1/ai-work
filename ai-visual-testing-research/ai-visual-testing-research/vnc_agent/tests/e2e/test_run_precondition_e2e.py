"""Declarative run-precondition fail-closed gate before the first input event
(Feature 003 T020, FR-025, SC-008). Replaces test_start_state_precondition.py
— generic named facts instead of fixed cart_items/cart_amount fields."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.e2e.conftest import FakeVNC, build_runtime
from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.domain.run import DeclaredFact, RunPrecondition
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.planner_client import StubPlanner


class Screens:
    def __init__(self, screens):
        self.screens = screens
        self.index = 0

    async def observe(self, **_kwargs):
        value = self.screens[min(self.index, len(self.screens) - 1)]
        self.index += 1
        return value


def _screen(texts: list[str], *, changed: bool = False) -> StructuredScreen:
    return StructuredScreen(
        frame_id="start",
        resolution=(300, 200),
        captured_at=datetime.now(UTC),
        changed_since_last=changed,
        ocr_items=[
            OCRItem(text=text, bbox=(i * 50, 0, i * 50 + 40, 20), confidence=0.99)
            for i, text in enumerate(texts)
        ],
    )


def _precondition() -> RunPrecondition:
    return RunPrecondition(
        facts=[
            DeclaredFact(
                key="example_state",
                spec=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="text_appears", value="ready")],
                ),
            )
        ]
    )


def _case(*, with_precondition: bool) -> TestCase:
    return TestCase(
        id="precondition-gate",
        name="precondition-gate",
        target_id="win10-test-01",
        mode="explicit",
        precondition=_precondition() if with_precondition else None,
        steps=[
            TestStep(
                id="safe",
                name="safe",
                intent="press escape",
                verification_mode="effect_only",
                expected=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="screen_changed")],
                ),
            )
        ],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("texts", "expected_status", "expected_keys"),
    [
        (["ready"], "passed", 1),
        (["busy"], "failed", 0),
    ],
)
async def test_declarative_precondition_gate(
    tmp_path: Path,
    app_config,
    texts,
    expected_status,
    expected_keys,
) -> None:
    driver = FakeVNC()
    planner = StubPlanner(
        action=SemanticAction(
            action_id="safe",
            intent="press escape",
            action_type="press_key",
            keys=["escape"],
            action_kind="idempotent",
        )
    )
    runtime, _ = await build_runtime(tmp_path, app_config, driver=driver, planner=planner)
    runtime.pipeline = Screens([_screen(texts), _screen(texts + ["done"], changed=True)])
    ctx = await runtime.run(_case(with_precondition=True))

    assert ctx.test_run.precondition_evaluation.status == expected_status
    assert len(driver.keys) == expected_keys
    if expected_status == "failed":
        assert ctx.test_run.status == "failed"
        assert all(
            iteration.execution_result is None
            for step in ctx.test_run.steps
            for iteration in step.iterations
        )


@pytest.mark.asyncio
async def test_no_declared_precondition_is_not_required(tmp_path: Path, app_config) -> None:
    driver = FakeVNC()
    planner = StubPlanner(
        action=SemanticAction(
            action_id="safe",
            intent="press escape",
            action_type="press_key",
            keys=["escape"],
            action_kind="idempotent",
        )
    )
    runtime, _ = await build_runtime(tmp_path, app_config, driver=driver, planner=planner)
    runtime.pipeline = Screens([_screen(["anything"]), _screen(["anything", "done"], changed=True)])
    ctx = await runtime.run(_case(with_precondition=False))

    assert ctx.test_run.precondition_evaluation.status == "not_required"
    assert len(driver.keys) == 1
