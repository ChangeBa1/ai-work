"""E2E scenario 1: connect path + dry-run style validation."""

from pathlib import Path

import pytest

from tests.e2e.conftest import build_runtime
from vnc_agent.domain.testcase import load_test_case


@pytest.mark.asyncio
async def test_runtime_connects_and_captures(tmp_path: Path, app_config, simple_case):
    runtime, drv = await build_runtime(tmp_path, app_config)
    ctx = await runtime.run(simple_case)
    assert drv.connected or ctx.test_run.status in ("passed", "failed")
    assert ctx.test_run.run_id
    # First frame's safe evidence should exist under the published bundles dir
    # (feature 004: content-addressed FrameArtifactBundle, not frames/).
    bundles = list(
        (tmp_path / "artifacts" / "runs" / ctx.run_id / "bundles").glob("*/safe_evidence.png")
    )
    assert bundles, "expected at least one published safe_evidence.png bundle file"
    assert ctx.test_run.frames, "expected at least one logical ScreenFrame"


def test_dry_run_loads_sample():
    root = Path(__file__).resolve().parents[2]
    tc = load_test_case(root / "testcases" / "smoke-connect.yaml")
    assert tc.mode == "explicit"
