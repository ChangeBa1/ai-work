"""T038: build_hints() outcome matrix — hit / no_match / inconsistent /
not_configured (contracts §6, research.md §9, FR-007/008/009/010/011)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from vnc_agent.config import UiIndexConfig
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.ui_index.repository import UiIndexBundle
from vnc_agent.ui_index.runtime_adapter import build_hints

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ui_index"
ICON_OVERLAY = FIXTURES / "fixture_icon_overlay"
FORM_INPUT = FIXTURES / "fixture_form_input"


def _screen(texts: list[str]) -> StructuredScreen:
    return StructuredScreen(
        frame_id="frame-1",
        resolution=(1000, 1000),
        captured_at=datetime.now(timezone.utc),
        ocr_items=[
            OCRItem(text=t, bbox=(0, 0, 10, 10), confidence=0.95) for t in texts
        ],
    )


def test_build_hints_not_configured_when_bundle_is_none():
    hints, candidates, audit = build_hints(None, _screen([]), UiIndexConfig())
    assert hints == []
    assert candidates == []
    assert audit.outcome == "not_configured"
    assert audit.bundle_id is None


def test_build_hints_hit_returns_sorted_hints_and_candidates():
    bundle = UiIndexBundle.load(ICON_OVERLAY)
    screen = _screen(["Workspace", "Main Canvas", "Desk", "help", "gear"])
    hints, candidates, audit = build_hints(bundle, screen, UiIndexConfig())

    assert audit.outcome == "hit"
    assert audit.matched_screen_id == "screen.workspace"
    assert audit.bundle_id == bundle.manifest.bundle_id
    assert audit.schema_version == bundle.manifest.schema_version

    hint_ids = [h.element_id for h in hints]
    assert hint_ids == sorted(hint_ids)
    assert hint_ids == ["el.ws.help_icon", "el.ws.settings_icon"]
    assert audit.hint_element_ids == hint_ids

    # Only el.ws.help_icon carries normalized_bounds on this fixture;
    # el.ws.settings_icon has none and therefore yields a hint but no candidate.
    assert len(candidates) == 1
    for candidate in candidates:
        assert candidate["source"] == "ui_index"
        assert candidate["coordinate_space"] in {"normalized_1000", "pixel"}


def test_build_hints_no_match_when_ocr_text_unrelated():
    bundle = UiIndexBundle.load(ICON_OVERLAY)
    screen = _screen(["completely", "unrelated", "text", "blob"])
    hints, candidates, audit = build_hints(bundle, screen, UiIndexConfig())

    assert hints == []
    assert candidates == []
    assert audit.outcome == "no_match"
    assert audit.no_match_reason == "no_screen_matched"
    assert audit.matched_screen_id is None
    assert audit.bundle_id == bundle.manifest.bundle_id


def test_build_hints_inconsistent_when_screen_matches_but_elements_missing():
    """Screen-level texts alone push the match score to the threshold, but
    none of the confirmed/visually_confirmed elements' texts appear in OCR —
    this must surface as 'inconsistent', not silently 'hit'."""
    bundle = UiIndexBundle.load(ICON_OVERLAY)
    screen = _screen(["Workspace", "Main Canvas", "Desk"])
    hints, candidates, audit = build_hints(bundle, screen, UiIndexConfig())

    assert hints == []
    assert candidates == []
    assert audit.outcome == "inconsistent"
    assert audit.matched_screen_id == "screen.workspace"
    assert audit.no_match_reason == "screen_content_inconsistent"


def test_build_hints_hit_on_form_input_fixture_covers_confidence_and_bounds():
    bundle = UiIndexBundle.load(FORM_INPUT)
    screen = _screen(
        [
            "Contact Form",
            "Edit Details",
            "Form Page",
            "Name",
            "Full name",
            "Your name",
            "Submit",
            "Send",
        ]
    )
    hints, candidates, audit = build_hints(bundle, screen, UiIndexConfig())

    assert audit.outcome == "hit"
    assert audit.matched_screen_id == "screen.form_edit"
    assert {h.element_id for h in hints} == {"el.form.name_field", "el.form.submit_btn"}
    # el.form.name_field has normalized_bounds -> candidate produced.
    assert any(c["label"] == "Name" for c in candidates)
    # el.form.submit_btn also has normalized_bounds -> candidate produced.
    assert any(c["label"] == "Submit" for c in candidates)


def test_build_hints_element_without_bounds_yields_hint_but_no_candidate():
    """el.done.close on FORM_INPUT's screen.form_done has no
    normalized_bounds — it MUST still surface as a Planner hint (text-only)
    but MUST NOT produce a Grounder candidate (no coordinates to propose)."""
    bundle = UiIndexBundle.load(FORM_INPUT)
    screen = _screen(["Thank You", "Submission Complete", "Close"])
    hints, candidates, audit = build_hints(bundle, screen, UiIndexConfig())

    assert audit.outcome == "hit"
    assert audit.matched_screen_id == "screen.form_done"
    assert [h.element_id for h in hints] == ["el.done.close"]
    assert candidates == []


def test_build_hints_never_returns_raw_pixel_coordinates_in_hints():
    """Contract: VisibleElementHint MUST NOT carry coordinate fields — only
    the allow-listed text/role/region fields (FR-014/015)."""
    bundle = UiIndexBundle.load(FORM_INPUT)
    screen = _screen(["Name", "Full name", "Submit", "Send", "Contact Form"])
    hints, _candidates, audit = build_hints(bundle, screen, UiIndexConfig())
    assert audit.outcome == "hit"
    for hint in hints:
        dumped = hint.model_dump()
        assert "bbox" not in dumped
        assert "normalized_bounds" not in dumped
        assert "x1" not in dumped
