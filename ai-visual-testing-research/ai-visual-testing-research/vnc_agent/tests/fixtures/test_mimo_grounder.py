"""US4 / T101-T103: Grounding wire protocol (OpenCode Go / OpenAI chat.completions)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest

from vnc_agent.config import GrounderModelConfig
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.models.mimo_grounder import MimoGrounderClient, StubGrounder
from vnc_agent.models.provider import GroundingRequest
from vnc_agent.models.response_parser import parse_grounding_response


def test_parse_found_false():
    r = parse_grounding_response({"found": False, "candidates": []})
    assert r.found is False
    assert r.candidates == []


def test_parse_candidates_capped():
    cands = [
        {"bbox": [i, i, i + 5, i + 5], "confidence": 0.9 - i * 0.01} for i in range(5)
    ]
    r = parse_grounding_response({"found": True, "candidates": cands}, model_name="m")
    assert len(r.candidates) <= 3


def test_parse_chat_completion_envelope():
    """T102: parse from OpenAI chat.completion shape."""
    payload = {
        "found": True,
        "candidates": [
            {
                "bbox": [10, 20, 30, 40],
                "confidence": 0.91,
                "label": "保存",
                "reason": "right bottom",
            }
        ],
    }
    envelope = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
                "finish_reason": "stop",
            }
        ],
    }
    r = parse_grounding_response(envelope, model_name="mimo-v2.5")
    assert r.found is True
    assert len(r.candidates) == 1
    assert r.candidates[0].bbox == (10, 20, 30, 40)
    assert r.model_name == "mimo-v2.5"


def test_parse_chat_completion_with_json_fence():
    """T102: strip ```json fences before parsing."""
    inner = {
        "found": True,
        "candidates": [
            {"bbox": [1, 2, 3, 4], "confidence": 0.8, "label": None, "reason": "x"}
        ],
    }
    fenced = "```json\n" + json.dumps(inner) + "\n```"
    envelope = {
        "choices": [{"message": {"role": "assistant", "content": fenced}}]
    }
    r = parse_grounding_response(envelope, model_name="m")
    assert r.found is True
    assert r.candidates[0].bbox == (1, 2, 3, 4)


@pytest.mark.asyncio
async def test_crop_offset_restore():
    base = GroundingResult(
        found=True,
        candidates=[GroundingCandidate(bbox=(5, 5, 15, 15), confidence=0.9)],
        model_name="stub",
    )
    g = StubGrounder(base)
    res = await g.ground(
        GroundingRequest(
            image_ref="x.png",
            crop_offset=(100, 50),
            target={"description": "btn"},
        )
    )
    assert res.candidates[0].bbox == (105, 55, 115, 65)


def _png_bytes(tmp_path: Path) -> Path:
    img = np.zeros((40, 60, 3), dtype=np.uint8)
    img[10:30, 20:40] = (0, 200, 0)
    path = tmp_path / "screen.png"
    cv2.imwrite(str(path), img)
    return path


@pytest.mark.asyncio
async def test_mimo_grounder_openai_wire_protocol(tmp_path: Path):
    """
    T101/T103: POST /chat/completions with OpenAI messages + base64 image,
    not the old /v1/ground custom shape.
    """
    image_path = _png_bytes(tmp_path)
    raw_bytes = image_path.read_bytes()
    captured: dict = {}

    grounding_json = {
        "found": True,
        "candidates": [
            {
                "bbox": [20, 10, 40, 30],
                "coordinate_space": "pixel",
                "confidence": 0.93,
                "label": "btn",
                "reason": "green patch",
            }
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        body = json.loads(request.content.decode("utf-8"))
        captured["body"] = body
        # Assert OpenAI-compatible shape (not /v1/ground custom payload)
        assert request.method == "POST"
        assert request.url.path.endswith("/chat/completions")
        assert "messages" in body
        assert body["model"] == "mimo-v2.5"
        assert "image_ref" not in body  # must not forward internal path field
        assert "crop_offset" not in body
        msgs = body["messages"]
        assert msgs[0]["role"] == "system"
        assert msgs[1]["role"] == "user"
        content = msgs[1]["content"]
        assert isinstance(content, list)
        types = {part["type"] for part in content}
        assert "text" in types
        assert "image_url" in types
        img_part = next(p for p in content if p["type"] == "image_url")
        url = img_part["image_url"]["url"]
        assert url.startswith("data:image/png;base64,")
        b64 = url.split(",", 1)[1]
        assert base64.b64decode(b64) == raw_bytes

        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(grounding_json),
                        },
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    cfg = GrounderModelConfig(
        base_url="https://opencode.ai/zen/go/v1",
        model="mimo-v2.5",
        timeout_seconds=10,
    )
    client = MimoGrounderClient(cfg, transport=httpx.MockTransport(handler))
    result = await client.ground(
        GroundingRequest(
            image_ref=str(image_path),
            crop_offset=(0, 0),
            target={"role": "button", "text": "保存", "description": "main"},
            ocr_candidates=[{"text": "保存"}],
            template_candidates=[],
        )
    )
    assert result.found is True
    assert len(result.candidates) == 1
    assert result.candidates[0].bbox == (20, 10, 40, 30)
    assert result.model_name == "mimo-v2.5"
    assert "/chat/completions" in captured["url"]
    assert "/v1/ground" not in captured["url"]


@pytest.mark.asyncio
async def test_mimo_grounder_fenced_json_response(tmp_path: Path):
    """T103: content wrapped in ```json fence still parses."""
    image_path = _png_bytes(tmp_path)
    inner = {
        "found": True,
        "candidates": [
                {
                    "bbox": [5, 5, 15, 15],
                    "coordinate_space": "pixel",
                    "confidence": 0.7,
                    "label": None,
                    "reason": "ok",
                }
        ],
    }
    fenced = "```json\n" + json.dumps(inner) + "\n```"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": fenced}}
                ]
            },
        )

    cfg = GrounderModelConfig(base_url="https://example.test/v1", model="mimo-v2.5")
    client = MimoGrounderClient(cfg, transport=httpx.MockTransport(handler))
    result = await client.ground(
        GroundingRequest(
            image_ref=str(image_path),
            target={"description": "x"},
        )
    )
    assert result.found is True
    assert result.candidates[0].bbox == (5, 5, 15, 15)


@pytest.mark.asyncio
async def test_mimo_grounder_parse_failure_returns_not_found(tmp_path: Path):
    """T102: invalid model content → found=false (recovery path), not raise."""
    image_path = _png_bytes(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "this is not json at all",
                        }
                    }
                ]
            },
        )

    cfg = GrounderModelConfig(base_url="https://example.test/v1", model="mimo-v2.5")
    client = MimoGrounderClient(cfg, transport=httpx.MockTransport(handler))
    result = await client.ground(
        GroundingRequest(image_ref=str(image_path), target={"description": "x"})
    )
    assert result.found is False
    assert result.candidates == []


@pytest.mark.asyncio
async def test_mimo_grounder_applies_crop_offset(tmp_path: Path):
    image_path = _png_bytes(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "found": True,
                                    "candidates": [
                                        {
                                                "bbox": [5, 5, 15, 15],
                                                "coordinate_space": "pixel",
                                            "confidence": 0.9,
                                            "label": None,
                                            "reason": "local",
                                        }
                                    ],
                                }
                            ),
                        }
                    }
                ]
            },
        )

    cfg = GrounderModelConfig(base_url="https://example.test/v1", model="mimo-v2.5")
    client = MimoGrounderClient(cfg, transport=httpx.MockTransport(handler))
    result = await client.ground(
        GroundingRequest(
            image_ref=str(image_path),
            crop_offset=(100, 50),
            resolution=(200, 100),
            target={"description": "x"},
        )
    )
    assert result.candidates[0].bbox == (105, 55, 115, 65)
