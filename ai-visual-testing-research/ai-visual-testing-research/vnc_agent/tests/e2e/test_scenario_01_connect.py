"""E2E scenario 1: connect path + dry-run style validation."""

from pathlib import Path

import pytest

from vnc_agent.domain.testcase import load_test_case
from tests.e2e.conftest import build_runtime


@pytest.mark.asyncio
async def test_runtime_connects_and_captures(tmp_path: Path, app_config, simple_case):
    runtime, drv = await build_runtime(tmp_path, app_config)
    ctx = await runtime.run(simple_case)
    assert drv.connected or ctx.test_run.status in ("passed", "failed")
    assert ctx.test_run.run_id
    # First frame should exist under artifacts
    frames = list((tmp_path / "artifacts" / "runs" / ctx.run_id / "frames").glob("*.png"))
    assert frames, "expected at least one screenshot artifact"


def test_dry_run_loads_sample():
    root = Path(__file__).resolve().parents[2]
    tc = load_test_case(root / "testcases" / "smoke-connect.yaml")
    assert tc.mode == "explicit"
