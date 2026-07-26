"""Feature 018 (model-image-downscale): planner-bound screenshots are
proportionally downscaled + JPEG-encoded before upload; the Grounder's
payload stays byte-identical to the original file (red line, FR-004);
`enabled=false` and undecodable inputs are byte-identical to the pre-018
passthrough (FR-002)."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest

from vnc_agent.config import GrounderModelConfig, PlannerModelConfig
from vnc_agent.models.image_payload import (
    _image_url_content_part,
    planner_image_url_content_part,
)
from vnc_agent.models.mimo_grounder import MimoGrounderClient
from vnc_agent.models.planner_client import HttpPlannerClient
from vnc_agent.models.provider import GroundingRequest, VisionUnderstandingRequest


def _write_png(path: Path, width: int, height: int) -> None:
    rng = np.random.default_rng(seed=width * 100003 + height)
    image = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def _decode_data_uri(part: dict) -> tuple[str, bytes]:
    url = part["image_url"]["url"]
    header, b64 = url.split(",", 1)
    return header, base64.b64decode(b64)


def _decoded_shape(raw: bytes) -> tuple[int, int]:
    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image is not None
    height, width = image.shape[:2]
    return width, height


# ---------------------------------------------------------------- helper (US1)


def test_downscale_geometry_proportional(tmp_path: Path):
    png = tmp_path / "wide.png"
    _write_png(png, 2048, 1024)
    part = planner_image_url_content_part(str(png), max_width=1024, jpeg_quality=80)
    header, raw = _decode_data_uri(part)
    assert header == "data:image/jpeg;base64"
    assert _decoded_shape(raw) == (1024, 512), "must shrink to max_width, aspect kept"


def test_small_image_never_upscaled(tmp_path: Path):
    png = tmp_path / "small.png"
    _write_png(png, 640, 480)
    part = planner_image_url_content_part(str(png), max_width=1024, jpeg_quality=80)
    _, raw = _decode_data_uri(part)
    assert _decoded_shape(raw) == (640, 480), "smaller-than-max images keep geometry"


def test_jpeg_data_uri_format(tmp_path: Path):
    png = tmp_path / "img.png"
    _write_png(png, 1500, 900)
    part = planner_image_url_content_part(str(png))
    assert part["type"] == "image_url"
    url = part["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    _, raw = _decode_data_uri(part)
    assert raw[:2] == b"\xff\xd8", "payload must be real JPEG bytes (SOI marker)"


def test_downscaled_payload_is_much_smaller(tmp_path: Path):
    png = tmp_path / "big.png"
    _write_png(png, 1920, 1080)
    down = planner_image_url_content_part(str(png), max_width=1024, jpeg_quality=80)
    orig = _image_url_content_part(str(png))
    assert len(down["image_url"]["url"]) < len(orig["image_url"]["url"])


def test_undecodable_file_falls_back_to_passthrough(tmp_path: Path):
    fake = tmp_path / "fake.png"
    fake.write_bytes(b"\x89PNG\r\n\x1a\nfake-but-nonempty-png-bytes")
    part = planner_image_url_content_part(str(fake), enabled=True)
    assert part == _image_url_content_part(str(fake)), (
        "undecodable input must produce the byte-identical pre-018 passthrough "
        "(preprocessing must never turn a working model call into an error)"
    )


def test_config_defaults():
    cfg = PlannerModelConfig()
    assert cfg.planner_image_downscale_enabled is True
    assert cfg.planner_image_max_width == 1024
    assert cfg.planner_image_jpeg_quality == 80


# ------------------------------------------------------------ kill switch (US3)


def test_disabled_is_byte_identical_to_pre_018(tmp_path: Path):
    png = tmp_path / "shot.png"
    _write_png(png, 1600, 900)
    part = planner_image_url_content_part(
        str(png), enabled=False, max_width=64, jpeg_quality=1
    )
    assert part == _image_url_content_part(str(png))
    _, raw = _decode_data_uri(part)
    assert raw == png.read_bytes(), "disabled path must carry raw file bytes"


# --------------------------------------------------- describe_screen wire (US1)


def _chat_completion(content_obj: dict) -> dict:
    return {
        "choices": [
            {"message": {"content": json.dumps(content_obj, ensure_ascii=False)}}
        ]
    }


def _capture_transport(captured: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json=_chat_completion(
                {
                    "mode": "describe",
                    "description": "screen",
                    "confidence": 0.9,
                    "model_name": "planner-v1",
                }
            ),
        )

    return httpx.MockTransport(handler)


def _image_parts(body: dict) -> list[dict]:
    user_content = body["messages"][1]["content"]
    return [c for c in user_content if c.get("type") == "image_url"]


@pytest.mark.asyncio
async def test_describe_screen_sends_downscaled_jpeg(tmp_path: Path):
    png = tmp_path / "before.png"
    _write_png(png, 2000, 1000)
    captured: dict = {}
    client = HttpPlannerClient(
        PlannerModelConfig(base_url="http://test/v1"),
        transport=_capture_transport(captured),
    )
    resp = await client.describe_screen(
        VisionUnderstandingRequest(mode="describe", image_ref=str(png))
    )
    await client.aclose()
    assert resp.mode == "describe"
    parts = _image_parts(captured["body"])
    assert parts, "expected an image_url content part"
    url = parts[0]["image_url"]["url"]
    assert url.startswith("data:image/jpeg;base64,")
    raw = base64.b64decode(url.split(",", 1)[1])
    assert _decoded_shape(raw) == (1024, 512), (
        "describe_screen must upload the proportionally downscaled JPEG "
        "(2000x1000 -> 1024x512 at the default max width)"
    )


@pytest.mark.asyncio
async def test_describe_screen_disabled_matches_original_bytes(tmp_path: Path):
    png = tmp_path / "before.png"
    _write_png(png, 2000, 1000)
    captured: dict = {}
    client = HttpPlannerClient(
        PlannerModelConfig(
            base_url="http://test/v1", planner_image_downscale_enabled=False
        ),
        transport=_capture_transport(captured),
    )
    await client.describe_screen(
        VisionUnderstandingRequest(mode="describe", image_ref=str(png))
    )
    await client.aclose()
    url = _image_parts(captured["body"])[0]["image_url"]["url"]
    assert url == "data:image/png;base64," + base64.b64encode(
        png.read_bytes()
    ).decode("ascii"), "kill switch must restore the pre-018 payload byte-for-byte"


# ----------------------------------------------------- grounder red line (US2)


def test_grounder_payload_byte_identical_to_original_file(tmp_path: Path):
    """FR-004 red line: whatever the planner downscale config says, the
    Grounder outputs pixel coordinates and MUST see the original image —
    its data URI is exactly base64(raw file bytes) with the original mime."""
    png = tmp_path / "frame.png"
    _write_png(png, 2000, 1000)
    grounder = MimoGrounderClient(GrounderModelConfig(base_url="http://test/v1"))
    payload = grounder._build_payload(
        GroundingRequest(
            image_ref=str(png),
            target={"role": "button", "text": "OK", "description": "ok button"},
        )
    )
    parts = [
        c for c in payload["messages"][1]["content"] if c.get("type") == "image_url"
    ]
    assert len(parts) == 1
    expected = "data:image/png;base64," + base64.b64encode(png.read_bytes()).decode(
        "ascii"
    )
    assert parts[0]["image_url"]["url"] == expected
    # and it is the same output the shared passthrough helper produces
    assert parts[0] == _image_url_content_part(str(png))
