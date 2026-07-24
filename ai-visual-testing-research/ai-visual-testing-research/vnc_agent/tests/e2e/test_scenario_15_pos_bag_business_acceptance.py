"""Offline end-to-end proof for the formal POS bag business case (T039)."""

from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

from tests.e2e.conftest import FakeVNC, build_runtime
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.domain.testcase import load_test_case
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.models.provider import (
    PlannerRequest,
    PlannerResponse,
    VisionUnderstandingResponse,
)
from vnc_agent.reporting.json_report import build_report_dict


class StepPlanner(StubPlanner):
    async def plan(self, request: PlannerRequest) -> PlannerResponse:
        self.plan_calls += 1
        if "預/現計" in request.step_intent:
            action_id, target_text = "cash-start", "預/現計"
        elif "確定" in request.step_intent:
            action_id, target_text = "cash-finalize", "確定"
        elif "小計" in request.step_intent:
            action_id, target_text = "subtotal", "小計"
        else:
            action_id, target_text = "add-bag", "レジ袋"
        return PlannerResponse(
            semantic_action=SemanticAction(
                action_id=action_id,
                intent=request.step_intent,
                action_type="click",
                target=TargetDescription(text=target_text),
                action_kind="non_idempotent",
            )
        )


class ScriptedPipeline:
    def __init__(self, screens: list[StructuredScreen]) -> None:
        self.screens = screens
        self.index = 0

    async def observe(self, **_kwargs) -> StructuredScreen:
        screen = self.screens[min(self.index, len(self.screens) - 1)]
        self.index += 1
        return screen


def _write_frames(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    before = np.zeros((1000, 1000, 3), dtype=np.uint8)
    after_bag = before.copy()
    after_bag.reshape(-1, 3)[:4669] = 255
    after_subtotal = after_bag.copy()
    after_subtotal[200:260, 200:300] = 127
    after_cash_start = after_subtotal.copy()
    after_cash_start[300:360, 300:400] = 191
    after_cash_finalize = after_cash_start.copy()
    after_cash_finalize[400:460, 400:500] = 63
    paths = tuple(
        tmp_path / name
        for name in ("before.png", "bag.png", "subtotal.png", "cash.png", "fixed.png")
    )
    images = (before, after_bag, after_subtotal, after_cash_start, after_cash_finalize)
    for path, image in zip(paths, images, strict=True):
        assert cv2.imwrite(str(path), image)
    return paths  # type: ignore[return-value]


def _screen(path: Path, texts: list[str], changed: bool) -> StructuredScreen:
    return StructuredScreen(
        frame_id=path.stem,
        resolution=(1000, 1000),
        captured_at=datetime.now(UTC),
        image_path=str(path),
        changed_since_last=changed,
        global_diff_ratio=0.004669 if path.stem == "bag" else 0.01,
        ocr_items=[
            OCRItem(text=text, bbox=(10, i * 30, 100, i * 30 + 20), confidence=0.9)
            for i, text in enumerate(texts)
        ],
    )


@pytest.mark.asyncio
async def test_pos_bag_business_acceptance_and_low_ratio_expected_effect(
    tmp_path: Path, app_config
) -> None:
    before, bag, subtotal, cash, fixed = _write_frames(tmp_path)
    bag_texts = ["レジ袋", "5", "点数", "1", "内税10%", "1個"]
    screens = [
        _screen(before, ["0"], False),
        _screen(bag, bag_texts, True),
        _screen(bag, bag_texts, False),
        _screen(subtotal, ["不足額"], True),
        _screen(subtotal, ["不足額"], False),
        _screen(cash, ["預り金", "10,000", "お釣り", "9,995", "確定"], True),
        _screen(cash, ["預り金", "10,000", "お釣り", "9,995", "確定"], False),
        _screen(fixed, ["済"], True),
    ]
    driver = FakeVNC()
    runtime, _ = await build_runtime(
        tmp_path,
        app_config,
        driver=driver,
        planner=StepPlanner(
            answer=VisionUnderstandingResponse(
                mode="answer_question",
                answer="passed",
                confidence=1.0,
                reason="fixture confirms the cart count is 0",
                model_name="stub",
            )
        ),
        grounder=StubGrounder(
            GroundingResult(
                found=True,
                candidates=[
                    GroundingCandidate(
                        bbox=(100, 100, 180, 150),
                        coordinate_space="pixel",
                        confidence=0.99,
                    )
                ],
            )
        ),
    )
    runtime.pipeline = ScriptedPipeline(screens)  # type: ignore[assignment]
    case = load_test_case(Path(__file__).parents[2] / "testcases" / "pos-buy-bag-checkout.yaml")

    ctx = await runtime.run(case)

    assert ctx.test_run.status == "passed"
    assert len(driver.clicks) == 4
    assert driver.keys == []
    first, second, third, fourth = ctx.test_run.steps
    assert first.iterations[0].action_effect.status == "expected_effect"
    assert first.iterations[0].action_effect.evidence.global_diff_ratio == pytest.approx(
        0.004669
    )
    assert first.iterations[0].verification_result.status == "passed"
    assert second.iterations[0].verification_result.status == "passed"
    assert third.iterations[0].verification_result.status == "passed"
    assert fourth.iterations[0].verification_result.status == "passed"
    assert all(
        "模拟器" not in (iteration.semantic_action.target.text or "")
        for step in ctx.test_run.steps
        for iteration in step.iterations
        if iteration.semantic_action is not None
    )

    # Feature 003: this scenario uses the exact same generic mechanisms as
    # the other three (unrelated) scenarios — declarative precondition and
    # declarative tag audit — not any bespoke business field or core branch.
    assert ctx.test_run.precondition_evaluation.status == "passed"
    assert ctx.test_run.precondition_evaluation.fact_evaluations[0].key == "cart_item_count"

    report = build_report_dict(ctx.test_run, action_tags=case.action_tags)
    assert report["declared_tag_counts"] == {
        "add_to_bag": 1,
        "subtotal": 1,
        "cash_start": 1,
        "cash_finalize": 1,
    }
    assert report["precondition_evaluation"]["status"] == "passed"
