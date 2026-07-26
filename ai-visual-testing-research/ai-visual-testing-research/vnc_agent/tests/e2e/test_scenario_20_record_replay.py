"""E2E scenario 20 (feature 016): record-replay.

a (SC-001): a fully-passed exploration run auto-generates a versioned
ReplayScript (steps/templates/fingerprints/anchors persisted).

b (SC-002): a mode:"replay" run happy path — ZERO planner calls, ZERO
grounder calls, every step independently verified, run passed, locate
method audited.

c (SC-003): a moved button — direct locate path fails verification, the
grounder fallback succeeds, a pending ReplayPatch is stored and the original
script step is byte-identical; run passed.

d (SC-003): the fallback fails too — run failed and the failure reason names
the ReplayStep.

e (SC-004): replay disabled / no recorded script — fail fast before any VNC
connection (ReplayUnavailableError).
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
from vnc_agent.runtime.exceptions import ReplayUnavailableError
from vnc_agent.runtime.telemetry import derive_performance_summary
from vnc_agent.storage.database import init_db, make_engine, make_session_factory
from vnc_agent.storage.repositories import ReplayRepository

# Geometry on the 300x200 fake screen (same conventions as scenario 19).
_ANCHOR_BOX = [[100, 80], [160, 80], [160, 96], [100, 96]]
_DONE_BOX = [[10, 150], [60, 150], [60, 166], [10, 166]]
_TARGET_BBOX = (150, 85, 170, 95)  # recorded location
_MOVED_BBOX = (200, 120, 220, 130)  # moved location (outside the search window)
_EXPECTED_CLICK = (160, 90)
_MOVED_CLICK = (210, 125)


def _texture(w: int = 20, h: int = 10) -> np.ndarray:
    xx, yy = np.meshgrid(np.arange(w), np.arange(h))
    pat = ((xx * 23 + yy * 57) % 256).astype(np.uint8)
    return np.stack([pat, 255 - pat, pat // 2], axis=-1)


def _base_frame(button_bbox) -> np.ndarray:
    base = np.zeros((200, 300, 3), dtype=np.uint8)
    base[80:120, 100:200] = (0, 200, 0)
    x1, y1, x2, y2 = button_bbox
    base[y1:y2, x1:x2] = _texture(x2 - x1, y2 - y1)
    return base


def _with_done(frame: np.ndarray) -> np.ndarray:
    out = frame.copy()
    out[150:166, 10:60] = (255, 255, 255)
    return out


class ClickAwareVNC(FakeVNC):
    """Deterministic driver: the DONE confirmation appears only after a
    click actually lands inside the (possibly moved) button bbox."""

    def __init__(self, button_bbox) -> None:
        base = _base_frame(button_bbox)
        super().__init__(frames=[base])
        self._base = base
        self._done = _with_done(base)
        self._button = button_bbox
        self._hit = False

    async def click(self, x, y, button=1):
        await super().click(x, y, button)
        x1, y1, x2, y2 = self._button
        if x1 <= x < x2 and y1 <= y < y2:
            self._hit = True

    async def capture_screen(self) -> bytes:
        self.call_log.append("capture")
        frame = self._done if self._hit else self._base
        ok, buf = cv2.imencode(".png", frame)
        return buf.tobytes()


class _StubOcr:
    """Reads 'TOTAL' always and 'DONE' when the confirmation box is white."""

    def __call__(self, img):
        items = [[_ANCHOR_BOX, "TOTAL", 0.9]]
        if img[155, 30].min() > 200:
            items.append([_DONE_BOX, "DONE", 0.9])
        return items, None


class CountingGrounder:
    def __init__(self, bbox=_TARGET_BBOX, found: bool = True) -> None:
        self.calls: list[GroundingRequest] = []
        self.bbox = bbox
        self.found = found

    async def ground(self, request: GroundingRequest) -> GroundingResult:
        self.calls.append(request)
        if not self.found:
            return GroundingResult(found=False, candidates=[], model_name="counting")
        return GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=self.bbox,
                    coordinate_space="pixel",
                    confidence=0.9,
                    reason="scripted",
                )
            ],
            model_name="counting",
        )


def _case(mode: str = "explicit") -> TestCase:
    return TestCase(
        id="e2e-replay",
        name="record replay",
        target_id="win10-test-01",
        mode=mode,
        steps=[
            TestStep(
                id="s1",
                name="click OK",
                intent="click the OK button",
                max_retries=2,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="text_appears", value="DONE")],
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


async def _replay_repo(tmp_path: Path) -> ReplayRepository:
    engine = make_engine(str(tmp_path / "test.db"))
    await init_db(engine)
    return ReplayRepository(make_session_factory(engine))


async def _run(tmp_path, app_config, *, mode: str, button_bbox=_TARGET_BBOX, grounder=None):
    grounder = grounder or CountingGrounder()
    planner = _planner()
    runtime, drv = await build_runtime(
        tmp_path,
        app_config,
        driver=ClickAwareVNC(button_bbox),
        planner=planner,
        grounder=grounder,
        ocr_enabled=True,
    )
    ctx = await runtime.run(_case(mode=mode))
    return ctx, planner, grounder, drv


@pytest.fixture(autouse=True)
def _content_ocr():
    ocr_engine.set_engine(_StubOcr())
    yield
    ocr_engine.reset_engine()


@pytest.mark.asyncio
async def test_a_exploration_success_generates_script(tmp_path: Path, app_config):
    """SC-001: fully-passed exploration -> version-1 script with content."""
    ctx, planner, grounder, drv = await _run(tmp_path, app_config, mode="explicit")
    assert ctx.test_run.status == "passed"
    assert len(grounder.calls) == 1  # exploration grounding happened once

    repo = await _replay_repo(tmp_path)
    scripts = await repo.list_scripts("e2e-replay")
    assert len(scripts) == 1
    script = scripts[0]
    assert script.version == 1
    assert script.source_run_id == ctx.run_id
    assert [s.step_id for s in script.steps] == ["s1"]

    step = script.steps[0]
    assert step.preferred_method == "mouse"
    assert step.bbox == _TARGET_BBOX
    assert step.normalized_bbox == (150 / 300, 85 / 200, 170 / 300, 95 / 200)
    assert "TOTAL" in step.anchor_texts
    assert step.expected.conditions[0].type == "text_appears"
    assert step.expected.conditions[0].value == "DONE"
    assert step.page_fingerprint.resolution == (300, 200)
    assert step.target_template_path is not None
    assert Path(step.target_template_path).is_file()
    assert Path(step.target_template_path).is_relative_to(tmp_path / "artifacts")

    # A second passing exploration appends version 2 and keeps version 1.
    ctx2, _, _, _ = await _run(tmp_path, app_config, mode="explicit")
    assert ctx2.test_run.status == "passed"
    versions = [s.version for s in await repo.list_scripts("e2e-replay")]
    assert versions == [1, 2]


@pytest.mark.asyncio
async def test_b_replay_happy_path_zero_model_calls(tmp_path: Path, app_config):
    """SC-002: replay happy path — zero planner AND zero grounder calls."""
    ctx1, _, grounder1, _ = await _run(tmp_path, app_config, mode="explicit")
    assert ctx1.test_run.status == "passed"

    ctx, planner, grounder, drv = await _run(tmp_path, app_config, mode="replay")
    assert ctx.test_run.status == "passed"

    # Red lines: neither model role was invoked at all.
    assert planner.plan_calls == 0
    assert grounder.calls == []
    assert _EXPECTED_CLICK in drv.clicks

    # Telemetry-level assertion (spec FR-007): no planner/grounder model_call.
    role_calls = [
        e.payload.get("model_role")
        for e in ctx.test_run.counter_events
        if e.kind == "model_call"
    ]
    assert "planner" not in role_calls
    assert "grounder" not in role_calls
    summary = derive_performance_summary(ctx.test_run)
    assert summary.model_calls.get("planner", 0) == 0
    assert summary.model_calls.get("grounder", 0) == 0

    # Per-step verification still ran and passed (Constitution IV).
    iterations = [it for s in ctx.test_run.steps for it in s.iterations]
    assert iterations
    assert all(
        it.verification_result is not None and it.verification_result.status == "passed"
        for it in iterations
    )

    # Locate-method audit: the recorded template matched directly.
    audits = [it.replay_audit for it in iterations if it.replay_audit is not None]
    assert len(audits) == 1
    audit = audits[0]
    assert audit.locate_method == "template"
    assert audit.script_version == 1
    assert audit.template_score is not None and audit.template_score >= 0.85
    assert audit.page_similarity >= 0.88
    assert audit.patch_id is None

    # Counter + performance summary.
    replayed = [e for e in ctx.test_run.counter_events if e.kind == "replay_step_replayed"]
    assert len(replayed) == 1
    assert replayed[0].payload["method"] == "template"
    assert summary.replay_locate_methods == {"template": 1}
    assert summary.replay_patch_count == 0

    # Statistics-only update on the stored step.
    repo = await _replay_repo(tmp_path)
    script = await repo.get_latest_script("e2e-replay")
    assert script is not None
    stored = await repo.get_step(script.steps[0].replay_step_id)
    assert stored is not None and stored.success_count == 1


@pytest.mark.asyncio
async def test_c_moved_button_fallback_generates_pending_patch(tmp_path: Path, app_config):
    """SC-003: direct path fails -> grounder fallback passes -> pending patch,
    original script untouched, run passed."""
    ctx1, _, _, _ = await _run(tmp_path, app_config, mode="explicit")
    assert ctx1.test_run.status == "passed"

    repo = await _replay_repo(tmp_path)
    script_before = await repo.get_latest_script("e2e-replay")
    assert script_before is not None
    step_before = script_before.steps[0]

    # The button moved: template cannot match in the recorded neighborhood
    # and the recorded-location click has no effect.
    ctx, planner, grounder, drv = await _run(
        tmp_path,
        app_config,
        mode="replay",
        button_bbox=_MOVED_BBOX,
        grounder=CountingGrounder(bbox=_MOVED_BBOX),
    )
    assert ctx.test_run.status == "passed"
    assert planner.plan_calls == 0  # replay never plans (design §21.3)
    assert len(grounder.calls) == 1  # exactly one fallback grounding
    assert _MOVED_CLICK in drv.clicks

    # Pending patch stored with old/new targets; step row byte-identical
    # except the statistics counters (ADR-005).
    patches = await repo.list_patches("e2e-replay", status="pending")
    assert len(patches) == 1
    patch = patches[0]
    assert patch.replay_step_id == step_before.replay_step_id
    assert patch.status == "pending"
    assert patch.old_target["bbox"] == list(_TARGET_BBOX)
    assert patch.new_target["bbox"] == list(_MOVED_BBOX)
    assert patch.before_image and patch.after_image

    stored = await repo.get_step(step_before.replay_step_id)
    assert stored is not None
    assert stored.bbox == step_before.bbox
    assert stored.normalized_bbox == step_before.normalized_bbox
    assert stored.target_template_path == step_before.target_template_path
    assert stored.anchors == step_before.anchors
    assert stored.semantic_action == step_before.semantic_action
    assert stored.expected == step_before.expected

    # Audit trail: final method is fallback_grounding and carries the patch id.
    iterations = [it for s in ctx.test_run.steps for it in s.iterations]
    audits = [it.replay_audit for it in iterations if it.replay_audit is not None]
    assert audits[-1].locate_method == "fallback_grounding"
    assert audits[-1].patch_id == patch.patch_id
    events = [e.kind for e in ctx.test_run.counter_events]
    assert "replay_patch_generated" in events
    summary = derive_performance_summary(ctx.test_run)
    assert summary.replay_patch_count == 1
    assert summary.replay_locate_methods.get("fallback_grounding") == 1
    # The one grounder call is a real, audited model call.
    assert summary.model_calls.get("grounder") == 1


@pytest.mark.asyncio
async def test_d_fallback_failure_fails_run_and_names_step(tmp_path: Path, app_config):
    """SC-003: fallback also fails -> run failed, ReplayStep named."""
    ctx1, _, _, _ = await _run(tmp_path, app_config, mode="explicit")
    assert ctx1.test_run.status == "passed"

    repo = await _replay_repo(tmp_path)
    script = await repo.get_latest_script("e2e-replay")
    assert script is not None
    replay_step_id = script.steps[0].replay_step_id

    ctx, planner, grounder, _ = await _run(
        tmp_path,
        app_config,
        mode="replay",
        button_bbox=_MOVED_BBOX,
        grounder=CountingGrounder(found=False),
    )
    assert ctx.test_run.status == "failed"
    assert planner.plan_calls == 0
    assert len(grounder.calls) == 1

    failed_step = ctx.test_run.steps[-1]
    assert failed_step.final_status == "failed"
    assert failed_step.failure_reason is not None
    assert "replay step failed" in failed_step.failure_reason
    assert replay_step_id in failed_step.failure_reason
    assert "step_id=s1" in failed_step.failure_reason

    # No patch on a failed fallback.
    assert await repo.list_patches("e2e-replay", status="pending") == []


@pytest.mark.asyncio
async def test_e_replay_unavailable_fails_fast(tmp_path: Path, app_config):
    """SC-004: no script recorded / replay disabled -> fail fast, no VNC."""
    # e1: no script exists yet.
    grounder = CountingGrounder()
    runtime, drv = await build_runtime(
        tmp_path,
        app_config,
        driver=ClickAwareVNC(_TARGET_BBOX),
        planner=_planner(),
        grounder=grounder,
        ocr_enabled=True,
    )
    with pytest.raises(ReplayUnavailableError, match="no replay script"):
        await runtime.run(_case(mode="replay"))
    assert not drv.connected  # failed before any VNC connection

    # e2: script exists but replay.enabled=false.
    ctx1, _, _, _ = await _run(tmp_path, app_config, mode="explicit")
    assert ctx1.test_run.status == "passed"
    app_config.agent.replay.enabled = False
    runtime2, drv2 = await build_runtime(
        tmp_path,
        app_config,
        driver=ClickAwareVNC(_TARGET_BBOX),
        planner=_planner(),
        grounder=CountingGrounder(),
        ocr_enabled=True,
    )
    with pytest.raises(ReplayUnavailableError, match="replay.enabled is false"):
        await runtime2.run(_case(mode="replay"))
    assert not drv2.connected
    app_config.agent.replay.enabled = True


@pytest.mark.asyncio
async def test_replay_disabled_keeps_exploration_baseline(tmp_path: Path, app_config):
    """FR-013: replay.enabled=false -> exploration behaves like pre-016
    (no script rows, no replay artifacts, no replay telemetry)."""
    app_config.agent.replay.enabled = False
    ctx, planner, grounder, _ = await _run(tmp_path, app_config, mode="explicit")
    assert ctx.test_run.status == "passed"
    assert planner.plan_calls == 1
    assert len(grounder.calls) == 1

    repo = await _replay_repo(tmp_path)
    assert await repo.list_scripts("e2e-replay") == []
    assert not (tmp_path / "artifacts" / "replay").exists()
    assert not [
        e
        for e in ctx.test_run.counter_events
        if e.kind in ("replay_step_replayed", "replay_patch_generated")
    ]
    summary = derive_performance_summary(ctx.test_run)
    assert summary.replay_locate_methods == {}
    assert summary.replay_patch_count == 0
    app_config.agent.replay.enabled = True
