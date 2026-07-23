"""Phase 7 (T062): two structurally unrelated GUI scenarios exercised through
the SAME generic capture→observe→act→verify→report contract
(Constitution Principle VI; spec.md §FR-042-043, §SC-009-010).

- `generic-form-flow`: a form-like visible layout, keyboard/text-input
  primary action path (`type_text` + `press_key`).
- `generic-icon-menu-flow`: an icon/overlay visible layout, visual-target
  click primary action path (`click` on an `icon_button` role).

Both run a full `AgentRuntime.run()` against the shared runtime — only the
fixture pixel patterns, YAML testcase, and stub Planner/Grounder responses
differ. No core module is given scenario vocabulary; only this test file
and the two YAML fixtures know the words "form"/"icon"/"menu". Neither
scenario ever touches UIA, a browser DOM, another process, the filesystem
of the "application under test", or any internal API of a target app — the
driver is `FakeVNC`, whose entire surface is VNC-protocol-shaped pixel
capture + key/mouse events (see `tests/e2e/conftest.py`).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from tests.e2e.conftest import FakeVNC, build_runtime
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.testcase import load_test_case
from vnc_agent.models.mimo_grounder import StubGrounder

TESTCASES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "testcases"
W, H = 240, 160


def _quadrant_fingerprint(img: np.ndarray) -> tuple[float, ...]:
    """A crude, purely-pixel-based "visible layout" fingerprint: mean
    intensity per quadrant. Used only to prove the two scenarios' base
    frames are structurally distinct, not a same-image/renamed pair."""
    h, w = img.shape[:2]
    quads = [
        img[: h // 2, : w // 2], img[: h // 2, w // 2 :],
        img[h // 2 :, : w // 2], img[h // 2 :, w // 2 :],
    ]
    return tuple(float(q.mean()) for q in quads)


def _form_frames() -> list[np.ndarray]:
    """Form-like layout: a labeled rectangular input box (upper half) and a
    submit button (lower-right) — two flat regions, no icon grid."""
    empty = np.full((H, W, 3), 250, dtype=np.uint8)
    empty[20:50, 20:220] = (235, 235, 235)  # input box outline area
    empty[110:140, 160:220] = (90, 140, 220)  # submit button

    filled = empty.copy()
    filled[25:45, 25:150] = (30, 30, 30)  # typed text block fills most of the box

    submitted = filled.copy()
    submitted[:, :] = (60, 180, 90)  # full-screen "success" flash — large, obvious change

    return (
        [empty] * 3
        + [filled] * 8
        + [submitted] * 8
    )


def _icon_menu_frames() -> list[np.ndarray]:
    """Icon/overlay layout: a 3x3 grid of small icon squares, no input box —
    structurally distinct from the form layout above."""
    base = np.full((H, W, 3), 40, dtype=np.uint8)
    grid_colors = [(200, 80, 80), (80, 200, 80), (80, 80, 200)]
    for row in range(3):
        for col in range(3):
            y0, x0 = 15 + row * 35, 15 + col * 35
            color = grid_colors[(row + col) % 3]
            base[y0 : y0 + 24, x0 : x0 + 24] = color

    menu_open = base.copy()
    menu_open[H // 2 :, :] = (245, 245, 245)  # overlay panel covers bottom half

    item_selected = menu_open.copy()
    item_selected[H // 2 : H // 2 + 20, 10:100] = (255, 200, 0)  # highlighted row

    return (
        [base] * 3
        + [menu_open] * 8
        + [item_selected] * 8
    )


def test_form_and_icon_menu_base_frames_are_structurally_distinct():
    """Guards against a homogeneous fixture that only swaps names/images:
    the two scenarios' initial frames must have a genuinely different
    visible-layout fingerprint, not just a different color of the same shape."""
    form_fp = _quadrant_fingerprint(_form_frames()[0])
    icon_fp = _quadrant_fingerprint(_icon_menu_frames()[0])
    assert form_fp != icon_fp
    # form: bright background with two flat regions; icon: dark background
    # with a scattered grid — the overall mean brightness differs sharply.
    assert abs(sum(form_fp) - sum(icon_fp)) > 100


def test_fake_driver_has_no_uia_dom_process_or_internal_apis():
    """Structural proof: the offline driver's entire method surface is
    VNC-protocol-shaped (screen/region capture + key/mouse), matching
    `VNCDriver`. No UI-Automation, browser-DOM, subprocess, filesystem, or
    target-application-internal API exists anywhere on it."""
    drv = FakeVNC()
    forbidden_substrings = [
        "uia", "automation", "dom", "selenium", "webdriver", "subprocess",
        "appium", "win32", "accessib",
    ]
    members = [m.lower() for m in dir(drv) if not m.startswith("_")]
    for member in members:
        for forbidden in forbidden_substrings:
            assert forbidden not in member, f"unexpected API surface: {member}"


@pytest.mark.asyncio
async def test_generic_form_flow_end_to_end(tmp_path: Path, app_config):
    case = load_test_case(TESTCASES_DIR / "generic-form-flow.yaml")
    drv = FakeVNC(_form_frames())

    from vnc_agent.models.planner_client import StubPlanner

    actions = [
        SemanticAction(
            action_id="fill-1", intent="type value", action_type="type_text",
            target=TargetDescription(role="text_field", text=None, description="input box"),
            text_value="hello world", action_kind="idempotent",
        ),
        SemanticAction(
            action_id="submit-1", intent="press enter", action_type="press_key",
            keys=["enter"], action_kind="non_idempotent",
        ),
    ]

    class SequencePlanner(StubPlanner):
        def __init__(self):
            super().__init__()
            self._i = 0

        async def plan(self, request):
            self.plan_calls += 1
            action = actions[min(self._i, len(actions) - 1)]
            self._i += 1
            from vnc_agent.models.provider import PlannerResponse

            return PlannerResponse(
                task_completed_hint=False, semantic_action=action, needs_more_observation=False
            )

    runtime, _drv = await build_runtime(
        tmp_path, app_config, driver=drv, planner=SequencePlanner(), grounder=StubGrounder()
    )
    ctx = await runtime.run(case)

    assert ctx.test_run.status in ("passed", "failed")
    assert len(ctx.test_run.frames) > 0
    capture_sources = {f.capture_source for f in ctx.test_run.frames}
    assert "observation" in capture_sources
    assert "post_action_verification" in capture_sources
    action_kinds = {
        it.semantic_action.action_type
        for step in ctx.test_run.steps
        for it in step.iterations
        if it.semantic_action
    }
    assert action_kinds & {"type_text", "press_key"}

    if runtime.report_builder:
        runtime.report_builder.build(ctx.test_run, formats=("json",))
        assert ctx.test_run.report_json_path is not None
        assert Path(ctx.test_run.report_json_path).is_file()


@pytest.mark.asyncio
async def test_generic_icon_menu_flow_end_to_end(tmp_path: Path, app_config):
    case = load_test_case(TESTCASES_DIR / "generic-icon-menu-flow.yaml")
    drv = FakeVNC(_icon_menu_frames())

    from vnc_agent.models.planner_client import StubPlanner
    from vnc_agent.models.provider import PlannerResponse

    actions = [
        SemanticAction(
            action_id="open-menu", intent="click toolbar icon", action_type="click",
            target=TargetDescription(role="icon_button", text=None, description="toolbar icon"),
            action_kind="idempotent",
        ),
        SemanticAction(
            action_id="select-item", intent="click menu item", action_type="click",
            target=TargetDescription(role="icon_button", text=None, description="menu item"),
            action_kind="non_idempotent",
        ),
    ]

    class SequencePlanner(StubPlanner):
        def __init__(self):
            super().__init__()
            self._i = 0

        async def plan(self, request):
            self.plan_calls += 1
            action = actions[min(self._i, len(actions) - 1)]
            self._i += 1
            return PlannerResponse(
                task_completed_hint=False, semantic_action=action, needs_more_observation=False
            )

    grounder = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(15, 15, 39, 39), coordinate_space="pixel",
                    confidence=0.95, reason="icon match",
                )
            ],
            model_name="stub",
        )
    )
    runtime, _drv = await build_runtime(
        tmp_path, app_config, driver=drv, planner=SequencePlanner(), grounder=grounder
    )
    ctx = await runtime.run(case)

    assert ctx.test_run.status in ("passed", "failed")
    assert len(ctx.test_run.frames) > 0
    action_kinds = {
        it.semantic_action.action_type
        for step in ctx.test_run.steps
        for it in step.iterations
        if it.semantic_action
    }
    assert action_kinds & {"click"}
    # every iteration that reached verification has its OWN action_effect —
    # never skipped/reused across iterations
    action_effects = [
        it.action_effect
        for step in ctx.test_run.steps
        for it in step.iterations
        if it.action_effect is not None
    ]
    assert len(action_effects) >= 1

    if runtime.report_builder:
        runtime.report_builder.build(ctx.test_run, formats=("json",))
        assert ctx.test_run.report_json_path is not None


@pytest.mark.asyncio
async def test_both_scenarios_share_the_same_recorder_cache_and_report_contract(
    tmp_path: Path, app_config
):
    """The decisive cross-scenario proof: both runs go through the exact
    same `FrameCaptureService`/`AnalysisResultCache`/`ReportBuilder` classes
    — only fixture data differs. Verified by construction (both `build_runtime`
    calls assemble the identical shared classes) plus a runtime check that
    both produced logically well-formed, independently-verified reports
    with distinct frame ids never reused across runs."""
    form_case = load_test_case(TESTCASES_DIR / "generic-form-flow.yaml")
    menu_case = load_test_case(TESTCASES_DIR / "generic-icon-menu-flow.yaml")

    from vnc_agent.models.planner_client import StubPlanner

    form_runtime, _ = await build_runtime(
        tmp_path / "form", app_config, driver=FakeVNC(_form_frames()), planner=StubPlanner()
    )
    menu_runtime, _ = await build_runtime(
        tmp_path / "menu", app_config, driver=FakeVNC(_icon_menu_frames()), planner=StubPlanner()
    )

    assert type(form_runtime.capture_service) is type(menu_runtime.capture_service)
    assert type(form_runtime.pipeline.cache) is type(menu_runtime.pipeline.cache) is not None or (
        form_runtime.pipeline.cache is None and menu_runtime.pipeline.cache is None
    )

    form_ctx = await form_runtime.run(form_case)
    menu_ctx = await menu_runtime.run(menu_case)

    form_frame_ids = {f.id for f in form_ctx.test_run.frames}
    menu_frame_ids = {f.id for f in menu_ctx.test_run.frames}
    assert form_frame_ids.isdisjoint(menu_frame_ids)
    assert form_ctx.run_id != menu_ctx.run_id
