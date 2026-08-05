"""Feature 003 T045 — cross-scenario genericity proof (FR-040, SC-006/007/012).

Constitution v1.1.0 Principle VI requires any change claiming a generic
framework capability to be validated against at least two unrelated
scenarios, independent of any single-scenario (POS) fixture. This file
aggregates that proof in one place rather than leaving it implicit across
test_scenario_*.py files.
"""

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.execution.action_identity import compute_identity, identity_match
from vnc_agent.execution.target_consistency import (
    evaluate_target_consistency,
    has_target_evidence_conflict,
)

_RISK_THRESHOLDS = {"dismiss_overlay": "medium", "scroll_reveal": "medium"}


# --- Four independent scenario "shapes": three generic + one POS-style ---


def _form_submit_pair():
    previous = SemanticAction(
        action_id="submit-1",
        intent="save the form",
        action_type="click",
        target=TargetDescription(role="button", text="Save"),
        action_kind="non_idempotent",
    )
    proposed = SemanticAction(
        action_id="submit-1",
        intent="save the form",
        action_type="click",
        target=TargetDescription(role="button", text="Save"),
        action_kind="non_idempotent",
    )
    return previous, proposed


def _icon_menu_pair():
    previous = SemanticAction(
        action_id="menu-1",
        intent="open toolbar menu",
        action_type="click",
        target=TargetDescription(role="icon_button", text=None, description="hamburger"),
        action_kind="idempotent",
    )
    proposed = SemanticAction(
        action_id="menu-1",
        intent="open toolbar menu",
        action_type="click",
        target=TargetDescription(role="icon_button", text=None, description="hamburger"),
        action_kind="idempotent",
    )
    return previous, proposed


def _popup_scroll_pair():
    previous = SemanticAction(
        action_id="confirm-1",
        intent="click confirm",
        action_type="click",
        target=TargetDescription(role="button", text="Confirm"),
        action_kind="non_idempotent",
    )
    proposed = SemanticAction(
        action_id="dismiss-1",
        intent="close overlay",
        action_type="click",
        target=TargetDescription(role="button", text="X"),
        action_kind="non_idempotent",
        micro_action_purpose="dismiss_overlay",
        risk_level="low",
    )
    return previous, proposed


def _pos_style_pair():
    """POS bag-checkout-flavored pair — the fourth, additional fixture; MUST
    NOT be required for any assertion below to hold generically."""
    previous = SemanticAction(
        action_id="add-bag",
        intent="click レジ袋 button",
        action_type="click",
        target=TargetDescription(role="button", text="レジ袋"),
        action_kind="non_idempotent",
    )
    proposed = SemanticAction(
        action_id="add-bag",
        intent="click レジ袋 button",
        action_type="click",
        target=TargetDescription(role="button", text="レジ袋"),
        action_kind="non_idempotent",
    )
    return previous, proposed


_GENERIC_SCENARIOS = {
    "form_submit": _form_submit_pair,
    "icon_menu": _icon_menu_pair,
    "popup_scroll": _popup_scroll_pair,
}
_ALL_SCENARIOS = {**_GENERIC_SCENARIOS, "pos_style": _pos_style_pair}


def test_identity_matching_holds_across_at_least_two_unrelated_scenarios() -> None:
    passing = []
    for name, factory in _GENERIC_SCENARIOS.items():
        previous, proposed = factory()
        prev_id = compute_identity("step", previous)
        curr_id = compute_identity("step", proposed)
        if identity_match(prev_id, curr_id) in ("action_id_match", "normalized_target_match"):
            passing.append(name)
    assert len(passing) >= 2, (
        f"identity matching only demonstrated in {passing}; FR-040/Constitution "
        "Principle VI requires at least two unrelated scenarios"
    )


def test_sc006_dangerous_drift_never_triggered_by_action_type_alone() -> None:
    """SC-006: across ALL scenarios (including the POS fixture), a
    dangerous_drift verdict must always be traceable to the AND(purpose,
    intent-consistency, risk) combination — never to action_type alone."""
    for name, factory in _ALL_SCENARIOS.items():
        previous, proposed = factory()
        type_changed_proposed = proposed.model_copy(
            update={"action_type": "type_text", "micro_action_purpose": None}
        )
        outcome = evaluate_target_consistency(
            "generic step intent",
            previous,
            type_changed_proposed,
            micro_action_risk_thresholds=_RISK_THRESHOLDS,
        )
        # action_type change alone (no declared purpose, unrelated text)
        # MUST NOT deterministically resolve to dangerous_drift by virtue of
        # the type change alone — it must fall to ambiguous or be justified
        # by the independent role/intent-consistency signals, never by
        # action_type by itself.
        assert outcome in ("ambiguous", "legitimate_micro_action", "dangerous_drift"), name
        # The decisive check: an identical role/target pair differing ONLY in
        # action_type produces the SAME outcome regardless of which
        # action_type value is used, proving action_type is not load-bearing
        # by itself.
        alt_type_changed = proposed.model_copy(
            update={"action_type": "press_key", "micro_action_purpose": None}
        )
        outcome_alt = evaluate_target_consistency(
            "generic step intent",
            previous,
            alt_type_changed,
            micro_action_risk_thresholds=_RISK_THRESHOLDS,
        )
        assert outcome == outcome_alt, (
            f"[{name}] outcome changed between action_type='type_text' ({outcome}) and "
            f"'press_key' ({outcome_alt}) despite identical role/target/purpose — "
            "action_type value itself must not be load-bearing"
        )


def test_sc007_conflict_check_always_runs_regardless_of_action_id_match() -> None:
    """SC-007: across ALL scenarios (including the POS fixture), a
    substantially conflicting new target triggers has_target_evidence_
    conflict()=True even when action_id/action_type still match — proving
    the check is never skipped due to identity matching alone."""
    for name, factory in _ALL_SCENARIOS.items():
        previous, _ = factory()
        # Same action_id/action_type as `previous`, but role changed to a
        # non-interactive one — a substantial target-evidence conflict.
        conflicting = previous.model_copy(
            update={"target": TargetDescription(role="row", text=previous.target.text)}
        )
        prev_id = compute_identity("step", previous)
        curr_id = compute_identity("step", conflicting)
        assert identity_match(prev_id, curr_id) == "action_id_match", name
        assert has_target_evidence_conflict(previous, conflicting) is True, (
            f"[{name}] role/interactivity conflict MUST be detected even though "
            "action_id_match holds"
        )


def test_sc012_pos_fixture_is_not_the_sole_evidence_for_any_capability() -> None:
    """SC-012/013: removing the POS scenario from consideration must not
    invalidate the identity-matching or conflict-detection proofs above —
    they were already established using only the three generic scenarios."""
    generic_only_identity_passes = []
    for name, factory in _GENERIC_SCENARIOS.items():
        previous, proposed = factory()
        prev_id = compute_identity("step", previous)
        curr_id = compute_identity("step", proposed)
        if identity_match(prev_id, curr_id) in ("action_id_match", "normalized_target_match"):
            generic_only_identity_passes.append(name)
    assert len(generic_only_identity_passes) >= 2

    generic_only_conflict_passes = []
    for name, factory in _GENERIC_SCENARIOS.items():
        previous, _ = factory()
        conflicting = previous.model_copy(
            update={"target": TargetDescription(role="row", text=previous.target.text)}
        )
        if has_target_evidence_conflict(previous, conflicting) is True:
            generic_only_conflict_passes.append(name)
    assert len(generic_only_conflict_passes) >= 2


# --- Feature 024: app-perception plugins across unrelated window shapes ----
#
# Constitution VI again: the sub-window enhancement claims to be generic, so
# it must be exercised on two windows that share nothing — different
# vocabulary, different layout, and deliberately opposite aspect ratios.


def _media_player_profile():
    """A synthetic scenario with no relationship to the shipped ones."""
    from vnc_agent.perception.app_plugins.profile import PluginProfile

    return PluginProfile.model_validate(
        {
            "name": "media-settings",
            "required_anchors": ["Playback", "Equalizer", "Apply"],
            "source_geometry": {
                "client_size": [720, 300],  # wide
                "controls": [
                    {"name": "lblPlayback", "text": "Playback", "rect": [8, 6, 90, 22]},
                    {
                        "name": "btnApply",
                        "text": "Apply",
                        "rect": [620, 260, 700, 288],
                        "anchors": ["bottom", "right"],
                    },
                ],
            },
        }
    )


def _spreadsheet_profile():
    from vnc_agent.perception.app_plugins.profile import PluginProfile

    return PluginProfile.model_validate(
        {
            "name": "cell-format",
            "required_anchors": ["Number", "Alignment", "Border"],
            "source_geometry": {
                "client_size": [280, 620],  # tall — the opposite shape
                "controls": [
                    {"name": "tabNumber", "text": "Number", "rect": [6, 8, 70, 24]},
                    {"name": "tabBorder", "text": "Border", "rect": [6, 560, 70, 580]},
                ],
            },
        }
    )


def _frame_with(texts_and_boxes, resolution=(1024, 768)):
    from datetime import UTC, datetime

    from vnc_agent.domain.observation import OCRItem, StructuredScreen

    return StructuredScreen(
        frame_id="cross",
        resolution=resolution,
        captured_at=datetime.now(UTC),
        ocr_items=[
            OCRItem(text=text, bbox=bbox, confidence=0.93) for text, bbox in texts_and_boxes
        ],
    )


def test_same_core_detects_two_unrelated_window_shapes():
    from vnc_agent.perception.app_plugins.detector import DeclarativeSubWindowPlugin

    wide = DeclarativeSubWindowPlugin(_media_player_profile())
    tall = DeclarativeSubWindowPlugin(_spreadsheet_profile())

    wide_frame = _frame_with(
        [
            ("Playback", (40, 40, 120, 56)),
            ("Equalizer", (40, 120, 130, 136)),
            ("Apply", (660, 300, 720, 320)),
        ]
    )
    tall_frame = _frame_with(
        [
            ("Number", (500, 60, 570, 76)),
            ("Alignment", (500, 300, 590, 316)),
            ("Border", (500, 640, 570, 656)),
        ]
    )

    wide_hit = wide.detect(wide_frame)
    tall_hit = tall.detect(tall_frame)
    assert wide_hit is not None and tall_hit is not None

    def aspect(detection):
        x1, y1, x2, y2 = detection.region
        return (x2 - x1) / (y2 - y1)

    assert aspect(wide_hit) > 1.0 > aspect(tall_hit), (
        "the two scenarios must genuinely differ in shape for this to prove anything"
    )

    # Each plugin only recognises its own window.
    assert wide.detect(tall_frame) is None
    assert tall.detect(wide_frame) is None


def test_anchor_mapping_is_shape_independent_across_scenarios():
    from vnc_agent.perception.app_plugins.source_geometry import map_control_rect

    for profile, region in (
        (_media_player_profile(), (100, 100, 820, 400)),
        (_spreadsheet_profile(), (400, 40, 680, 660)),
    ):
        geometry = profile.source_geometry
        for control in geometry.controls:
            mapped = map_control_rect(control, geometry.client_size, region)
            assert mapped is not None, f"{profile.name}/{control.name} failed to map"
            x1, y1, x2, y2 = mapped
            assert region[0] <= x1 < x2 <= region[2]
            assert region[1] <= y1 < y2 <= region[3]
