"""Semantic key names → vncdotool keycodes."""

from __future__ import annotations

# Map common semantic names to vncdotool / X11-style key names
KEY_MAP: dict[str, str] = {
    "enter": "enter",
    "return": "enter",
    "tab": "tab",
    "escape": "esc",
    "esc": "esc",
    "space": "space",
    "backspace": "bsp",
    "delete": "del",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "home": "home",
    "end": "end",
    "pageup": "pgup",
    "pagedown": "pgdn",
    "ctrl": "ctrl",
    "control": "ctrl",
    "alt": "alt",
    "shift": "shift",
    "win": "super",
    "super": "super",
    "meta": "super",
    "cmd": "super",
    "f1": "f1",
    "f2": "f2",
    "f3": "f3",
    "f4": "f4",
    "f5": "f5",
    "f6": "f6",
    "f7": "f7",
    "f8": "f8",
    "f9": "f9",
    "f10": "f10",
    "f11": "f11",
    "f12": "f12",
}

MODIFIERS = frozenset({"ctrl", "control", "alt", "shift", "win", "super", "meta", "cmd"})


def normalize_key(name: str) -> str:
    key = name.strip().lower()
    return KEY_MAP.get(key, key)


def normalize_hotkey(keys: list[str]) -> list[str]:
    return [normalize_key(k) for k in keys]


def is_batch_repeatable_key(name: str) -> bool:
    """True if `name` is a recognized, non-modifier single key (Feature 005 FR-005)."""
    key = normalize_key(name)
    return key in KEY_MAP.values() and key not in MODIFIERS
