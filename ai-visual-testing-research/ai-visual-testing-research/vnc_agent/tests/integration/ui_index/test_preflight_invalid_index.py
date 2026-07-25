"""T041: preflight fail-fast for an explicitly-configured invalid UI index
(contracts/ui-index-consumer-interfaces.md §9, FR-012).

Uses the same offline stub-driver/stub-model harness pattern as
`tests/e2e/conftest.py` (FakeVNC + StubPlanner + StubGrounder) so this test
never touches a real VNC target, but builds its own minimal AgentRuntime
here to keep this integration test self-contained.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import cv2
import numpy as np
import pytest

from vnc_agent.config import (
    AgentConfig,
    AppConfig,
    ModelsConfig,
    RecoveryPolicy,
    UiIndexConfig,
    VNCTarget,
    VNCTargetsConfig,
)
from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner
from vnc_agent.perception.pipeline import ObservationPipeline
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.perception.stability import StabilityEngine
from vnc_agent.reporting.report_builder import ReportBuilder
from vnc_agent.runtime.agent_runtime import AgentRuntime
from vnc_agent.storage.artifact_store import ArtifactStore
from vnc_agent.storage.database import init_db, make_engine, make_session_factory
from vnc_agent.storage.repositories import RunRepository
from vnc_agent.ui_index.repository import UiIndexValidationError

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ui_index"
VALID_MINIMAL = FIXTURES / "valid_minimal"
INVALID = FIXTURES / "invalid"


class FakeVNC:
    """Minimal fake VNC driver that records whether connect() was ever called."""

    def __init__(self) -> None:
        base = np.zeros((200, 300, 3), dtype=np.uint8)
        base[80:120, 100:200] = (0, 200, 0)
        self.frames = [base]
        self.i = 0
        self._connected = False
        self.connect_calls = 0

    @property
    def resolution(self):
        return (300, 200)

    @property
    def connected(self):
        return self._connected

    async def connect(self):
        self.connect_calls += 1
        self._connected = True

    async def disconnect(self):
        self._connected = False

    async def reconnect(self):
        self._connected = True

    async def capture_screen(self) -> bytes:
        f = self.frames[min(self.i, len(self.frames) - 1)]
        ok, buf = cv2.imencode(".png", f)
        return buf.tobytes()

    async def capture_region(self, x, y, w, h) -> bytes:
        return await self.capture_screen()

    async def send_key(self, key: str):
        pass

    async def send_hotkey(self, keys: list[str]):
        pass

    async def send_text(self, text: str):
        pass

    async def mouse_move(self, x, y):
        pass

    async def click(self, x, y, button=1):
        pass

    async def double_click(self, x, y):
        pass

    async def right_click(self, x, y):
        pass

    async def scroll(self, x, y, direction, amount=3):
        pass

    async def drag(self, x1, y1, x2, y2, button=1):
        pass

    async def release_modifiers(self):
        pass


def _make_app_config(*, ui_index_bundle_dir: str | None) -> AppConfig:
    recovery = {
        ft: RecoveryPolicy(
            max_retries=1,
            cooldown_ms=0,
            consumes_global_retry_budget=True,
            allows_action_path_change=False,
            requires_strong_model=False,
            requires_human_confirmation=False,
        )
        for ft in [
            "vnc_connect_failed",
            "vnc_disconnected",
            "black_screen",
            "page_not_stable",
            "target_not_found",
            "grounding_low_confidence",
            "action_no_effect",
            "focus_error",
            "input_method_error",
            "unexpected_dialog",
            "verification_failed",
            "timeout",
        ]
    }
    agent_cfg = AgentConfig(
        recovery=recovery,
        ui_index=UiIndexConfig(bundle_dir=ui_index_bundle_dir),
    )
    return AppConfig(
        agent=agent_cfg,
        models=ModelsConfig(),
        vnc_targets=VNCTargetsConfig(targets=[VNCTarget(id="t1", host="127.0.0.1")]),
        config_dir="config",
    )


def _simple_case() -> TestCase:
    return TestCase(
        id="preflight-case",
        name="preflight",
        target_id="t1",
        mode="explicit",
        steps=[
            TestStep(
                id="s1",
                name="step1",
                intent="press escape",
                max_retries=1,
                expected=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="screen_changed")],
                ),
            )
        ],
    )


async def _build_runtime(
    tmp_path: Path, app_config: AppConfig, drv: FakeVNC
) -> AgentRuntime:
    pl = StubPlanner(
        action=SemanticAction(
            action_id="a1", intent="escape", action_type="press_key", keys=["escape"]
        )
    )
    gr = StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(100, 80, 200, 120), coordinate_space="pixel", confidence=0.9, reason="ok"
                )
            ],
            model_name="stub",
        )
    )
    engine = make_engine(str(tmp_path / "test.db"))
    await init_db(engine)
    repo = RunRepository(make_session_factory(engine))
    store = ArtifactStore(tmp_path / "artifacts")
    capture_service = FrameCaptureService(
        drv,
        run_id=str(uuid.uuid4()),
        vnc_session_id=str(uuid.uuid4()),
        test_run=None,
        artifact_store=store,
    )
    pipeline = ObservationPipeline(
        capture_service, planner=pl, ocr_enabled=False, template_enabled=False, vision_fallback=False
    )
    stability = StabilityEngine(
        capture_service,
        min_delay_ms=5,
        max_delay_ms=50,
        capture_interval_ms=5,
        stable_frame_count=2,
        pixel_diff_threshold=0.5,
    )
    return AgentRuntime(
        config=app_config,
        driver=drv,
        planner=pl,
        grounder=gr,
        pipeline=pipeline,
        stability=stability,
        capture_service=capture_service,
        artifact_store=store,
        repo=repo,
        report_builder=ReportBuilder(store),
    )


@pytest.mark.parametrize(
    "fixture_name",
    [
        "unsupported_version",
        "missing_file",
        "jsonl_syntax_error",
        "duplicate_id",
        "missing_reference",
        "invalid_coordinates",
        "invalid_confidence",
        "checksum_mismatch",
        "path_traversal",
    ],
)
async def test_invalid_index_aborts_before_first_step_and_before_vnc_connect(
    tmp_path: Path, fixture_name: str
):
    drv = FakeVNC()
    app_config = _make_app_config(ui_index_bundle_dir=str(INVALID / fixture_name))
    runtime = await _build_runtime(tmp_path, app_config, drv)
    case = _simple_case()

    with pytest.raises(UiIndexValidationError) as excinfo:
        await runtime.run(case)

    assert excinfo.value.report.ok is False
    assert len(excinfo.value.report.issues) > 0
    # Fail-fast MUST happen strictly before the driver ever connects — no
    # VNC session, no observation, no planner/grounder/executor call.
    assert drv.connect_calls == 0
    assert drv.connected is False


async def test_no_index_configured_proceeds_past_preflight(tmp_path: Path):
    from vnc_agent.logging_setup import configure_logging

    configure_logging()
    drv = FakeVNC()
    app_config = _make_app_config(ui_index_bundle_dir=None)
    runtime = await _build_runtime(tmp_path, app_config, drv)
    case = _simple_case()

    ctx = await runtime.run(case)

    assert drv.connect_calls == 1
    assert ctx.test_run.status in {"passed", "failed"}
    assert len(ctx.test_run.steps) >= 1


async def test_valid_index_configured_proceeds_past_preflight(tmp_path: Path):
    from vnc_agent.logging_setup import configure_logging

    configure_logging()
    drv = FakeVNC()
    app_config = _make_app_config(ui_index_bundle_dir=str(VALID_MINIMAL))
    runtime = await _build_runtime(tmp_path, app_config, drv)
    case = _simple_case()

    ctx = await runtime.run(case)

    assert drv.connect_calls == 1
    assert ctx.test_run.status in {"passed", "failed"}
    assert len(ctx.test_run.steps) >= 1
