"""vncdotool-backed VNC driver with asyncio bridge (research.md §1)."""

from __future__ import annotations

import asyncio
import io
from typing import Any

from vnc_agent.drivers.key_mapping import normalize_hotkey, normalize_key
from vnc_agent.runtime.exceptions import VNCConnectionError, VNCDisconnectedError


class VNCToolDriver:
    """
    Async wrapper around vncdotool's blocking API.

    Uses asyncio.to_thread for each blocking call so the Agent Runtime event loop
    is not stalled (research.md §1).
    """

    def __init__(
        self,
        host: str,
        port: int = 5900,
        password: str | None = None,
        *,
        connect_timeout_seconds: int = 15,
        reconnect_attempts: int = 3,
    ) -> None:
        self.host = host
        self.port = port
        self.password = password
        self.connect_timeout_seconds = connect_timeout_seconds
        self.reconnect_attempts = reconnect_attempts
        self._client: Any = None
        self._connected = False
        self._width = 0
        self._height = 0
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self._connected and self._client is not None

    @property
    def resolution(self) -> tuple[int, int]:
        return (self._width, self._height)

    def _server_string(self) -> str:
        return f"{self.host}::{self.port}" if self.port != 5900 else self.host

    def _sync_connect(self) -> None:
        try:
            from vncdotool import api as vnc_api
        except ImportError as e:
            raise VNCConnectionError(
                "vncdotool is not installed; pip install vncdotool"
            ) from e
        try:
            factory = vnc_api.connect(
                self._server_string(),
                password=self.password,
            )
            self._client = factory
            self._connected = True
        except Exception as e:
            self._connected = False
            self._client = None
            raise VNCConnectionError(f"VNC connect failed: {e}") from e

        # Best-effort resolution probe via a real screenshot (same mechanism as
        # _sync_capture — vncdotool's captureScreen() needs a real file path with
        # a valid extension; passing None/a BytesIO raises "unknown file
        # extension" from the underlying PIL save, and MUST NOT be misreported
        # as a connection failure once the RFB handshake already succeeded).
        try:
            self._width, self._height = self._probe_resolution()
        except Exception:
            # Resolution self-corrects on the first real capture_screen() call;
            # do not fail connect() over a failed best-effort probe.
            pass

    def _probe_resolution(self) -> tuple[int, int]:
        import os
        import tempfile

        from PIL import Image

        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        try:
            self._client.captureScreen(tmp)
            with open(tmp, "rb") as f:
                img = Image.open(io.BytesIO(f.read()))
            return img.size
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def _sync_disconnect(self, *, shutdown_reactor: bool = True) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
        self._client = None
        self._connected = False
        # vncdotool owns one process-global Twisted reactor. It cannot be
        # restarted after shutdown(), so recovery reconnects must disconnect
        # only the client and keep the reactor alive. Final CLI cleanup uses
        # the default True value to stop the reactor before process exit.
        if not shutdown_reactor:
            return
        try:
            from vncdotool import api as vnc_api

            vnc_api.shutdown()
        except Exception:
            pass

    def _ensure(self) -> Any:
        if not self._connected or self._client is None:
            raise VNCDisconnectedError("VNC is not connected")
        return self._client

    def _sync_capture(self) -> bytes:
        client = self._ensure()
        try:
            # vncdotool captureScreen writes to path; use temp via BytesIO not always supported
            import os
            import tempfile

            from PIL import Image

            fd, tmp = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            try:
                client.captureScreen(tmp)
                with open(tmp, "rb") as f:
                    data = f.read()
                img = Image.open(io.BytesIO(data))
                self._width, self._height = img.size
                return data
            finally:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        except VNCDisconnectedError:
            raise
        except Exception as e:
            self._connected = False
            raise VNCDisconnectedError(f"capture failed: {e}") from e

    def _sync_capture_region(self, x: int, y: int, w: int, h: int) -> bytes:
        full = self._sync_capture()
        from PIL import Image

        img = Image.open(io.BytesIO(full))
        crop = img.crop((x, y, x + w, y + h))
        buf = io.BytesIO()
        crop.save(buf, format="PNG")
        return buf.getvalue()

    def _sync_key(self, key: str) -> None:
        client = self._ensure()
        client.keyPress(normalize_key(key))

    def _sync_hotkey(self, keys: list[str]) -> None:
        client = self._ensure()
        mapped = normalize_hotkey(keys)
        # Hold modifiers, press last key, release
        if len(mapped) == 1:
            client.keyPress(mapped[0])
            return
        *mods, final = mapped
        for m in mods:
            client.keyDown(m)
        try:
            client.keyPress(final)
        finally:
            for m in reversed(mods):
                client.keyUp(m)

    def _sync_text(self, text: str) -> None:
        client = self._ensure()
        for ch in text:
            if ch == "\n":
                client.keyPress("enter")
            elif ch == "\t":
                client.keyPress("tab")
            else:
                client.keyPress(ch)

    def _sync_move(self, x: int, y: int) -> None:
        self._ensure().mouseMove(x, y)

    def _sync_click(self, x: int, y: int, button: int = 1) -> None:
        client = self._ensure()
        client.mouseMove(x, y)
        client.mousePress(button)

    def _sync_double_click(self, x: int, y: int) -> None:
        client = self._ensure()
        client.mouseMove(x, y)
        client.mousePress(1)
        client.mousePress(1)

    def _sync_right_click(self, x: int, y: int) -> None:
        self._sync_click(x, y, button=3)

    def _sync_scroll(self, x: int, y: int, direction: str, amount: int) -> None:
        client = self._ensure()
        client.mouseMove(x, y)
        # button 4 = up, 5 = down (X11 convention)
        btn = 4 if direction.lower() in ("up", "u") else 5
        for _ in range(max(1, amount)):
            client.mousePress(btn)

    def _sync_drag(self, x1: int, y1: int, x2: int, y2: int, button: int = 1) -> None:
        client = self._ensure()
        client.mouseMove(x1, y1)
        client.mouseDown(button)
        try:
            client.mouseMove(x2, y2)
        finally:
            client.mouseUp(button)

    def _sync_release_modifiers(self) -> None:
        client = self._ensure()
        for m in ("ctrl", "alt", "shift", "super"):
            try:
                client.keyUp(m)
            except Exception:
                pass

    async def connect(self) -> None:
        async with self._lock:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._sync_connect),
                    timeout=self.connect_timeout_seconds,
                )
            except TimeoutError as e:
                raise VNCConnectionError("VNC connect timed out") from e

    async def disconnect(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_disconnect)

    async def reconnect(self) -> None:
        last_err: Exception | None = None
        async with self._lock:
            for attempt in range(self.reconnect_attempts):
                try:
                    # Do not call public disconnect(): it shuts down Twisted's
                    # process-global reactor, which raises ReactorNotRestartable
                    # when connect() is attempted again in this process.
                    await asyncio.to_thread(
                        self._sync_disconnect, shutdown_reactor=False
                    )
                    await asyncio.wait_for(
                        asyncio.to_thread(self._sync_connect),
                        timeout=self.connect_timeout_seconds,
                    )
                    return
                except Exception as e:
                    last_err = e
                    await asyncio.sleep(0.5 * (attempt + 1))
        raise VNCConnectionError(
            f"reconnect exhausted after {self.reconnect_attempts} attempts: {last_err}"
        )

    async def capture_screen(self) -> bytes:
        async with self._lock:
            return await asyncio.to_thread(self._sync_capture)

    async def capture_region(self, x: int, y: int, w: int, h: int) -> bytes:
        async with self._lock:
            return await asyncio.to_thread(self._sync_capture_region, x, y, w, h)

    async def send_key(self, key: str) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_key, key)

    async def send_hotkey(self, keys: list[str]) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_hotkey, keys)

    async def send_text(self, text: str) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_text, text)

    async def mouse_move(self, x: int, y: int) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_move, x, y)

    async def click(self, x: int, y: int, button: int = 1) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_click, x, y, button)

    async def double_click(self, x: int, y: int) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_double_click, x, y)

    async def right_click(self, x: int, y: int) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_right_click, x, y)

    async def scroll(self, x: int, y: int, direction: str, amount: int = 3) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_scroll, x, y, direction, amount)

    async def drag(
        self, x1: int, y1: int, x2: int, y2: int, button: int = 1
    ) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_drag, x1, y1, x2, y2, button)

    async def release_modifiers(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_release_modifiers)


# Alias matching plan naming
VncdotoolDriver = VNCToolDriver
