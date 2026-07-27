"""Feature 016 unit tests: ReplayRecorder (spec FR-003/FR-004, SC-005)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

from vnc_agent.domain.action import ExecutableAction, SemanticAction
from vnc_agent.domain.observation import OCRItem, Region, StructuredScreen
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.replay.recorder import ReplayRecorder
from vnc_agent.storage.database import init_db, make_engine, make_session_factory
from vnc_agent.storage.repositories import ReplayRepository

RESOLUTION = (300, 200)
TARGET_REGION = Region(x1=150, y1=85, x2=170, y2=95)


class _FakeCtx:
    def __init__(self, test_case: TestCase, run_id: str = "run-1") -> None:
        self.test_case = test_case
        self.run_id = run_id


def _spec() -> VerificationSpec:
    return VerificationSpec(
        operator="all",
        conditions=[VerificationCondition(type="text_appears", value="DONE")],
    )


def _case(step_ids: list[str]) -> TestCase:
    return TestCase(
        id="tc-rec",
        name="rec",
        target_id="t1",
        mode="explicit",
        steps=[
            TestStep(id=sid, name=sid, intent=f"do {sid}", expected=_spec())
            for sid in step_ids
        ],
    )


def _screen(tmp_path: Path) -> StructuredScreen:
    frame = np.zeros((200, 300, 3), dtype=np.uint8)
    frame[85:95, 150:170] = (10, 200, 30)
    path = tmp_path / "frame.png"
    cv2.imwrite(str(path), frame)
    return StructuredScreen(
        frame_id="f1",
        resolution=RESOLUTION,
        captured_at=datetime.now(UTC),
        ocr_items=[OCRItem(text="TOTAL", bbox=(100, 80, 160, 96), confidence=0.9)],
        image_path=str(path),
    )


def _sa() -> SemanticAction:
    return SemanticAction(action_id="a1", intent="click ok", action_type="click")


def _mouse_exec() -> ExecutableAction:
    return ExecutableAction(
        method="mouse",
        operation="click",
        coordinates=(160, 90),
        target_region=TARGET_REGION,
    )


def _keyboard_exec() -> ExecutableAction:
    return ExecutableAction(method="keyboard", operation="press_key", keys=["enter"])


async def _repo(tmp_path: Path) -> ReplayRepository:
    engine = make_engine(str(tmp_path / "replay.db"))
    await init_db(engine)
    return ReplayRepository(make_session_factory(engine))


def _recorder(repo, tmp_path: Path, mask_regions=None) -> ReplayRecorder:
    return ReplayRecorder(
        repo=repo,
        template_dir=tmp_path / "templates",
        mask_regions=mask_regions or [],
    )


@pytest.mark.asyncio
async def test_finalize_persists_full_script(tmp_path: Path):
    repo = await _repo(tmp_path)
    recorder = _recorder(repo, tmp_path)
    case = _case(["s1", "s2"])
    screen = _screen(tmp_path)
    recorder.observe_passed_iteration(case.steps[0], screen, _sa(), _mouse_exec())
    recorder.observe_passed_iteration(case.steps[1], screen, _sa(), _keyboard_exec())

    await recorder.finalize(_FakeCtx(case))

    script = await repo.get_latest_script("tc-rec")
    assert script is not None
    assert script.version == 1
    assert script.source_run_id == "run-1"
    assert [s.step_id for s in script.steps] == ["s1", "s2"]

    mouse = script.steps[0]
    assert mouse.preferred_method == "mouse"
    assert mouse.bbox == TARGET_REGION.as_tuple()
    assert mouse.normalized_bbox == (150 / 300, 85 / 200, 170 / 300, 95 / 200)
    assert mouse.anchor_texts == ["TOTAL"]
    assert mouse.anchors[0].bbox == (100, 80, 160, 96)
    assert mouse.expected == case.steps[0].expected
    assert mouse.target_template_path is not None
    template = cv2.imread(mouse.target_template_path)
    assert template.shape[:2] == (10, 20)  # region h x w crop
    assert mouse.page_fingerprint.resolution == RESOLUTION

    keyboard = script.steps[1]
    assert keyboard.preferred_method == "keyboard"
    assert keyboard.recorded_executable is not None
    assert keyboard.recorded_executable.keys == ["enter"]
    assert keyboard.target_template_path is None


@pytest.mark.asyncio
async def test_second_success_creates_new_version_and_keeps_old(tmp_path: Path):
    repo = await _repo(tmp_path)
    recorder = _recorder(repo, tmp_path)
    case = _case(["s1"])
    screen = _screen(tmp_path)

    for run_id in ("run-1", "run-2"):
        recorder.reset()
        recorder.observe_passed_iteration(case.steps[0], screen, _sa(), _mouse_exec())
        await recorder.finalize(_FakeCtx(case, run_id=run_id))

    scripts = await repo.list_scripts("tc-rec")
    assert [s.version for s in scripts] == [1, 2]
    assert scripts[0].source_run_id == "run-1"
    assert scripts[1].source_run_id == "run-2"


@pytest.mark.asyncio
async def test_masked_region_refuses_template_and_marks_fallback_only(tmp_path: Path):
    """Spec FR-004 security red line: mask-intersecting targets never become
    templates; the step replays via grounder fallback only."""
    repo = await _repo(tmp_path)
    recorder = _recorder(repo, tmp_path, mask_regions=[[140, 80, 180, 100]])
    case = _case(["s1"])
    recorder.observe_passed_iteration(case.steps[0], _screen(tmp_path), _sa(), _mouse_exec())

    await recorder.finalize(_FakeCtx(case))

    script = await repo.get_latest_script("tc-rec")
    assert script is not None
    step = script.steps[0]
    assert step.direct_fallback_only is True
    assert step.target_template_path is None
    assert not (tmp_path / "templates").exists()  # nothing was written


@pytest.mark.asyncio
async def test_missing_step_draft_aborts_whole_script(tmp_path: Path):
    """Spec Clarification 1: a partial script is worse than none."""
    repo = await _repo(tmp_path)
    recorder = _recorder(repo, tmp_path)
    case = _case(["s1", "s2"])
    recorder.observe_passed_iteration(case.steps[0], _screen(tmp_path), _sa(), _mouse_exec())
    # s2 never passed with an executable -> no draft

    await recorder.finalize(_FakeCtx(case))

    assert await repo.get_latest_script("tc-rec") is None


@pytest.mark.asyncio
async def test_mouse_step_without_region_aborts_script(tmp_path: Path):
    repo = await _repo(tmp_path)
    recorder = _recorder(repo, tmp_path)
    case = _case(["s1"])
    no_region = ExecutableAction(method="mouse", operation="click", coordinates=(5, 5))
    recorder.observe_passed_iteration(case.steps[0], _screen(tmp_path), _sa(), no_region)

    await recorder.finalize(_FakeCtx(case))

    assert await repo.get_latest_script("tc-rec") is None


@pytest.mark.asyncio
async def test_finalize_is_fail_open_on_storage_error(tmp_path: Path):
    class _BoomRepo:
        async def next_version(self, test_case_id: str) -> int:
            raise RuntimeError("db down")

    recorder = ReplayRecorder(repo=_BoomRepo(), template_dir=tmp_path / "t")
    case = _case(["s1"])
    recorder.observe_passed_iteration(case.steps[0], _screen(tmp_path), _sa(), _mouse_exec())
    # Must not raise (spec FR-003 fail-open).
    await recorder.finalize(_FakeCtx(case))
