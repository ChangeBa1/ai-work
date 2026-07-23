"""T070: end-to-end AgentRuntime wiring of focus path (not RecoveryEngine-direct)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.e2e.conftest import FakeVNC, build_runtime
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import (
    VerificationCondition,
    VerificationSpec,
    WaitResult,
)
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.provider import (
    PlannerRequest,
    PlannerResponse,
    VisionUnderstandingRequest,
    VisionUnderstandingResponse,
)


def _screen(
    frame_id: str,
    ocr: list[str],
    *,
    extra_ocr: list[str] | None = None,
) -> StructuredScreen:
    """Ordered anchors: search → qty → レジ袋 (top-to-bottom)."""
    texts = list(ocr) + list(extra_ocr or [])
    items = [
        OCRItem(
            text=t,
            bbox=(10, 10 + i * 40, 100, 35 + i * 40),
            confidence=0.95,
        )
        for i, t in enumerate(texts)
    ]
    return StructuredScreen(
        frame_id=frame_id,
        resolution=(400, 300),
        captured_at=datetime.now(UTC),
        ocr_items=items,
        image_path="",  # no real files — ActionEffect uses OCR diff only
        changed_since_last=False,
    )


class SequencePlanner:
    """First plan → click search; subsequent plans → click レジ袋."""

    def __init__(self) -> None:
        self.plan_calls = 0
        self.describe_calls = 0
        self.search = SemanticAction(
            action_id="focus-search",
            intent="click search field",
            action_type="click",
            target=TargetDescription(role="button", text="search"),
            action_kind="idempotent",
        )
        self.bag = SemanticAction(
            action_id="click-bag",
            intent="click レジ袋",
            action_type="click",
            target=TargetDescription(role="button", text="レジ袋"),
            action_kind="non_idempotent",
        )

    async def plan(self, request: PlannerRequest) -> PlannerResponse:
        self.plan_calls += 1
        action = self.search if self.plan_calls == 1 else self.bag
        return PlannerResponse(
            task_completed_hint=False,
            semantic_action=action,
            needs_more_observation=False,
        )

    async def describe_screen(
        self, request: VisionUnderstandingRequest
    ) -> VisionUnderstandingResponse:
        self.describe_calls += 1
        if request.mode == "describe":
            return VisionUnderstandingResponse(
                mode="describe",
                description="stub",
                confidence=0.5,
                model_name="stub",
            )
        return VisionUnderstandingResponse(
            mode="answer_question",
            answer="uncertain",
            confidence=0.4,
            reason="stub",
            model_name="stub",
        )


class ScriptedPipeline:
    """Returns prebuilt StructuredScreen instances in order (offline, no OCR/VNC)."""

    def __init__(self, screens: list[StructuredScreen]) -> None:
        self.screens = screens
        self.i = 0

    async def observe(
        self, *, step_id: str | None = None, capture_source: str = "observation", roi=None
    ) -> StructuredScreen:
        s = self.screens[min(self.i, len(self.screens) - 1)]
        self.i += 1
        return s


class InstantStability:
    async def wait_stable(self, *, step_id: str | None = None, roi=None, early_exit=None):
        return WaitResult(waited_ms=1, stable=True, end_reason="stable")


@pytest.mark.asyncio
async def test_runtime_switch_to_keyboard_sends_derived_tab_sequence(
    tmp_path: Path, app_config
):
    """
    Full AgentRuntime.run() path:

    1) click search lands (expected_effect) → remember_focus("search")
    2) click bag no_effect → second_candidate
    3) click bag no_effect → switch_to_keyboard builds structural path search→bag
    4) next resolve emits ExecutableAction.keys == derived tab_sequence (not OCR mouse)

    Proves T070 wiring — not just RecoveryEngine unit tests.
    """
    anchors = ["search", "qty", "レジ袋"]
    # Per iteration: before + after observe (stability is mocked, no reobserve on failed)
    # iter0 search: before base, after + "ok"  → expected_effect
    # iter1 bag: before base, after base → no_effect → second_candidate
    # iter2 bag: before base, after base → no_effect → switch_to_keyboard
    # iter3 bag: before base, after base → keyboard tabs executed
    base = _screen("base", anchors)
    after_search = _screen("after_search", anchors, extra_ocr=["ok"])
    screens = [
        base,
        after_search,  # iter0
        base,
        base,  # iter1
        base,
        base,  # iter2
        base,
        base,  # iter3
        base,
        base,  # slack for any extra observe
    ]

    planner = SequencePlanner()
    grounder = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(10, 90, 100, 120),
                    coordinate_space="pixel",
                    confidence=0.95,
                    reason="bag",
                )
            ],
            model_name="stub",
        )
    )
    case = TestCase(
        id="focus-wiring",
        name="focus-wiring",
        target_id="win10-test-01",
        mode="explicit",
        steps=[
            TestStep(
                id="reach-bag-via-focus",
                name="reach bag",
                intent="click レジ袋 via focus recovery",
                max_retries=4,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[
                        VerificationCondition(type="text_appears", value="NEVER_MATCH")
                    ],
                ),
            )
        ],
    )

    runtime, drv = await build_runtime(
        tmp_path,
        app_config,
        driver=FakeVNC(),
        planner=planner,
        grounder=grounder,
    )
    runtime.pipeline = ScriptedPipeline(screens)  # type: ignore[assignment]
    runtime.stability = InstantStability()  # type: ignore[assignment]

    execute_log: list = []
    original_execute = runtime.executor.execute

    async def tracked(executable):
        execute_log.append(executable)
        return await original_execute(executable)

    runtime.executor.execute = tracked  # type: ignore[method-assign]

    ctx = await runtime.run(case)
    step = ctx.test_run.steps[0]
    assert len(step.iterations) >= 3

    # Wiring self-check: known focus must have been populated during the run
    assert runtime.recovery._last_known_focus_hint, (
        "remember_focus never wired — _last_known_focus_hint still empty"
    )

    # At least one keyboard executable with a multi-tab derived sequence
    # (search index 0 → レジ袋 index 2 ⇒ ["tab","tab"])
    # Prefer exact derived sequence
    derived = [k for k in (list(e.keys) for e in execute_log if e.method == "keyboard") if k]
    assert ["tab", "tab"] in derived, (
        f"expected derived tab_sequence ['tab','tab'] from structural anchors; "
        f"keyboard keys seen={derived}; mouse_ops="
        f"{[e for e in execute_log if e.method == 'mouse']}; "
        f"focus_path={runtime.recovery.focus_path}; "
        f"prefer_keyboard={runtime.recovery.prefer_keyboard}; "
        f"known_focus={runtime.recovery._last_known_focus_hint!r}; "
        f"strategies={[a.strategy for it in step.iterations for a in it.recovery_attempts]}"
    )

    # Confirm it was not a blind single-tab without path evidence
    for e in execute_log:
        if e.method == "keyboard" and e.keys == ["tab"]:
            # Single tab only allowed if focus_path said so
            assert runtime.recovery.focus_path is not None
