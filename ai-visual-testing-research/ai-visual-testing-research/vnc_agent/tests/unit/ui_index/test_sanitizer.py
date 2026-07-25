"""T036: to_visible_hint() allow-list guarantee (FR-015, data-model.md §4.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from vnc_agent.ui_index.models import Confidence, Element
from vnc_agent.ui_index.repository import UiIndexBundle
from vnc_agent.ui_index.sanitizer import VisibleElementHint, to_visible_hint

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ui_index"
FORM_INPUT = FIXTURES / "fixture_form_input"
ICON_OVERLAY = FIXTURES / "fixture_icon_overlay"

EXPECTED_FIELDS = {
    "element_id",
    "visible_texts",
    "aliases",
    "role",
    "region",
    "anchor_texts",
    "neighbor_texts",
}


def test_visible_element_hint_field_set_is_exactly_the_seven_fields():
    assert set(VisibleElementHint.model_fields.keys()) == EXPECTED_FIELDS


def test_visible_element_hint_rejects_unknown_fields():
    with pytest.raises(Exception):
        VisibleElementHint(
            element_id="e1",
            visible_texts=[],
            aliases=[],
            role="button",
            region="body",
            anchor_texts=[],
            neighbor_texts={},
            source_evidence="should not be accepted",  # type: ignore[call-arg]
        )


def test_to_visible_hint_excludes_source_evidence_leak():
    secret_path = "C:/internal/source/checkout_controller.cs:142"
    bundle = UiIndexBundle.load(FORM_INPUT)
    element = Element(
        element_id="el.leaky",
        screen_id="screen.form_edit",
        name="Leaky",
        role="button",
        visible_texts=["Public Label"],
        aliases=["Public Alias"],
        supported_actions=["click"],
        source_evidence=secret_path,
        metadata={"internal_note": secret_path},
        confidence=Confidence(level="confirmed", score=0.9),
    )
    hint = to_visible_hint(element, bundle)

    dumped = hint.model_dump()
    for value in dumped.values():
        serialized = repr(value)
        assert secret_path not in serialized

    assert set(hint.model_dump().keys()) == EXPECTED_FIELDS


def test_to_visible_hint_copies_basic_fields():
    bundle = UiIndexBundle.load(FORM_INPUT)
    element = bundle.elements["el.form.submit_btn"]
    hint = to_visible_hint(element, bundle)

    assert hint.element_id == element.element_id
    assert hint.visible_texts == element.visible_texts
    assert hint.aliases == element.aliases
    assert hint.role == element.role
    assert hint.region == element.region


def test_to_visible_hint_resolves_anchor_texts_from_bundle():
    bundle = UiIndexBundle.load(FORM_INPUT)
    element = bundle.elements["el.form.submit_btn"]
    hint = to_visible_hint(element, bundle)

    anchor_element = bundle.elements["el.form.name_field"]
    for text in anchor_element.visible_texts:
        assert text in hint.anchor_texts


def test_to_visible_hint_resolves_neighbor_texts_by_direction():
    bundle = UiIndexBundle.load(ICON_OVERLAY)
    element = bundle.elements["el.ws.help_icon"]
    hint = to_visible_hint(element, bundle)

    # el.ws.help_icon has a "left" neighbor -> el.ws.settings_icon
    assert "left" in hint.neighbor_texts
    settings = bundle.elements["el.ws.settings_icon"]
    for text in settings.visible_texts:
        assert text in hint.neighbor_texts["left"]


def test_to_visible_hint_dangling_anchor_neighbor_does_not_raise():
    bundle = UiIndexBundle.load(FORM_INPUT)
    element = Element(
        element_id="el.with_dangling",
        screen_id="screen.form_edit",
        name="Dangling",
        role="button",
        visible_texts=["X"],
        aliases=[],
        supported_actions=["click"],
        anchors=["el.does_not_exist"],
        confidence=Confidence(level="confirmed", score=0.9),
    )
    hint = to_visible_hint(element, bundle)
    assert hint.anchor_texts == []
