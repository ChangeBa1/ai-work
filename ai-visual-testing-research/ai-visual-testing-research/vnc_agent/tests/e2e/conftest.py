"""E2E helpers: offline runtime with fake VNC + stub models."""

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


class FakeVNC:
    def __init__(self, frames: list[np.ndarray] | None = None):
        base = np.zeros((200, 300, 3), dtype=np.uint8)
        base[80:120, 100:200] = (0, 200, 0)
        self.frames = frames or [base]
        self.i = 0
        self._connected = False
        self.clicks: list[tuple[int, int]] = []
        self.keys: list[str] = []
        self.hotkeys: list[list[str]] = []
        self.texts: list[str] = []
        # Feature 005 (T009): a single shared ordered log of capture/send
        # calls, used to prove no capture happens *between* individual key
        # sends within a batch (FR-003/SC-002) without depending on any
        # particular total call count (see StabilityEngine's own polling).
        self.call_log: list[str] = []
        self._w, self._h = self.frames[0].shape[1], self.frames[0].shape[0]

    @property
    def resolution(self):
        return (self._w, self._h)

    @property
    def connected(self):
        return self._connected

    async def connect(self):
        self._connected = True

    async def disconnect(self):
        self._connected = False

    async def reconnect(self):
        self._connected = True

    async def capture_screen(self) -> bytes:
        self.call_log.append("capture")
        f = self.frames[min(self.i, len(self.frames) - 1)]
        if self.i < len(self.frames) - 1:
            self.i += 1
        ok, buf = cv2.imencode(".png", f)
        return buf.tobytes()

    async def capture_region(self, x, y, w, h) -> bytes:
        return await self.capture_screen()

    async def send_key(self, key: str):
        self.call_log.append(f"key:{key}")
        self.keys.append(key)

    async def send_hotkey(self, keys: list[str]):
        self.hotkeys.append(list(keys))

    async def send_text(self, text: str):
        self.texts.append(text)

    async def mouse_move(self, x, y):
        pass

    async def click(self, x, y, button=1):
        self.clicks.append((x, y))

    async def double_click(self, x, y):
        self.clicks.append((x, y))

    async def right_click(self, x, y):
        self.clicks.append((x, y))

    async def scroll(self, x, y, direction, amount=3):
        pass

    async def drag(self, x1, y1, x2, y2, button=1):
        pass

    async def release_modifiers(self):
        pass


@pytest.fixture
def app_config() -> AppConfig:
    recovery = {
        ft: RecoveryPolicy(
            max_retries=2,
            cooldown_ms=0,
            consumes_global_retry_budget=True,
            allows_action_path_change=ft
            in {
                "target_not_found",
                "grounding_low_confidence",
                "action_no_effect",
                "focus_error",
                "input_method_error",
                "timeout",
            },
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
    return AppConfig(
        agent=AgentConfig(recovery=recovery),
        models=ModelsConfig(),
        vnc_targets=VNCTargetsConfig(
            targets=[VNCTarget(id="win10-test-01", host="127.0.0.1")]
        ),
        config_dir="config",
    )


@pytest.fixture
def simple_case() -> TestCase:
    return TestCase(
        id="e2e-simple",
        name="e2e",
        target_id="win10-test-01",
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


async def build_runtime(
    tmp_path: Path,
    app_config: AppConfig,
    *,
    driver: FakeVNC | None = None,
    planner: StubPlanner | None = None,
    grounder: StubGrounder | None = None,
) -> tuple[AgentRuntime, FakeVNC]:
    drv = driver or FakeVNC()
    pl = planner or StubPlanner(
        action=SemanticAction(
            action_id="a1",
            intent="escape",
            action_type="press_key",
            keys=["escape"],
        )
    )
    gr = grounder or StubGrounder(
        GroundingResult(
            found=True,
            candidates=[
                GroundingCandidate(
                    bbox=(100, 80, 200, 120),
                    coordinate_space="pixel",
                    confidence=0.9,
                    reason="ok",
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
        capture_service,
        planner=pl,
        ocr_enabled=False,
        template_enabled=False,
        vision_fallback=False,
    )
    stability = StabilityEngine(
        capture_service,
        min_delay_ms=5,
        max_delay_ms=50,
        capture_interval_ms=5,
        stable_frame_count=2,
        pixel_diff_threshold=0.5,  # lenient for fake static frames
    )
    # Force wait to finish quickly with stable end
    runtime = AgentRuntime(
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
    return runtime, drv
