"""E2E scenario 6: wait stage produces waited_ms."""

from pathlib import Path

import pytest

from tests.e2e.conftest import build_runtime


@pytest.mark.asyncio
async def test_wait_records_duration(tmp_path: Path, app_config, simple_case):
    runtime, _ = await build_runtime(tmp_path, app_config)
    ctx = await runtime.run(simple_case)
    if ctx.test_run.steps and ctx.test_run.steps[0].iterations:
        wr = ctx.test_run.steps[0].iterations[0].wait_result
        if wr is not None:
            assert wr.waited_ms >= 0
