"""Structured logging with sensitive-field redaction (FR-047)."""

from __future__ import annotations

import logging
import sys
from typing import Any, Iterable

import structlog

DEFAULT_SENSITIVE = frozenset(
    {
        "password",
        "api_key",
        "apikey",
        "secret",
        "token",
        "authorization",
        "vnc_password",
        "text_value",
    }
)


def _redact_value(key: str, value: Any, sensitive: frozenset[str]) -> Any:
    kl = key.lower()
    if kl in sensitive or any(s in kl for s in sensitive):
        return "***REDACTED***"
    if isinstance(value, dict):
        return {k: _redact_value(k, v, sensitive) for k, v in value.items()}
    if isinstance(value, list):
        return [
            _redact_value(key, v, sensitive) if isinstance(v, dict) else v for v in value
        ]
    return value


def sensitive_filter(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    sensitive = event_dict.pop("_sensitive_fields", None) or DEFAULT_SENSITIVE
    if not isinstance(sensitive, frozenset):
        sensitive = frozenset(sensitive)
    return {k: _redact_value(k, v, sensitive) for k, v in event_dict.items()}


def configure_logging(
    *,
    json_lines: bool = True,
    level: int = logging.INFO,
    sensitive_fields: Iterable[str] | None = None,
) -> None:
    sens = frozenset(s.lower() for s in (sensitive_fields or DEFAULT_SENSITIVE))

    def filter_proc(
        logger: Any, method_name: str, event_dict: dict[str, Any]
    ) -> dict[str, Any]:
        return {k: _redact_value(k, v, sens) for k, v in event_dict.items()}

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        filter_proc,
        structlog.processors.StackInfoRenderer(),
    ]
    if json_lines:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
