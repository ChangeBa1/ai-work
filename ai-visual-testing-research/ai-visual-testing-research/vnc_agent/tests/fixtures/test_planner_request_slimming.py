"""
Feature 019 (planner-request-slimming): wire-level assertions through
httpx.MockTransport — the kill switch restores byte-identical pre-019 user
messages; the default-enabled path preserves field names/structure (key sets
are subsets of the unslimmed dump at every level), keeps target-relevant OCR
text, shrinks the serialized payload, and logs before/after char lengths at
DEBUG.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

import httpx
import pytest

from vnc_agent.config import PlannerModelConfig, PlanningConfig
from vnc_agent.domain.observation import OCRItem, StructuredScreen, TemplateMatch
from vnc_agent.domain.verification import VerificationSpec
from vnc_agent.models.planner_client import HttpPlannerClient
from vnc_agent.models.provider import PlannerRequest

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


def _planning_cfg(**overrides) -> PlanningConfig:
    return PlanningConfig(ocr_sanity_check_ratio=0.10, **overrides)


def _pos_like_request(n_ocr: int = 60) -> PlannerRequest:
    """A POS-frame-shaped request: keypad noise + one low-confidence item
    matching the expected condition value."""
    ocr_items = [
        OCRItem(
            text=str(i % 10),
            bbox=(10 * i, 20, 10 * i + 30, 60),
            confidence=0.40 + i * 0.009,
        )
        for i in range(n_ocr - 1)
    ]
    ocr_items.append(
        OCRItem(text="小計", bbox=(600, 400, 700, 440), confidence=0.11)
    )
    screen = StructuredScreen(
        frame_id="frame-1",
        resolution=(1920, 1080),
        captured_at=datetime(2026, 7, 27, 12, 0, 0),
        ocr_items=ocr_items,
        template_matches=[
            TemplateMatch(
                template_id=f"tpl-{i}",
                bbox=(i, i, i + 5, i + 5),
                confidence=(i % 20) / 20,
            )
            for i in range(25)
        ],
        changed_since_last=True,
        global_diff_ratio=0.123456789,
        image_path="artifacts/shots/frame-1.png",
    )
    return PlannerRequest(
        step_intent="点击 小計 按钮",
        expected=VerificationSpec(
            operator="all",
            conditions=[{"type": "text_appears", "value": "小計"}],
        ),
        structured_screen=screen,
        iteration_index=1,
        remaining_iteration_budget=2,
    )


class _Capture:
    def __init__(self) -> None:
        self.user_contents: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        self.user_contents.append(body["messages"][1]["content"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": json.dumps(_PLAN_CONTENT)}}
                ]
            },
        )


def _client(capture: _Capture, planning_cfg: PlanningConfig | None) -> HttpPlannerClient:
    return HttpPlannerClient(
        PlannerModelConfig(base_url="http://test/v1"),
        transport=httpx.MockTransport(capture.handler),
        planning_cfg=planning_cfg,
    )


def _key_sets_are_subset(slimmed, original, path="$") -> None:
    """Recursively assert no key in the slimmed JSON was renamed/invented."""
    if isinstance(slimmed, dict):
        assert isinstance(original, dict), f"{path}: type changed"
        extra = set(slimmed) - set(original)
        assert not extra, f"{path}: keys not present in the original dump: {extra}"
        for k, v in slimmed.items():
            _key_sets_are_subset(v, original[k], f"{path}.{k}")
    elif isinstance(slimmed, list) and original and isinstance(original, list):
        # list items may be a selected subset; compare shapes against the
        # first original item (homogeneous lists in this payload)
        for i, v in enumerate(slimmed):
            if isinstance(v, dict):
                _key_sets_are_subset(v, original[0], f"{path}[{i}]")


@pytest.mark.asyncio
async def test_kill_switch_sends_byte_identical_pre_019_payload():
    """FR-005/SC-003: prompt_slimming_enabled=false → exact pre-019 bytes."""
    capture = _Capture()
    client = _client(capture, _planning_cfg(prompt_slimming_enabled=False))
    request = _pos_like_request()
    await client.plan(request)
    await client.aclose()
    expected = json.dumps(request.model_dump(mode="json"), ensure_ascii=False)
    assert capture.user_contents[0] == expected


@pytest.mark.asyncio
async def test_default_enabled_slims_and_preserves_structure():
    """FR-002/FR-009/SC-001/002/004 end to end on a 60-item POS-like frame."""
    capture = _Capture()
    client = _client(capture, _planning_cfg())
    request = _pos_like_request()
    await client.plan(request)
    await client.aclose()

    sent = capture.user_contents[0]
    original_dump = request.model_dump(mode="json")
    original = json.dumps(original_dump, ensure_ascii=False)
    # strictly smaller with the caps binding (SC-001)
    assert len(sent) < len(original)

    slimmed = json.loads(sent)
    # structure: no renamed/invented keys anywhere (SC-004)
    _key_sets_are_subset(slimmed, original_dump)
    # prompt-described fields still present under their original names
    assert slimmed["step_intent"] == "点击 小計 按钮"
    assert slimmed["expected"]["conditions"][0]["value"] == "小計"
    screen = slimmed["structured_screen"]
    assert len(screen["ocr_items"]) == 40
    assert len(screen["template_matches"]) == 10
    # target-relevant low-confidence item survived (SC-002)
    texts = [i["text"] for i in screen["ocr_items"]]
    assert "小計" in texts
    # per-item reduction: 2-decimal confidence, int bbox, no duplicate
    # normalized_text (default normalization of "小計" equals the text)
    target_item = next(i for i in screen["ocr_items"] if i["text"] == "小計")
    assert target_item["confidence"] == 0.11
    assert target_item["bbox"] == [600, 400, 700, 440]
    assert "normalized_text" not in target_item
    # floats rounded, nulls/empty lists gone
    assert screen["global_diff_ratio"] == 0.1235
    assert "vision_understanding" not in screen
    assert "previous_verification_result" not in slimmed
    assert "ui_index_hints" not in slimmed


@pytest.mark.asyncio
async def test_unwired_client_defaults_match_config_defaults():
    """planning_cfg=None (direct construction) behaves like a default
    PlanningConfig: slimming on, caps 40/10."""
    capture = _Capture()
    client = _client(capture, None)
    await client.plan(_pos_like_request())
    await client.aclose()
    slimmed = json.loads(capture.user_contents[0])
    assert len(slimmed["structured_screen"]["ocr_items"]) == 40
    assert len(slimmed["structured_screen"]["template_matches"]) == 10
    cfg = _planning_cfg()
    assert cfg.prompt_slimming_enabled is True
    assert cfg.prompt_ocr_items_max == 40
    assert cfg.prompt_list_items_max == 10


@pytest.mark.asyncio
async def test_debug_log_records_before_after_char_lengths(caplog):
    """FR-008: DEBUG log 'planner request slimming: <before> -> <after> chars'
    with before > after on a payload where the caps bind."""
    capture = _Capture()
    client = _client(capture, _planning_cfg())
    with caplog.at_level(logging.DEBUG, logger="vnc_agent.models.planner_client"):
        await client.plan(_pos_like_request())
    await client.aclose()
    records = [
        r for r in caplog.records if "planner request slimming" in r.getMessage()
    ]
    assert len(records) == 1
    before, after = records[0].args
    assert before > after
    assert after == len(capture.user_contents[0])


@pytest.mark.asyncio
async def test_configure_planning_hook_applies_knobs_post_construction():
    """FR-007: the composition root (api/cli.py) wires the agent.yaml
    `planning:` section through the duck-typed configure_planning hook —
    build_planner's signature is unchanged, and stub planners (which lack the
    hook) are skipped by the CLI's callable() guard."""
    from vnc_agent.models.planner_client import StubPlanner

    assert not hasattr(StubPlanner(), "configure_planning")

    capture = _Capture()
    client = _client(capture, None)
    client.configure_planning(_planning_cfg(prompt_slimming_enabled=False))
    request = _pos_like_request()
    await client.plan(request)
    await client.aclose()
    expected = json.dumps(request.model_dump(mode="json"), ensure_ascii=False)
    assert capture.user_contents[0] == expected


@pytest.mark.asyncio
async def test_dict_shaped_offline_request_still_served():
    """Totality on the offline-test shape (expected={}, structured_screen={})
    — the default-enabled slimming path must never raise."""
    capture = _Capture()
    client = _client(capture, None)
    resp = await client.plan(
        PlannerRequest(step_intent="noop", expected={}, structured_screen={})
    )
    await client.aclose()
    assert resp.semantic_action.action_type == "wait"
    slimmed = json.loads(capture.user_contents[0])
    assert slimmed["step_intent"] == "noop"
    assert slimmed["expected"] == {}
    assert slimmed["structured_screen"] == {}
