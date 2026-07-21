"""E2E: uncertain contagion in compound verification."""

import pytest

from vnc_agent.domain.observation import StructuredScreen, OCRItem
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.models.provider import VisionUnderstandingResponse
from vnc_agent.verification.engine import VerificationEngine
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_all_failed_over_uncertain():
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="uncertain",
            confidence=0.5,
            reason="maybe",
            model_name="stub",
        )
    )
    eng = VerificationEngine(planner)
    screen = StructuredScreen(
        frame_id="f",
        resolution=(10, 10),
        captured_at=datetime.now(timezone.utc),
        ocr_items=[],
        image_path="x.png",
    )
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="NO"),
            VerificationCondition(type="visual_question", value="seen?"),
        ],
    )
    vr = await eng.verify(spec, screen)
    assert vr.status == "failed"  # failed beats uncertain under all


@pytest.mark.asyncio
async def test_all_passed_plus_uncertain():
    planner = StubPlanner(
        answer=VisionUnderstandingResponse(
            mode="answer_question",
            answer="uncertain",
            confidence=0.5,
            reason="maybe",
            model_name="stub",
        )
    )
    eng = VerificationEngine(planner)
    screen = StructuredScreen(
        frame_id="f",
        resolution=(10, 10),
        captured_at=datetime.now(timezone.utc),
        ocr_items=[OCRItem(text="OK", bbox=(0, 0, 1, 1), confidence=1.0)],
        image_path="x.png",
    )
    spec = VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="OK"),
            VerificationCondition(type="visual_question", value="seen?"),
        ],
    )
    vr = await eng.verify(spec, screen)
    assert vr.status == "uncertain"
