"""T004: field-level validation for ui_index models (data-model.md §1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from vnc_agent.ui_index.models import (
    BundleManifest,
    Confidence,
    ContentFileEntry,
    Diagnostic,
    Element,
    ElementGuardRef,
    Flow,
    FlowStep,
    NamedGuardRef,
    NeighborRef,
    NormalizedBounds,
    ProducerInfo,
    Screen,
    Transition,
    Viewport,
)


def test_confidence_level_enum_and_score_range():
    for level in (
        "confirmed",
        "statically_inferred",
        "visually_confirmed",
        "requires_runtime_verification",
    ):
        c = Confidence(level=level, score=0.5)
        assert c.level == level
    with pytest.raises(ValidationError):
        Confidence(level="unknown", score=0.5)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        Confidence(level="confirmed", score=1.5)
    with pytest.raises(ValidationError):
        Confidence(level="confirmed", score=-0.1)
    assert Confidence(level="confirmed", score=None).score is None
    assert Confidence(level="confirmed", score=0.0).score == 0.0
    assert Confidence(level="confirmed", score=1.0).score == 1.0


def test_normalized_bounds_space_and_ordering():
    b = NormalizedBounds(coordinate_space="normalized_1000", x1=0, y1=0, x2=100, y2=200)
    assert b.coordinate_space == "normalized_1000"
    with pytest.raises(ValidationError):
        NormalizedBounds(coordinate_space="design_pixels", x1=0, y1=0, x2=1, y2=1)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        NormalizedBounds(coordinate_space="normalized_1000", x1=10, y1=0, x2=10, y2=20)
    with pytest.raises(ValidationError):
        NormalizedBounds(coordinate_space="normalized_1000", x1=0, y1=20, x2=10, y2=10)
    with pytest.raises(ValidationError):
        NormalizedBounds(coordinate_space="normalized_1000", x1=-1, y1=0, x2=10, y2=20)
    with pytest.raises(ValidationError):
        NormalizedBounds(coordinate_space="normalized_1000", x1=0, y1=0, x2=1001, y2=20)


def test_neighbor_ref_direction_enum():
    for d in ("up", "down", "left", "right", "near"):
        assert NeighborRef(direction=d, element_id="el.a").direction == d
    with pytest.raises(ValidationError):
        NeighborRef(direction="diagonal", element_id="el.a")  # type: ignore[arg-type]


def _conf() -> Confidence:
    return Confidence(level="confirmed", score=0.9)


def test_screen_element_transition_guard_flow_diagnostic_fields():
    screen = Screen(
        screen_id="screen.form",
        name="Form",
        screen_type="page",
        visible_titles=["Form"],
        aliases=[],
        confidence=_conf(),
    )
    assert screen.parent_screen_id is None

    element = Element(
        element_id="el.submit",
        screen_id="screen.form",
        name="Submit",
        role="button",
        visible_texts=["Submit"],
        aliases=[],
        supported_actions=["click"],
        confidence=_conf(),
    )
    assert element.region == "unknown"
    assert element.anchors == []
    assert element.neighbors == []

    guard_el = ElementGuardRef(element_id="el.submit", condition="enabled")
    guard_named = NamedGuardRef(name="ready", description="form ready")
    assert guard_el.element_id == "el.submit"
    assert guard_named.name == "ready"

    transition = Transition(
        transition_id="tr.submit",
        from_screen_id="screen.form",
        trigger_element_id="el.submit",
        trigger_action="click",
        to_screen_id="screen.done",
        transition_type="replace",
        confidence=_conf(),
        guards=[guard_el, guard_named],
    )
    assert transition.transition_type == "replace"

    step_tr = FlowStep.model_validate({"transition_id": "tr.submit"})
    step_el = FlowStep.model_validate({"element_id": "el.submit", "action": "click"})
    with pytest.raises(ValidationError):
        FlowStep.model_validate({"transition_id": "tr.submit", "element_id": "el.submit", "action": "click"})
    with pytest.raises(ValidationError):
        FlowStep.model_validate({})

    flow = Flow(
        flow_id="flow.main",
        name="Main",
        start_screen_id="screen.form",
        steps=[step_tr, step_el],
        completion_screen_id="screen.done",
        confidence=_conf(),
    )
    assert len(flow.steps) == 2

    with pytest.raises(ValidationError):
        Diagnostic(
            diagnostic_id="d1",
            category="unconfirmed_element",
            reason="x",
            confidence=Confidence(level="confirmed", score=0.5),
        )

    diag = Diagnostic(
        diagnostic_id="d1",
        category="unconfirmed_element",
        reason="needs check",
        confidence=Confidence(level="requires_runtime_verification", score=None),
    )
    assert diag.confidence.level == "requires_runtime_verification"


def test_bundle_manifest_schema_version_and_extra_allow():
    with pytest.raises(ValidationError):
        BundleManifest(
            schema_version="1",
            bundle_id="b1",
            project_id="p1",
            generated_at=datetime.now(timezone.utc),
            producer=ProducerInfo(name="t", version="0.1"),
            source_revision="r1",
            frameworks=[],
            coordinate_spaces=["normalized_1000"],
            content_files={
                "screens.jsonl": ContentFileEntry(required=True),
            },
        )
    m = BundleManifest(
        schema_version="1.0",
        bundle_id="b1",
        project_id="p1",
        generated_at=datetime.now(timezone.utc),
        producer=ProducerInfo(name="t", version="0.1"),
        source_revision="r1",
        frameworks=[],
        coordinate_spaces=["normalized_1000"],
        default_viewports=[Viewport(name="desktop", width=1920, height=1080)],
        content_files={
            "screens.jsonl": ContentFileEntry(required=True, sha256=None, record_count=1),
        },
        custom_producer_field="kept",
    )
    assert m.model_extra is not None
    assert m.model_extra.get("custom_producer_field") == "kept"
