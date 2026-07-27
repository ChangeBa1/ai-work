"""Feature 020 (wait-tuning): tuned wait defaults + 2-sample stable path.

FR-001/FR-002 pin the tuned defaults in both sources of truth
(config/agent.yaml and config.py::WaitConfig); FR-003 proves that with the
new default ``stable_frame_count=2`` a static screen is declared stable after
exactly 2 logical samples (= 1 unchanged comparison); FR-004 proves the
``max(2, ...)`` constructor floor still forbids zero-comparison stability.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml

from vnc_agent.config import WaitConfig
from vnc_agent.domain.run import TestRun
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.perception.stability import StabilityEngine
from vnc_agent.storage.artifact_store import ArtifactStore

REPO_AGENT_YAML = Path(__file__).parents[2] / "config" / "agent.yaml"


class StaticDriver:
    """Serves the same encoded frame forever (instantly-stable screen)."""

    def __init__(self) -> None:
        frame = np.zeros((60, 60, 3), dtype=np.uint8)
        frame[10:30, 10:30] = 128
        ok, buf = cv2.imencode(".png", frame)
        assert ok
        self._png = buf.tobytes()

    @property
    def resolution(self):
        return (60, 60)

    async def capture_screen(self) -> bytes:
        return self._png

    async def capture_region(self, x, y, w, h) -> bytes:
        return await self.capture_screen()


def test_waitconfig_defaults_are_tuned():
    """FR-002 / SC-003: code defaults match the tuned values."""
    cfg = WaitConfig()
    assert cfg.min_delay_ms == 200
    assert cfg.capture_interval_ms == 300
    assert cfg.stable_frame_count == 2
    # deliberately unchanged (FR-001)
    assert cfg.max_delay_ms == 20000
    assert cfg.pixel_diff_threshold == 0.02


def test_shipped_agent_yaml_wait_values_are_tuned():
    """FR-001 / SC-003: shipped yaml stays in lockstep with WaitConfig."""
    data = yaml.safe_load(REPO_AGENT_YAML.read_text(encoding="utf-8"))
    wait = data["wait"]
    assert wait["min_delay_ms"] == 200
    assert wait["capture_interval_ms"] == 300
    assert wait["stable_frame_count"] == 2
    assert wait["max_delay_ms"] == 20000
    assert wait["pixel_diff_threshold"] == 0.02


@pytest.mark.asyncio
async def test_default_stable_frame_count_stable_after_one_comparison(tmp_path: Path):
    """FR-003 / SC-002: with the new default stable_frame_count=2 a static
    screen is stable after exactly 2 logical samples — the 1st sample has no
    local comparison basis, the 2nd yields the single unchanged comparison
    required by ``consecutive_stable >= stable_frame_count - 1``.

    Timers are scaled down for CI; the decision path under test depends only
    on stable_frame_count, which is taken from the shipped WaitConfig default.
    """
    svc = FrameCaptureService(
        StaticDriver(),
        run_id="r1",
        vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    eng = StabilityEngine(
        svc,
        min_delay_ms=1,
        max_delay_ms=5000,
        capture_interval_ms=1,
        stable_frame_count=WaitConfig().stable_frame_count,
    )
    result = await eng.wait_stable(step_id="s1")
    assert result.stable is True
    assert result.end_reason == "stable"
    # exactly 2 captures were needed: sample1 (no basis) + sample2 (1 stable)
    assert svc._sequence == 2


def test_constructor_floor_forbids_zero_comparison_stability(tmp_path: Path):
    """FR-004: stable_frame_count below 2 is clamped to 2."""
    svc = FrameCaptureService(
        StaticDriver(),
        run_id="r1",
        vnc_session_id="s1",
        test_run=TestRun(run_id="r1", test_case_id="tc"),
        artifact_store=ArtifactStore(tmp_path),
    )
    assert StabilityEngine(svc, stable_frame_count=1).stable_frame_count == 2
    assert StabilityEngine(svc, stable_frame_count=0).stable_frame_count == 2
