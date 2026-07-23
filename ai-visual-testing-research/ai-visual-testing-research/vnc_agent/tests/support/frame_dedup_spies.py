"""Deterministic offline spies + clock for feature 004 tests.

All spies are pure in-memory call recorders: no filesystem, no network. Every
spy exposes ``call_count`` and a ``calls`` list of sanitized
(args, kwargs, sequence) records so tests can assert exact invocation counts
against an independent oracle (contracts/telemetry-contract.md "Test oracle").

Raw pixel arrays / PNG bytes are never retained verbatim in ``calls`` — they
are replaced with a short descriptor so spy history itself never becomes an
image cache and never leaks bytes into assertion failure output.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np


def _sanitize(value: Any) -> Any:
    """Strip raw pixel/byte payloads from a value before recording a call."""
    if isinstance(value, np.ndarray):
        return f"<ndarray shape={value.shape} dtype={value.dtype}>"
    if isinstance(value, (bytes, bytearray)):
        return f"<bytes len={len(value)}>"
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(_sanitize(v) for v in value)
    return value


@dataclass
class RecordedCall:
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    sequence: int


class _CallRecorder:
    """Shared call-tracking mixin: sanitized args/kwargs + monotonic sequence."""

    def __init__(self) -> None:
        self.calls: list[RecordedCall] = []
        self._sequence = itertools.count(1)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    def reset(self) -> None:
        self.calls.clear()

    def _record(self, *args: Any, **kwargs: Any) -> RecordedCall:
        call = RecordedCall(
            args=tuple(_sanitize(a) for a in args),
            kwargs={k: _sanitize(v) for k, v in kwargs.items()},
            sequence=next(self._sequence),
        )
        self.calls.append(call)
        return call


class SpyOCR(_CallRecorder):
    """Spies on the OCR analysis-component boundary (data-model.md §5 `ocr`)."""

    def __init__(
        self,
        *,
        result_fn: Callable[..., list[Any]] | None = None,
        results: list[Any] | None = None,
        backend: str = "spy-ocr",
        version: str = "1.0",
    ) -> None:
        super().__init__()
        self._result_fn = result_fn
        self._results = results if results is not None else []
        self.backend = backend
        self.version = version

    def __call__(self, pixels: Any, **identity: Any) -> list[Any]:
        self._record(pixels, **identity)
        if self._result_fn is not None:
            return self._result_fn(pixels, **identity)
        return list(self._results)


class SpyTemplateAnalyzer(_CallRecorder):
    """Spies on the template analysis-component boundary (`template`)."""

    def __init__(
        self,
        *,
        result_fn: Callable[..., list[Any]] | None = None,
        results: list[Any] | None = None,
        matcher_revision: str = "1.0",
    ) -> None:
        super().__init__()
        self._result_fn = result_fn
        self._results = results if results is not None else []
        self.matcher_revision = matcher_revision

    def __call__(self, pixels: Any, **identity: Any) -> list[Any]:
        self._record(pixels, **identity)
        if self._result_fn is not None:
            return self._result_fn(pixels, **identity)
        return list(self._results)


class SpyVisionProvider(_CallRecorder):
    """Spies on the cacheable `vision_describe` content component.

    Distinct from :class:`SpyPlannerProvider` — this only stands in for the
    pixel-content-addressed "describe this screen" call, never for the
    context-sensitive Planner/Verifier decisions that must not be cached.
    """

    def __init__(
        self,
        *,
        result_fn: Callable[..., Any] | None = None,
        response: Any = None,
        model: str = "spy-vision",
        version: str = "1.0",
    ) -> None:
        super().__init__()
        self._result_fn = result_fn
        self._response = response
        self.model = model
        self.version = version

    def describe(self, pixels: Any, **identity: Any) -> Any:
        self._record(pixels, **identity)
        if self._result_fn is not None:
            return self._result_fn(pixels, **identity)
        return self._response


class SpyPlannerProvider(_CallRecorder):
    """Implements the `PlannerProvider` protocol (plan + describe_screen).

    Tracks `plan()` (Planner role, context-sensitive) and `describe_screen()`
    (used both for vision-describe and for Verifier `answer_question`)
    invocations independently so context-guard tests can assert exact
    per-role call counts.
    """

    def __init__(
        self,
        *,
        plan_fn: Callable[..., Any] | None = None,
        plan_response: Any = None,
        describe_fn: Callable[..., Any] | None = None,
        describe_response: Any = None,
        answer_fn: Callable[..., Any] | None = None,
        answer_response: Any = None,
    ) -> None:
        super().__init__()
        self.plan_calls: list[RecordedCall] = []
        self.describe_calls: list[RecordedCall] = []
        self.answer_calls: list[RecordedCall] = []
        self._plan_fn = plan_fn
        self._plan_response = plan_response
        self._describe_fn = describe_fn
        self._describe_response = describe_response
        self._answer_fn = answer_fn
        self._answer_response = answer_response

    async def plan(self, request: Any) -> Any:
        call = self._record(request=request)
        self.plan_calls.append(call)
        if self._plan_fn is not None:
            return self._plan_fn(request)
        return self._plan_response

    async def describe_screen(self, request: Any) -> Any:
        call = self._record(request=request)
        mode = getattr(request, "mode", None)
        if mode == "answer_question":
            self.answer_calls.append(call)
            if self._answer_fn is not None:
                return self._answer_fn(request)
            return self._answer_response
        self.describe_calls.append(call)
        if self._describe_fn is not None:
            return self._describe_fn(request)
        return self._describe_response


class SpyGrounder(_CallRecorder):
    """Implements the `GrounderProvider` protocol (`ground`)."""

    def __init__(
        self,
        *,
        result_fn: Callable[..., Any] | None = None,
        result: Any = None,
    ) -> None:
        super().__init__()
        self._result_fn = result_fn
        self._result = result

    async def ground(self, request: Any) -> Any:
        self._record(request=request)
        if self._result_fn is not None:
            return self._result_fn(request)
        return self._result


class SpyVerifier(_CallRecorder):
    """Spies on independent post-action Verifier execution.

    Records every actual invocation so tests can prove the Verifier always
    runs on fresh post-action evidence, even when the underlying frame is a
    deterministic pixel duplicate of its predecessor.
    """

    def __init__(
        self,
        *,
        result_fn: Callable[..., Any] | None = None,
        result: Any = None,
    ) -> None:
        super().__init__()
        self._result_fn = result_fn
        self._result = result

    async def verify(self, spec: Any, screen: Any, **kwargs: Any) -> Any:
        self._record(spec=spec, screen=screen, **kwargs)
        if self._result_fn is not None:
            return self._result_fn(spec, screen, **kwargs)
        return self._result


class DeterministicClock:
    """Injectable monotonic + UTC wall clock (telemetry-contract.md "Measurement semantics").

    ``perf_counter_ns`` mirrors ``time.perf_counter_ns`` for duration math;
    ``utc_now`` mirrors ``datetime.now(timezone.utc)`` for `started_at`. Both
    auto-advance by ``step_ns`` per read by default so successive stage
    measurements get distinct, deterministic non-zero durations without a
    real sleep; call :meth:`freeze` to stop auto-advance for exact control.
    """

    def __init__(
        self,
        *,
        start_ns: int = 0,
        start_utc: datetime | None = None,
        step_ns: int = 1_000_000,
    ) -> None:
        self._ns = start_ns
        self._utc = start_utc or datetime(2026, 1, 1, tzinfo=UTC)
        self._auto_step_ns = step_ns

    def perf_counter_ns(self) -> int:
        value = self._ns
        self._ns += self._auto_step_ns
        return value

    def utc_now(self) -> datetime:
        value = self._utc
        self._utc += timedelta(microseconds=self._auto_step_ns / 1000)
        return value

    def advance(self, *, ns: int = 0, ms: float = 0.0) -> None:
        total_ns = ns + int(ms * 1_000_000)
        self._ns += total_ns
        self._utc += timedelta(milliseconds=total_ns / 1_000_000)

    def freeze(self) -> None:
        self._auto_step_ns = 0
