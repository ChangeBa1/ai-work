"""E2E scenario 21 (feature 022): wrong-click detection — two deterministic
defense lines, zero new model calls.

a) Stale-frame guard: the screen drifts inside the target neighborhood
   between observation and execution → the mouse action is NOT sent, the
   iteration fails as STALE_FRAME, and the re-observed retry succeeds.
b) Wrong-target upgrade: the click lands but every change blob is far from
   the target and the verification fails → attribution upgrades to
   WRONG_TARGET, recovery re-locates, the retry passes.
c) Suspected but verification passed → the step passes untouched; only the
   evidence/telemetry records the suspicion.
d) Guard disabled → no pre_click_guard capture, pre-022 behavior.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from tests.e2e.conftest import FakeVNC, build_runtime
from vnc_agent.config import AppConfig
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.recovery import FailureType
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.perception.ocr import engine as ocr_engine

# 300x200 fake screen; the believed target button.
TARGET_BBOX = (100, 80, 200, 120)
# Exact marker color painted on the "DONE" frame (BGR) — the OCR stub keys
# off its presence, so crops/upscales behave consistently.
_DONE_BGR = (13, 217, 255)


def _base_frame() -> np.ndarray:
    f = np.zeros((200, 300, 3), dtype=np.uint8)
    f[80:120, 100:200] = (0, 200, 0)  # target button
    return f


def _guard_config(app_config: AppConfig, *, enabled: bool = True) -> AppConfig:
    """Scenario-21 config: same recovery table as the shared fixture, with
    the feature-022 stale-frame guard toggled explicitly."""
    cfg = app_config.model_copy(deep=True)
    cfg.agent.execution.stale_frame_check_enabled = enabled
    return cfg


class ClickScriptedVNC(FakeVNC):
    """Captures walk the pre-click frame list (shared FakeVNC semantics)
    until the first click; after the n-th click every capture returns
    ``post_frames[n-1]`` — UI changes are click-driven, as on a real app."""

    def __init__(self, pre_frames: list[np.ndarray], post_frames: list[np.ndarray]):
        super().__init__(pre_frames)
        self.post_frames = post_frames

    async def capture_screen(self) -> bytes:
        if self.clicks:
            f = self.post_frames[min(len(self.clicks) - 1, len(self.post_frames) - 1)]
            self.call_log.append("capture")
            ok, buf = cv2.imencode(".png", f)
            return buf.tobytes()
        return await super().capture_screen()


class SeqGrounder:
    """One scripted GroundingResult per call (last one repeats)."""

    def __init__(self, results: list[GroundingResult]):
        self.results = results
        self.calls: list[object] = []

    async def ground(self, request) -> GroundingResult:
        self.calls.append(request)
        return self.results[min(len(self.calls) - 1, len(self.results) - 1)]


def _click_planner(*, idempotent: bool = False) -> StubPlanner:
    return StubPlanner(
        action=SemanticAction(
            action_id="c1",
            intent="click the confirm button",
            action_type="click",
            target=TargetDescription(text="btn", description="confirm button"),
            action_kind="idempotent" if idempotent else None,
        )
    )


def _grounding(bbox: tuple[int, int, int, int]) -> GroundingResult:
    return GroundingResult(
        found=True,
        candidates=[GroundingCandidate(bbox=bbox, confidence=0.95, reason="top")],
        model_name="stub",
    )


def _case(
    conditions: list[VerificationCondition],
    *,
    max_retries: int = 3,
    verification_mode: str | None = None,
) -> TestCase:
    return TestCase(
        id="e2e-021",
        name="wrong click detection",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="s1",
                name="click confirm",
                intent="click the confirm button",
                max_retries=max_retries,
                verification_mode=verification_mode,  # type: ignore[arg-type]
                expected=VerificationSpec(operator="all", conditions=conditions),
            )
        ],
    )


def _screen_changed() -> list[VerificationCondition]:
    return [VerificationCondition(type="screen_changed")]


def _guard_frames(ctx) -> list:
    return [f for f in ctx.test_run.frames if f.capture_source == "pre_click_guard"]


# ---------------------------------------------------------------- case (a)


@pytest.mark.asyncio
async def test_stale_frame_vetoes_click_then_reobserve_succeeds(
    tmp_path: Path, app_config
):
    """US-A: target neighborhood drifts after observation → action NOT sent,
    STALE_FRAME recovery, next iteration re-observes/re-grounds and passes."""
    f0 = _base_frame()
    f_shift = np.zeros((200, 300, 3), dtype=np.uint8)
    f_shift[110:150, 100:200] = (0, 200, 0)  # button moved down 30px
    f_after = f_shift.copy()
    f_after[110:150, 100:200] = (200, 80, 0)  # clicked → button turns blue

    drv = ClickScriptedVNC([f0, f_shift], [f_after])
    grounder = SeqGrounder(
        [_grounding(TARGET_BBOX), _grounding((100, 110, 200, 150))]
    )
    runtime, drv = await build_runtime(
        tmp_path,
        _guard_config(app_config, enabled=True),
        driver=drv,
        planner=_click_planner(),
        grounder=grounder,
    )
    ctx = await runtime.run(
        _case(_screen_changed(), verification_mode="effect_only")
    )

    assert ctx.test_run.status == "passed"
    iterations = ctx.test_run.steps[0].iterations
    assert len(iterations) == 2

    it1, it2 = iterations
    # Iteration 1: resolved an executable but never sent it.
    assert it1.executable_action is not None
    assert it1.execution_result is None
    assert it1.failure_attribution == FailureType.STALE_FRAME.value
    assert it1.verification_result is not None
    assert it1.verification_result.status == "failed"
    assert it1.verification_result.reason.startswith("stale_frame:")
    stale_attempts = [
        a for a in it1.recovery_attempts if a.failure_type == FailureType.STALE_FRAME
    ]
    assert len(stale_attempts) == 1
    assert stale_attempts[0].strategy == "recapture"

    # Exactly one click total, inside the re-grounded (moved) bbox.
    assert len(drv.clicks) == 1
    x, y = drv.clicks[0]
    assert 100 <= x <= 200 and 110 <= y <= 150
    assert it2.failure_attribution is None

    # The guard frames went through the shared capture service (audited).
    assert len(_guard_frames(ctx)) >= 2  # one veto + one clean pass


# ---------------------------------------------------------------- case (b)


class _DoneOcrStub:
    """RapidOCR-shaped stub: reads 'DONE' iff the marker color is present."""

    def __call__(self, img):
        if img is None or getattr(img, "size", 0) == 0:
            return None, None
        mask = (
            (img[:, :, 0] == _DONE_BGR[0])
            & (img[:, :, 1] == _DONE_BGR[1])
            & (img[:, :, 2] == _DONE_BGR[2])
        )
        if bool(mask.any()):
            ys, xs = np.nonzero(mask)
            x1, y1 = int(xs.min()), int(ys.min())
            x2, y2 = int(xs.max()) + 1, int(ys.max()) + 1
            box = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
            return [[box, "DONE", 0.95]], None
        return [], None


@pytest.fixture()
def _done_ocr():
    ocr_engine.set_engine(_DoneOcrStub())
    yield
    ocr_engine.reset_engine()


@pytest.mark.asyncio
async def test_wrong_target_upgrade_then_relocate_succeeds(
    tmp_path: Path, app_config, _done_ocr
):
    """US-B: click lands beside the target (all change far away) + verification
    fails → attribution upgrades to WRONG_TARGET, recovery re-locates, the
    second click produces the expected business result."""
    f_idle = _base_frame()
    f_wrong = f_idle.copy()
    f_wrong[160:178, 20:80] = (255, 255, 255)  # response far bottom-left
    f_done = f_idle.copy()
    f_done[90:110, 120:180] = _DONE_BGR  # DONE marker on the target itself

    drv = ClickScriptedVNC([f_idle], [f_wrong, f_done])
    grounder = SeqGrounder([_grounding(TARGET_BBOX)])
    runtime, drv = await build_runtime(
        tmp_path,
        _guard_config(app_config, enabled=True),
        driver=drv,
        planner=_click_planner(idempotent=True),
        grounder=grounder,
        ocr_enabled=True,
    )
    ctx = await runtime.run(
        _case([VerificationCondition(type="text_appears", value="DONE")])
    )

    assert ctx.test_run.status == "passed"
    iterations = ctx.test_run.steps[0].iterations
    assert len(iterations) == 2

    it1, it2 = iterations
    # Iteration 1: executed, expected_effect, but suspected + failed → upgraded.
    assert it1.action_effect is not None
    assert it1.action_effect.status == "expected_effect"
    ev = it1.wrong_target_evidence
    assert ev is not None and ev.suspected is True
    assert ev.blobs_intersecting_neighborhood == 0
    assert ev.nearest_blob_distance_px is not None and ev.nearest_blob_distance_px > 50
    assert ev.nearest_blob_direction == "down_left"
    assert ev.global_diff_ratio < 0.10
    assert it1.failure_attribution == FailureType.WRONG_TARGET.value
    assert it1.verification_result is not None
    assert it1.verification_result.status == "failed"
    assert it1.verification_result.reason.startswith("wrong_target:")
    wt_attempts = [
        a for a in it1.recovery_attempts if a.failure_type == FailureType.WRONG_TARGET
    ]
    assert len(wt_attempts) == 1
    assert wt_attempts[0].strategy == "recapture"

    # Iteration 2: re-located click passes the business verification.
    assert it2.verification_result is not None
    assert it2.verification_result.status == "passed"
    assert it2.failure_attribution is None
    assert len(drv.clicks) == 2

    # The upgraded attribution reaches the experience stream for 021/023.
    upgraded = [
        e for e in runtime.experience.written if e.failure_type == "wrong_target"
    ]
    assert len(upgraded) == 1


# ---------------------------------------------------------------- case (c)


@pytest.mark.asyncio
async def test_suspected_but_verification_passed_stays_passed(
    tmp_path: Path, app_config
):
    """US-B edge (FR-B03): suspected wrong-click whose verification passes is
    NOT upgraded — the step passes and only the evidence records suspicion
    (the response region may legitimately live far from the click)."""
    f_idle = _base_frame()
    f_far = f_idle.copy()
    f_far[160:178, 20:80] = (255, 255, 255)  # small change far from target

    drv = ClickScriptedVNC([f_idle], [f_far])
    runtime, drv = await build_runtime(
        tmp_path,
        _guard_config(app_config, enabled=True),
        driver=drv,
        planner=_click_planner(),
        grounder=SeqGrounder([_grounding(TARGET_BBOX)]),
    )
    ctx = await runtime.run(
        _case(_screen_changed(), verification_mode="effect_only")
    )

    assert ctx.test_run.status == "passed"
    iterations = ctx.test_run.steps[0].iterations
    assert len(iterations) == 1

    it1 = iterations[0]
    ev = it1.wrong_target_evidence
    assert ev is not None and ev.suspected is True
    assert it1.failure_attribution is None
    assert it1.verification_result is not None
    assert it1.verification_result.status == "passed"
    assert not it1.verification_result.reason.startswith("wrong_target:")
    assert all(
        a.failure_type != FailureType.WRONG_TARGET for a in it1.recovery_attempts
    )
    assert len(drv.clicks) == 1


# ---------------------------------------------------------------- case (d)


@pytest.mark.asyncio
async def test_guard_disabled_matches_pre_022_baseline(tmp_path: Path, app_config):
    """FR-A03: stale_frame_check_enabled=false → no pre_click_guard capture,
    no STALE_FRAME classification; the click executes exactly as before 022."""
    f_idle = _base_frame()
    f_near = f_idle.copy()
    f_near[80:120, 100:200] = (200, 80, 0)  # change at the target

    drv = ClickScriptedVNC([f_idle], [f_near])
    runtime, drv = await build_runtime(
        tmp_path,
        _guard_config(app_config, enabled=False),
        driver=drv,
        planner=_click_planner(),
        grounder=SeqGrounder([_grounding(TARGET_BBOX)]),
    )
    ctx = await runtime.run(
        _case(_screen_changed(), verification_mode="effect_only")
    )

    assert ctx.test_run.status == "passed"
    assert _guard_frames(ctx) == []
    # Pre-022 capture vocabulary only.
    assert {f.capture_source for f in ctx.test_run.frames} <= {
        "observation",
        "stability_wait",
        "retry",
        "recovery",
        "post_action_verification",
    }
    iterations = ctx.test_run.steps[0].iterations
    assert len(iterations) == 1
    assert iterations[0].failure_attribution is None
    assert all(
        a.failure_type != FailureType.STALE_FRAME
        for it in iterations
        for a in it.recovery_attempts
    )
    assert len(drv.clicks) == 1
