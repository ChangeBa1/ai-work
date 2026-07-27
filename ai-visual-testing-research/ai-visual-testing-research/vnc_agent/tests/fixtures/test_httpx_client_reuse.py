"""
Feature 017 (httpx-client-reuse): HttpPlannerClient and MimoGrounderClient
hold one lazily-created, instance-level httpx.AsyncClient and reuse its
keep-alive connection pool across calls, instead of paying DNS+TCP+TLS on
every model call. aclose() is idempotent and the client is re-creatable
afterwards; test transport injection backs the long-lived client.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from vnc_agent.config import GrounderModelConfig, PlannerModelConfig
from vnc_agent.models.mimo_grounder import MimoGrounderClient
from vnc_agent.models.planner_client import HttpPlannerClient
from vnc_agent.models.provider import (
    GroundingRequest,
    PlannerRequest,
    VisionUnderstandingRequest,
)


def _png(tmp_path: Path) -> str:
    path = tmp_path / "frame.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nfake-but-nonempty-png-bytes")
    return str(path)


def _chat_completion(content_obj: dict) -> dict:
    return {
        "choices": [
            {"message": {"role": "assistant", "content": json.dumps(content_obj)}}
        ]
    }


_PLAN_CONTENT = {
    "task_completed_hint": False,
    "semantic_action": {
        "action_id": "act-1",
        "intent": "noop",
        "action_type": "wait",
        "target": None,
        "text_value": None,
        "keys": [],
        "risk_level": "low",
    },
    "needs_more_observation": False,
}

_DESCRIBE_CONTENT = {
    "mode": "describe",
    "description": "a screen",
    "confidence": 0.8,
    "model_name": "planner-v1",
}

_GROUND_CONTENT = {"found": False, "candidates": []}


def _planner_request() -> PlannerRequest:
    return PlannerRequest(
        step_intent="noop",
        expected={},
        structured_screen={},
    )


@pytest.mark.asyncio
async def test_grounder_reuses_one_async_client_across_calls(tmp_path: Path):
    """FR-001/SC-001: two ground() calls on one instance share one AsyncClient."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=_chat_completion(_GROUND_CONTENT))

    cfg = GrounderModelConfig(base_url="https://example.test/v1", model="mimo-v2.5")
    client = MimoGrounderClient(cfg, transport=httpx.MockTransport(handler))
    assert client._client is None, "client must be lazy — nothing before 1st call"

    request = GroundingRequest(image_ref=_png(tmp_path), target={"description": "x"})
    await client.ground(request)
    inner_after_first = client._client
    assert isinstance(inner_after_first, httpx.AsyncClient)

    await client.ground(request)
    assert client._client is inner_after_first, (
        "second call must reuse the same AsyncClient instance (keep-alive pool)"
    )
    assert calls["n"] == 2
    await client.aclose()


@pytest.mark.asyncio
async def test_planner_constructs_exactly_one_async_client(tmp_path: Path, monkeypatch):
    """FR-001/SC-001: plan() then describe_screen() construct one AsyncClient.

    Also FR-005: the shared client preserves per-method timeout semantics —
    plan() observes timeout_seconds, describe_screen() observes
    describe_timeout() — asserted from each request's effective timeout.
    """
    seen_timeouts: list[tuple[str, float | None]] = []
    responses = [_chat_completion(_PLAN_CONTENT), _chat_completion(_DESCRIBE_CONTENT)]

    def handler(request: httpx.Request) -> httpx.Response:
        timeout = request.extensions.get("timeout", {})
        seen_timeouts.append((request.url.path, timeout.get("read")))
        return httpx.Response(200, json=responses[len(seen_timeouts) - 1])

    constructed: list[httpx.AsyncClient] = []
    orig_async_client = httpx.AsyncClient

    def counting(*args, **kwargs):
        instance = orig_async_client(*args, **kwargs)
        constructed.append(instance)
        return instance

    import vnc_agent.models.planner_client as mod

    monkeypatch.setattr(mod.httpx, "AsyncClient", counting)

    cfg = PlannerModelConfig(
        base_url="http://test/v1",
        timeout_seconds=7,
        describe_screen_timeout_seconds=99,
    )
    client = HttpPlannerClient(cfg, transport=httpx.MockTransport(handler))

    await client.plan(_planner_request())
    await client.describe_screen(
        VisionUnderstandingRequest(mode="describe", image_ref=_png(tmp_path))
    )

    assert len(constructed) == 1, "exactly one AsyncClient for both call kinds"
    assert client._client is constructed[0]
    assert seen_timeouts[0][1] == 7.0, "plan() must observe timeout_seconds"
    assert seen_timeouts[1][1] == 99.0, "describe_screen() must observe describe_timeout()"
    await client.aclose()


@pytest.mark.asyncio
async def test_aclose_idempotent_and_client_recreatable(tmp_path: Path):
    """FR-003/SC-002: aclose twice, aclose on virgin instance, reuse after close."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_chat_completion(_GROUND_CONTENT))

    cfg = GrounderModelConfig(base_url="https://example.test/v1", model="mimo-v2.5")

    # Virgin instance: aclose() is a no-op and creates nothing.
    virgin = MimoGrounderClient(cfg, transport=httpx.MockTransport(handler))
    await virgin.aclose()
    assert virgin._client is None

    client = MimoGrounderClient(cfg, transport=httpx.MockTransport(handler))
    request = GroundingRequest(image_ref=_png(tmp_path), target={"description": "x"})
    await client.ground(request)
    first = client._client
    assert first is not None

    await client.aclose()
    assert first.is_closed
    assert client._client is None
    await client.aclose()  # idempotent

    # A later call lazily re-creates a fresh client — no "closed forever" state.
    await client.ground(request)
    second = client._client
    assert isinstance(second, httpx.AsyncClient)
    assert second is not first
    await client.aclose()


@pytest.mark.asyncio
async def test_planner_aclose_idempotent_before_and_after_use(tmp_path: Path):
    """FR-003 for the planner side."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_chat_completion(_PLAN_CONTENT))

    cfg = PlannerModelConfig(base_url="http://test/v1")
    client = HttpPlannerClient(cfg, transport=httpx.MockTransport(handler))
    await client.aclose()  # virgin no-op
    assert client._client is None

    await client.plan(_planner_request())
    inner = client._client
    assert inner is not None
    await client.aclose()
    assert inner.is_closed
    await client.aclose()  # idempotent


@pytest.mark.asyncio
async def test_planner_transport_injection_serves_requests():
    """FR-006: HttpPlannerClient(transport=...) routes requests through the
    injected transport, mirroring the grounder's existing test seam."""
    served = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        served["n"] += 1
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(200, json=_chat_completion(_PLAN_CONTENT))

    client = HttpPlannerClient(
        PlannerModelConfig(base_url="http://test/v1"),
        transport=httpx.MockTransport(handler),
    )
    resp = await client.plan(_planner_request())
    assert resp.semantic_action.action_type == "wait"
    assert served["n"] == 1
    await client.aclose()
