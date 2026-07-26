"""Phase 4 (T030) RED->GREEN: role-specific context-sensitive identity
(data-model.md §6A, perception-cache-contract.md "Role-specific
request/context identity" + "Explicit exclusions").

Planner/Grounder/Verifier identities are canonical serializations of their
full required-field set; any missing or changed field must produce a
different (or absent) identity, and same_context() must never report True
for two different identities. Structurally, none of these functions take a
content hash or pixel array — they can never be routed through the
pixel-content AnalysisResultCache.
"""

from __future__ import annotations

import inspect
from typing import get_args

import pytest

from vnc_agent.perception.cache import Component
from vnc_agent.runtime.context_identity import (
    MissingIdentityFieldError,
    grounder_identity,
    planner_identity,
    same_context,
    verifier_identity,
)


def _planner_kwargs(**overrides):
    base = dict(
        request_semantics="click login",
        step_intent="log in",
        action_history_state="hist-1",
        retry_iteration_state=0,
        structured_screen_identity="screen-1",
        requested_model_config={"model": "planner-v1"},
        route_state="observing",
    )
    base.update(overrides)
    return base


def _grounder_kwargs(**overrides):
    base = dict(
        target_semantics="login button",
        candidate_set_identity="cands-1",
        coordinate_transform_identity="transform-1",
        requested_model_config={"model": "grounder-v1"},
        retry_grounding_state=0,
    )
    base.update(overrides)
    return base


def _verifier_kwargs(**overrides):
    base = dict(
        visual_question_or_assertion="is the popup gone?",
        before_frame_identity="frame-before",
        after_frame_identity="frame-after",
        action_audit_context="action-1",
        retry_iteration_state=0,
        requested_model_config={"model": "planner-v1"},
    )
    base.update(overrides)
    return base


# --- structural exclusion from the pixel-content cache -------------------------


def test_context_sensitive_functions_have_no_pixel_or_content_hash_params():
    for fn in (planner_identity, grounder_identity, verifier_identity):
        params = set(inspect.signature(fn).parameters)
        assert "content_hash" not in params
        assert "pixels" not in params


def test_analysis_cache_component_enum_excludes_context_sensitive_roles():
    allowed = set(get_args(Component))
    # Feature 008 (vision-answer-cache-contract.md) narrowly amends the 004
    # exclusions: the *pure* visual answer (content + question + model) is a
    # cacheable content component; role-level results remain excluded.
    assert allowed == {"ocr", "template", "diff", "vision_describe", "vision_answer"}
    assert "planner" not in allowed
    assert "grounder" not in allowed
    assert "verification" not in allowed
    assert "verifier" not in allowed


# --- Planner -------------------------------------------------


def test_planner_identity_deterministic_for_identical_inputs():
    a = planner_identity(**_planner_kwargs())
    b = planner_identity(**_planner_kwargs())
    assert a == b


@pytest.mark.parametrize(
    "overrides",
    [
        {"request_semantics": "click logout"},
        {"step_intent": "log out"},
        {"action_history_state": "hist-2"},
        {"retry_iteration_state": 1},
        {"structured_screen_identity": "screen-2"},
        {"requested_model_config": {"model": "planner-v2"}},
        {"route_state": "recovering"},
    ],
)
def test_planner_identity_changes_with_any_required_field(overrides):
    a = planner_identity(**_planner_kwargs())
    b = planner_identity(**_planner_kwargs(**overrides))
    assert not same_context(a, b)


def test_planner_identity_missing_field_raises():
    with pytest.raises(MissingIdentityFieldError):
        planner_identity(**_planner_kwargs(step_intent=None))


# --- Grounder -------------------------------------------------


def test_grounder_identity_deterministic_for_identical_inputs():
    a = grounder_identity(**_grounder_kwargs())
    b = grounder_identity(**_grounder_kwargs())
    assert a == b


@pytest.mark.parametrize(
    "overrides",
    [
        {"target_semantics": "logout button"},
        {"candidate_set_identity": "cands-2"},
        {"coordinate_transform_identity": "transform-2"},
        {"requested_model_config": {"model": "grounder-v2"}},
        {"retry_grounding_state": 1},
    ],
)
def test_grounder_identity_changes_with_any_required_field(overrides):
    a = grounder_identity(**_grounder_kwargs())
    b = grounder_identity(**_grounder_kwargs(**overrides))
    assert not same_context(a, b)


def test_grounder_identity_missing_field_raises():
    with pytest.raises(MissingIdentityFieldError):
        grounder_identity(**_grounder_kwargs(target_semantics=None))


# --- Verifier -------------------------------------------------


def test_verifier_identity_deterministic_for_identical_inputs():
    a = verifier_identity(**_verifier_kwargs())
    b = verifier_identity(**_verifier_kwargs())
    assert a == b


@pytest.mark.parametrize(
    "overrides",
    [
        {"visual_question_or_assertion": "is the dialog visible?"},
        {"before_frame_identity": "frame-before-2"},
        {"after_frame_identity": "frame-after-2"},
        {"action_audit_context": "action-2"},
        {"retry_iteration_state": 1},
        {"requested_model_config": {"model": "planner-v2"}},
    ],
)
def test_verifier_identity_changes_with_any_required_field(overrides):
    a = verifier_identity(**_verifier_kwargs())
    b = verifier_identity(**_verifier_kwargs(**overrides))
    assert not same_context(a, b)


def test_verifier_identity_missing_field_raises():
    with pytest.raises(MissingIdentityFieldError):
        verifier_identity(**_verifier_kwargs(after_frame_identity=None))


def test_verifier_before_and_after_must_both_be_present_and_distinct_dimension():
    # Same question/context but before==after still yields a valid (not
    # missing) identity — before/after equality is not itself forbidden,
    # only a missing frame identity is.
    same_frame = verifier_identity(
        **_verifier_kwargs(before_frame_identity="f1", after_frame_identity="f1")
    )
    diff_frame = verifier_identity(
        **_verifier_kwargs(before_frame_identity="f1", after_frame_identity="f2")
    )
    assert same_frame != diff_frame


# --- same_context() -------------------------------------------------


def test_same_context_false_when_either_side_missing():
    identity = planner_identity(**_planner_kwargs())
    assert same_context(identity, None) is False
    assert same_context(None, identity) is False
    assert same_context(None, None) is False
