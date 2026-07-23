"""Session-wide structlog target stabilization for pytest (test infra only).

structlog binds its `PrintLoggerFactory`'s `file` to whatever `sys.stderr`
object is live at the *first* successful call through a given cached bound
logger (e.g. a module-level `log = get_logger(...)` singleton), and
`cache_logger_on_first_use` locks that binding in permanently —
`structlog._config.BoundLoggerLazyProxy` monkey-patches its own `.bind`
method after first use, so a later `structlog.configure()`/
`reset_defaults()` call cannot retarget an already-realized logger.

Pytest's default fd-level capture swaps `sys.stderr` in/out per test and
closes the swapped-in buffer at test teardown. Whichever test happens to
trigger a given module's logger's first-ever use therefore poisons every
later call through that same logger for the rest of the session — a
`ValueError: I/O operation on closed file` from deep inside structlog,
unrelated to whatever the failing test actually does. Configuring once,
here, against `sys.__stderr__` (the untouched original stream, never
swapped or closed by pytest's capture manager) avoids ever caching a
reference to a buffer that later gets closed.
"""

from __future__ import annotations

import sys

import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(file=sys.__stderr__),
    cache_logger_on_first_use=True,
)
