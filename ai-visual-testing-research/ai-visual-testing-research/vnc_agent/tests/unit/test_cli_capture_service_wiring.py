"""Phase 3 (T017 RED / T024 GREEN): execute assembles exactly one shared
FrameCaptureService for ObservationPipeline + StabilityEngine; the offline
report path never creates/connects a capture service and never grows
TestRun.frames.
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
    VNCTarget,
    VNCTargetsConfig,
)
from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.run import TestRun
from vnc_agent.domain.testcase import TestCase, TestStep
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.models.mimo_grounder import StubGrounder
from vnc_agent.models.planner_client import StubPlanner


class FakeVNCDriver:
    """Signature-compatible stand-in for VNCToolDriver's constructor."""

    def __init__(self, *, host, port, password, connect_timeout_seconds, reconnect_attempts):
        img = np.zeros((40, 40, 3), dtype=np.uint8)
        ok, buf = cv2.imencode(".png", img)
        self._bytes = buf.tobytes()
        self._connected = False

    @property
    def resolution(self):
        return (40, 40)

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
        return self._bytes

    async def capture_region(self, x, y, w, h) -> bytes:
        return self._bytes

    async def send_key(self, key):
        pass

    async def send_hotkey(self, keys):
        pass

    async def send_text(self, text):
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


def _app_config() -> AppConfig:
    ft_list = [
        "vnc_connect_failed", "vnc_disconnected", "black_screen", "page_not_stable",
        "target_not_found", "grounding_low_confidence", "action_no_effect",
        "focus_error", "input_method_error", "unexpected_dialog",
        "verification_failed", "timeout",
    ]
    recovery = {
        ft: RecoveryPolicy(
            max_retries=1, cooldown_ms=0, consumes_global_retry_budget=True,
            allows_action_path_change=False, requires_strong_model=False,
            requires_human_confirmation=False,
        )
        for ft in ft_list
    }
    return AppConfig(
        agent=AgentConfig(
            recovery=recovery,
            wait={"min_delay_ms": 1, "max_delay_ms": 20, "capture_interval_ms": 1,
                  "stable_frame_count": 2, "pixel_diff_threshold": 0.5},
        ),
        models=ModelsConfig(),
        vnc_targets=VNCTargetsConfig(targets=[VNCTarget(id="t1", host="127.0.0.1")]),
        config_dir="config",
    )


def _case() -> TestCase:
    return TestCase(
        id="wiring-check", name="wiring-check", target_id="t1", mode="explicit",
        steps=[
            TestStep(
                id="s1", name="step1", intent="press escape", max_retries=1,
                expected=VerificationSpec(
                    operator="all", conditions=[VerificationCondition(type="screen_changed")],
                ),
            )
        ],
    )


@pytest.mark.asyncio
async def test_execute_assembles_exactly_one_shared_capture_service(tmp_path: Path, monkeypatch):
    from vnc_agent import api as api_pkg  # noqa: F401
    from vnc_agent.api import cli
    from vnc_agent.perception import screenshot as shot

    monkeypatch.setattr(
        "vnc_agent.drivers.vncdotool_driver.VNCToolDriver", FakeVNCDriver
    )
    monkeypatch.setattr(
        "vnc_agent.models.provider.build_planner",
        lambda models_cfg: StubPlanner(
            action=SemanticAction(
                action_id="a1", intent="esc", action_type="press_key", keys=["escape"]
            )
        ),
    )
    monkeypatch.setattr(
        "vnc_agent.models.provider.build_grounder", lambda models_cfg: StubGrounder()
    )

    construct_count = {"n": 0}
    real_init = shot.FrameCaptureService.__init__

    def counting_init(self, *args, **kwargs):
        construct_count["n"] += 1
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(shot.FrameCaptureService, "__init__", counting_init)

    cfg = _app_config()
    cfg.agent.artifacts.root_dir = str(tmp_path / "artifacts")
    cfg.agent.artifacts.db_path = str(tmp_path / "test.db")
    case = _case()

    await cli._execute(case, cfg, json_only=True)

    assert construct_count["n"] == 1, "execute must assemble exactly one FrameCaptureService"


@pytest.mark.asyncio
async def test_offline_report_path_never_creates_capture_service_or_grows_frames(
    tmp_path: Path, monkeypatch
):
    from vnc_agent.api import cli
    from vnc_agent.perception import screenshot as shot
    from vnc_agent.storage.database import init_db, make_engine, make_session_factory
    from vnc_agent.storage.repositories import RunRepository

    construct_count = {"n": 0}
    real_init = shot.FrameCaptureService.__init__

    def counting_init(self, *args, **kwargs):
        construct_count["n"] += 1
        return real_init(self, *args, **kwargs)

    monkeypatch.setattr(shot.FrameCaptureService, "__init__", counting_init)

    db_path = tmp_path / "report.db"
    engine = make_engine(str(db_path))
    await init_db(engine)
    repo = RunRepository(make_session_factory(engine))
    run_id = str(uuid.uuid4())
    run = TestRun(run_id=run_id, test_case_id="tc", status="passed")
    await repo.save_run(run)

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "agent.yaml").write_text(
        f"artifacts:\n  root_dir: {tmp_path / 'artifacts'!s}\n  db_path: {db_path!s}\n",
        encoding="utf-8",
    )

    code = await cli._report(run_id, "json", config_dir)
    assert code == cli.EXIT_PASSED
    assert construct_count["n"] == 0, "report-only path must never create a FrameCaptureService"

    reloaded = await repo.get_run(run_id)
    assert reloaded is not None
    assert reloaded.frames == []
