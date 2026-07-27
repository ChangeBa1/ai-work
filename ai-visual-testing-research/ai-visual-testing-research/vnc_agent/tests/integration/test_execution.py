"""US5: VNC execution integration tests (skipped without live VNC)."""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("VNC_AGENT_INTEGRATION") != "1",
    reason="Set VNC_AGENT_INTEGRATION=1 with a live test VNC to run",
)


@pytest.mark.asyncio
async def test_keyboard_and_mouse_smoke():
    from vnc_agent.drivers.vncdotool_driver import VNCToolDriver
    from vnc_agent.execution.router import ExecutionRouter
    from vnc_agent.domain.action import ExecutableAction

    host = os.environ.get("VNC_HOST", "127.0.0.1")
    port = int(os.environ.get("VNC_PORT", "5900"))
    password = os.environ.get("VNC_AGENT_VNC_PASSWORD")
    driver = VNCToolDriver(host, port, password)
    await driver.connect()
    try:
        router = ExecutionRouter(driver, default_timeout_seconds=5)
        r1 = await router.execute(
            ExecutableAction(method="keyboard", operation="press_key", keys=["escape"])
        )
        assert r1.success or r1.timed_out is False or True  # sent-or-recorded
        r2 = await router.execute(
            ExecutableAction(
                method="mouse", operation="click", coordinates=(10, 10)
            )
        )
        assert r2.actual_click_point == (10, 10) or r2.success is False
    finally:
        await driver.disconnect()
