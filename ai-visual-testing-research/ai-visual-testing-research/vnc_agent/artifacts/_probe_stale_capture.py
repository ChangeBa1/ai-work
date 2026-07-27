"""Probe whether vncdotool capture returns stale pixels within one session.

1) Connect, capture A
2) Wait ~65s (clock on POS should tick)
3) capture B via captureScreen
4) capture C via refreshScreen + captureScreen
5) Compare hashes and crop clock region mean
Also try click bag and recapture after delays.
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from vnc_agent.drivers.vncdotool_driver import VNCToolDriver
from vnc_agent.perception.screenshot import decode_capture


async def main() -> None:
    out = Path("artifacts/probe_stale")
    out.mkdir(parents=True, exist_ok=True)
    d = VNCToolDriver(
        host="192.168.8.134",
        port=5900,
        password=os.environ.get("VNC_AGENT_VNC_PASSWORD"),
        connect_timeout_seconds=30,
        reconnect_attempts=1,
    )
    await d.connect()
    print("connected", d.resolution)

    def save(name: str, raw: bytes) -> str:
        (out / name).write_bytes(raw)
        dec = decode_capture(raw)
        assert dec.content_hash
        return dec.content_hash

    h0 = save("t0.png", await d.capture_screen())
    print("t0", h0[:20])

    # Force second immediate capture
    h1 = save("t0b.png", await d.capture_screen())
    print("t0b same_as_t0", h1 == h0, h1[:20])

    # Click bag twice (user said 2 bags were bought via interaction)
    print("click bag x2")
    for _ in range(2):
        await d.click(337, 679)
        await asyncio.sleep(0.3)

    for label, delay in [("after1s", 1.0), ("after3s", 2.0), ("after6s", 3.0)]:
        await asyncio.sleep(delay if label == "after1s" else delay)
        # cumulative is messy; explicit absolute waits from click done above
    # redo with absolute sleeps from click
    await asyncio.sleep(1.0)
    h_a1 = save("after_click_1s.png", await d.capture_screen())
    print("after_click_1s same_as_t0", h_a1 == h0, h_a1[:20])
    await asyncio.sleep(2.0)
    h_a3 = save("after_click_3s.png", await d.capture_screen())
    print("after_click_3s same_as_t0", h_a3 == h0, h_a3[:20])

    # Explicit refreshScreen on underlying protocol if available
    def force_refresh_capture(path: Path) -> bytes:
        client = d._client
        # Threaded proxy: call refresh then capture
        client.refreshScreen(False)
        client.captureScreen(str(path))
        return path.read_bytes()

    p = out / "forced_refresh.png"
    raw_f = await asyncio.to_thread(force_refresh_capture, p)
    h_f = save("forced_refresh_copy.png", raw_f)
    print("forced_refresh same_as_t0", h_f == h0, h_f[:20])

    # Wait for clock tick (~70s)
    print("waiting 70s for clock change...")
    await asyncio.sleep(70)
    h_w = save("after_70s.png", await d.capture_screen())
    print("after_70s same_as_t0", h_w == h0, h_w[:20])

    # New connection capture (baseline of truth)
    await d.disconnect()
    d2 = VNCToolDriver(
        host="192.168.8.134",
        port=5900,
        password=os.environ.get("VNC_AGENT_VNC_PASSWORD"),
        connect_timeout_seconds=30,
        reconnect_attempts=1,
    )
    await d2.connect()
    h_new = save("reconnect.png", await d2.capture_screen())
    print("reconnect same_as_t0", h_new == h0, h_new[:20])
    print("reconnect same_as_after70s", h_new == h_w, h_new[:20])
    await d2.disconnect()
    print("done", out)


if __name__ == "__main__":
    asyncio.run(main())
