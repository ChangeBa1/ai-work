"""MiMo-V2.5 Grounder via OpenCode Go API (FR-015~018, wire protocol 2026-07-22)."""

from __future__ import annotations

from typing import Any

import cv2
import httpx

from vnc_agent.config import GrounderModelConfig
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.models.coordinate_space import resolve_pixel_bbox, restore_original_bbox
from vnc_agent.models.planner_client import _KEEPALIVE_LIMITS, _image_url_content_part
from vnc_agent.models.provider import GroundingRequest
from vnc_agent.models.response_parser import parse_grounding_response
from vnc_agent.runtime.exceptions import GroundingError, PlanValidationError

# contracts/model-provider-contract.md — system prompt for structured grounding JSON
_GROUNDING_SYSTEM_PROMPT = (
    "你是一个 GUI 元素定位助手。根据截图和目标描述，只输出一个 JSON 对象"
    "（不要 markdown 代码块、不要任何多余文字），格式为："
    '{"found": bool, "candidates": [{"bbox": [x1,y1,x2,y2], '
    '"coordinate_space": "pixel" 或 "normalized_1000", '
    '"confidence": 0~1 之间的数, "label": string 或 null, "reason": string}]}。'
    "pixel 表示原始像素坐标；normalized_1000 表示 X/Y 分别按宽/高映射到 0~1000；"
    "每个候选必须独立声明 coordinate_space；candidates 最多 3 个，按置信度降序；"
    '无法可靠判断时返回 {"found": false, "candidates": []}，不得编造坐标。'
)


def _request_resolution(request: GroundingRequest) -> tuple[int, int] | None:
    if request.resolution is not None:
        return request.resolution
    image = cv2.imread(request.image_ref)
    if image is None:
        return None
    height, width = image.shape[:2]
    return (width, height)


def _resolve_coordinate_spaces(
    result: GroundingResult,
    request: GroundingRequest,
) -> GroundingResult:
    resolution = _request_resolution(request)
    candidates: list[GroundingCandidate] = []
    audit: list[dict[str, Any]] = []
    for index, candidate in enumerate(result.candidates):
        raw_bbox = candidate.raw_bbox or candidate.bbox
        siblings = [item for offset, item in enumerate(result.candidates) if offset != index]
        resolved = (
            resolve_pixel_bbox(
                raw_bbox,
                candidate.coordinate_space,
                resolution,
                siblings=siblings,
            )
            if resolution is not None
            else (raw_bbox if candidate.coordinate_space in (None, "pixel") else None)
        )
        accepted = resolved is not None
        audit.append(
            {
                "coordinate_space": candidate.coordinate_space,
                "raw_bbox": raw_bbox,
                "resolved_bbox": resolved,
                "accepted": accepted,
            }
        )
        if accepted:
            candidates.append(
                candidate.model_copy(update={"bbox": resolved, "raw_bbox": raw_bbox})
            )
    return result.model_copy(
        update={
            "found": result.found and bool(candidates),
            "candidates": candidates,
            "coordinate_space_audit": audit,
        }
    )


def _ui_index_candidates_to_grounding(
    ui_index_candidates: list[dict[str, Any]],
) -> list[GroundingCandidate]:
    """Feature 007 (FR-009): convert `GroundingRequest.ui_index_candidates`
    (derived from `Element.normalized_bounds`) into `GroundingCandidate`
    objects tagged with a `"ui_index:"` reason prefix so the final
    `GroundingResult.candidates` always makes its ocr/template/ui_index
    provenance traceable (contracts/ui-index-consumer-interfaces.md §9).
    These candidates are never used as final coordinates directly — they
    are merged in *before* `_resolve_coordinate_spaces()` and go through
    the exact same `resolve_pixel_bbox()` conversion/rejection path as
    every model-produced candidate."""
    converted: list[GroundingCandidate] = []
    for item in ui_index_candidates or []:
        bbox = item.get("bbox")
        if not bbox or len(bbox) != 4:
            continue
        try:
            bbox_t = (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))
        except (TypeError, ValueError):
            continue
        label = item.get("label")
        reason = item.get("reason") or label or ""
        try:
            confidence = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        confidence = min(max(confidence, 0.0), 1.0)
        converted.append(
            GroundingCandidate(
                bbox=bbox_t,
                coordinate_space=item.get("coordinate_space", "normalized_1000"),
                raw_bbox=bbox_t,
                confidence=confidence,
                label=label,
                reason=f"ui_index:{reason}" if reason else "ui_index",
            )
        )
    return converted


def _merge_ui_index_candidates(
    result: GroundingResult,
    request: GroundingRequest,
) -> GroundingResult:
    extra = _ui_index_candidates_to_grounding(request.ui_index_candidates)
    if not extra:
        return result
    merged = sorted([*result.candidates, *extra], key=lambda c: c.confidence, reverse=True)[:3]
    return result.model_copy(update={"candidates": merged, "found": bool(merged)})


def _restore_and_cap(
    result: GroundingResult,
    request: GroundingRequest,
    *,
    model_name: str,
    top_k: int = 3,
) -> GroundingResult:
    """Feature 014 (FR-004): map already coordinate-space-resolved candidate
    bboxes from the model-seen image back to original frame pixels via
    ``round(v / scale_factor) + crop_offset``, strictly rejecting degenerate
    or out-of-original-bounds results (never clamping). Shared by
    MimoGrounderClient and StubGrounder so tests exercise the same math.
    Identity for the legacy full-screen path (scale=1, offset=(0, 0),
    original_resolution=None)."""
    ox, oy = request.crop_offset
    scale = request.scale_factor
    candidates: list[GroundingCandidate] = []
    audit = list(result.coordinate_space_audit)
    needs_restore = bool(ox or oy) or scale != 1.0 or request.original_resolution is not None
    for candidate in result.candidates:
        if needs_restore:
            restored = restore_original_bbox(
                candidate.bbox,
                scale_factor=scale,
                crop_offset=(ox, oy),
                original_resolution=request.original_resolution,
            )
            audit.append(
                {
                    "stage": "zoom_restore",
                    "model_bbox": candidate.bbox,
                    "scale_factor": scale,
                    "crop_offset": (ox, oy),
                    "restored_bbox": restored,
                    "accepted": restored is not None,
                }
            )
            if restored is None:
                continue
            candidates.append(candidate.model_copy(update={"bbox": restored}))
        else:
            candidates.append(candidate)
    candidates = candidates[: min(3, top_k)]
    return result.model_copy(
        update={
            "candidates": candidates,
            "found": result.found and bool(candidates),
            "model_name": model_name or result.model_name,
            "coordinate_space_audit": audit,
        }
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
    ui_index_candidates: list[dict[str, Any]] | None = None,
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
    ui_bits = []
    for item in (ui_index_candidates or [])[:5]:
        label = item.get("label") or item.get("reason") or ""
        if label:
            ui_bits.append(str(label))
    return (
        f"已知 OCR 候选（供参考）：{ocr_bits or '[]'}；"
        f"模板候选：{tmpl_bits or '[]'}；"
        f"UI 索引候选：{ui_bits or '[]'}"
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
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Feature 017 (httpx-client-reuse): lazily create one long-lived
        AsyncClient per instance (on the first request's event loop) and reuse
        its keep-alive pool for every subsequent ground() call. An injected
        test transport backs this same long-lived client."""
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
        """Close the shared client. Idempotent; safe when no request was ever
        made; a later request lazily re-creates a fresh client (FR-003)."""
        if self._client is not None:
            client, self._client = self._client, None
            await client.aclose()

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
            f"{_candidates_summary(
                request.ocr_candidates,
                request.template_candidates,
                request.ui_index_candidates,
            )}"
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

    async def ground(self, request: GroundingRequest) -> GroundingResult:
        payload = self._build_payload(request)
        url = f"{self.cfg.base_url.rstrip('/')}/chat/completions"
        client = self._get_client()
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

        # Feature 014 (FR-004) pipeline order: parse → merge ui_index →
        # coordinate-space resolution in the model-seen image's resolution →
        # strict restore (÷scale_factor, +crop_offset) back to original frame
        # pixels. Identity for the legacy full-screen path.
        merged = _merge_ui_index_candidates(result, request)
        resolved = _resolve_coordinate_spaces(merged, request)
        return _restore_and_cap(
            resolved, request, model_name=self.cfg.model, top_k=self.cfg.top_k
        )


class StubGrounder:
    """Deterministic grounder for offline tests."""

    def __init__(self, result: GroundingResult | None = None) -> None:
        self.result = result or GroundingResult(
            found=False, candidates=[], model_name="stub"
        )
        self.calls: list[GroundingRequest] = []

    async def ground(self, request: GroundingRequest) -> GroundingResult:
        self.calls.append(request)
        # Same finalize path as MimoGrounderClient (Feature 014): stub-declared
        # bboxes are interpreted in the model-seen image's coordinate space and
        # go through the identical resolve + restore math.
        merged = _merge_ui_index_candidates(self.result, request)
        resolved = _resolve_coordinate_spaces(merged, request)
        return _restore_and_cap(
            resolved, request, model_name=self.result.model_name, top_k=3
        )
