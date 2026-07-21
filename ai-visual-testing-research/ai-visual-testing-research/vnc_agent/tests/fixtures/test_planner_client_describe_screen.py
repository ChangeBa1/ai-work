"""
describe_screen() MUST actually send the screenshot's bytes to the model
(contracts/model-provider-contract.md, 2026-07-22 wire-protocol fix) — the
image_ref path string alone is meaningless to a remote model server.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest

from vnc_agent.config import PlannerModelConfig
from vnc_agent.models.planner_client import HttpPlannerClient
from vnc_agent.models.provider import VisionUnderstandingRequest


def _chat_completion(content_obj: dict) -> dict:
    return {
        "choices": [
            {"message": {"content": json.dumps(content_obj, ensure_ascii=False)}}
        ]
    }


@pytest.mark.asyncio
async def test_describe_screen_inlines_image_bytes(tmp_path: Path):
    png_bytes = b"\x89PNG\r\n\x1a\nfake-but-nonempty-png-bytes"
    image_path = tmp_path / "before.png"
    image_path.write_bytes(png_bytes)

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        captured["body"] = body
        return httpx.Response(
            200,
            json=_chat_completion(
                {
                    "mode": "describe",
                    "description": "a login screen",
                    "confidence": 0.8,
                    "model_name": "planner-v1",
                }
            ),
        )

    transport = httpx.MockTransport(handler)
    client = HttpPlannerClient(PlannerModelConfig(base_url="http://test/v1"))

    orig_async_client = httpx.AsyncClient

    def patched(*args, **kwargs):
        kwargs["transport"] = transport
        return orig_async_client(*args, **kwargs)

    import vnc_agent.models.planner_client as mod

    mod.httpx.AsyncClient = patched  # type: ignore[assignment]
    try:
        resp = await client.describe_screen(
            VisionUnderstandingRequest(mode="describe", image_ref=str(image_path))
        )
    finally:
        mod.httpx.AsyncClient = orig_async_client  # type: ignore[assignment]

    assert resp.mode == "describe"
    assert resp.description == "a login screen"

    messages = captured["body"]["messages"]
    user_msg = messages[1]
    assert isinstance(user_msg["content"], list), (
        "content MUST be a multimodal list, not a plain JSON-dumped string "
        "(the pre-fix bug serialized the whole request, including image_ref, "
        "as inert text)"
    )
    image_parts = [c for c in user_msg["content"] if c.get("type") == "image_url"]
    assert image_parts, "expected an image_url content part"
    url = image_parts[0]["image_url"]["url"]
    assert url.startswith("data:image/"), "expected an inlined base64 data URI"
    b64_payload = url.split(",", 1)[1]
    assert base64.b64decode(b64_payload) == png_bytes, (
        "decoded image bytes must match the original screenshot file exactly"
    )
