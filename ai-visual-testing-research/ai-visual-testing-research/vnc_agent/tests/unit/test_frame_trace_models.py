"""Phase 2 (T005) RED: CaptureScope / PhysicalImageRef / OptimizationError /
extended ScreenFrame (data-model.md §1-4, §8).

Must fail before production model changes: current `ScreenFrame` has no
`scope`/`safe_image`/`deduplicated` fields yet.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vnc_agent.domain.observation import (
    CaptureScope,
    OptimizationError,
    PhysicalImageRef,
    ScreenFrame,
    scope_identity,
)


def _now():
    return datetime(2026, 1, 1, tzinfo=UTC)


def _scope(**overrides) -> CaptureScope:
    base = dict(
        capture_kind="full_screen",
        x=0,
        y=0,
        width=64,
        height=48,
        resolution=(64, 48),
        pixel_format="uint8:3",
        mask_identity="no-mask-v1",
        private_persistence_allowed=True,
    )
    base.update(overrides)
    return CaptureScope(**base)


def _physical_ref(**overrides) -> PhysicalImageRef:
    base = dict(
        physical_image_id="p1",
        owner_frame_id="f1",
        artifact_bundle_id="b1",
        purpose="safe_evidence",
        path="/runs/r1/frames/b1/safe.png",
        byte_size=1234,
        artifact_sha256="a" * 64,
        content_hash="c" * 64,
        mask_identity="no-mask-v1",
        created_at=_now(),
    )
    base.update(overrides)
    return PhysicalImageRef(**base)


# --- CaptureScope -------------------------------------------------


def test_capture_scope_requires_private_persistence_allowed():
    with pytest.raises(ValidationError):
        CaptureScope(
            capture_kind="full_screen", x=0, y=0, width=64, height=48,
            resolution=(64, 48), pixel_format="uint8:3", mask_identity="no-mask-v1",
        )


def test_scope_identity_stable_for_identical_fields():
    a = _scope()
    b = _scope()
    assert scope_identity(a) == scope_identity(b)


@pytest.mark.parametrize(
    "overrides",
    [
        {"capture_kind": "roi"},
        {"x": 5},
        {"width": 65},
        {"resolution": (65, 48)},
        {"pixel_format": "uint8:1"},
        {"mask_identity": "mask-v2"},
        {"private_persistence_allowed": False},
    ],
)
def test_scope_identity_changes_with_any_boundary_field(overrides):
    a = _scope()
    b = _scope(**overrides)
    assert scope_identity(a) != scope_identity(b)


def test_scope_identity_excludes_step_and_timestamp():
    # scope_identity is a pure function of CaptureScope fields only — the
    # signature itself proves no step_id/timestamp can leak in.
    import inspect

    params = inspect.signature(scope_identity).parameters
    assert set(params) <= {"scope"}


# --- PhysicalImageRef -------------------------------------------------


def test_physical_image_ref_requires_bundle_and_hash_fields():
    with pytest.raises(ValidationError):
        PhysicalImageRef(
            physical_image_id="p1",
            owner_frame_id="f1",
            purpose="safe_evidence",
            path="/x.png",
            byte_size=1,
            mask_identity="m",
            created_at=_now(),
        )


def test_physical_image_ref_content_hash_may_be_null_but_artifact_sha256_required():
    ref = _physical_ref(content_hash=None)
    assert ref.content_hash is None
    with pytest.raises(ValidationError):
        _physical_ref(artifact_sha256=None)


def test_physical_image_ref_purpose_enum():
    with pytest.raises(ValidationError):
        _physical_ref(purpose="not_a_purpose")
    for purpose in ("safe_evidence", "private_model", "report_copy"):
        assert _physical_ref(purpose=purpose).purpose == purpose


# --- OptimizationError -------------------------------------------------


def test_optimization_error_stage_and_fallback_enums():
    err = OptimizationError(
        stage="pixel_hash",
        error_type="hash_failure",
        message="sanitized message",
        occurred_at=_now(),
        fallback="unique_full_analysis",
    )
    assert err.stage == "pixel_hash"
    with pytest.raises(ValidationError):
        OptimizationError(
            stage="not_a_stage",
            error_type="x",
            message="x",
            occurred_at=_now(),
            fallback="unique_full_analysis",
        )
    with pytest.raises(ValidationError):
        OptimizationError(
            stage="pixel_hash",
            error_type="x",
            message="x",
            occurred_at=_now(),
            fallback="not_a_fallback",
        )


# --- ScreenFrame invariants -------------------------------------------------


def _frame(**overrides) -> ScreenFrame:
    base = dict(
        id="f1",
        run_id="r1",
        vnc_session_id="s1",
        step_id=None,
        capture_sequence=1,
        capture_source="observation",
        timestamp=_now(),
        scope=_scope(),
        content_hash="c" * 64,
        deduplicated=False,
        duplicate_of_frame_id=None,
        comparison_available=True,
        changed_since_last=True,
        safe_image=_physical_ref(),
        model_image=None,
        optimization_errors=[],
    )
    base.update(overrides)
    return ScreenFrame(**base)


def test_screen_frame_unique_requires_null_duplicate_of():
    with pytest.raises(ValidationError):
        _frame(deduplicated=False, duplicate_of_frame_id="prev-frame")


def test_screen_frame_duplicate_requires_source_hash_and_unchanged():
    with pytest.raises(ValidationError):
        _frame(deduplicated=True, duplicate_of_frame_id=None)
    with pytest.raises(ValidationError):
        _frame(deduplicated=True, duplicate_of_frame_id="prev", content_hash=None)
    with pytest.raises(ValidationError):
        _frame(
            deduplicated=True, duplicate_of_frame_id="prev",
            content_hash="c" * 64, changed_since_last=True,
        )
    ok = _frame(
        deduplicated=True, duplicate_of_frame_id="prev",
        content_hash="c" * 64, changed_since_last=False,
    )
    assert ok.deduplicated is True


def test_screen_frame_safe_image_purpose_must_be_safe_evidence():
    with pytest.raises(ValidationError):
        _frame(safe_image=_physical_ref(purpose="private_model"))


def test_screen_frame_model_image_purpose_restricted():
    with pytest.raises(ValidationError):
        _frame(model_image=_physical_ref(purpose="report_copy"))
    ok = _frame(model_image=_physical_ref(purpose="private_model"))
    assert ok.model_image is not None


def test_screen_frame_forbids_private_model_image_when_scope_disallows():
    with pytest.raises(ValidationError):
        _frame(
            scope=_scope(private_persistence_allowed=False),
            model_image=_physical_ref(purpose="private_model"),
        )
    # null model_image is always fine when private persistence is disallowed
    ok = _frame(scope=_scope(private_persistence_allowed=False), model_image=None)
    assert ok.model_image is None


def test_screen_frame_capture_source_enum():
    for source in (
        "observation", "stability_wait", "retry", "recovery",
        "post_action_verification",
    ):
        assert _frame(capture_source=source).capture_source == source
    with pytest.raises(ValidationError):
        _frame(capture_source="not_a_source")


def test_screen_frame_independent_ids_and_timestamps_across_instances():
    a = _frame(id="fa", capture_sequence=1, timestamp=_now())
    b = _frame(id="fb", capture_sequence=2, timestamp=_now())
    assert a.id != b.id
    assert a.capture_sequence != b.capture_sequence


def test_screen_frame_image_path_property_reads_from_safe_image():
    frame = _frame(safe_image=_physical_ref(path="/runs/r1/frames/b1/safe.png"))
    assert frame.image_path == "/runs/r1/frames/b1/safe.png"


def test_screen_frame_model_path_property_falls_back_to_safe_when_no_model_image():
    frame = _frame(safe_image=_physical_ref(path="/x/safe.png"), model_image=None)
    assert frame.path_for_model() == "/x/safe.png"
    frame_with_model = _frame(
        safe_image=_physical_ref(path="/x/safe.png"),
        model_image=_physical_ref(path="/x/private.png", purpose="private_model"),
    )
    assert frame_with_model.path_for_model() == "/x/private.png"


def test_screen_frame_content_hash_not_substitutable_for_artifact_sha256():
    # A frame whose safe_image.artifact_sha256 differs from content_hash must
    # still validate — proves the two are independent identities, never merged.
    frame = _frame(
        content_hash="c" * 64,
        safe_image=_physical_ref(artifact_sha256="d" * 64, content_hash="c" * 64),
    )
    assert frame.content_hash != frame.safe_image.artifact_sha256
