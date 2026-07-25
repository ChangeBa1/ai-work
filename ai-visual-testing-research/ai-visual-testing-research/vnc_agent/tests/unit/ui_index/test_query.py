"""T031: query_screen/query_by_text/query_by_alias/query_by_role/query_transitions
(data-model.md §3.1, FR-004/005)."""

from __future__ import annotations

from pathlib import Path

from vnc_agent.ui_index.repository import UiIndexBundle
from vnc_agent.ui_index.query import (
    query_by_alias,
    query_by_role,
    query_by_text,
    query_screen,
    query_transitions,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ui_index"
FORM_INPUT = FIXTURES / "fixture_form_input"
ICON_OVERLAY = FIXTURES / "fixture_icon_overlay"


def test_query_screen_hit_and_miss_form_input():
    bundle = UiIndexBundle.load(FORM_INPUT)
    screen = query_screen(bundle, "screen.form_edit")
    assert screen is not None
    assert screen.name == "Edit Form"
    assert screen.confidence is not None

    assert query_screen(bundle, "screen.does_not_exist") is None


def test_query_by_text_hit_preserves_confidence_and_source_evidence():
    bundle = UiIndexBundle.load(FORM_INPUT)
    results = query_by_text(bundle, "Submit")
    assert len(results) == 1
    el = results[0]
    assert el.element_id == "el.form.submit_btn"
    assert el.confidence.level == "confirmed"
    # source_evidence is a modeled field even if None on this fixture record
    assert hasattr(el, "source_evidence")


def test_query_by_text_miss_returns_empty_list_not_none():
    bundle = UiIndexBundle.load(FORM_INPUT)
    result = query_by_text(bundle, "text that does not appear anywhere")
    assert result == []


def test_query_by_alias_hit_and_miss():
    bundle = UiIndexBundle.load(ICON_OVERLAY)
    results = query_by_alias(bundle, "help")
    assert len(results) == 1
    assert results[0].element_id == "el.ws.help_icon"

    assert query_by_alias(bundle, "no-such-alias") == []


def test_query_by_role_multiple_candidates_sorted_by_element_id():
    bundle = UiIndexBundle.load(FORM_INPUT)
    results = query_by_role(bundle, "button")
    ids = [e.element_id for e in results]
    assert ids == sorted(ids)
    assert "el.form.submit_btn" in ids
    assert "el.done.close" in ids


def test_query_by_role_miss_returns_empty_list():
    bundle = UiIndexBundle.load(FORM_INPUT)
    assert query_by_role(bundle, "no_such_role") == []


def test_query_transitions_by_from_screen_id():
    bundle = UiIndexBundle.load(FORM_INPUT)
    results = query_transitions(bundle, from_screen_id="screen.form_edit")
    assert [t.transition_id for t in results] == ["tr.form.submit"]


def test_query_transitions_by_trigger_element_id():
    bundle = UiIndexBundle.load(ICON_OVERLAY)
    results = query_transitions(bundle, trigger_element_id="el.ws.help_icon")
    assert [t.transition_id for t in results] == ["tr.ws.open_help"]


def test_query_transitions_by_to_screen_id():
    bundle = UiIndexBundle.load(ICON_OVERLAY)
    results = query_transitions(bundle, to_screen_id="screen.help_modal")
    assert [t.transition_id for t in results] == ["tr.ws.open_help"]


def test_query_transitions_combined_filters_are_intersected():
    bundle = UiIndexBundle.load(FORM_INPUT)
    results = query_transitions(
        bundle,
        from_screen_id="screen.form_edit",
        trigger_element_id="el.form.submit_btn",
        to_screen_id="screen.form_done",
    )
    assert [t.transition_id for t in results] == ["tr.form.submit"]

    # Mismatched combination -> no results, not an error.
    results_miss = query_transitions(
        bundle,
        from_screen_id="screen.form_edit",
        to_screen_id="screen.form_edit",
    )
    assert results_miss == []


def test_query_transitions_no_filters_returns_empty_not_error():
    """No query dimension supplied at the pure-function level is treated as
    'nothing to match on' -> []; the CLI layer (T032) is responsible for
    rejecting this as a usage error before calling query_transitions()."""
    bundle = UiIndexBundle.load(FORM_INPUT)
    results = query_transitions(bundle)
    assert results == []


def test_query_transitions_preserves_confidence_and_source_evidence():
    bundle = UiIndexBundle.load(FORM_INPUT)
    results = query_transitions(bundle, from_screen_id="screen.form_edit")
    assert results[0].confidence.level == "confirmed"
    assert hasattr(results[0], "source_evidence")


def test_query_by_text_and_alias_deterministic_ordering_across_repeated_calls():
    bundle = UiIndexBundle.load(FORM_INPUT)
    ids1 = [e.element_id for e in query_by_text(bundle, "Name")]
    ids2 = [e.element_id for e in query_by_text(bundle, "Name")]
    assert ids1 == ids2 == sorted(ids1)
