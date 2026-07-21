"""Mouse executor (FR-020/023)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnc_agent.drivers.base import VNCDriver


class MouseExecutor:
    def __init__(self, driver: VNCDriver) -> None:
        self.driver = driver

    async def move(self, x: int, y: int) -> None:
        await self.driver.mouse_move(x, y)

    async def click(self, x: int, y: int) -> tuple[int, int]:
        await self.driver.click(x, y)
        return (x, y)

    async def double_click(self, x: int, y: int) -> tuple[int, int]:
        await self.driver.double_click(x, y)
        return (x, y)

    async def right_click(self, x: int, y: int) -> tuple[int, int]:
        await self.driver.right_click(x, y)
        return (x, y)

    async def scroll(self, x: int, y: int, direction: str = "down", amount: int = 3) -> None:
        await self.driver.scroll(x, y, direction, amount)

    async def drag(self, x1: int, y1: int, x2: int, y2: int) -> None:
        await self.driver.drag(x1, y1, x2, y2)
