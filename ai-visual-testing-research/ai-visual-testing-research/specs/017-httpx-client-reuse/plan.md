# Implementation Plan: Reuse httpx AsyncClient Across Model Calls

**Branch**: `017-httpx-client-reuse` | **Date**: 2026-07-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-httpx-client-reuse/spec.md`

## Summary

Replace the per-call `async with httpx.AsyncClient(...)` pattern in
`HttpPlannerClient.plan()/describe_screen()` and `MimoGrounderClient.ground()`
with one lazily-created, instance-level `AsyncClient` per provider object,
configured with keep-alive pool limits. Add idempotent `aclose()` to both
classes and wire it into the CLI run teardown (`api/cli.py::_execute` finally
block) so success and exception paths both release connections. Timeout and
error-mapping semantics stay identical; the grounder's `transport=` test seam
is preserved and mirrored onto the planner.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed project in `vnc_agent/`)

**Primary Dependencies**: httpx (AsyncClient, Limits, MockTransport), typer, pydantic

**Storage**: N/A (no persistence change)

**Testing**: pytest + pytest-asyncio; offline fixtures use `httpx.MockTransport`

**Target Platform**: same as project (Windows/Linux CLI)

**Project Type**: CLI agent library

**Performance Goals**: eliminate per-model-call DNS+TCP+TLS handshake (~100s of ms against https://opencode.ai) from the 2nd call onward

**Constraints**: no behavior change to request payloads, timeouts, or error mapping; no new dependencies

**Scale/Scope**: 3 source files touched + 1 new test file

## Constitution Check

*GATE: passed.*

- Principle I (deterministic runtime control): untouched — pure transport-lifecycle refactor; no model responsibilities change.
- Principle II (Planner/Grounder separation): untouched — both providers keep their contracts (`plan`/`describe_screen`/`ground` signatures unchanged; `aclose` is additive).
- Resource constraint (弱配置电脑 / avoid waste): directly served — removes redundant handshakes per model call.
- 凭据与隐私: unaffected — headers/auth resolution unchanged.

**Domain-Agnostic Core gate (Principle VI)**:

- [x] No business-specific fields/states/branches added to core modules — this is transport plumbing only.
- [x] No scenario semantics introduced.
- [x] Generic capability (connection reuse) validated by provider-level unit tests, not scenario fixtures.

## Phase 0 — Research (inline; no open unknowns)

- **httpx per-request timeout**: `client.post(..., timeout=...)` overrides the client default for that request only — exactly matches today's two-timeout planner behavior. Decision: client default = `cfg.timeout_seconds`, `describe_screen()` overrides per request with `cfg.describe_timeout()`.
- **httpx pool config**: `httpx.Limits(max_connections=10, max_keepalive_connections=5, keepalive_expiry=30.0)`; requests are sequential today so limits are generous headroom, `keepalive_expiry=30s` keeps the socket warm across a typical plan→ground→verify cadence.
- **Existing test seams**:
  - `tests/fixtures/test_mimo_grounder.py` constructs `MimoGrounderClient(cfg, transport=httpx.MockTransport(...))` → keep the parameter, hand it to the long-lived client.
  - `tests/fixtures/test_planner_client_describe_screen.py` monkeypatches `vnc_agent.models.planner_client.httpx.AsyncClient` around the call → stays valid because the lazy factory resolves `httpx.AsyncClient` at first-request time.
- **Event loop**: CLI funnels everything through `asyncio.run` (`_run_async`); client created on first request inside that loop. Recorded as an assumption in the spec.
- **CLI teardown location**: `_execute()` already has a `finally` that disconnects the VNC driver; the only code between provider construction and that `try` cannot have created a socket (client is lazy), so closing in the same `finally` is leak-free for every path that could have opened a connection.

## Phase 1 — Design

### Changes by file

1. `vnc_agent/src/vnc_agent/models/planner_client.py`
   - Module-level `_KEEPALIVE_LIMITS = httpx.Limits(max_connections=10, max_keepalive_connections=5, keepalive_expiry=30.0)` (shared; imported by mimo_grounder).
   - `HttpPlannerClient.__init__(cfg, *, transport: httpx.AsyncBaseTransport | None = None)`; fields `_transport`, `_client: httpx.AsyncClient | None = None`.
   - `_get_client()` lazy factory: builds `httpx.AsyncClient(timeout=cfg.timeout_seconds, limits=_KEEPALIVE_LIMITS[, transport=...])` once.
   - `plan()`: drop `async with`; `client = self._get_client()`; same try/except body.
   - `describe_screen()`: same, plus `timeout=self.cfg.describe_timeout()` passed to `client.post(...)`.
   - `async def aclose()`: if `_client` is not None → `await _client.aclose()`, reset to None. Idempotent.
2. `vnc_agent/src/vnc_agent/models/mimo_grounder.py`
   - Same lazy-client pattern in `MimoGrounderClient` (client default timeout = `cfg.timeout_seconds`, injected transport honored), same `aclose()`.
   - `ground()` request try/except and post-processing pipeline unchanged.
3. `vnc_agent/src/vnc_agent/api/cli.py`
   - In `_execute()`'s existing `finally`: after driver disconnect, duck-typed close of `planner` and `grounder` (`aclose = getattr(p, "aclose", None)`), each wrapped in try/except pass.

### Non-changes (explicit)

- `StubPlanner` / `StubGrounder`: untouched (no aclose needed; CLI close is duck-typed).
- `provider.py` protocols: untouched — `aclose` is not part of the provider contract; only the composition root cares.
- Request payload construction, response parsing, error types: untouched.

## Project Structure

### Documentation (this feature)

```text
specs/017-httpx-client-reuse/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code (repository root)

```text
vnc_agent/
├── src/vnc_agent/
│   ├── models/
│   │   ├── planner_client.py    # lazy shared client + aclose + transport seam
│   │   └── mimo_grounder.py     # lazy shared client + aclose (transport seam kept)
│   └── api/
│       └── cli.py               # _execute() finally: close planner/grounder
└── tests/
    └── fixtures/
        └── test_httpx_client_reuse.py   # new: reuse identity, aclose idempotency, timeout override
```

**Structure Decision**: single-project layout as-is; new test lives beside the
other model-client fixture tests.

## Complexity Tracking

No constitution violations; table not needed.
