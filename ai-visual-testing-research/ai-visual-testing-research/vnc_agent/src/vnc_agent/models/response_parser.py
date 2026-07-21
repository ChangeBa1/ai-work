"""Model response parsers (JSON → Pydantic).

Supports OpenAI-compatible chat.completion envelopes for Grounder (T102 /
contracts/model-provider-contract.md 2026-07-22).
"""

from __future__ import annotations

import json
import re
from typing import Any

from vnc_agent.domain.grounding import GroundingResult
from vnc_agent.models.provider import PlannerResponse
from vnc_agent.runtime.exceptions import PlanValidationError


def _strip_code_fence(text: str) -> str:
    """Strip optional ``` / ```json wrappers that models sometimes emit."""
    text = text.strip()
    if not text.startswith("```"):
        return text
    # Remove opening fence (``` or ```json)
    text = re.sub(r"^```(?:json|JSON)?\s*\n?", "", text, count=1)
    # Remove closing fence
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _extract_message_content(raw: str | dict[str, Any]) -> str | dict[str, Any]:
    """
    If `raw` is an OpenAI chat.completion object, return choices[0].message.content.
    Otherwise return raw unchanged.
    """
    if isinstance(raw, dict) and "choices" in raw:
        try:
            content = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise PlanValidationError(
                f"chat.completion missing choices[0].message.content: {e}"
            ) from e
        return content
    return raw


def _as_dict(raw: str | dict[str, Any]) -> dict[str, Any]:
    raw = _extract_message_content(raw)
    if isinstance(raw, dict):
        # Already a structured object (direct GroundingResult shape or nested JSON)
        return raw
    if not isinstance(raw, str):
        raise PlanValidationError(f"unexpected content type: {type(raw).__name__}")
    text = _strip_code_fence(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise PlanValidationError(f"invalid JSON: {e}") from e
    if not isinstance(data, dict):
        raise PlanValidationError("response root must be an object")
    return data


def parse_planner_response(raw: str | dict[str, Any]) -> PlannerResponse:
    data = _as_dict(raw)
    try:
        return PlannerResponse.model_validate(data)
    except Exception as e:
        raise PlanValidationError(f"PlannerResponse validation failed: {e}") from e


def parse_grounding_response(
    raw: str | dict[str, Any], *, model_name: str = ""
) -> GroundingResult:
    """
    Parse grounding output from either:
    - a chat.completion envelope (choices[0].message.content → JSON text)
    - a bare JSON string / dict with {found, candidates}

    Strips ```json fences when present (contract 2026-07-22).
    """
    data = _as_dict(raw)
    # Accept a few wire shapes
    if "found" not in data and "candidates" in data:
        data = {**data, "found": bool(data.get("candidates"))}
    if "model_name" not in data:
        data = {**data, "model_name": model_name}
    # Normalize candidate bboxes
    cands: list[Any] = []
    for c in data.get("candidates") or []:
        if isinstance(c, dict):
            bbox = c.get("bbox")
            if isinstance(bbox, dict):
                c = {
                    **c,
                    "bbox": (
                        int(bbox["x1"]),
                        int(bbox["y1"]),
                        int(bbox["x2"]),
                        int(bbox["y2"]),
                    ),
                }
            elif isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                c = {**c, "bbox": (int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3]))}
            cands.append(c)
    data = {**data, "candidates": cands[:3]}
    try:
        return GroundingResult.model_validate(data)
    except Exception as e:
        raise PlanValidationError(f"GroundingResult validation failed: {e}") from e
