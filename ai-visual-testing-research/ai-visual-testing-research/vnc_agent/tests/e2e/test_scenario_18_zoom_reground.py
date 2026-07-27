"""E2E scenario 18 (feature 014): zoom_reground escalation.

US1: full-screen grounding fails → recapture fails → zoom_reground crops,
upscales, re-grounds on the zoomed image and the click lands on the exact
restored original-frame coordinates.

US2: zoom_reground also fails → the run terminates through the existing
recovery/step-failure path within budget (no new retry loop, per-step cap).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.conftest import build_runtime
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.mimo_grounder import (
    _merge_ui_index_candidates,
    _resolve_coordinate_spaces,
    _restore_and_cap,
)
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.models.provider import GroundingRequest
from vnc_agent.perception.ocr import engine as ocr_engine

# Anchor text on the 300x200 fake screen (full-frame pixel coords)
_ANCHOR_BOX = [[100, 80], [160, 80], [160, 96], [100, 96]]
# ROI derived from the anchor (expand_factor 2.0 * 2 neighborhood, min 64px):
# anchor bbox (100,80,160,96) → window (10,56,250,120)
_EXPECTED_ROI = (10, 56, 250, 120)
# Target's true original bbox inside the ROI; at 2x zoom relative to the ROI
# origin it appears at ((150-10)*2, (85-56)*2, (170-10)*2, (95-56)*2)
_TARGET_ORIGINAL_BBOX = (150, 85, 170, 95)
_TARGET_ZOOMED_BBOX = (280, 58, 320, 78)
_EXPECTED_CLICK = (160, 90)  # center of the restored original bbox


class _StubOcrAnchor:
    """RapidOCR-shaped stub: always reads the anchor text 'TOTAL'."""

    def __call__(self, img):
        return [[_ANCHOR_BOX, "TOTAL", 0.9]], None


class ScriptedZoomGrounder:
    """found=false on full-screen requests; a high-confidence zoomed-image
    candidate on zoom requests (unless ``zoom_found`` is False)."""

    def __init__(self, *, zoom_found: bool = True) -> None:
        self.zoom_found = zoom_found
        self.calls: list[GroundingRequest] = []

    async def ground(self, request: GroundingRequest) -> GroundingResult:
        self.calls.append(request)
        if request.scale_factor == 1.0 or not self.zoom_found:
            result = GroundingResult(found=False, candidates=[], model_name="scripted")
        else:
            result = GroundingResult(
                found=True,
                candidates=[
                    GroundingCandidate(
                        bbox=_TARGET_ZOOMED_BBOX,
                        coordinate_space="pixel",
                        confidence=0.9,
                        reason="visible at 2x",
                    )
                ],
                model_name="scripted",
            )
        merged = _merge_ui_index_candidates(result, request)
        resolved = _resolve_coordinate_spaces(merged, request)
        return _restore_and_cap(resolved, request, model_name="scripted", top_k=3)


def _case(max_retries: int = 4) -> TestCase:
    return TestCase(
        id="e2e-zoom",
        name="zoom reground",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="s1",
                name="click small OK",
                intent="click the OK button",
                max_retries=max_retries,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="screen_changed")],
                ),
            )
        ],
    )


def _planner() -> StubPlanner:
    return StubPlanner(
        action=SemanticAction(
            action_id="a1",
            intent="click the OK button",
            action_type="click",
            target=TargetDescription(
                role="button",
                text="OK",
                description="small ok button",
                nearby_texts=["TOTAL"],
            ),
        )
    )


def _zoom_attempts(ctx):
    return [
        attempt
        for step in ctx.test_run.steps
        for it in step.iterations
        for attempt in it.recovery_attempts
        if attempt.strategy == "zoom_reground"
    ]


@pytest.fixture(autouse=True)
def _anchor_ocr():
    ocr_engine.set_engine(_StubOcrAnchor())
    yield
    ocr_engine.reset_engine()


@pytest.mark.asyncio
async def test_zoom_reground_locates_and_clicks_restored_coordinates(
    tmp_path: Path, app_config
):
    """US1/SC-001: fail → recapture → fail → zoom_reground → click at the
    pixel-exact restored original coordinates."""
    grounder = ScriptedZoomGrounder(zoom_found=True)
    runtime, drv = await build_runtime(
        tmp_path, app_config, planner=_planner(), grounder=grounder, ocr_enabled=True
    )
    ctx = await runtime.run(_case())

    # Escalation happened exactly once, fully observable (FR-008)
    attempts = _zoom_attempts(ctx)
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt.resolved is True
    assert attempt.roi == _EXPECTED_ROI
    assert attempt.scale_factor == 2.0
    assert attempt.roi_source == "anchor_text"

    # The grounder saw one zoom request with the zoom transform declared
    zoom_calls = [c for c in grounder.calls if c.scale_factor != 1.0]
    assert len(zoom_calls) == 1
    zoom_call = zoom_calls[0]
    assert zoom_call.crop_offset == (_EXPECTED_ROI[0], _EXPECTED_ROI[1])
    assert zoom_call.scale_factor == 2.0
    assert zoom_call.original_resolution == (300, 200)
    # zoomed image dims = ROI size * scale
    assert zoom_call.resolution == (
        (_EXPECTED_ROI[2] - _EXPECTED_ROI[0]) * 2,
        (_EXPECTED_ROI[3] - _EXPECTED_ROI[1]) * 2,
    )
    assert not zoom_call.ui_index_candidates

    # Red line (FR-004/SC-001): click landed on the restored original pixels
    assert _EXPECTED_CLICK in drv.clicks
    for x, y in drv.clicks:
        assert 0 <= x < 300 and 0 <= y < 200

    # The grounding result recorded for that iteration carries the restored bbox
    zoomed_iterations = [
        it
        for step in ctx.test_run.steps
        for it in step.iterations
        if it.grounding_result is not None
        and it.grounding_result.found
        and it.grounding_result.candidates
    ]
    assert zoomed_iterations
    assert zoomed_iterations[0].grounding_result.candidates[0].bbox == (
        _TARGET_ORIGINAL_BBOX
    )

    # FR-008: the upscaled screenshot was persisted as a run artifact
    zoom_files = list(Path(tmp_path / "artifacts").rglob("zoom/*.png"))
    assert zoom_files, "upscaled zoom screenshot must be persisted"


@pytest.mark.asyncio
async def test_zoom_reground_failure_terminates_via_existing_path(
    tmp_path: Path, app_config
):
    """US2/SC-003: zoom also fails → per-step cap respected, recovery falls
    back to the existing sequence and the run terminates failed in budget."""
    grounder = ScriptedZoomGrounder(zoom_found=False)
    runtime, drv = await build_runtime(
        tmp_path, app_config, planner=_planner(), grounder=grounder, ocr_enabled=True
    )
    ctx = await runtime.run(_case())

    assert ctx.test_run.status == "failed"
    # per-step hard cap: exactly one zoom escalation ever executed
    attempts = _zoom_attempts(ctx)
    assert len(attempts) == 1
    zoom_calls = [c for c in grounder.calls if c.scale_factor != 1.0]
    assert len(zoom_calls) == 1
    # after the zoom failure the existing strategy sequence continued
    all_strategies = [
        a.strategy
        for step in ctx.test_run.steps
        for it in step.iterations
        for a in it.recovery_attempts
    ]
    zoom_idx = all_strategies.index("zoom_reground")
    assert "recapture" in all_strategies[:zoom_idx]
    assert "re_ground" in all_strategies[zoom_idx + 1 :]
    # no clicks were ever issued (nothing was located)
    assert drv.clicks == []
