"""Feature 016 unit tests: replay domain models + repository versioning
(spec FR-001/FR-002/FR-003, SC-005)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vnc_agent.domain.action import SemanticAction
from vnc_agent.domain.memory import PageFingerprint
from vnc_agent.domain.replay import (
    ReplayAnchor,
    ReplayScript,
    ReplayStep,
    normalize_bbox,
)
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.replay.locator import restore_bbox_from_normalized
from vnc_agent.storage.database import init_db, make_engine, make_session_factory
from vnc_agent.storage.repositories import ReplayRepository

RESOLUTION = (300, 200)


def _spec() -> VerificationSpec:
    return VerificationSpec(
        operator="all",
        conditions=[VerificationCondition(type="text_appears", value="DONE")],
    )


def _sa() -> SemanticAction:
    return SemanticAction(
        action_id="a1", intent="click ok", action_type="click"
    )


def _mouse_step(version: int = 1, order_index: int = 0) -> ReplayStep:
    bbox = (150, 85, 170, 95)
    return ReplayStep(
        replay_step_id=str(uuid.uuid4()),
        step_id="s1",
        order_index=order_index,
        page_fingerprint=PageFingerprint(resolution=RESOLUTION),
        semantic_action=_sa(),
        preferred_method="mouse",
        anchors=[ReplayAnchor(text="TOTAL", bbox=(100, 80, 160, 96))],
        anchor_texts=["TOTAL"],
        bbox=bbox,
        normalized_bbox=normalize_bbox(bbox, RESOLUTION),
        expected=_spec(),
        version=version,
    )


class TestReplayStepModel:
    def test_serialization_round_trip(self):
        step = _mouse_step()
        restored = ReplayStep.model_validate(step.model_dump(mode="json"))
        assert restored == step

    def test_mouse_step_requires_geometry(self):
        with pytest.raises(ValueError):
            ReplayStep(
                replay_step_id="r1",
                step_id="s1",
                order_index=0,
                page_fingerprint=PageFingerprint(resolution=RESOLUTION),
                semantic_action=_sa(),
                preferred_method="mouse",
                expected=_spec(),
                version=1,
            )

    def test_direct_fallback_only_mouse_step_allows_missing_geometry(self):
        step = ReplayStep(
            replay_step_id="r1",
            step_id="s1",
            order_index=0,
            page_fingerprint=PageFingerprint(resolution=RESOLUTION),
            semantic_action=_sa(),
            preferred_method="mouse",
            direct_fallback_only=True,
            expected=_spec(),
            version=1,
        )
        assert step.target_template_path is None

    def test_script_rejects_out_of_order_steps(self):
        with pytest.raises(ValueError):
            ReplayScript(
                script_id="sc1",
                test_case_id="tc1",
                version=1,
                source_run_id="r1",
                steps=[_mouse_step(order_index=1)],
            )


class TestNormalizedBBox:
    def test_same_resolution_round_trip_is_exact(self):
        bbox = (150, 85, 170, 95)
        normalized = normalize_bbox(bbox, RESOLUTION)
        restored = restore_bbox_from_normalized(
            normalized,
            recorded_resolution=RESOLUTION,
            current_resolution=RESOLUTION,
        )
        assert restored == bbox

    def test_resolution_mismatch_refuses_direct_restore(self):
        """Spec Clarification 3: never a scaled guess across resolutions."""
        normalized = normalize_bbox((150, 85, 170, 95), RESOLUTION)
        assert (
            restore_bbox_from_normalized(
                normalized,
                recorded_resolution=RESOLUTION,
                current_resolution=(600, 400),
            )
            is None
        )

    def test_invalid_resolution_rejected(self):
        with pytest.raises(ValueError):
            normalize_bbox((0, 0, 10, 10), (0, 200))


@pytest.mark.asyncio
class TestReplayRepositoryVersioning:
    async def _repo(self, tmp_path: Path) -> ReplayRepository:
        engine = make_engine(str(tmp_path / "replay.db"))
        await init_db(engine)
        return ReplayRepository(make_session_factory(engine))

    def _script(self, version: int) -> ReplayScript:
        return ReplayScript(
            script_id=str(uuid.uuid4()),
            test_case_id="tc1",
            version=version,
            source_run_id=f"run-{version}",
            created_at=datetime.now(UTC),
            steps=[_mouse_step(version=version)],
        )

    async def test_versions_accumulate_and_latest_wins(self, tmp_path: Path):
        repo = await self._repo(tmp_path)
        assert await repo.next_version("tc1") == 1
        await repo.save_script(self._script(1))
        assert await repo.next_version("tc1") == 2
        await repo.save_script(self._script(2))

        scripts = await repo.list_scripts("tc1")
        assert [s.version for s in scripts] == [1, 2]  # old version retained
        latest = await repo.get_latest_script("tc1")
        assert latest is not None and latest.version == 2
        assert len(latest.steps) == 1

    async def test_bump_step_stats_touches_counters_only(self, tmp_path: Path):
        """ADR-005 / spec Clarification 5: target fields stay byte-identical."""
        repo = await self._repo(tmp_path)
        script = self._script(1)
        await repo.save_script(script)
        step_id = script.steps[0].replay_step_id

        await repo.bump_step_stats(step_id, passed=True)
        await repo.bump_step_stats(step_id, passed=False)

        stored = await repo.get_step(step_id)
        assert stored is not None
        assert stored.success_count == 1
        assert stored.failure_count == 1
        original = script.steps[0]
        assert stored.bbox == original.bbox
        assert stored.normalized_bbox == original.normalized_bbox
        assert stored.anchor_texts == original.anchor_texts
        assert stored.target_template_path == original.target_template_path
        assert stored.expected == original.expected
        assert stored.semantic_action == original.semantic_action

    async def test_unknown_test_case_has_no_script(self, tmp_path: Path):
        repo = await self._repo(tmp_path)
        assert await repo.get_latest_script("missing") is None
        assert await repo.list_scripts("missing") == []
        assert await repo.list_patches("missing") == []
