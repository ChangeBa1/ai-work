"""HTTP Planner client (OpenAI-compatible) via httpx."""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from vnc_agent.config import PlannerModelConfig
from vnc_agent.domain.action import SemanticAction
from vnc_agent.models.provider import (
    PlannerRequest,
    PlannerResponse,
    VisionUnderstandingRequest,
    VisionUnderstandingResponse,
)
from vnc_agent.models.response_parser import parse_planner_response
from vnc_agent.runtime.exceptions import PlanValidationError

# Feature 017 (httpx-client-reuse): shared connection-pool limits for the
# long-lived per-instance AsyncClient. Model calls are sequential today, so
# these are headroom; keepalive_expiry=30s keeps the TLS connection warm
# across a typical plan→ground→verify cadence without holding sockets forever.
_KEEPALIVE_LIMITS = httpx.Limits(
    max_connections=10,
    max_keepalive_connections=5,
    keepalive_expiry=30.0,
)

_PLANNER_SYSTEM_PROMPT = (
    "你是一个 GUI 测试的语义动作规划器（Planner）。你会收到当前测试步骤的意图"
    "（step_intent）、预期结果（expected）和当前屏幕的结构化观察（structured_screen，"
    "含 OCR 文字、模板匹配、变化检测等），你的唯一任务是决定"
    "\"下一步应该执行哪一个语义动作\"，MUST NOT 输出任何裸屏幕坐标。\n\n"
    "MUST 只输出一个 JSON 对象（不要 markdown 代码块、不要任何多余文字、不要把"
    "整个回答写成一句自然语言），字段与类型严格如下：\n"
    "{\n"
    '  "task_completed_hint": <boolean>,  // 仅供参考的提示：你认为该步骤是否已经\n'
    "                                      // 达成目标，MUST 是 true 或 false，\n"
    "                                      // 不是一段解释文字\n"
    '  "semantic_action": {\n'
    '    "action_id": <string>,           // 任意唯一字符串，如 "act-1"\n'
    '    "intent": <string>,              // 简短描述，如 "点击登录按钮"\n'
    '    "action_type": <string>,         // 必须是以下枚举值之一：\n'
    "                                      // click, double_click, right_click,\n"
    "                                      // type_text, press_key, hotkey,\n"
    "                                      // scroll, drag, wait, finish\n"
    '    "target": {                      // 仅当 action_type 需要定位目标（如\n'
    "                                      // click/double_click/right_click/\n"
    "                                      // scroll/drag）时提供，否则省略或为 null\n"
    '      "role": <string|null>,\n'
    '      "text": <string|null>,\n'
    '      "description": <string>,\n'
    '      "nearby_texts": [<string>, ...]\n'
    "    },\n"
    '    "text_value": <string|null>,     // 仅 action_type=type_text 时提供\n'
    '    "keys": [<string>, ...],         // 仅 action_type=press_key/hotkey 时\n'
    "                                      // 提供，如 [\"ctrl\",\"s\"]，否则为空数组\n"
    '    "risk_level": "low"\n'
    "  },\n"
    '  "needs_more_observation": <boolean>\n'
    "}\n\n"
    "示例（意图是关闭遮挡的安全提示弹窗）：\n"
    '{"task_completed_hint": false, "semantic_action": {"action_id": "act-1", '
    '"intent": "按 Escape 关闭安全提示弹窗", "action_type": "press_key", '
    '"target": null, "text_value": null, "keys": ["escape"], "risk_level": "low"}, '
    '"needs_more_observation": false}\n\n'
    "semantic_action MUST NOT 包含任何坐标/bbox/x/y 字段；一次只回答一个动作，"
    "不要在一次响应里打包多个步骤。"
)


def _image_url_content_part(image_path: str) -> dict[str, Any]:
    """
    Read a local image file and return an OpenAI-compatible multimodal
    `image_url` content part with the bytes inlined as a base64 data URI.

    Wire-protocol fix (contracts/model-provider-contract.md, 2026-07-22):
    the model server cannot read our local filesystem, so `image_ref`
    MUST be resolved to actual bytes before being sent, never passed as a
    bare path string.
    """
    path = Path(image_path)
    data = path.read_bytes()
    mime, _ = mimetypes.guess_type(path.name)
    mime = mime or "image/png"
    b64 = base64.b64encode(data).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{b64}"},
    }


class HttpPlannerClient:
    def __init__(
        self,
        cfg: PlannerModelConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.cfg = cfg
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Feature 017: lazily create one long-lived AsyncClient per instance
        (on the first request's event loop) and reuse its keep-alive pool for
        every subsequent request. Client default timeout is `timeout_seconds`;
        describe_screen() overrides per request (FR-005)."""
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

    async def plan(self, request: PlannerRequest) -> PlannerResponse:
        payload = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        request.model_dump(mode="json"), ensure_ascii=False
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        client = self._get_client()
        try:
            resp = await client.post(
                f"{self.cfg.base_url.rstrip('/')}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return parse_planner_response(content)
        except (httpx.HTTPError, KeyError, IndexError, PlanValidationError) as e:
            raise PlanValidationError(f"planner plan() failed: {e}") from e

    async def describe_screen(
        self, request: VisionUnderstandingRequest
    ) -> VisionUnderstandingResponse:
        # Wire-protocol fix (contracts/model-provider-contract.md, 2026-07-22):
        # the image bytes MUST actually be sent — image_ref is a local path the
        # model server cannot read, so it must never be forwarded as bare text.
        text_parts = [f"mode={request.mode}"]
        if request.question:
            text_parts.append(f"question={request.question}")
        if request.structured_screen_hint:
            text_parts.append(
                "structured_screen_hint="
                + json.dumps(request.structured_screen_hint, ensure_ascii=False)
            )
        user_content: list[dict[str, Any]] = [
            {"type": "text", "text": "\n".join(text_parts)},
            _image_url_content_part(request.image_ref),
        ]
        payload = {
            "model": self.cfg.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Look at the attached screenshot. Describe the screen or "
                        "answer the question about it. Return JSON matching "
                        "VisionUnderstandingResponse "
                        '({"mode","description","answer","confidence","reason",'
                        '"model_name"}). For answer_question mode, answer MUST be '
                        'exactly one of: "passed", "failed", "uncertain" '
                        "(never not_passed / pass / fail / yes / no)."
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        }
        # Feature 017: the shared client's default timeout is timeout_seconds;
        # describe_screen keeps its own (possibly longer) budget via a
        # per-request override — behavior identical to the old per-call client.
        client = self._get_client()
        try:
            resp = await client.post(
                f"{self.cfg.base_url.rstrip('/')}/chat/completions",
                headers=self._headers(),
                json=payload,
                timeout=self.cfg.describe_timeout(),
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, str):
                content = content.strip()
                if content.startswith("```"):
                    content = content.strip("`")
                    if content.lower().startswith("json"):
                        content = content[4:]
                    content = content.strip()
                parsed = json.loads(content)
            else:
                parsed = content
            return VisionUnderstandingResponse.model_validate(parsed)
        except Exception as e:
            raise PlanValidationError(f"describe_screen failed: {e}") from e


class StubPlanner:
    """Deterministic planner for offline tests."""

    def __init__(
        self,
        *,
        action: SemanticAction | None = None,
        describe: VisionUnderstandingResponse | None = None,
        answer: VisionUnderstandingResponse | None = None,
    ) -> None:
        self.action = action or SemanticAction(
            action_id="stub-1",
            intent="noop",
            action_type="wait",
            risk_level="low",
        )
        self.describe = describe
        self.answer = answer
        self.plan_calls = 0
        self.describe_calls = 0

    async def plan(self, request: PlannerRequest) -> PlannerResponse:
        self.plan_calls += 1
        return PlannerResponse(
            task_completed_hint=False,
            semantic_action=self.action,
            needs_more_observation=False,
        )

    async def describe_screen(
        self, request: VisionUnderstandingRequest
    ) -> VisionUnderstandingResponse:
        self.describe_calls += 1
        if request.mode == "describe":
            return self.describe or VisionUnderstandingResponse(
                mode="describe",
                description="stub screen",
                confidence=0.5,
                model_name="stub",
            )
        return self.answer or VisionUnderstandingResponse(
            mode="answer_question",
            answer="uncertain",
            confidence=0.5,
            reason="stub",
            model_name="stub",
        )
