"""Wrong-click post-mortem diagnosis client (feature 023, FR-001/FR-002).

A third, read-only model role beside Planner and Grounder: given the
pre-click frame plus an *annotated* post-click frame (the actual click point
marked and the intended target region framed, both at original resolution)
and the deterministic feature-022 evidence summary, the model answers what
was actually clicked and where the intended target really is.

Wire protocol: the existing OpenAI-compatible ``POST /chat/completions``
channel with the **grounder's** endpoint/model config (``models.grounder``)
— a separate lightweight client so the MiMo grounding chain stays untouched.
Parsing is strict fail-safe (spec FR-002): any decode/validation problem
raises :class:`PostmortemParseError`, and bbox resolution goes through the
single-point strict converter ``models/coordinate_space.resolve_pixel_bbox``
(never clamp, never guess).
"""

from __future__ import annotations

import base64
from typing import Any, Literal, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel, Field, model_validator

from vnc_agent.config import GrounderModelConfig
from vnc_agent.models.coordinate_space import resolve_pixel_bbox
from vnc_agent.models.image_payload import _image_url_content_part
from vnc_agent.models.planner_client import _KEEPALIVE_LIMITS
from vnc_agent.models.response_parser import _as_dict
from vnc_agent.runtime.exceptions import PlanValidationError


class PostmortemError(Exception):
    """Transport/request failure of a post-mortem diagnosis call."""


class PostmortemParseError(Exception):
    """Strict parse/validation failure of a post-mortem diagnosis response."""


# Spec FR-001 — system prompt for the strict diagnosis JSON. Mirrors the
# grounding prompt conventions (JSON only, no markdown, no invented
# coordinates, per-response coordinate_space declaration).
_POSTMORTEM_SYSTEM_PROMPT = (
    "你是一个 GUI 点击事后诊断助手。你会看到两张图："
    "图1 是点击前的屏幕；图2 是点击后的屏幕，其上已标注了"
    "红色圆圈+十字（agent 实际点击的位置）和橙色矩形框（agent 想点的目标区域）。"
    "结合目标描述与变化证据，判断实际点中了什么控件，以及想点的目标现在在哪里。"
    "只输出一个 JSON 对象（不要 markdown 代码块、不要任何多余文字），格式为："
    '{"clicked_element": string, "target_found": bool, '
    '"corrected_bbox": [x1,y1,x2,y2] 或 null, '
    '"coordinate_space": "pixel" 或 "normalized_1000", '
    '"confidence": 0~1 之间的数, "reason": string}。'
    "corrected_bbox 是目标控件在图2（原始分辨率）上的外接框；"
    "pixel 表示原始像素坐标；normalized_1000 表示 X/Y 分别按宽/高映射到 0~1000。"
    "目标不可见或无法可靠判断时返回 target_found=false 且 corrected_bbox=null，"
    "不得编造坐标。"
)


class PostmortemDiagnosis(BaseModel):
    """Strict diagnosis answer (spec FR-002). ``target_found`` and
    ``confidence`` are mandatory; ``target_found=true`` without a bbox is a
    validation error (fail-safe: an unusable "found" is a failed diagnosis)."""

    clicked_element: str = ""
    target_found: bool
    corrected_bbox: tuple[int, int, int, int] | None = None
    coordinate_space: Literal["pixel", "normalized_1000"] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = ""

    @model_validator(mode="after")
    def _found_requires_bbox(self) -> PostmortemDiagnosis:
        if self.target_found and self.corrected_bbox is None:
            raise ValueError("target_found=true requires a corrected_bbox")
        return self


def parse_postmortem_diagnosis(raw: str | dict[str, Any]) -> PostmortemDiagnosis:
    """Parse a diagnosis from a chat.completion envelope or bare JSON.

    Strict path (spec FR-002): decode failure, non-object root, missing
    mandatory fields, malformed bbox and out-of-range confidence all raise
    :class:`PostmortemParseError` — the caller treats that as a failed
    diagnosis, never as data to repair.
    """
    try:
        data = _as_dict(raw)
    except PlanValidationError as e:
        raise PostmortemParseError(str(e)) from e
    bbox = data.get("corrected_bbox")
    if bbox is not None:
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            raise PostmortemParseError(f"corrected_bbox must be [x1,y1,x2,y2], got {bbox!r}")
        try:
            data = {**data, "corrected_bbox": tuple(int(v) for v in bbox)}
        except (TypeError, ValueError) as e:
            raise PostmortemParseError(f"corrected_bbox not integer-coercible: {e}") from e
    try:
        return PostmortemDiagnosis.model_validate(data)
    except Exception as e:
        raise PostmortemParseError(f"PostmortemDiagnosis validation failed: {e}") from e


def resolve_corrected_bbox(
    diagnosis: PostmortemDiagnosis,
    resolution: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    """Strictly resolve the diagnosis bbox to original-frame pixels.

    Delegates to the single-point converter ``resolve_pixel_bbox`` (014/018
    lineage: no clamping, no guessing; an undeclared coordinate_space is
    accepted only when exactly one interpretation is valid). None = reject.
    """
    if diagnosis.corrected_bbox is None:
        return None
    return resolve_pixel_bbox(
        diagnosis.corrected_bbox,
        diagnosis.coordinate_space,
        resolution,
        siblings=(),
    )


class PostmortemRequest(BaseModel):
    """One diagnosis request. ``annotated_image_png`` is the already-rendered
    annotated post-click frame at original resolution (bytes are inlined into
    the payload — the annotated model image is never persisted)."""

    before_image_ref: str
    annotated_image_png: bytes
    target: dict[str, Any]
    evidence_summary: str
    resolution: tuple[int, int]


@runtime_checkable
class PostmortemProvider(Protocol):
    async def diagnose(self, request: PostmortemRequest) -> dict[str, Any]: ...


def _png_bytes_content_part(png_bytes: bytes) -> dict[str, Any]:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{b64}"},
    }


def _user_text(request: PostmortemRequest) -> str:
    target = request.target
    width, height = request.resolution
    return (
        f"目标：role={target.get('role')}, text={target.get('text')}, "
        f"description={target.get('description') or ''}, "
        f"nearby_texts={target.get('nearby_texts') or []}。"
        f"屏幕分辨率：{width}x{height}。"
        f"点错证据（确定性像素分析）：{request.evidence_summary}"
    )


class HttpPostmortemClient:
    """PostmortemProvider over the OpenAI-compatible chat.completions API.

    Reuses the grounder's endpoint/model config (``models.grounder``) and the
    feature-017 long-lived keep-alive AsyncClient pattern. Returns the raw
    chat.completion payload — strict parsing stays with the caller so stubs
    and the HTTP client exercise the identical parse path.
    """

    def __init__(
        self,
        cfg: GrounderModelConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.cfg = cfg
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            client_kwargs: dict[str, Any] = {
                "timeout": self.cfg.timeout_seconds,
                "limits": _KEEPALIVE_LIMITS,
            }
            if self._transport is not None:
                client_kwargs["transport"] = self._transport
            self._client = httpx.AsyncClient(**client_kwargs)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            client, self._client = self._client, None
            await client.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        key = self.cfg.resolve_api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _build_payload(self, request: PostmortemRequest) -> dict[str, Any]:
        # FR-049 convention: images for the model API are the unmasked
        # model-facing files/bytes; both are inlined as base64 (the server
        # cannot read our filesystem).
        return {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": _POSTMORTEM_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _user_text(request)},
                        _image_url_content_part(request.before_image_ref),
                        _png_bytes_content_part(request.annotated_image_png),
                    ],
                },
            ],
            "response_format": {"type": "json_object"},
        }

    async def diagnose(self, request: PostmortemRequest) -> dict[str, Any]:
        payload = self._build_payload(request)
        url = f"{self.cfg.base_url.rstrip('/')}/chat/completions"
        client = self._get_client()
        try:
            resp = await client.post(url, headers=self._headers(), json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            raise PostmortemError(f"postmortem HTTP failed: {e}") from e
        except Exception as e:
            raise PostmortemError(f"postmortem request failed: {e}") from e


class StubPostmortemClient:
    """Deterministic PostmortemProvider for offline tests: returns scripted
    raw chat.completion envelopes (last one repeats), recording requests."""

    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        self.responses = responses
        self.calls: list[PostmortemRequest] = []

    @staticmethod
    def envelope(content: str) -> dict[str, Any]:
        return {"choices": [{"message": {"content": content}}]}

    async def diagnose(self, request: PostmortemRequest) -> dict[str, Any]:
        self.calls.append(request)
        item = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item
