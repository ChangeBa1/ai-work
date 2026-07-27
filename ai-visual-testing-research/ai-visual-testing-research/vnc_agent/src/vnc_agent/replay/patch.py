"""ReplayPatch construction (feature 016, spec FR-009, ADR-005).

A patch is a *candidate* produced when a replay fallback grounding succeeded
where the recorded target failed. It is born ``pending`` and is never applied
by the runtime: ``replay.patch_auto_apply`` exists as configuration but is
deliberately inert in this MVP — even ``true`` only emits a warning
(:func:`warn_if_auto_apply_configured`). Approving/rejecting a patch is a
human-review workflow outside this codebase's scope (设计 ADR-005 自愈需要审核).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from vnc_agent.domain.action import ExecutableAction
from vnc_agent.domain.replay import ReplayPatch, ReplayScript, ReplayStep
from vnc_agent.logging_setup import get_logger
from vnc_agent.runtime.telemetry import log_event

log = get_logger("replay_patch")


def build_pending_patch(
    *,
    script: ReplayScript,
    step: ReplayStep,
    new_executable: ExecutableAction,
    reason: str,
    before_image: str | None,
    after_image: str | None,
    verification_evidence: list[str] | None = None,
) -> ReplayPatch:
    """Build the pending self-heal candidate for one fallback success.

    ``old_target``/``new_target`` are generic geometry/evidence dicts — no
    business vocabulary (Constitution VI).
    """
    old_target: dict[str, Any] = {
        "template_path": step.target_template_path,
        "bbox": list(step.bbox) if step.bbox is not None else None,
        "normalized_bbox": (
            list(step.normalized_bbox) if step.normalized_bbox is not None else None
        ),
        "anchor_texts": list(step.anchor_texts),
    }
    new_target: dict[str, Any] = {
        "bbox": (
            list(new_executable.target_region.as_tuple())
            if new_executable.target_region is not None
            else None
        ),
        "coordinates": (
            list(new_executable.coordinates)
            if new_executable.coordinates is not None
            else None
        ),
        "source": "grounder_fallback",
    }
    return ReplayPatch(
        patch_id=str(uuid.uuid4()),
        script_id=script.script_id,
        replay_step_id=step.replay_step_id,
        old_version=step.version,
        proposed_version=step.version + 1,
        old_target=old_target,
        new_target=new_target,
        reason=reason,
        before_image=before_image,
        after_image=after_image,
        verification_evidence=list(verification_evidence or []),
        status="pending",
        created_at=datetime.now(UTC),
    )


def warn_if_auto_apply_configured(patch_auto_apply: bool) -> bool:
    """ADR-005 red line (spec FR-009): the auto-apply switch never takes
    effect in this MVP. Returns True iff the warning was emitted — patches
    stay pending and scripts stay untouched either way."""
    if not patch_auto_apply:
        return False
    try:
        # Best-effort sink write (same convention as telemetry.log_event):
        # a closed/broken log stream must never break the replay flow.
        log.warning(
            "replay_patch_auto_apply_ignored",
            detail=(
                "replay.patch_auto_apply=true has no effect in this release: "
                "self-heal patches require human review (ADR-005); the patch "
                "remains pending and the stored script is not modified"
            ),
        )
    except Exception:
        pass
    log_event("replay_patch_auto_apply_ignored")
    return True
