"""Feature 008 (vision-answer-cache-contract.md): call-count oracle for the
`vision_answer` cached component.

Same dedup-proven frame content + same question + same model ⇒ exactly one
real `describe_screen(mode="answer_question")` call; different question,
different frame content, different model identity, or window eviction ⇒ each
issues its own real call. Call counts on the planner double are the oracle —
never durations or report-side counting (telemetry-contract.md "Test oracle").

Frames are produced by the real FrameCaptureService/ObservationPipeline so
`deduplicated` / `capture_sequence` / `scope_key` come from the production
path (fixtures: tests/fixtures/images/frame_dedup).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vnc_agent.domain.action_effect import ActionEffect, ActionEffectEvidence
from vnc_agent.domain.run import TestRun
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.provider import (
    VisionUnderstandingRequest,
    VisionUnderstandingResponse,
)
from vnc_agent.perception.cache import AnalysisResultCache
from vnc_agent.perception.pipeline import ObservationPipeline
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.runtime.telemetry import derive_performance_summary
from vnc_agent.storage.artifact_store import ArtifactStore
from vnc_agent.verification.answer_cache import CachedVisualAnswerer
from vnc_agent.verification.business_resolver import resolve_step_result
from vnc_agent.verification.engine import VerificationEngine

FIXTURES = Path(__file__).resolve().parent / "images" / "frame_dedup"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))

QUESTION_A = "Is the login dialog visible?"
QUESTION_B = "Is an error popup visible?"


class SequenceDriver:
    def __init__(self, names: list[str]):
        self._bytes = [(FIXTURES / MANIFEST[n]["file"]).read_bytes() for n in names]
        self._i = 0
        meta = MANIFEST[names[0]]
        self._resolution = (meta["width"], meta["height"])

    @property
    def resolution(self):
        return self._resolution

    async def capture_screen(self) -> bytes:
        data = self._bytes[min(self._i, len(self._bytes) - 1)]
        self._i += 1
        return data

    async def capture_region(self, x, y, w, h) -> bytes:
        return await self.capture_screen()


class CountingPlanner:
    """Planner double counting answer_question calls; the count is the oracle."""

    def __init__(self, answer: str = "passed"):
        self.answer = answer
        self.answer_calls: list[str] = []  # question per real call

    async def plan(self, request):  # pragma: no cover - not exercised here
        raise AssertionError("plan must not be called by verification")

    async def describe_screen(
        self, request: VisionUnderstandingRequest
    ) -> VisionUnderstandingResponse:
        assert request.mode == "answer_question"
        self.answer_calls.append(request.question or "")
        return VisionUnderstandingResponse(
            mode="answer_question",
            answer=self.answer,
            confidence=0.9,
            reason=f"model-answer:{len(self.answer_calls)}",
            model_name="fake-vlm",
        )


def _make_env(names: list[str], tmp_path: Path, *, max_frames: int = 5):
    test_run = TestRun(run_id="r1", test_case_id="tc")
    svc = FrameCaptureService(
        SequenceDriver(names),
        run_id="r1",
        vnc_session_id="s1",
        test_run=test_run,
        artifact_store=ArtifactStore(tmp_path),
    )
    cache = AnalysisResultCache(max_frames=max_frames)
    pipeline = ObservationPipeline(
        svc,
        ocr_enabled=False,
        template_enabled=False,
        vision_fallback=False,
        cache=cache,
    )
    planner = CountingPlanner()
    engine = VerificationEngine(
        planner,
        answerer=CachedVisualAnswerer(
            cache=cache,
            test_run_provider=lambda: svc.test_run,
            provider_name="planner-provider",
            model="fake-vlm-config",
        ),
    )
    return test_run, svc, cache, pipeline, planner, engine


def _spec(question: str) -> VerificationSpec:
    return VerificationSpec(
        operator="all",
        conditions=[VerificationCondition(type="visual_question", value=question)],
    )


@pytest.mark.asyncio
async def test_same_frame_same_question_calls_model_once(tmp_path: Path):
    """US1: N dedup-identical frames + one question ⇒ exactly 1 real call,
    identical verdict/reason each time (SC-001)."""
    test_run, _, _, pipeline, planner, engine = _make_env(["baseline_full"] * 3, tmp_path)

    results = []
    for _ in range(3):
        screen = await pipeline.observe(step_id="s1", capture_source="observation")
        results.append(await engine.verify(_spec(QUESTION_A), screen))

    assert len(planner.answer_calls) == 1, "same frame + same question must call once"
    assert {r.status for r in results} == {"passed"}
    assert len({r.reason for r in results}) == 1, "cached answer must be verbatim"

    summary = derive_performance_summary(test_run)
    assert summary.cache_hits["vision_answer"] == 2, "2nd and 3rd eval are hits"


@pytest.mark.asyncio
async def test_no_cache_configured_behaves_like_today(tmp_path: Path):
    """FR-004: a bare engine (no answerer/cache) issues one real call per eval."""
    _, _, _, pipeline, planner, _ = _make_env(["baseline_full"] * 3, tmp_path)
    bare_engine = VerificationEngine(planner)

    for _ in range(3):
        screen = await pipeline.observe(step_id="s1", capture_source="observation")
        await bare_engine.verify(_spec(QUESTION_A), screen)

    assert len(planner.answer_calls) == 3


@pytest.mark.asyncio
async def test_different_question_each_gets_own_call(tmp_path: Path):
    """US2-AS1: question B on the same cached frame is its own real call;
    re-asking either question on a later duplicate hits its own entry."""
    _, _, _, pipeline, planner, engine = _make_env(["baseline_full"] * 3, tmp_path)

    s1 = await pipeline.observe(step_id="s1", capture_source="observation")
    await engine.verify(_spec(QUESTION_A), s1)
    s2 = await pipeline.observe(step_id="s1", capture_source="observation")
    await engine.verify(_spec(QUESTION_B), s2)  # different question -> real call
    s3 = await pipeline.observe(step_id="s1", capture_source="observation")
    await engine.verify(_spec(QUESTION_A), s3)  # hit on A's entry
    await engine.verify(_spec(QUESTION_B), s3)  # hit on B's entry

    assert planner.answer_calls == [QUESTION_A, QUESTION_B]


@pytest.mark.asyncio
async def test_changed_frame_reissues_call(tmp_path: Path):
    """US2-AS2: content change breaks the key — fresh call on the new frame."""
    names = ["baseline_full", "baseline_full", "single_pixel_changed", "single_pixel_changed"]
    _, _, _, pipeline, planner, engine = _make_env(names, tmp_path)

    for _ in range(4):
        screen = await pipeline.observe(step_id="s1", capture_source="observation")
        await engine.verify(_spec(QUESTION_A), screen)

    # frame1: real; frame2 (dup of 1): hit; frame3 (changed): real; frame4 (dup of 3): hit
    assert len(planner.answer_calls) == 2


@pytest.mark.asyncio
async def test_different_model_identity_reissues_call(tmp_path: Path):
    """US2-AS3: same cache, same frame+question, different requested model ⇒
    each identity issues its own real call."""
    _, svc, cache, pipeline, planner, engine = _make_env(["baseline_full"] * 2, tmp_path)

    await pipeline.observe(step_id="s1", capture_source="observation")
    screen2 = await pipeline.observe(step_id="s1", capture_source="observation")

    answerer_m2 = CachedVisualAnswerer(
        cache=cache,
        test_run_provider=lambda: svc.test_run,
        provider_name="planner-provider",
        model="other-model",
    )
    await engine.verify(_spec(QUESTION_A), screen2)  # stores under fake-vlm-config
    await engine.verify(_spec(QUESTION_A), screen2)  # hit
    await answerer_m2.answer(planner, screen2, QUESTION_A)  # other model -> real call

    assert len(planner.answer_calls) == 2


@pytest.mark.asyncio
async def test_window_eviction_reissues_call(tmp_path: Path):
    """US3-AS1: an entry unreferenced for >= cache_max_frames captures is
    evicted; the next identical frame+question is a real call again."""
    _, _, _, pipeline, planner, engine = _make_env(
        ["baseline_full"] * 6, tmp_path, max_frames=3
    )

    screen = await pipeline.observe(step_id="s1", capture_source="observation")  # seq 1
    await engine.verify(_spec(QUESTION_A), screen)  # real call, stored @1

    for _ in range(4):  # seq 2..5 captured without evaluating the question
        screen = await pipeline.observe(step_id="s1", capture_source="observation")

    # last screen is deduplicated (eligible) but 5 - 1 >= 3 -> evicted -> real
    await engine.verify(_spec(QUESTION_A), screen)
    assert len(planner.answer_calls) == 2

    # freshly stored @5 -> next duplicate hits again
    screen = await pipeline.observe(step_id="s1", capture_source="observation")  # seq 6
    await engine.verify(_spec(QUESTION_A), screen)
    assert len(planner.answer_calls) == 2


@pytest.mark.asyncio
async def test_escalation_shares_cache_with_condition_eval(tmp_path: Path):
    """FR-004b: business_resolver's escalation fallback goes through the same
    helper — across two resolves on identical frames, the condition question
    and the escalation question are each asked exactly once."""
    test_run, _, _, pipeline, planner, engine = _make_env(["baseline_full"] * 2, tmp_path)
    planner.answer = "uncertain"  # keep engine_result uncertain -> escalation runs
    effect = ActionEffect(
        status="effect_uncertain", evidence=ActionEffectEvidence(), reason="test"
    )

    for _ in range(2):
        screen = await pipeline.observe(step_id="s1", capture_source="observation")
        await resolve_step_result(
            _spec(QUESTION_A),
            "business",
            effect,
            screen,
            planner=planner,
            reobserve=None,
            engine=engine,
            escalate=True,
        )

    assert planner.answer_calls == [
        QUESTION_A,
        "Did the expected business result appear on screen?",
    ], "second resolve must be served entirely from cache"

    summary = derive_performance_summary(test_run)
    assert summary.cache_hits["vision_answer"] == 2
    assert summary.analysis_invocations.get("vision_answer") == 2


def test_performance_summary_always_reports_vision_answer():
    """FR-006: the counter is present (0) even when the feature never fired."""
    summary = derive_performance_summary(TestRun(run_id="r0", test_case_id="tc"))
    assert summary.cache_hits["vision_answer"] == 0
