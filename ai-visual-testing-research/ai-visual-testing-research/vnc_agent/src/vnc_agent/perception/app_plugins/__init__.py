"""Feature 024 (app-perception-plugins): pluggable pre-grounding sub-window
crop+upscale enhancement.

Business-agnostic by construction — every application/window/control specific
fact lives in the declarative profile YAML files under `profiles/`, never in
this package (Constitution VI).
"""

from vnc_agent.perception.app_plugins.base import (
    ActivationContext,
    ActivationVote,
    AppPerceptionPlugin,
)
from vnc_agent.perception.app_plugins.coordinator import (
    AppPerceptionCoordinator,
    DeclaredWindowMissingError,
)
from vnc_agent.perception.app_plugins.detector import DeclarativeSubWindowPlugin
from vnc_agent.perception.app_plugins.profile import PluginProfile, ProfileError, load_profile
from vnc_agent.perception.app_plugins.registry import DuplicatePluginError, PluginRegistry

__all__ = [
    "ActivationContext",
    "ActivationVote",
    "AppPerceptionCoordinator",
    "AppPerceptionPlugin",
    "DeclarativeSubWindowPlugin",
    "DeclaredWindowMissingError",
    "DuplicatePluginError",
    "PluginProfile",
    "PluginRegistry",
    "ProfileError",
    "load_profile",
]
