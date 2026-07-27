"""Feature 016 unit tests: ReplayPatch lifecycle (spec FR-009, ADR-005, SC-005)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vnc_agent.domain.action import ExecutableAction, SemanticAction
from vnc_agent.domain.memory import PageFingerprint
from vnc_agent.domain.observation import Region
from vnc_agent.domain.replay import ReplayScript, ReplayStep, normalize_bbox
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.replay.patch import build_pending_patch, warn_if_auto_apply_configured
from vnc_agent.storage.database import init_db, make_engine, make_session_factory
from vnc_agent.storage.repositories import ReplayRepository

RESOLUTION = (300, 200)
OLD_BBOX = (150, 85, 170, 95)
NEW_BBOX = (200, 120, 220, 130)


def _step() -> ReplayStep:
    return ReplayStep(
        replay_step_id=str(uuid.uuid4()),
        step_id="s1",
        order_index=0,
        page_fingerprint=PageFingerprint(resolution=RESOLUTION),
        semantic_action=SemanticAction(action_id="a1", intent="click", action_type="click"),
        preferred_method="mouse",
        target_template_path="templates/t.png",
        anchor_texts=["TOTAL"],
        bbox=OLD_BBOX,
        normalized_bbox=normalize_bbox(OLD_BBOX, RESOLUTION),
        expected=VerificationSpec(
            operator="all",
            conditions=[VerificationCondition(type="text_appears", value="DONE")],
        ),
        version=3,
    )


def _script(step: ReplayStep) -> ReplayScript:
    return ReplayScript(
        script_id="sc1",
        test_case_id="tc1",
        version=3,
        source_run_id="run-1",
        created_at=datetime.now(UTC),
        steps=[step.model_copy(update={"order_index": 0})],
    )


def _new_executable() -> ExecutableAction:
    return ExecutableAction(
        method="mouse",
        operation="click",
        coordinates=(210, 125),
        target_region=Region(x1=NEW_BBOX[0], y1=NEW_BBOX[1], x2=NEW_BBOX[2], y2=NEW_BBOX[3]),
    )


class TestBuildPendingPatch:
    def test_patch_is_pending_with_old_and_new_targets(self):
        step = _step()
        patch = build_pending_patch(
            script=_script(step),
            step=step,
            new_executable=_new_executable(),
            reason="template/anchor/bbox locate all missed",
            before_image="before.png",
            after_image="after.png",
            verification_evidence=["ev1"],
        )
        assert patch.status == "pending"
        assert patch.replay_step_id == step.replay_step_id
        assert patch.old_version == 3 and patch.proposed_version == 4
        assert patch.old_target["bbox"] == list(OLD_BBOX)
        assert patch.old_target["template_path"] == "templates/t.png"
        assert patch.old_target["anchor_texts"] == ["TOTAL"]
        assert patch.new_target["bbox"] == list(NEW_BBOX)
        assert patch.new_target["coordinates"] == [210, 125]
        assert patch.before_image == "before.png"
        assert patch.after_image == "after.png"
        assert patch.verification_evidence == ["ev1"]

    def test_round_trip(self):
        step = _step()
        patch = build_pending_patch(
            script=_script(step),
            step=step,
            new_executable=_new_executable(),
            reason="r",
            before_image=None,
            after_image=None,
        )
        from vnc_agent.domain.replay import ReplayPatch

        assert ReplayPatch.model_validate(patch.model_dump(mode="json")) == patch


class TestAutoApplyRedLine:
    def test_false_emits_nothing(self):
        assert warn_if_auto_apply_configured(False) is False

    def test_true_only_warns_never_applies(self, tmp_path: Path):
        # The warning fires...
        assert warn_if_auto_apply_configured(True) is True
        # ...and there is no apply machinery at all: the patch module exposes
        # nothing that could mutate a script (ADR-005).
        import vnc_agent.replay.patch as patch_mod

        assert not [n for n in dir(patch_mod) if "apply_patch" in n]


@pytest.mark.asyncio
async def test_patch_persistence_and_stored_script_untouched(tmp_path: Path):
    """SC-003 core: saving a patch never modifies the stored step row."""
    engine = make_engine(str(tmp_path / "replay.db"))
    await init_db(engine)
    repo = ReplayRepository(make_session_factory(engine))

    step = _step().model_copy(update={"order_index": 0, "version": 1})
    script = ReplayScript(
        script_id="sc1",
        test_case_id="tc1",
        version=1,
        source_run_id="run-1",
        created_at=datetime.now(UTC),
        steps=[step],
    )
    await repo.save_script(script)
    before = await repo.get_step(step.replay_step_id)

    patch = build_pending_patch(
        script=script,
        step=step,
        new_executable=_new_executable(),
        reason="moved",
        before_image=None,
        after_image=None,
    )
    await repo.save_patch(patch)

    after = await repo.get_step(step.replay_step_id)
    assert after == before  # byte-identical target fields

    patches = await repo.list_patches("tc1")
    assert len(patches) == 1
    assert patches[0].status == "pending"
    pending = await repo.list_patches("tc1", status="pending")
    assert len(pending) == 1
    assert await repo.list_patches("tc1", status="approved") == []
