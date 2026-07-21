"""Keyboard executor (FR-020)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnc_agent.drivers.base import VNCDriver


class KeyboardExecutor:
    def __init__(self, driver: VNCDriver) -> None:
        self.driver = driver

    async def type_text(self, text: str) -> None:
        await self.driver.send_text(text)

    async def press_key(self, key: str) -> None:
        await self.driver.send_key(key)

    async def hotkey(self, keys: list[str]) -> None:
        await self.driver.send_hotkey(keys)

    async def focus_nav(self, keys: list[str]) -> None:
        if len(keys) == 1:
            await self.press_key(keys[0])
        else:
            await self.hotkey(keys)

    async def release_modifiers(self) -> None:
        if hasattr(self.driver, "release_modifiers"):
            await self.driver.release_modifiers()  # type: ignore[attr-defined]
        else:
            for m in ("ctrl", "alt", "shift", "win"):
                try:
                    await self.driver.send_key(m)
                except Exception:
                    pass
