"""Feature 012: suspicious unique-OCR hits fall back to grounding.

Covers the suspicion rule table (spec 012 R-A1/R-A2/R-B/R-C), the exact-match
exemption (FR-003 byte-identical direct click), the mixed OCR+template branch
(FR-007), threshold configurability (FR-004) and observability (FR-005).
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vnc_agent.config import AgentConfig, PlanningConfig
from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.observation import OCRItem, StructuredScreen, TemplateMatch
from vnc_agent.planning.action_policy import (
    SUSPICION_LOW_CONFIDENCE,
    SUSPICION_PARTIAL_TEXT_OVERLAP,
    SUSPICION_SHORT_TEXT,
    SUSPICION_TRUNCATED_OCR_READ,
    ActionPolicy,
)


def _screen(ocr=None, templates=None) -> StructuredScreen:
    return StructuredScreen(
        frame_id="f1",
        resolution=(800, 600),
        captured_at=datetime.now(UTC),
        ocr_items=ocr or [],
        template_matches=templates or [],
        image_path="x.png",
    )


def _click(text: str) -> SemanticAction:
    return SemanticAction(
        action_id="a",
        intent="click target",
        action_type="click",
        target=TargetDescription(text=text),
    )


# ---------------------------------------------------------------------------
# FR-004: threshold configuration model
# ---------------------------------------------------------------------------


def test_planning_config_default_threshold_is_085():
    cfg = PlanningConfig(ocr_sanity_check_ratio=0.10)
    assert cfg.ocr_direct_click_min_confidence == 0.85
    # AgentConfig default factory carries the same default (single source).
    assert AgentConfig().planning.ocr_direct_click_min_confidence == 0.85


def test_planning_config_threshold_loads_explicit_value():
    cfg = AgentConfig.model_validate(
        {
            "planning": {
                "ocr_sanity_check_ratio": 0.10,
                "ocr_direct_click_min_confidence": 0.7,
            }
        }
    )
    assert cfg.planning.ocr_direct_click_min_confidence == 0.7


@pytest.mark.parametrize("bad", [-0.1, 1.2])
def test_planning_config_threshold_bounds_validated(bad):
    with pytest.raises(ValidationError):
        PlanningConfig(
            ocr_sanity_check_ratio=0.10, ocr_direct_click_min_confidence=bad
        )


# ---------------------------------------------------------------------------
# US1 / R-A2: non-exact containment hit is not clicked (partial_text_overlap)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("target_text", "ocr_text"),
    [
        # POS button flow (JP): OCR merged neighbouring glyphs into the hit.
        ("レジ袋", "レジ袋合計"),
        # Unrelated form-submit flow (EN) — Constitution VI cross-scenario.
        ("Submit Order", "Submit Orders"),
    ],
)
def test_partial_overlap_hit_falls_back_to_grounding(target_text, ocr_text):
    policy = ActionPolicy()
    screen = _screen(
        ocr=[OCRItem(text=ocr_text, bbox=(10, 10, 200, 40), confidence=0.95)]
    )
    result = policy.resolve(_click(target_text), screen)
    assert result.outcome == "grounding"
    assert result.needs_grounding is True
    assert result.executable is None
    assert result.ocr_suspicion is not None
    assert SUSPICION_PARTIAL_TEXT_OVERLAP in result.ocr_suspicion.reasons
    assert result.ocr_suspicion.ocr_text == ocr_text
    # FR-002 premise: the suspicious hit is part of screen.ocr_items, which the
    # runtime forwards verbatim as GroundingRequest.ocr_candidates.
    assert any(i.text == ocr_text for i in screen.ocr_items)


# ---------------------------------------------------------------------------
# US1 / R-A1: truncated partial read («ジ袋» ⊂ «レジ袋») — behavior already
# fell through to grounding; observability payload explains it.
# ---------------------------------------------------------------------------


def test_truncated_partial_read_reported_as_suspicion():
    policy = ActionPolicy()
    screen = _screen(
        ocr=[OCRItem(text="ジ袋", bbox=(80, 80, 180, 130), confidence=0.9)]
    )
    result = policy.resolve(_click("レジ袋"), screen)
    assert result.outcome == "grounding"
    assert result.needs_grounding is True
    assert result.ocr_suspicion is not None
    assert result.ocr_suspicion.reasons == [SUSPICION_TRUNCATED_OCR_READ]
    assert result.ocr_suspicion.ocr_text == "ジ袋"


def test_ambiguous_truncation_candidates_yield_no_suspicion():
    policy = ActionPolicy()
    screen = _screen(
        ocr=[
            OCRItem(text="ジ袋", bbox=(80, 80, 180, 130), confidence=0.9),
            OCRItem(text="レジ", bbox=(300, 80, 380, 130), confidence=0.9),
        ]
    )
    result = policy.resolve(_click("レジ袋"), screen)
    assert result.needs_grounding is True
    assert result.ocr_suspicion is None


# ---------------------------------------------------------------------------
# US2 / R-B + R-C: low confidence and single-character hits
# ---------------------------------------------------------------------------


def test_low_confidence_exact_hit_falls_back_to_grounding():
    policy = ActionPolicy()
    screen = _screen(
        ocr=[OCRItem(text="レジ袋", bbox=(80, 80, 180, 130), confidence=0.5)]
    )
    result = policy.resolve(_click("レジ袋"), screen)
    assert result.needs_grounding is True
    assert result.ocr_suspicion is not None
    assert result.ocr_suspicion.reasons == [SUSPICION_LOW_CONFIDENCE]
    assert result.ocr_suspicion.ocr_confidence == 0.5


def test_single_char_hit_falls_back_even_when_exact_and_confident():
    policy = ActionPolicy()
    screen = _screen(
        ocr=[OCRItem(text="+", bbox=(10, 10, 30, 30), confidence=0.99)]
    )
    result = policy.resolve(_click("+"), screen)
    assert result.needs_grounding is True
    assert result.ocr_suspicion is not None
    assert SUSPICION_SHORT_TEXT in result.ocr_suspicion.reasons


def test_multiple_reasons_are_all_recorded():
    policy = ActionPolicy()
    screen = _screen(
        ocr=[OCRItem(text="レジ袋合計", bbox=(10, 10, 200, 40), confidence=0.5)]
    )
    result = policy.resolve(_click("レジ袋"), screen)
    assert result.needs_grounding is True
    assert result.ocr_suspicion is not None
    assert set(result.ocr_suspicion.reasons) == {
        SUSPICION_PARTIAL_TEXT_OVERLAP,
        SUSPICION_LOW_CONFIDENCE,
    }


def test_threshold_is_configurable_on_policy():
    screen_ocr = [OCRItem(text="レジ袋", bbox=(80, 80, 180, 130), confidence=0.5)]
    lenient = ActionPolicy(ocr_direct_click_min_confidence=0.3)
    result = lenient.resolve(_click("レジ袋"), _screen(ocr=list(screen_ocr)))
    assert result.outcome == "ocr_template"
    assert result.needs_grounding is False
    # Default (0.85) rejects the same hit.
    strict = ActionPolicy()
    assert (
        strict.resolve(_click("レジ袋"), _screen(ocr=list(screen_ocr))).needs_grounding
        is True
    )


# ---------------------------------------------------------------------------
# US3 / FR-003: exact confident hits keep the legacy direct click, byte for byte
# ---------------------------------------------------------------------------


def test_exact_confident_hit_direct_click_unchanged():
    policy = ActionPolicy()
    bbox = (10, 10, 80, 40)
    screen = _screen(ocr=[OCRItem(text="登录", bbox=bbox, confidence=0.9)])
    result = policy.resolve(_click("登录"), screen)
    assert result.outcome == "ocr_template"
    assert result.needs_grounding is False
    assert result.ocr_suspicion is None
    assert result.executable is not None
    assert result.executable.method == "mouse"
    assert result.executable.operation == "click"
    assert result.executable.coordinates == (
        (bbox[0] + bbox[2]) // 2,
        (bbox[1] + bbox[3]) // 2,
    )
    assert result.executable.target_region is not None
    assert (
        result.executable.target_region.x1,
        result.executable.target_region.y1,
        result.executable.target_region.x2,
        result.executable.target_region.y2,
    ) == bbox


def test_decorative_punctuation_difference_still_direct_clicks():
    policy = ActionPolicy()
    screen = _screen(
        ocr=[OCRItem(text="【ログイン】", bbox=(10, 10, 120, 40), confidence=0.9)]
    )
    result = policy.resolve(_click("ログイン"), screen)
    assert result.outcome == "ocr_template"
    assert result.needs_grounding is False
    assert result.ocr_suspicion is None


def test_unique_template_hit_unchanged():
    policy = ActionPolicy()
    bbox = (50, 50, 150, 90)
    screen = _screen(
        templates=[TemplateMatch(template_id="save_btn", bbox=bbox, confidence=0.8)]
    )
    result = policy.resolve(_click("save"), screen)
    assert result.outcome == "ocr_template"
    assert result.executable.coordinates == (
        (bbox[0] + bbox[2]) // 2,
        (bbox[1] + bbox[3]) // 2,
    )


# ---------------------------------------------------------------------------
# US3 / FR-007: mixed unique-OCR + unique-template branch
# ---------------------------------------------------------------------------


def test_suspicious_ocr_with_unique_template_uses_template_bbox():
    policy = ActionPolicy()
    tmpl_bbox = (300, 300, 400, 340)
    screen = _screen(
        ocr=[OCRItem(text="レジ袋合計", bbox=(10, 10, 200, 40), confidence=0.95)],
        templates=[
            TemplateMatch(template_id="レジ袋_btn", bbox=tmpl_bbox, confidence=0.8)
        ],
    )
    result = policy.resolve(_click("レジ袋"), screen)
    # Pixel evidence wins over the suspicious OCR hit — still a direct click,
    # no grounding call.
    assert result.outcome == "ocr_template"
    assert result.needs_grounding is False
    assert result.executable.coordinates == (
        (tmpl_bbox[0] + tmpl_bbox[2]) // 2,
        (tmpl_bbox[1] + tmpl_bbox[3]) // 2,
    )


def test_trusted_ocr_with_unique_template_keeps_confidence_pick():
    policy = ActionPolicy()
    ocr_bbox = (10, 10, 80, 40)
    screen = _screen(
        ocr=[OCRItem(text="レジ袋", bbox=ocr_bbox, confidence=0.95)],
        templates=[
            TemplateMatch(
                template_id="レジ袋_btn", bbox=(300, 300, 400, 340), confidence=0.8
            )
        ],
    )
    result = policy.resolve(_click("レジ袋"), screen)
    assert result.outcome == "ocr_template"
    assert result.executable.coordinates == (
        (ocr_bbox[0] + ocr_bbox[2]) // 2,
        (ocr_bbox[1] + ocr_bbox[3]) // 2,
    )


# ---------------------------------------------------------------------------
# US3: second resolve pass (with grounding result) keeps the existing
# grounding defenses and carries the suspicion payload for reporting.
# ---------------------------------------------------------------------------


def test_second_pass_grounding_keeps_defenses_and_carries_suspicion():
    policy = ActionPolicy()
    screen = _screen(
        ocr=[OCRItem(text="ジ袋", bbox=(80, 80, 180, 130), confidence=0.9)]
    )
    grounding = GroundingResult(
        found=True,
        candidates=[
            GroundingCandidate(
                bbox=(100, 100, 160, 140),
                raw_bbox=(100, 100, 160, 140),
                coordinate_space="pixel",
                confidence=0.9,
            )
        ],
    )
    result = policy.resolve(_click("レジ袋"), screen, grounding_result=grounding)
    assert result.outcome == "grounding"
    assert result.executable is not None
    assert result.selected_candidate is not None
    assert result.ocr_suspicion is not None
    assert result.ocr_suspicion.reasons == [SUSPICION_TRUNCATED_OCR_READ]


def test_low_confidence_grounding_still_stops():
    policy = ActionPolicy()
    screen = _screen(
        ocr=[OCRItem(text="レジ袋", bbox=(80, 80, 180, 130), confidence=0.5)]
    )
    grounding = GroundingResult(
        found=True,
        candidates=[
            GroundingCandidate(
                bbox=(100, 100, 160, 140),
                raw_bbox=(100, 100, 160, 140),
                coordinate_space="pixel",
                confidence=0.4,  # below overall_confidence_threshold (0.55)
            )
        ],
    )
    result = policy.resolve(_click("レジ袋"), screen, grounding_result=grounding)
    assert result.outcome == "stop_recover"
    assert result.sub_reason == "overall_low_confidence"
    assert result.ocr_suspicion is not None


# ---------------------------------------------------------------------------
# FR-005: INFO log explains why no direct click happened
# ---------------------------------------------------------------------------


def test_suspicion_logged_on_first_pass(caplog):
    policy = ActionPolicy()
    screen = _screen(
        ocr=[OCRItem(text="レジ袋合計", bbox=(10, 10, 200, 40), confidence=0.95)]
    )
    with caplog.at_level("INFO", logger="vnc_agent.planning.action_policy"):
        policy.resolve(_click("レジ袋"), screen)
    assert any(
        "suspicious" in rec.message and "grounding" in rec.message
        for rec in caplog.records
    )
