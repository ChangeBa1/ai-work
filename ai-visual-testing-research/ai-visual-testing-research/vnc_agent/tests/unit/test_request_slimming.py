"""
Feature 019 (planner-request-slimming): pure-function coverage of
planning/request_slimming.py — OCR cap with confidence ranking and
target-hit priority, per-item field reduction (integer bbox, 2-decimal
confidence, redundant normalized_text dropped), other list caps, recursive
float rounding and null/empty-list drops, purity and totality.
"""

from __future__ import annotations

import copy

from vnc_agent.planning.request_slimming import (
    DEFAULT_LIST_ITEMS_MAX,
    DEFAULT_OCR_ITEMS_MAX,
    slim_planner_payload,
)


def _ocr_item(text: str, confidence: float, bbox=(0, 0, 10, 10), normalized=None):
    item = {
        "text": text,
        "bbox": list(bbox),
        "confidence": confidence,
        "normalized_text": normalized if normalized is not None else text,
    }
    return item


def _payload(ocr_items, *, step_intent="点击 登录 按钮", conditions=()):
    return {
        "step_intent": step_intent,
        "expected": {
            "operator": "all",
            "conditions": [{"type": "text_appears", "value": v, "region": None} for v in conditions]
            or [{"type": "screen_changed", "value": "", "region": None}],
            "timeout_seconds": None,
        },
        "structured_screen": {
            "frame_id": "f-1",
            "resolution": [1920, 1080],
            "captured_at": "2026-07-27T00:00:00",
            "ocr_items": ocr_items,
            "template_matches": [],
            "changed_since_last": False,
            "changed_regions": [],
            "local_blobs": [],
            "global_diff_ratio": 0.0,
            "vision_understanding": None,
            "image_path": "shots/1.png",
        },
        "iteration_index": 0,
        "remaining_iteration_budget": 3,
        "previous_verification_result": None,
        "recent_step_summaries": [],
        "risk_policy": {"max_risk_level": "low"},
        "ui_index_hints": [],
    }


class TestOcrCapAndRanking:
    def test_count_capped_and_lowest_confidence_dropped(self):
        # 60 keypad-noise items with distinct confidences 0.40..0.99
        items = [_ocr_item(str(i % 10), 0.40 + i * 0.01) for i in range(60)]
        payload = _payload(items, step_intent="点住 テンキー 以外")
        slimmed = slim_planner_payload(payload)
        kept = slimmed["structured_screen"]["ocr_items"]
        assert len(kept) == DEFAULT_OCR_ITEMS_MAX == 40
        # Selection is confidence-descending: the 20 lowest-confidence items
        # (0.40..0.59) are exactly the dropped ones.
        kept_conf = sorted(i["confidence"] for i in kept)
        assert kept_conf[0] >= round(0.40 + 20 * 0.01, 2)

    def test_under_cap_keeps_everything(self):
        items = [_ocr_item(f"t{i}", 0.5) for i in range(5)]
        slimmed = slim_planner_payload(_payload(items))
        assert len(slimmed["structured_screen"]["ocr_items"]) == 5

    def test_survivors_keep_original_reading_order(self):
        items = [_ocr_item(f"line-{i}", confidence=(i * 37 % 100) / 100) for i in range(50)]
        slimmed = slim_planner_payload(_payload(items), ocr_items_max=10)
        kept_texts = [i["text"] for i in slimmed["structured_screen"]["ocr_items"]]
        original_order = [i["text"] for i in items]
        assert kept_texts == [t for t in original_order if t in set(kept_texts)]

    def test_custom_cap_respected(self):
        items = [_ocr_item(f"t{i}", 0.9) for i in range(30)]
        slimmed = slim_planner_payload(_payload(items), ocr_items_max=7)
        assert len(slimmed["structured_screen"]["ocr_items"]) == 7


class TestTargetHitPriority:
    def test_low_confidence_step_intent_hit_survives(self):
        noise = [_ocr_item(str(i % 10), 0.99) for i in range(59)]
        target = _ocr_item("登録", 0.05)  # far below every noise item
        payload = _payload(noise + [target], step_intent="点击 登録 完成登记")
        kept = slim_planner_payload(payload, ocr_items_max=40)
        texts = [i["text"] for i in kept["structured_screen"]["ocr_items"]]
        assert "登録" in texts

    def test_expected_condition_value_hit_survives(self):
        noise = [_ocr_item(str(i % 10), 0.99) for i in range(59)]
        target = _ocr_item("小計", 0.01)
        payload = _payload(
            noise + [target], step_intent="按下按钮", conditions=("小計",)
        )
        kept = slim_planner_payload(payload, ocr_items_max=40)
        texts = [i["text"] for i in kept["structured_screen"]["ocr_items"]]
        assert "小計" in texts

    def test_match_is_case_insensitive_and_bidirectional(self):
        noise = [_ocr_item(str(i), 0.99) for i in range(59)]
        # Item text is a *superstring* of the condition value, different case.
        target = _ocr_item("LOGIN BUTTON", 0.01)
        payload = _payload(noise + [target], step_intent="x", conditions=("login",))
        kept = slim_planner_payload(payload, ocr_items_max=10)
        texts = [i["text"] for i in kept["structured_screen"]["ocr_items"]]
        assert "LOGIN BUTTON" in texts

    def test_hits_exceeding_cap_pick_highest_confidence_hits(self):
        hits = [_ocr_item("登録", 0.10 + i * 0.01) for i in range(20)]
        payload = _payload(hits, step_intent="点击 登録")
        kept = slim_planner_payload(payload, ocr_items_max=5)
        confs = [i["confidence"] for i in kept["structured_screen"]["ocr_items"]]
        assert len(confs) == 5
        assert min(confs) >= round(0.10 + 15 * 0.01, 2)


class TestOcrItemFieldReduction:
    def test_bbox_rounded_to_int_confidence_two_decimals(self):
        item = _ocr_item("小計", 0.987654, bbox=(10.6, 20.4, 99.5, 40.0))
        kept = slim_planner_payload(_payload([item]))["structured_screen"]["ocr_items"][0]
        assert kept["bbox"] == [11, 20, 100, 40]
        assert all(isinstance(v, int) for v in kept["bbox"])
        assert kept["confidence"] == 0.99

    def test_redundant_normalized_text_dropped(self):
        item = _ocr_item("小計", 0.9, normalized="小計")
        kept = slim_planner_payload(_payload([item]))["structured_screen"]["ocr_items"][0]
        assert "normalized_text" not in kept
        assert kept["text"] == "小計"

    def test_differing_normalized_text_kept(self):
        item = _ocr_item("Login", 0.9, normalized="login")
        kept = slim_planner_payload(_payload([item]))["structured_screen"]["ocr_items"][0]
        assert kept["normalized_text"] == "login"

    def test_item_carries_only_expected_keys(self):
        item = _ocr_item("小計", 0.9, normalized="小計")
        kept = slim_planner_payload(_payload([item]))["structured_screen"]["ocr_items"][0]
        assert set(kept) == {"text", "bbox", "confidence"}


class TestOtherListCaps:
    def test_template_matches_top_confidence_original_order(self):
        matches = [
            {"template_id": f"tpl-{i}", "bbox": [0, 0, 5, 5], "confidence": (i * 13 % 25) / 25}
            for i in range(25)
        ]
        payload = _payload([])
        payload["structured_screen"]["template_matches"] = matches
        slimmed = slim_planner_payload(payload)
        kept = slimmed["structured_screen"]["template_matches"]
        assert len(kept) == DEFAULT_LIST_ITEMS_MAX == 10
        # top-10 by confidence...
        expected_ids = {
            m["template_id"]
            for m in sorted(matches, key=lambda m: m["confidence"], reverse=True)[:10]
        }
        assert {m["template_id"] for m in kept} == expected_ids
        # ...emitted in original order
        original_order = [m["template_id"] for m in matches if m["template_id"] in expected_ids]
        assert [m["template_id"] for m in kept] == original_order

    def test_regions_blobs_hints_first_n(self):
        region = {"x1": 0, "y1": 0, "x2": 5, "y2": 5}
        payload = _payload([])
        payload["structured_screen"]["changed_regions"] = [dict(region, x1=i) for i in range(15)]
        payload["structured_screen"]["local_blobs"] = [dict(region, y1=i) for i in range(12)]
        payload["ui_index_hints"] = [{"element_id": f"e{i}", "role": "button"} for i in range(14)]
        slimmed = slim_planner_payload(payload)
        assert len(slimmed["structured_screen"]["changed_regions"]) == 10
        assert slimmed["structured_screen"]["changed_regions"][0]["x1"] == 0
        assert len(slimmed["structured_screen"]["local_blobs"]) == 10
        assert len(slimmed["ui_index_hints"]) == 10
        assert slimmed["ui_index_hints"][0]["element_id"] == "e0"

    def test_recent_step_summaries_keep_most_recent_tail(self):
        payload = _payload([])
        payload["recent_step_summaries"] = [f"step-{i}" for i in range(15)]
        slimmed = slim_planner_payload(payload)
        assert slimmed["recent_step_summaries"] == [f"step-{i}" for i in range(5, 15)]


class TestCleanupPass:
    def test_floats_rounded_confidence_2_others_4(self):
        payload = _payload([])
        payload["structured_screen"]["global_diff_ratio"] = 0.123456789
        payload["structured_screen"]["vision_understanding"] = {
            "description": "d",
            "confidence": 0.876543,
            "model_name": "m",
        }
        slimmed = slim_planner_payload(payload)
        assert slimmed["structured_screen"]["global_diff_ratio"] == 0.1235
        assert slimmed["structured_screen"]["vision_understanding"]["confidence"] == 0.88

    def test_null_and_empty_list_keys_dropped_at_all_levels(self):
        payload = _payload([])
        slimmed = slim_planner_payload(payload)
        assert "previous_verification_result" not in slimmed
        assert "recent_step_summaries" not in slimmed
        assert "ui_index_hints" not in slimmed
        screen = slimmed["structured_screen"]
        for key in ("ocr_items", "template_matches", "changed_regions",
                    "local_blobs", "vision_understanding"):
            assert key not in screen
        # nested null inside expected.conditions[*].region dropped too
        assert "region" not in slimmed["expected"]["conditions"][0]
        assert "timeout_seconds" not in slimmed["expected"]

    def test_empty_strings_false_and_zero_are_kept(self):
        payload = _payload([])
        payload["structured_screen"]["scope_key"] = ""
        slimmed = slim_planner_payload(payload)
        assert slimmed["structured_screen"]["scope_key"] == ""
        assert slimmed["structured_screen"]["changed_since_last"] is False
        assert slimmed["iteration_index"] == 0

    def test_booleans_not_treated_as_floats(self):
        payload = _payload([])
        payload["structured_screen"]["changed_since_last"] = True
        slimmed = slim_planner_payload(payload)
        assert slimmed["structured_screen"]["changed_since_last"] is True


class TestPurityAndTotality:
    def test_input_payload_never_mutated(self):
        items = [_ocr_item(str(i), 0.4 + i * 0.01, bbox=(1.5, 2.5, 3.5, 4.5)) for i in range(50)]
        payload = _payload(items)
        snapshot = copy.deepcopy(payload)
        slim_planner_payload(payload)
        assert payload == snapshot

    def test_dict_shaped_offline_payload_passes_through(self):
        # The offline-test construction shape: expected={} / structured_screen={}
        payload = {
            "step_intent": "noop",
            "expected": {},
            "structured_screen": {},
            "iteration_index": 0,
            "remaining_iteration_budget": 0,
            "risk_policy": {"max_risk_level": "low"},
        }
        slimmed = slim_planner_payload(payload)
        assert slimmed["step_intent"] == "noop"
        assert slimmed["expected"] == {}
        assert slimmed["structured_screen"] == {}

    def test_malformed_substructures_do_not_raise(self):
        payload = {
            "step_intent": None,
            "expected": {"conditions": "not-a-list"},
            "structured_screen": {
                "ocr_items": "not-a-list",
                "template_matches": {"weird": True},
            },
            "ui_index_hints": {"also": "not-a-list"},
            "recent_step_summaries": None,
        }
        slimmed = slim_planner_payload(payload)
        assert slimmed["structured_screen"]["ocr_items"] == "not-a-list"
        assert "step_intent" not in slimmed  # null dropped by cleanup
