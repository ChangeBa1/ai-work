"""E2E scenario 19 (feature 015): page/element memory.

US1+US2 (SC-001): run 1 resolves a click through grounding, passes and writes
memory; run 2 on the same page/target clicks directly from memory with ZERO
grounder calls, and the hit is fully observable (memory_hit, counters,
skipped grounder audit).

US2-5 (SC-002): a memory direct click that fails verification bumps the
element's failure counter and bans it for the rest of the step (at most one
memory hit; no second one).

US3 (SC-003): memory.enabled=false behaves exactly like the baseline —
grounder called every run, no memory rows, no template dir.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from tests.e2e.conftest import FakeVNC, build_runtime
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.models.provider import GroundingRequest
from vnc_agent.perception.ocr import engine as ocr_engine
from vnc_agent.runtime.telemetry import derive_performance_summary
from vnc_agent.storage.database import init_db, make_engine, make_session_factory
from vnc_agent.storage.repositories import MemoryRepository

# Anchor text on the 300x200 fake screen (always OCR-readable)
_ANCHOR_BOX = [[100, 80], [160, 80], [160, 96], [100, 96]]
# Confirmation text visible only on the post-click frame
_DONE_BOX = [[10, 150], [60, 150], [60, 166], [10, 166]]
# Target button bbox — deliberately NOT OCR-readable so resolution always
# needs grounding (same setup shape as scenario 18).
_TARGET_BBOX = (150, 85, 170, 95)
_EXPECTED_CLICK = (160, 90)  # safe point == center (no siblings)


def _frame_before() -> np.ndarray:
    base = np.zeros((200, 300, 3), dtype=np.uint8)
    base[80:120, 100:200] = (0, 200, 0)
    # Distinctive deterministic texture at the target (template matching needs
    # non-flat pixels; TM_CCOEFF_NORMED on a flat patch never scores).
    xx, yy = np.meshgrid(np.arange(20), np.arange(10))
    pat = ((xx * 23 + yy * 57) % 256).astype(np.uint8)
    base[85:95, 150:170] = np.stack([pat, 255 - pat, pat // 2], axis=-1)
    return base


def _frame_after() -> np.ndarray:
    # Post-click state: a white confirmation box appears (real pixel change,
    # so the action-effect classifier sees an expected effect).
    after = _frame_before()
    after[150:166, 10:60] = (255, 255, 255)
    return after


class _StubOcrContent:
    """RapidOCR-shaped stub: reads 'TOTAL' always, plus 'DONE' only when the
    post-click white confirmation box is present on the frame."""

    def __call__(self, img):
        items = [[_ANCHOR_BOX, "TOTAL", 0.9]]
        if img[155, 30].min() > 200:
            items.append([_DONE_BOX, "DONE", 0.9])
        return items, None


class CountingGrounder:
    """Always finds the target; counts every call."""

    def __init__(self) -> None:
        self.calls: list[GroundingRequest] = []

    async def ground(self, request: GroundingRequest) -> GroundingResult:
        self.calls.append(request)
        return GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=_TARGET_BBOX,
                    coordinate_space="pixel",
                    confidence=0.9,
                    reason="scripted",
                )
            ],
            model_name="counting",
        )


def _case(expected_text: str = "DONE", max_retries: int = 2) -> TestCase:
    return TestCase(
        id="e2e-memory",
        name="page element memory",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="s1",
                name="click OK",
                intent="click the OK button",
                max_retries=max_retries,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[
                        VerificationCondition(type="text_appears", value=expected_text)
                    ],
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


async def _memory_repo(tmp_path: Path) -> MemoryRepository:
    engine = make_engine(str(tmp_path / "test.db"))
    await init_db(engine)
    return MemoryRepository(make_session_factory(engine))


async def _run_once(tmp_path, app_config, *, expected_text="DONE"):
    grounder = CountingGrounder()
    runtime, drv = await build_runtime(
        tmp_path,
        app_config,
        # first capture (the pre-action observation) sees the "before" frame;
        # every later capture (stability + post-action) sees the "after" one.
        driver=FakeVNC(frames=[_frame_before(), _frame_after()]),
        planner=_planner(),
        grounder=grounder,
        ocr_enabled=True,
    )
    ctx = await runtime.run(_case(expected_text=expected_text))
    return ctx, grounder, drv


@pytest.fixture(autouse=True)
def _content_ocr():
    ocr_engine.set_engine(_StubOcrContent())
    yield
    ocr_engine.reset_engine()


@pytest.mark.asyncio
async def test_second_run_hits_memory_with_zero_grounder_calls(tmp_path: Path, app_config):
    """US1+US2/SC-001: grounding once, then memory direct click forever."""
    # --- run 1: grounding path, passes, writes memory -------------------
    ctx1, grounder1, drv1 = await _run_once(tmp_path, app_config)
    assert ctx1.test_run.status == "passed"
    assert len(grounder1.calls) == 1
    assert _EXPECTED_CLICK in drv1.clicks

    repo = await _memory_repo(tmp_path)
    pages = await repo.list_pages()
    assert len(pages) == 1
    elements = await repo.list_elements(pages[0].page_id)
    assert len(elements) == 1
    element = elements[0]
    assert element.target_label == "ok"
    assert element.bbox == _TARGET_BBOX
    assert element.success_count == 1
    assert element.template_path is not None and Path(element.template_path).is_file()
    # template dir defaults under the artifact root (spec FR-003)
    assert Path(element.template_path).is_relative_to(tmp_path / "artifacts")

    # --- run 2: same page/target -> zero grounder calls -----------------
    ctx2, grounder2, drv2 = await _run_once(tmp_path, app_config)
    assert ctx2.test_run.status == "passed"
    assert grounder2.calls == []  # red line: the grounder was never invoked
    assert _EXPECTED_CLICK in drv2.clicks

    # iteration-level audit (US4/FR-010)
    iterations = [it for s in ctx2.test_run.steps for it in s.iterations]
    hits = [it.memory_hit for it in iterations if it.memory_hit is not None]
    assert len(hits) == 1
    hit = hits[0]
    assert hit.source == "element_memory"
    assert hit.element_memory_id == element.element_id
    assert hit.page_similarity >= 0.88
    assert hit.template_score >= 0.85
    assert hit.matched_bbox == _TARGET_BBOX
    # a memory iteration has no grounding result (nothing was called)
    memory_iter = next(it for it in iterations if it.memory_hit is not None)
    assert memory_iter.grounding_result is None

    # counters + skipped grounder audit (US4/FR-010)
    kinds = [e.kind for e in ctx2.test_run.counter_events]
    assert kinds.count("element_memory_hit") == 1
    skipped = [
        e
        for e in ctx2.test_run.counter_events
        if e.kind == "model_call_skipped"
        and e.payload.get("model_role") == "grounder"
        and e.payload.get("reason") == "element_memory_hit"
    ]
    assert len(skipped) == 1
    audits = [
        a
        for a in ctx2.test_run.model_call_audits
        if a.model_role == "grounder" and a.outcome == "skipped"
    ]
    assert len(audits) == 1
    assert audits[0].reason == "element_memory_hit"
    assert audits[0].source_ref == element.element_id
    # no actual grounder model_call event at all in run 2
    assert not [
        e
        for e in ctx2.test_run.counter_events
        if e.kind == "model_call" and e.payload.get("model_role") == "grounder"
    ]

    # performance summary (US4): memory_hits mirrors the cache_hits shape
    summary = derive_performance_summary(ctx2.test_run)
    assert summary.memory_hits["element_memory"] == 1
    assert summary.skipped_model_call_count >= 1
    # run 1 had no hits but the key is still present at 0
    summary1 = derive_performance_summary(ctx1.test_run)
    assert summary1.memory_hits["element_memory"] == 0

    # memory statistics accumulated across runs
    element_after = (await repo.list_elements(pages[0].page_id))[0]
    assert element_after.success_count == 2


@pytest.mark.asyncio
async def test_memory_hit_failing_verification_bans_element(tmp_path: Path, app_config):
    """US2-5/SC-002: failed verification after a memory click -> failure
    counter +1 and the element is banned for the rest of the step."""
    # run 1 (passing) seeds memory
    ctx1, grounder1, _ = await _run_once(tmp_path, app_config)
    assert ctx1.test_run.status == "passed"
    assert len(grounder1.calls) == 1

    # run 2 expects a text that never appears -> every iteration fails
    ctx2, grounder2, _ = await _run_once(tmp_path, app_config, expected_text="MISSING")
    assert ctx2.test_run.status == "failed"

    iterations = [it for s in ctx2.test_run.steps for it in s.iterations]
    hits = [it for it in iterations if it.memory_hit is not None]
    # the element was used exactly once, then banned for the step (FR-008)
    assert len(hits) == 1
    hit_kinds = [e.kind for e in ctx2.test_run.counter_events]
    assert hit_kinds.count("element_memory_hit") == 1

    repo = await _memory_repo(tmp_path)
    pages = await repo.list_pages()
    element = (await repo.list_elements(pages[0].page_id))[0]
    assert element.failure_count >= 1
    assert element.consecutive_success_count == 0


@pytest.mark.asyncio
async def test_memory_disabled_matches_baseline(tmp_path: Path, app_config):
    """US3/SC-003: enabled=false -> grounder called each run, no memory rows,
    no template artifacts, no memory telemetry."""
    app_config.agent.memory.enabled = False

    ctx1, grounder1, drv1 = await _run_once(tmp_path, app_config)
    ctx2, grounder2, drv2 = await _run_once(tmp_path, app_config)
    assert ctx1.test_run.status == "passed"
    assert ctx2.test_run.status == "passed"
    assert len(grounder1.calls) == 1
    assert len(grounder2.calls) == 1  # no memory shortcut
    assert _EXPECTED_CLICK in drv2.clicks

    repo = await _memory_repo(tmp_path)
    assert await repo.list_pages() == []
    assert not (tmp_path / "artifacts" / "memory").exists()

    for ctx in (ctx1, ctx2):
        assert not [
            e for e in ctx.test_run.counter_events if e.kind == "element_memory_hit"
        ]
        assert all(
            it.memory_hit is None for s in ctx.test_run.steps for it in s.iterations
        )
        summary = derive_performance_summary(ctx.test_run)
        assert summary.memory_hits == {"element_memory": 0}
