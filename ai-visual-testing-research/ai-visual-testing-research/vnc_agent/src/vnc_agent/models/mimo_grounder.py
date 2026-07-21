"""MiMo-V2.5 Grounder via OpenCode Go API (FR-015~018, wire protocol 2026-07-22)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from vnc_agent.config import GrounderModelConfig
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.models.provider import GroundingRequest
from vnc_agent.models.planner_client import _image_url_content_part
from vnc_agent.models.response_parser import parse_grounding_response
from vnc_agent.runtime.exceptions import GroundingError, PlanValidationError

# contracts/model-provider-contract.md — system prompt for structured grounding JSON
_GROUNDING_SYSTEM_PROMPT = (
    "你是一个 GUI 元素定位助手。根据截图和目标描述，只输出一个 JSON 对象"
    "（不要 markdown 代码块、不要任何多余文字），格式为："
    '{"found": bool, "candidates": [{"bbox": [x1,y1,x2,y2], '
    '"confidence": 0~1 之间的数, "label": string 或 null, "reason": string}]}。'
    "bbox 为图片内的像素坐标；candidates 最多 3 个，按置信度降序；"
    '无法可靠判断时返回 {"found": false, "candidates": []}，不得编造坐标。'
)


def _target_text(target: dict[str, Any]) -> str:
    role = target.get("role")
    text = target.get("text")
    desc = target.get("description") or ""
    nearby = target.get("nearby_texts") or []
    return (
        f"目标：role={role}, text={text}, description={desc}, "
        f"nearby_texts={nearby}"
    )


def _candidates_summary(
    ocr_candidates: list[dict[str, Any]],
    template_candidates: list[dict[str, Any]],
) -> str:
    ocr_bits = []
    for item in (ocr_candidates or [])[:5]:
        t = item.get("text") or item.get("normalized_text") or ""
        if t:
            ocr_bits.append(str(t))
    tmpl_bits = []
    for item in (template_candidates or [])[:5]:
        tid = item.get("template_id") or ""
        if tid:
            tmpl_bits.append(str(tid))
    return (
        f"已知 OCR 候选（供参考）：{ocr_bits or '[]'}；"
        f"模板候选：{tmpl_bits or '[]'}"
    )


class MimoGrounderClient:
    """
    GrounderProvider default implementation.

    Translates internal GroundingRequest → OpenAI-compatible
    POST {base_url}/chat/completions with base64-inlined image (OpenCode Go).
    Callers continue to use GrounderProvider.ground() unchanged.
    """

    def __init__(
        self,
        cfg: GrounderModelConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.cfg = cfg
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        key = self.cfg.resolve_api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        return headers

    def _build_payload(self, request: GroundingRequest) -> dict[str, Any]:
        # Images sent to model API MUST NOT be masked (FR-049); image_ref is the
        # unmasked local path. Bytes are inlined — never send a bare path (server
        # cannot read our filesystem).
        user_text = (
            f"{_target_text(request.target)}。"
            f"{_candidates_summary(request.ocr_candidates, request.template_candidates)}"
        )
        return {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": _GROUNDING_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        _image_url_content_part(request.image_ref),
                    ],
                },
            ],
            # Prefer JSON mode when the provider supports it
            "response_format": {"type": "json_object"},
        }

    def _apply_crop_and_cap(
        self, result: GroundingResult, request: GroundingRequest
    ) -> GroundingResult:
        ox, oy = request.crop_offset
        candidates = list(result.candidates)
        if ox or oy:
            restored = []
            for c in candidates:
                x1, y1, x2, y2 = c.bbox
                restored.append(
                    c.model_copy(
                        update={"bbox": (x1 + ox, y1 + oy, x2 + ox, y2 + oy)}
                    )
                )
            candidates = restored
        if len(candidates) > 3:
            candidates = candidates[:3]
        top_k = min(3, self.cfg.top_k)
        candidates = candidates[:top_k]
        return result.model_copy(
            update={
                "candidates": candidates,
                "found": result.found and bool(candidates) if result.found else False,
                "model_name": self.cfg.model,
            }
        )

    async def ground(self, request: GroundingRequest) -> GroundingResult:
        payload = self._build_payload(request)
        url = f"{self.cfg.base_url.rstrip('/')}/chat/completions"
        client_kwargs: dict[str, Any] = {"timeout": self.cfg.timeout_seconds}
        if self._transport is not None:
            client_kwargs["transport"] = self._transport

        async with httpx.AsyncClient(**client_kwargs) as client:
            try:
                resp = await client.post(
                    url, headers=self._headers(), json=payload
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                raise GroundingError(f"grounding HTTP failed: {e}") from e
            except Exception as e:
                raise GroundingError(f"grounding request failed: {e}") from e

        # Parse chat.completion → GroundingResult. Parse failures MUST NOT kill
        # the whole TestRun: return found=false so Action Policy / recovery can
        # treat it as target_not_found (contract step 4, T102).
        try:
            result = parse_grounding_response(data, model_name=self.cfg.model)
        except (PlanValidationError, Exception):
            return GroundingResult(
                found=False,
                candidates=[],
                model_name=self.cfg.model,
            )

        return self._apply_crop_and_cap(result, request)


class StubGrounder:
    """Deterministic grounder for offline tests."""

    def __init__(self, result: GroundingResult | None = None) -> None:
        self.result = result or GroundingResult(
            found=False, candidates=[], model_name="stub"
        )
        self.calls: list[GroundingRequest] = []

    async def ground(self, request: GroundingRequest) -> GroundingResult:
        self.calls.append(request)
        ox, oy = request.crop_offset
        if ox or oy:
            restored = []
            for c in self.result.candidates:
                x1, y1, x2, y2 = c.bbox
                restored.append(
                    GroundingCandidate(
                        bbox=(x1 + ox, y1 + oy, x2 + ox, y2 + oy),
                        confidence=c.confidence,
                        label=c.label,
                        reason=c.reason,
                    )
                )
            return GroundingResult(
                found=self.result.found and bool(restored),
                candidates=restored,
                model_name=self.result.model_name,
            )
        return self.result
