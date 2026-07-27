"""E2E scenario 22 (feature 023): click post-mortem correction.

a) Misplaced click → WRONG_TARGET → post-mortem diagnosis (stub model returns
   a corrected bbox) → corrected re-click → verified pass → memory write-back
   + full recovery/audit trail.
b) The wrong click opened a dialog → one Esc undo restores the page → the
   diagnosis proceeds → corrected click passes.
c) Low-confidence diagnosis → refused, falls back to the 022 recapture chain.
d) `wrong_target_postmortem.enabled: false` → 022-identical behavior, zero
   diagnosis calls.
e) Corrected click fails verification again → no second diagnosis in the
   step, run terminates through existing budgets.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from tests.e2e.conftest import build_runtime
from tests.e2e.test_scenario_21_wrong_click_detection import (
    ClickScriptedVNC,
    SeqGrounder,
    _click_planner,
    _grounding,
)
from vnc_agent.config import AppConfig
from vnc_agent.domain.recovery import FailureType
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.postmortem_client import StubPostmortemClient
from vnc_agent.perception.ocr import engine as ocr_engine

# 300x200 busy app-like screen (flat black frames make pHash hypersensitive
# to any bright blob — realistic content keeps small local changes inside
# the fingerprint high-similarity tier, matching real screenshots).
TARGET_BBOX = (100, 80, 200, 120)  # the button the agent believed it clicked
CORRECTED_BBOX = (210, 80, 290, 120)  # where the stub diagnosis relocates it
CORRECTED_POINT = (250, 100)  # safe_click_point(CORRECTED_BBOX, siblings=[])

# Marker colors (BGR) the OCR stub keys off.
_MENU_BGR = (1, 99, 199)
_DONE_BGR = (13, 217, 255)
_DIALOG_BGR = (199, 9, 9)


def _base_frame() -> np.ndarray:
    img = np.full((200, 300, 3), (230, 225, 220), dtype=np.uint8)
    img[0:24, 0:300] = (180, 120, 60)  # title bar
    img[24:40, 0:300] = (210, 205, 200)  # menu strip
    img[28:36, 10:60] = _MENU_BGR  # stable OCR anchor ("MENU")
    img[80:120, 100:200] = (60, 180, 60)  # believed target button
    img[80:120, 210:290] = (160, 160, 240)  # actual target (neighbor) button
    img[140:190, 10:290] = (250, 250, 250)  # list panel
    for y in (150, 162, 174):
        img[y : y + 6, 16:200] = (120, 120, 120)
    return img


def _wrong_frame(x1: int = 20, x2: int = 80) -> np.ndarray:
    """Far small response (bottom row highlight) — outside the x0.5 target
    neighborhood, well under the 10% screen-scale exemption."""
    img = _base_frame()
    img[160:178, x1:x2] = (0, 0, 220)
    return img


def _done_frame() -> np.ndarray:
    img = _base_frame()
    img[90:110, 220:280] = _DONE_BGR  # DONE marker on the neighbor button
    return img


def _dialog_frame() -> np.ndarray:
    """Small accidental dialog (5000 px = 8.3% < the 10% exemption) far from
    the target neighborhood, carrying its own OCR text."""
    img = _base_frame()
    img[145:195, 10:110] = (180, 210, 255)
    img[150:160, 20:100] = _DIALOG_BGR
    return img


class _MarkerOcrStub:
    """RapidOCR-shaped stub keyed off exact marker colors."""

    _MARKERS = (("MENU", _MENU_BGR), ("DIALOG", _DIALOG_BGR), ("DONE", _DONE_BGR))

    def __call__(self, img):
        if img is None or getattr(img, "size", 0) == 0:
            return None, None
        out = []
        for text, bgr in self._MARKERS:
            mask = (
                (img[:, :, 0] == bgr[0])
                & (img[:, :, 1] == bgr[1])
                & (img[:, :, 2] == bgr[2])
            )
            if bool(mask.any()):
                ys, xs = np.nonzero(mask)
                x1, y1 = int(xs.min()), int(ys.min())
                x2, y2 = int(xs.max()) + 1, int(ys.max()) + 1
                box = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
                out.append([box, text, 0.95])
        return out, None


@pytest.fixture()
def _marker_ocr():
    ocr_engine.set_engine(_MarkerOcrStub())
    yield
    ocr_engine.reset_engine()


class UndoScriptedVNC(ClickScriptedVNC):
    """ClickScriptedVNC whose Esc dismisses the current post-click frame:
    after an escape (and until the next click) captures return
    ``restore_frame`` — the pre-click page, as a real dialog dismiss would."""

    def __init__(self, pre_frames, post_frames, restore_frame: np.ndarray):
        super().__init__(pre_frames, post_frames)
        self.restore_frame = restore_frame
        self._escaped_at_clicks: int | None = None

    async def send_key(self, key: str):
        await super().send_key(key)
        if key == "escape":
            self._escaped_at_clicks = len(self.clicks)

    async def capture_screen(self) -> bytes:
        if self.clicks and self._escaped_at_clicks == len(self.clicks):
            self.call_log.append("capture")
            ok, buf = cv2.imencode(".png", self.restore_frame)
            return buf.tobytes()
        return await super().capture_screen()


def _pm_config(app_config: AppConfig, *, enabled: bool = True) -> AppConfig:
    """Scenario-22 config: shared recovery table, stale guard stays off
    (harness artifact, see conftest), post-mortem tier toggled explicitly."""
    cfg = app_config.model_copy(deep=True)
    cfg.agent.wrong_target_postmortem.enabled = enabled
    return cfg


def _diagnosis_json(**overrides) -> str:
    data = {
        "clicked_element": "list row",
        "target_found": True,
        "corrected_bbox": list(CORRECTED_BBOX),
        "coordinate_space": "pixel",
        "confidence": 0.9,
        "reason": "actual click hit the list; intended button is to the right",
    }
    data.update(overrides)
    return json.dumps(data)


def _stub_client(**overrides) -> StubPostmortemClient:
    return StubPostmortemClient(
        [StubPostmortemClient.envelope(_diagnosis_json(**overrides))]
    )


def _case(*, max_retries: int = 3) -> TestCase:
    return TestCase(
        id="e2e-022",
        name="click postmortem correction",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="s1",
                name="click confirm",
                intent="click the confirm button",
                max_retries=max_retries,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="text_appears", value="DONE")],
                ),
            )
        ],
    )


async def _memory_elements(runtime) -> list:
    memory = runtime.memory
    assert memory is not None
    elements = []
    for page in await memory.repo.list_pages():
        elements.extend(await memory.repo.list_elements(page.page_id))
    return elements


def _wt_attempts(iteration):
    return [
        a
        for a in iteration.recovery_attempts
        if a.failure_type == FailureType.WRONG_TARGET
    ]


# ---------------------------------------------------------------- case (a)


@pytest.mark.asyncio
async def test_postmortem_corrects_misplaced_click_and_writes_memory(
    tmp_path: Path, app_config, _marker_ocr
):
    """US-A: wrong click → postmortem diagnosis → corrected re-click through
    the unchanged verification loop → memory write-back + full audit."""
    drv = ClickScriptedVNC([_base_frame()], [_wrong_frame(), _done_frame()])
    grounder = SeqGrounder([_grounding(TARGET_BBOX)])
    pm = _stub_client()
    runtime, drv = await build_runtime(
        tmp_path,
        _pm_config(app_config),
        driver=drv,
        planner=_click_planner(idempotent=True),
        grounder=grounder,
        ocr_enabled=True,
        postmortem_client=pm,
    )
    ctx = await runtime.run(_case())

    assert ctx.test_run.status == "passed"
    it1, it2 = ctx.test_run.steps[0].iterations

    # Iteration 1: WRONG_TARGET upgrade + postmortem selection (first choice).
    assert it1.failure_attribution == FailureType.WRONG_TARGET.value
    assert it1.verification_result.status == "failed"
    assert it1.verification_result.reason.startswith("wrong_target:")
    attempts = _wt_attempts(it1)
    assert [a.strategy for a in attempts] == ["postmortem"]
    assert attempts[0].resolved is True

    # The diagnosis audit + artifacts (FR-010).
    audit = it1.postmortem
    assert audit is not None and audit.outcome == "corrected"
    assert audit.clicked_element == "list row"
    assert audit.corrected_bbox == CORRECTED_BBOX
    assert audit.corrected_click_point == CORRECTED_POINT
    assert audit.undo_performed is False
    annotated = cv2.imread(audit.annotated_image_ref)
    assert annotated is not None and annotated.shape == (200, 300, 3)
    assert Path(audit.request_ref).is_file() and Path(audit.response_ref).is_file()
    assert "escape" not in drv.keys  # same page — no undo
    assert len(pm.calls) == 1
    assert pm.calls[0].resolution == (300, 200)

    # Iteration 2: corrected click — grounder skipped, geometry from the plan.
    assert len(grounder.calls) == 1
    assert it2.postmortem is None
    ea = it2.executable_action
    assert ea is not None and ea.coordinates == CORRECTED_POINT
    assert ea.target_region.as_tuple() == CORRECTED_BBOX
    assert it2.verification_result.status == "passed"
    assert len(drv.clicks) == 2 and drv.clicks[1] == CORRECTED_POINT

    # Telemetry: one actual postmortem model call + one skipped grounder call.
    pm_audits = [
        a for a in ctx.test_run.model_call_audits if a.model_role == "postmortem"
    ]
    assert len(pm_audits) == 1 and pm_audits[0].outcome == "actual"
    skipped = [
        a
        for a in ctx.test_run.model_call_audits
        if a.outcome == "skipped" and a.reason == "postmortem_correction"
    ]
    assert len(skipped) == 1 and skipped[0].model_role == "grounder"
    pm_calls = [
        e
        for e in ctx.test_run.counter_events
        if e.kind == "model_call" and e.payload.get("model_role") == "postmortem"
    ]
    assert len(pm_calls) == 1

    # Memory write-back (FR-006): the corrected region became the memory of
    # the target label, through the existing 015 write path.
    elements = await _memory_elements(runtime)
    btn = [e for e in elements if e.target_label == "btn"]
    assert len(btn) == 1
    assert tuple(btn[0].bbox) == CORRECTED_BBOX
    assert btn[0].success_count == 1

    # The upgraded attribution still reaches the experience stream (022).
    upgraded = [
        e for e in runtime.experience.written if e.failure_type == "wrong_target"
    ]
    assert len(upgraded) == 1


# ---------------------------------------------------------------- case (b)


@pytest.mark.asyncio
async def test_dialog_is_undone_then_diagnosis_corrects(
    tmp_path: Path, app_config, _marker_ocr
):
    """US-B: the wrong click opened a small dialog → fingerprint mismatch →
    one Esc undo restores the page → diagnosis proceeds → corrected click."""
    drv = UndoScriptedVNC(
        [_base_frame()], [_dialog_frame(), _done_frame()], _base_frame()
    )
    pm = _stub_client()
    runtime, drv = await build_runtime(
        tmp_path,
        _pm_config(app_config),
        driver=drv,
        planner=_click_planner(idempotent=True),
        grounder=SeqGrounder([_grounding(TARGET_BBOX)]),
        ocr_enabled=True,
        postmortem_client=pm,
    )
    ctx = await runtime.run(_case())

    assert ctx.test_run.status == "passed"
    it1, it2 = ctx.test_run.steps[0].iterations

    assert it1.failure_attribution == FailureType.WRONG_TARGET.value
    audit = it1.postmortem
    assert audit is not None and audit.outcome == "corrected"
    assert audit.undo_performed is True
    assert audit.undo_restored_page is True
    # Exactly one safe Esc (FR-003) — and nothing destructive.
    assert drv.keys.count("escape") == 1
    assert drv.hotkeys == []
    undo_attempts = [
        a for a in it1.recovery_attempts if a.strategy == "postmortem_undo"
    ]
    assert len(undo_attempts) == 1 and undo_attempts[0].resolved is True
    assert [a.strategy for a in _wt_attempts(it1)] == ["postmortem", "postmortem_undo"]

    assert len(pm.calls) == 1
    assert it2.verification_result.status == "passed"
    assert drv.clicks[1] == CORRECTED_POINT
    elements = await _memory_elements(runtime)
    assert any(
        e.target_label == "btn" and tuple(e.bbox) == CORRECTED_BBOX for e in elements
    )


# ---------------------------------------------------------------- case (c)


@pytest.mark.asyncio
async def test_low_confidence_falls_back_to_recapture_chain(
    tmp_path: Path, app_config, _marker_ocr
):
    """US-C: the diagnosis is refused (low confidence) → the same iteration
    falls back to the 022 chain (recapture) and the step recovers the
    pre-023 way (re-observe + re-ground)."""
    drv = ClickScriptedVNC([_base_frame()], [_wrong_frame(), _done_frame()])
    grounder = SeqGrounder([_grounding(TARGET_BBOX)])
    pm = _stub_client(confidence=0.4)
    runtime, drv = await build_runtime(
        tmp_path,
        _pm_config(app_config),
        driver=drv,
        planner=_click_planner(idempotent=True),
        grounder=grounder,
        ocr_enabled=True,
        postmortem_client=pm,
    )
    ctx = await runtime.run(_case())

    assert ctx.test_run.status == "passed"
    it1, it2 = ctx.test_run.steps[0].iterations

    audit = it1.postmortem
    assert audit is not None and audit.outcome == "low_confidence"
    assert audit.confidence == 0.4
    assert audit.corrected_bbox == CORRECTED_BBOX  # evidence kept for review
    attempts = _wt_attempts(it1)
    assert [a.strategy for a in attempts] == ["postmortem", "recapture"]
    assert attempts[0].resolved is False  # downgraded by the refused diagnosis
    assert attempts[1].resolved is True

    # No correction plan: iteration 2 went through the normal re-ground path.
    assert len(pm.calls) == 1
    assert len(grounder.calls) == 2
    assert it2.executable_action.target_region.as_tuple() == TARGET_BBOX
    assert it2.verification_result.status == "passed"


# ---------------------------------------------------------------- case (d)


@pytest.mark.asyncio
async def test_disabled_postmortem_matches_022_baseline(
    tmp_path: Path, app_config, _marker_ocr
):
    """FR-007: wrong_target_postmortem.enabled=false → routing, attempts and
    report fields are the 022 baseline; the diagnosis client is never called."""
    drv = ClickScriptedVNC([_base_frame()], [_wrong_frame(), _done_frame()])
    grounder = SeqGrounder([_grounding(TARGET_BBOX)])
    pm = _stub_client()
    runtime, drv = await build_runtime(
        tmp_path,
        _pm_config(app_config, enabled=False),
        driver=drv,
        planner=_click_planner(idempotent=True),
        grounder=grounder,
        ocr_enabled=True,
        postmortem_client=pm,
    )
    ctx = await runtime.run(_case())

    assert ctx.test_run.status == "passed"
    it1, it2 = ctx.test_run.steps[0].iterations
    assert it1.failure_attribution == FailureType.WRONG_TARGET.value
    assert [a.strategy for a in _wt_attempts(it1)] == ["recapture"]
    assert it1.postmortem is None and it2.postmortem is None
    assert pm.calls == []
    assert all(a.model_role != "postmortem" for a in ctx.test_run.model_call_audits)
    assert len(grounder.calls) == 2  # normal re-ground recovery
    assert len(drv.clicks) == 2


# ---------------------------------------------------------------- case (e)


@pytest.mark.asyncio
async def test_failed_corrected_click_never_rediagnoses(
    tmp_path: Path, app_config, _marker_ocr
):
    """FR-008: the corrected re-click fails verification again → no second
    diagnosis in the step (per-step cap 1); the run terminates through the
    existing budgets."""
    drv = ClickScriptedVNC(
        [_base_frame()], [_wrong_frame(), _wrong_frame(x1=220, x2=280)]
    )
    pm = _stub_client()
    runtime, drv = await build_runtime(
        tmp_path,
        _pm_config(app_config),
        driver=drv,
        planner=_click_planner(idempotent=True),
        grounder=SeqGrounder([_grounding(TARGET_BBOX)]),
        ocr_enabled=True,
        postmortem_client=pm,
    )
    # max_retries=1: the postmortem consumes the shared recovery budget and
    # reserves the corrected-click iteration; after that retry fails there is
    # no budget left — the step terminates without a second diagnosis.
    ctx = await runtime.run(_case(max_retries=1))

    assert ctx.test_run.status == "failed"
    iterations = ctx.test_run.steps[0].iterations
    assert len(iterations) == 2
    it1, it2 = iterations

    # Iteration 1 diagnosed once; iteration 2 applied the corrected click.
    assert it1.postmortem is not None and it1.postmortem.outcome == "corrected"
    assert it2.executable_action.coordinates == CORRECTED_POINT
    assert it2.verification_result.status == "failed"
    assert it2.failure_attribution == FailureType.WRONG_TARGET.value

    # No second diagnosis anywhere (SC-001e): one model call total, and the
    # second WRONG_TARGET routing never selected postmortem again.
    assert len(pm.calls) == 1
    assert it2.postmortem is None
    assert [a.strategy for a in _wt_attempts(it2)] == ["recapture"]
    pm_audits = [
        a for a in ctx.test_run.model_call_audits if a.model_role == "postmortem"
    ]
    assert len(pm_audits) == 1
