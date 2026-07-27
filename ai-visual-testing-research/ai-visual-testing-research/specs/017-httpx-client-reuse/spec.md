# Feature Specification: Reuse httpx AsyncClient Across Model Calls

**Feature Branch**: `017-httpx-client-reuse`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "HttpPlannerClient.plan()/describe_screen() and MimoGrounderClient.ground() each open a fresh `async with httpx.AsyncClient(...)` per call and destroy it on exit, so every model call re-pays DNS + TCP + TLS handshake (hundreds of ms against the HTTPS opencode.ai endpoint). Hold one long-lived instance-level AsyncClient per client object (lazy creation is fine), reuse its connection pool / keep-alive across requests, add `aclose()` to both classes, and close them at the CLI run teardown on both success and failure paths."

## Clarifications

### Session 2026-07-27 (self-resolved; fully automated run — decisions recorded here instead of asked)

- Q: Client-level vs per-request timeout — how is the planner's two-timeout scheme (`timeout_seconds` for `plan()`, `describe_timeout()` for `describe_screen()`) preserved with a single shared client? → A: The long-lived client is constructed with `timeout=cfg.timeout_seconds` as its default; `describe_screen()` passes `timeout=cfg.describe_timeout()` per request, which httpx applies for that request only. Behavior is equivalent to today's per-call clients: each request observes exactly the same timeout value as before. The grounder has a single `timeout_seconds`, carried as the client default.
- Q: Where is the client created relative to the event loop? → A: Lazily, on the first request, inside the running loop. The CLI (`api/cli.py`) drives every command through one `asyncio.run(...)` call, so creation and all reuse happen on a single loop. **Assumption recorded**: a client instance is not shared across event loops; embedders that call the providers from multiple loops must create one provider per loop (out of scope — the CLI is the only composition root today).
- Q: What are the pool limits? → A: `httpx.Limits(max_connections=10, max_keepalive_connections=5, keepalive_expiry=30.0)`. Model calls are strictly sequential in the runtime today, so the numbers are generous; `keepalive_expiry=30s` matches the request cadence of a typical run loop (planner→grounder→verify within seconds) while not holding sockets open indefinitely.
- Q: `MimoGrounderClient(transport=...)` test-injection semantics? → A: Preserved — the injected transport is passed to the single long-lived client at lazy-creation time; all subsequent requests route through it. For symmetry (and to let new tests avoid monkeypatching), `HttpPlannerClient` gains the same optional keyword-only `transport` parameter. The existing planner test that monkeypatches `vnc_agent.models.planner_client.httpx.AsyncClient` stays valid because the constructor is looked up at first-request time, not import time.
- Q: What does `aclose()` guarantee? → A: Idempotent; safe to call before any request (no-op when no client was ever created); after `aclose()` a subsequent request lazily creates a fresh client (no "closed forever" state). CLI teardown calls it in the existing `finally` block of `_execute()` so both success and exception paths release sockets; failures during close are swallowed (teardown must never mask the run's real outcome).
- Q: Error-handling semantics per request? → A: Unchanged. The `try/except` blocks that wrapped each request keep wrapping each request; only the client's lifetime moves out. A request-level failure does not close or invalidate the shared client (httpx discards broken connections from its pool automatically).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consecutive model calls reuse one connection pool (Priority: P1)

A test run makes many planner/grounder calls over its lifetime. From the second call onward, each HTTPS request reuses the already-established keep-alive connection instead of re-doing DNS + TCP + TLS, removing hundreds of milliseconds of per-call overhead against the cloud endpoints.

**Why this priority**: This is the entire point of the feature — per-call latency and connection-churn waste on every single model call in every run.

**Independent Test**: Inject a counting `httpx.MockTransport` into a client instance, issue two calls, and assert both were served by the same underlying `httpx.AsyncClient` object (instance identity) and that no second AsyncClient was constructed.

**Acceptance Scenarios**:

1. **Given** one `MimoGrounderClient` instance, **When** `ground()` is called twice, **Then** both requests go through the same underlying `httpx.AsyncClient` instance.
2. **Given** one `HttpPlannerClient` instance, **When** `plan()` and then `describe_screen()` are called, **Then** exactly one `httpx.AsyncClient` is constructed and both requests flow through it.

---

### User Story 2 - Run teardown closes clients on every path (Priority: P1)

An operator running `vnc-agent run ...` never leaks sockets/connections: whether the run passes, fails, or aborts with an exception, the CLI teardown closes both model clients.

**Why this priority**: A long-lived client without a deterministic close is a resource leak and produces "Unclosed client session"-class noise; correctness of the lifecycle is as important as the reuse itself.

**Independent Test**: Call `aclose()` on a client twice (and once on a virgin client that never issued a request) and assert no error; inspect `api/cli.py` teardown wiring.

**Acceptance Scenarios**:

1. **Given** a client that has served requests, **When** `aclose()` is called, **Then** the underlying AsyncClient is closed; a second `aclose()` is a no-op.
2. **Given** a client that never issued a request, **When** `aclose()` is called, **Then** nothing fails and nothing is created.
3. **Given** the CLI `_execute()` path, **When** the run finishes normally OR raises, **Then** the `finally` teardown closes both planner and grounder clients.

---

### User Story 3 - Test transport injection keeps working (Priority: P2)

A test author keeps using `MimoGrounderClient(cfg, transport=httpx.MockTransport(handler))` exactly as before, and can now do the same with `HttpPlannerClient`; the injected transport backs the long-lived client.

**Why this priority**: The offline test suite depends on this seam; breaking it would invalidate existing fixtures.

**Acceptance Scenarios**:

1. **Given** a grounder constructed with an injected transport, **When** `ground()` is called repeatedly, **Then** every request is served by that transport (existing fixture tests stay green unchanged).
2. **Given** a planner constructed with an injected transport, **When** `plan()` is called, **Then** the request is served by that transport.

### Edge Cases

- `aclose()` called concurrently with an in-flight request: out of scope — the runtime is strictly sequential per run; teardown runs after `runtime.run()` returns/raises.
- Client used again after `aclose()`: a fresh AsyncClient is lazily created (report re-render or embedder reuse stays safe).
- Keep-alive expired between calls (>30 s idle): httpx transparently opens a new connection; no behavior change beyond the latency of that one handshake.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `HttpPlannerClient` and `MimoGrounderClient` MUST each hold at most one instance-level `httpx.AsyncClient`, created lazily on first request and reused by all subsequent requests of that instance.
- **FR-002**: The long-lived clients MUST be configured with connection-pool keep-alive limits (`httpx.Limits`, `keepalive_expiry=30s`).
- **FR-003**: Both classes MUST expose `async def aclose()` that is idempotent and safe when no client was ever created; after `aclose()`, a later request lazily re-creates the client.
- **FR-004**: `api/cli.py` `_execute()` MUST close both model clients in its existing `finally` teardown, covering success, failure, and exception paths, without masking the run's exit code.
- **FR-005**: Timeout semantics MUST be preserved: `plan()` and `ground()` observe `cfg.timeout_seconds`; `describe_screen()` observes `cfg.describe_timeout()` (implemented as a per-request timeout override on the shared client).
- **FR-006**: `MimoGrounderClient`'s existing `transport=` injection seam MUST keep working, now backing the long-lived client; `HttpPlannerClient` MUST gain the equivalent keyword-only `transport=` parameter.
- **FR-007**: Per-request error mapping (`GroundingError`, `PlanValidationError`, parse-failure → `found=false`) MUST remain byte-for-byte the same; a failed request MUST NOT tear down the shared client.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Two consecutive calls on one client instance construct exactly one `httpx.AsyncClient` (asserted by test).
- **SC-002**: `aclose()` twice, and `aclose()` on a virgin instance, complete without error (asserted by test).
- **SC-003**: Full offline regression (`tests/unit tests/fixtures tests/e2e tests/integration`) passes with no test modified except additions (1 pre-existing skip allowed).
- **SC-004**: In production runs, from the second model call onward no new TCP/TLS handshake is required while keep-alive is warm (design property of the shared pool; not measured in offline CI).

## Assumptions

- The CLI is the only composition root; it drives each command through a single `asyncio.run(...)`, so each client instance lives and dies on one event loop.
- Model calls within a run are sequential; no concurrent multi-loop sharing of a client instance.
- `StubPlanner` / `StubGrounder` need no `aclose()`; CLI teardown uses duck-typing (`getattr(..., "aclose", None)`) so any provider without `aclose` is skipped silently.
- Out of scope: any other HTTP call sites (e.g., OCR engines, artifact upload — none exist today), retry/连接预热 logic, HTTP/2.
