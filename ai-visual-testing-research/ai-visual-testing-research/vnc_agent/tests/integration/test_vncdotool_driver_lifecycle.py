"""Regression coverage for vncdotool's process-global Twisted reactor."""

import pytest

from vnc_agent.drivers.vncdotool_driver import VNCToolDriver


@pytest.mark.asyncio
async def test_reconnect_keeps_reactor_alive(monkeypatch: pytest.MonkeyPatch) -> None:
    driver = VNCToolDriver("test-host", reconnect_attempts=1)
    calls: list[tuple[str, bool | None]] = []

    def fake_disconnect(*, shutdown_reactor: bool = True) -> None:
        calls.append(("disconnect", shutdown_reactor))

    def fake_connect() -> None:
        calls.append(("connect", None))

    monkeypatch.setattr(driver, "_sync_disconnect", fake_disconnect)
    monkeypatch.setattr(driver, "_sync_connect", fake_connect)

    await driver.reconnect()

    assert calls == [("disconnect", False), ("connect", None)]


@pytest.mark.asyncio
async def test_final_disconnect_shuts_down_reactor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = VNCToolDriver("test-host")
    shutdown_flags: list[bool] = []

    def fake_disconnect(*, shutdown_reactor: bool = True) -> None:
        shutdown_flags.append(shutdown_reactor)

    monkeypatch.setattr(driver, "_sync_disconnect", fake_disconnect)

    await driver.disconnect()

    assert shutdown_flags == [True]
