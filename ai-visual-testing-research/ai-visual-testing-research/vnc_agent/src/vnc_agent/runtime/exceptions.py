"""Runtime exception hierarchy."""

from __future__ import annotations


class VNCAgentError(Exception):
    """Base error for the agent runtime."""


class VNCConnectionError(VNCAgentError):
    """Failed to establish VNC connection."""


class VNCDisconnectedError(VNCAgentError):
    """VNC session dropped mid-run."""


class StepBudgetExhaustedError(VNCAgentError):
    """TestStep.max_retries (Tier-1) budget exhausted."""


class PlanValidationError(VNCAgentError):
    """Planner response failed structural / whitelist validation."""


class GroundingError(VNCAgentError):
    """Grounding request or response failure."""


class ActionTimeoutError(VNCAgentError):
    """Single action exceeded its timeout (FR-021)."""


class CancellationError(VNCAgentError):
    """User/system cancellation requested."""


class ConfigError(VNCAgentError):
    """Invalid or incomplete configuration."""


class ProviderContractError(VNCAgentError):
    """Model provider failed Protocol structural check at startup."""


class ReplayUnavailableError(VNCAgentError):
    """Feature 016 (FR-005): a mode:"replay" run cannot start — replay is
    disabled, persistence is missing, no script exists for the test case, or
    the stored script no longer matches the declared step sequence. Raised
    before any VNC connection (fail fast, spec Clarification 11)."""


class KeyRepeatSendError(VNCAgentError):
    """A key send within a batch repeat failed partway through (Feature 005 FR-009)."""

    def __init__(
        self, *, key: str, requested_count: int, completed_count: int, cause: Exception
    ) -> None:
        self.key = key
        self.requested_count = requested_count
        self.completed_count = completed_count
        self.cause = cause
        super().__init__(
            f"press_key_repeat({key!r}) failed after {completed_count}/{requested_count} "
            f"sends: {cause}"
        )
