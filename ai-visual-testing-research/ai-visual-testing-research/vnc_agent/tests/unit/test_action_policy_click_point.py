"""Feature 013 (safe-click-point): ActionPolicy wiring tests (T012/T014).

Asserts that resolved coordinates fall inside the inset safe zone, that
``target_region`` keeps the raw bbox, that adjacent-candidate overlap is
avoided, and that behavior is identical across two unrelated GUI scenario
vocabularies (Constitution VI).
"""

from datetime import UTC, datetime

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.observation import OCRItem, StructuredScreen, TemplateMatch
from vnc_agent.planning.action_policy import ActionPolicy


def _screen(*, ocr=None, templates=None, resolution=(800, 600)) -> StructuredScreen:
    return StructuredScreen(
        frame_id="f1",
        resolution=resolution,
        captured_at=datetime.now(UTC),
        ocr_items=ocr or [],
        template_matches=templates or [],
    )


def _click(text: str, description: str = "") -> SemanticAction:
    return SemanticAction(
        action_id="a1",
        intent=f"click {text or description}",
        action_type="click",
        target=TargetDescription(text=text or None, description=description),
    )


def _safe_zone(bbox, ratio=0.15):
    x1, y1, x2, y2 = bbox
    ix, iy = round((x2 - x1) * ratio), round((y2 - y1) * ratio)
    return (x1 + ix, y1 + iy, x2 - ix, y2 - iy)


def _inside(pt, rect):
    return rect[0] <= pt[0] <= rect[2] and rect[1] <= pt[1] <= rect[3]


# --- unique OCR path (FR-007/009) ---


def test_unique_ocr_coordinates_in_safe_zone_and_region_unchanged():
    bbox = (10, 10, 80, 40)
    screen = _screen(ocr=[OCRItem(text="登录", bbox=bbox, confidence=0.9)])
    result = ActionPolicy().resolve(_click("登录"), screen)
    assert result.outcome == "ocr_template"
    coords = result.executable.coordinates
    assert _inside(coords, _safe_zone(bbox))
    # No overlapping sibling -> exact geometric center is preserved.
    assert coords == (45, 25)
    region = result.executable.target_region
    assert (region.x1, region.y1, region.x2, region.y2) == bbox


def test_ocr_plus_template_pick_keeps_raw_region_and_safe_point():
    bbox_ocr = (100, 80, 200, 120)
    bbox_tmpl = (104, 84, 204, 124)  # overlapping hit for the same control
    screen = _screen(
        ocr=[OCRItem(text="保存", bbox=bbox_ocr, confidence=0.9)],
        templates=[TemplateMatch(template_id="保存-btn", bbox=bbox_tmpl, confidence=0.5)],
    )
    result = ActionPolicy().resolve(_click("保存"), screen)
    assert result.outcome == "ocr_template"
    # Higher-confidence OCR bbox picked; target_region must be its raw bbox.
    region = result.executable.target_region
    assert (region.x1, region.y1, region.x2, region.y2) == bbox_ocr
    assert _inside(result.executable.coordinates, _safe_zone(bbox_ocr))


def test_out_of_screen_ocr_bbox_is_clamped():
    # T014: slightly out-of-resolution OCR bbox -> coordinates clamped inside.
    bbox = (700, 560, 820, 660)
    screen = _screen(ocr=[OCRItem(text="確定", bbox=bbox, confidence=0.9)])
    result = ActionPolicy().resolve(_click("確定"), screen)
    assert result.outcome == "ocr_template"
    x, y = result.executable.coordinates
    assert 0 <= x <= 799 and 0 <= y <= 599
    region = result.executable.target_region
    assert (region.x1, region.y1, region.x2, region.y2) == bbox


# --- grounding path (FR-008/009) ---


def _grounding_result(candidates) -> GroundingResult:
    return GroundingResult(found=True, candidates=candidates, model_name="stub")


def test_grounding_adjacent_candidate_overlap_avoided():
    selected = GroundingCandidate(bbox=(100, 80, 160, 120), confidence=0.95)
    # Overlapping runner-up covering the selected candidate's center.
    other = GroundingCandidate(bbox=(130, 80, 220, 120), confidence=0.5)
    screen = _screen(resolution=(800, 600))
    result = ActionPolicy().resolve(
        _click("", description="ambiguous button"),
        screen,
        grounding_result=_grounding_result([selected, other]),
    )
    assert result.outcome == "grounding"
    coords = result.executable.coordinates
    assert _inside(coords, _safe_zone(selected.bbox))
    assert not _inside(coords, other.bbox)
    region = result.executable.target_region
    assert (region.x1, region.y1, region.x2, region.y2) == selected.bbox


def test_grounding_second_candidate_uses_its_own_safe_zone():
    c0 = GroundingCandidate(bbox=(100, 80, 160, 120), confidence=0.90)
    c1 = GroundingCandidate(bbox=(150, 80, 220, 120), confidence=0.89)
    screen = _screen(resolution=(800, 600))
    result = ActionPolicy().resolve(
        _click("", description="ambiguous button"),
        screen,
        grounding_result=_grounding_result([c0, c1]),
        candidate_index=1,
    )
    assert result.outcome == "grounding"
    coords = result.executable.coordinates
    assert _inside(coords, _safe_zone(c1.bbox))
    assert not _inside(coords, c0.bbox)
    region = result.executable.target_region
    assert (region.x1, region.y1, region.x2, region.y2) == c1.bbox


# --- cross-scenario contract + determinism (Constitution I/VI) ---


def test_cross_scenario_same_geometry_same_coordinates():
    bbox = (10, 10, 80, 40)
    sibling = (60, 10, 130, 40)
    outputs = []
    # Two unrelated GUI vocabularies: a form save flow and an icon menu flow.
    for text, tmpl in (("保存", "保存-btn"), ("設定", "設定-icon")):
        screen = _screen(
            ocr=[OCRItem(text=text, bbox=bbox, confidence=0.9)],
            templates=[TemplateMatch(template_id=tmpl, bbox=sibling, confidence=0.4)],
        )
        # One OCR hit + one template hit for the needle -> pick OCR (higher
        # confidence), template hit participates as sibling.
        result = ActionPolicy().resolve(_click(text), screen)
        assert result.outcome == "ocr_template"
        outputs.append(result.executable.coordinates)
    assert outputs[0] == outputs[1]


def test_policy_resolution_is_deterministic():
    bbox = (10, 10, 80, 40)
    screen = _screen(ocr=[OCRItem(text="登录", bbox=bbox, confidence=0.9)])
    policy = ActionPolicy()
    first = policy.resolve(_click("登录"), screen).executable.coordinates
    second = policy.resolve(_click("登录"), screen).executable.coordinates
    assert first == second


def test_custom_inset_ratio_is_honoured():
    bbox = (0, 0, 100, 100)
    screen = _screen(ocr=[OCRItem(text="次へ", bbox=bbox, confidence=0.9)])
    result = ActionPolicy(click_edge_inset_ratio=0.3).resolve(_click("次へ"), screen)
    assert _inside(result.executable.coordinates, _safe_zone(bbox, 0.3))
