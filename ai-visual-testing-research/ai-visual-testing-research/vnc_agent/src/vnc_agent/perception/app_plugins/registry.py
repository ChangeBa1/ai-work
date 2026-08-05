"""Feature 024 (FR-002): the plugin registry.

Two registration sources: declarative profile files (the shipped path) and
programmatic registration of code plugins (escape hatch). Lookup order is
deterministic so multi-plugin behaviour is reproducible.
"""

from __future__ import annotations

from pathlib import Path

from vnc_agent.domain.app_perception import SubWindowDetection
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.perception.app_plugins.base import AppPerceptionPlugin
from vnc_agent.perception.app_plugins.detector import DeclarativeSubWindowPlugin
from vnc_agent.perception.app_plugins.profile import ProfileError, load_profile


class DuplicatePluginError(Exception):
    pass


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, AppPerceptionPlugin] = {}

    def register(self, plugin: AppPerceptionPlugin) -> None:
        name = plugin.name
        if name in self._plugins:
            raise DuplicatePluginError(f"app-perception plugin {name!r} is already registered")
        self._plugins[name] = plugin

    def get(self, name: str) -> AppPerceptionPlugin | None:
        return self._plugins.get(name)

    def names(self) -> list[str]:
        return sorted(self._plugins)

    def __len__(self) -> int:
        return len(self._plugins)

    @classmethod
    def from_profiles_dir(cls, path: str | Path) -> PluginRegistry:
        """Load every ``*.yaml`` profile under ``path``.

        A missing directory yields an EMPTY registry rather than an error:
        "this machine has no profiles installed" is a normal state, and the
        whole feature then degrades to the unchanged full-frame path.
        An invalid profile is fatal at load time (SC-008) — never a silent
        runtime downgrade.
        """
        registry = cls()
        root = Path(path)
        if not root.is_dir():
            return registry
        for file in sorted(root.glob("*.yaml")):
            profile = load_profile(file)
            try:
                registry.register(DeclarativeSubWindowPlugin(profile))
            except DuplicatePluginError as exc:
                raise ProfileError(file, [{"path": "name", "reason": str(exc)}]) from exc
        return registry

    def detect_all(self, screen: StructuredScreen) -> list[SubWindowDetection]:
        """Every plugin that can see its window in this frame.

        Deterministic ordering: confidence desc, then plugin name asc. Callers
        take at most ONE detection — sub-window enhancement never combines or
        stacks regions.
        """
        found: list[SubWindowDetection] = []
        for name in self.names():
            plugin = self._plugins[name]
            detection = plugin.detect(screen)
            if detection is not None:
                found.append(detection)
        found.sort(key=lambda d: (-d.confidence, d.plugin_name))
        return found
