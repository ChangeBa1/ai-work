"""Persistence repositories for TestRun / StepRecord / iterations / recovery."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vnc_agent.domain.memory import ElementMemory, PageMemory
from vnc_agent.domain.replay import ReplayPatch, ReplayScript, ReplayStep
from vnc_agent.domain.run import StepRecord, TestRun, VisualExperience
from vnc_agent.storage.database import (
    ActionIterationRow,
    ElementMemoryRow,
    PageMemoryRow,
    RecoveryAttemptRow,
    ReplayPatchRow,
    ReplayScriptRow,
    ReplayStepRow,
    StepRecordRow,
    TestRunRow,
    VisualExperienceRow,
)


class RunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def save_run(self, run: TestRun) -> None:
        async with self.session_factory() as session:
            row = await session.get(TestRunRow, run.run_id)
            payload = run.model_dump(mode="json")
            if row is None:
                row = TestRunRow(
                    run_id=run.run_id,
                    test_case_id=run.test_case_id,
                    status=run.status,
                    started_at=run.started_at,
                    ended_at=run.ended_at,
                    report_json_path=run.report_json_path,
                    report_html_path=run.report_html_path,
                    payload=payload,
                )
                session.add(row)
            else:
                row.status = run.status
                row.started_at = run.started_at
                row.ended_at = run.ended_at
                row.report_json_path = run.report_json_path
                row.report_html_path = run.report_html_path
                row.payload = payload
            await session.commit()

    async def get_run(self, run_id: str) -> TestRun | None:
        async with self.session_factory() as session:
            row = await session.get(TestRunRow, run_id)
            if row is None:
                return None
            return TestRun.model_validate(row.payload)

    async def save_step(self, run_id: str, step: StepRecord) -> None:
        async with self.session_factory() as session:
            session.add(
                StepRecordRow(
                    run_id=run_id,
                    step_id=step.step_id,
                    final_status=step.final_status,
                    failure_reason=step.failure_reason,
                    payload=step.model_dump(mode="json"),
                )
            )
            for it in step.iterations:
                # 002: persist action_effect / repeat_guard as explicit nullable JSON keys
                # on the iteration payload (no new tables; database.py schema body unchanged)
                payload = it.model_dump(mode="json")
                payload["action_effect_json"] = (
                    it.action_effect.model_dump(mode="json")
                    if it.action_effect is not None
                    else None
                )
                payload["repeat_guard_decision_json"] = (
                    it.repeat_guard_decision.model_dump(mode="json")
                    if it.repeat_guard_decision is not None
                    else None
                )
                payload["canonical_identity_json"] = (
                    it.canonical_identity.model_dump(mode="json")
                    if it.canonical_identity is not None
                    else None
                )
                session.add(
                    ActionIterationRow(
                        run_id=run_id,
                        step_id=step.step_id,
                        iteration_index=it.iteration_index,
                        payload=payload,
                    )
                )
                for ra in it.recovery_attempts:
                    session.add(
                        RecoveryAttemptRow(
                            run_id=run_id,
                            step_id=step.step_id,
                            iteration_index=it.iteration_index,
                            payload=ra.model_dump(mode="json"),
                        )
                    )
            await session.commit()

    async def save_experience(self, exp: VisualExperience) -> None:
        async with self.session_factory() as session:
            session.add(
                VisualExperienceRow(
                    run_id=exp.run_id,
                    step_id=exp.step_id,
                    outcome=exp.outcome,
                    payload=exp.model_dump(mode="json"),
                )
            )
            await session.commit()


class EvolutionExportRepository:
    """Feature 021 (evolution-hardcase-export, FR-006): query-only access for
    the offline hard-case exporter. SELECTs only — this class MUST never
    add/update/delete rows (zero-runtime-impact red line; the run store's
    write path stays exclusively in :class:`RunRepository`)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def list_runs(self) -> list[dict]:
        """All runs, oldest-first by run_id for determinism. Each entry:
        run_id / test_case_id / started_at / payload (full TestRun dump —
        including ``frames[]`` used for frame-id → screenshot-path mapping).
        `--since` filtering happens in the exporter (UTC normalization of
        naive SQLite datetimes is policy, not storage)."""
        async with self.session_factory() as session:
            rows = (
                (await session.execute(select(TestRunRow).order_by(TestRunRow.run_id)))
                .scalars()
                .all()
            )
            return [
                {
                    "run_id": r.run_id,
                    "test_case_id": r.test_case_id,
                    "status": r.status,
                    "started_at": r.started_at,
                    "payload": r.payload or {},
                }
                for r in rows
            ]

    async def list_step_rows(self, run_id: str) -> list[dict]:
        async with self.session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(StepRecordRow)
                        .where(StepRecordRow.run_id == run_id)
                        .order_by(StepRecordRow.id)
                    )
                )
                .scalars()
                .all()
            )
            return [
                {
                    "step_id": r.step_id,
                    "final_status": r.final_status,
                    "failure_reason": r.failure_reason,
                    "payload": r.payload or {},
                }
                for r in rows
            ]

    async def list_iteration_rows(self, run_id: str) -> list[dict]:
        async with self.session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ActionIterationRow)
                        .where(ActionIterationRow.run_id == run_id)
                        .order_by(ActionIterationRow.step_id, ActionIterationRow.iteration_index)
                    )
                )
                .scalars()
                .all()
            )
            return [
                {
                    "step_id": r.step_id,
                    "iteration_index": r.iteration_index,
                    "payload": r.payload or {},
                }
                for r in rows
            ]

    async def list_recovery_rows(self, run_id: str) -> list[dict]:
        async with self.session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(RecoveryAttemptRow)
                        .where(RecoveryAttemptRow.run_id == run_id)
                        .order_by(RecoveryAttemptRow.id)
                    )
                )
                .scalars()
                .all()
            )
            return [
                {
                    "step_id": r.step_id,
                    "iteration_index": r.iteration_index,
                    "payload": r.payload or {},
                }
                for r in rows
            ]

    async def list_experience_rows(self, run_id: str) -> list[dict]:
        async with self.session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(VisualExperienceRow)
                        .where(VisualExperienceRow.run_id == run_id)
                        .order_by(VisualExperienceRow.id)
                    )
                )
                .scalars()
                .all()
            )
            return [
                {
                    "step_id": r.step_id,
                    "outcome": r.outcome,
                    "payload": r.payload or {},
                }
                for r in rows
            ]


class MemoryRepository:
    """Feature 015 (FR-003): page/element memory persistence — same
    payload-column repository pattern as :class:`RunRepository`."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    # --- pages ------------------------------------------------------------

    async def list_pages(self) -> list[PageMemory]:
        async with self.session_factory() as session:
            rows = (await session.execute(select(PageMemoryRow))).scalars().all()
            return [PageMemory.model_validate(r.payload) for r in rows]

    async def get_page(self, page_id: str) -> PageMemory | None:
        async with self.session_factory() as session:
            row = await session.get(PageMemoryRow, page_id)
            return PageMemory.model_validate(row.payload) if row is not None else None

    async def save_page(self, page: PageMemory) -> None:
        async with self.session_factory() as session:
            row = await session.get(PageMemoryRow, page.page_id)
            payload = page.model_dump(mode="json")
            if row is None:
                session.add(
                    PageMemoryRow(
                        page_id=page.page_id,
                        resolution_w=page.resolution[0],
                        resolution_h=page.resolution[1],
                        hit_count=page.hit_count,
                        last_seen_at=page.last_seen_at,
                        payload=payload,
                    )
                )
            else:
                row.resolution_w = page.resolution[0]
                row.resolution_h = page.resolution[1]
                row.hit_count = page.hit_count
                row.last_seen_at = page.last_seen_at
                row.payload = payload
            await session.commit()

    # --- elements ---------------------------------------------------------

    async def list_elements(self, page_id: str) -> list[ElementMemory]:
        async with self.session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ElementMemoryRow).where(ElementMemoryRow.page_id == page_id)
                    )
                )
                .scalars()
                .all()
            )
            return [ElementMemory.model_validate(r.payload) for r in rows]

    async def find_element(self, page_id: str, target_label: str) -> ElementMemory | None:
        """Legacy 015 label lookup (identity_enabled=false path)."""
        async with self.session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ElementMemoryRow).where(
                            ElementMemoryRow.page_id == page_id,
                            ElementMemoryRow.target_label == target_label,
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not rows:
                return None
            # Deterministic pick on the (unexpected) duplicate case.
            row = sorted(rows, key=lambda r: r.element_id)[0]
            return ElementMemory.model_validate(row.payload)

    async def find_elements_by_identity(
        self, page_id: str, identity_key: str
    ) -> list[ElementMemory]:
        """Feature 025: all rows for (page_id, identity_key)."""
        if not identity_key:
            return []
        async with self.session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ElementMemoryRow).where(
                            ElementMemoryRow.page_id == page_id,
                            ElementMemoryRow.identity_key == identity_key,
                        )
                    )
                )
                .scalars()
                .all()
            )
            return [
                ElementMemory.model_validate(r.payload)
                for r in sorted(rows, key=lambda r: r.element_id)
            ]

    async def save_element(self, element: ElementMemory) -> None:
        async with self.session_factory() as session:
            row = await session.get(ElementMemoryRow, element.element_id)
            payload = element.model_dump(mode="json")
            identity_key = element.identity_key or ""
            if row is None:
                session.add(
                    ElementMemoryRow(
                        element_id=element.element_id,
                        page_id=element.page_id,
                        target_label=element.target_label,
                        identity_key=identity_key,
                        success_count=element.success_count,
                        failure_count=element.failure_count,
                        last_success_at=element.last_success_at,
                        payload=payload,
                    )
                )
            else:
                row.page_id = element.page_id
                row.target_label = element.target_label
                row.identity_key = identity_key
                row.success_count = element.success_count
                row.failure_count = element.failure_count
                row.last_success_at = element.last_success_at
                row.payload = payload
            await session.commit()

    async def delete_element(self, element_id: str) -> None:
        async with self.session_factory() as session:
            row = await session.get(ElementMemoryRow, element_id)
            if row is not None:
                await session.delete(row)
                await session.commit()

    async def count_elements(self, page_id: str) -> int:
        async with self.session_factory() as session:
            result = await session.execute(
                select(func.count())
                .select_from(ElementMemoryRow)
                .where(ElementMemoryRow.page_id == page_id)
            )
            return int(result.scalar_one())

    async def purge_legacy_element_memories(
        self, *, current_prefix: str
    ) -> int:
        """Delete rows with empty identity_key or prefix != current schema:gG."""
        deleted = 0
        needle = current_prefix + "|"
        async with self.session_factory() as session:
            rows = (await session.execute(select(ElementMemoryRow))).scalars().all()
            for row in rows:
                key = (row.identity_key or "").strip()
                if not key.startswith(needle):
                    await session.delete(row)
                    deleted += 1
            await session.commit()
        return deleted


class ReplayRepository:
    """Feature 016 (FR-002): replay script / step / patch persistence — same
    payload-column repository pattern as :class:`RunRepository`.

    ADR-005 / spec FR-009: during replay only :meth:`bump_step_stats` may
    touch a stored step, and it rewrites the success/failure counters alone —
    target fields (template/bbox/anchors/action) are immutable once saved.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    # --- scripts ----------------------------------------------------------

    async def save_script(self, script: ReplayScript) -> None:
        """Insert a new script version with its ordered steps (never updates
        an existing version — versions are immutable, spec FR-003)."""
        async with self.session_factory() as session:
            meta = script.model_dump(mode="json", exclude={"steps"})
            session.add(
                ReplayScriptRow(
                    script_id=script.script_id,
                    test_case_id=script.test_case_id,
                    version=script.version,
                    source_run_id=script.source_run_id,
                    created_at=script.created_at,
                    payload=meta,
                )
            )
            for step in script.steps:
                session.add(
                    ReplayStepRow(
                        replay_step_id=step.replay_step_id,
                        script_id=script.script_id,
                        step_id=step.step_id,
                        order_index=step.order_index,
                        success_count=step.success_count,
                        failure_count=step.failure_count,
                        payload=step.model_dump(mode="json"),
                    )
                )
            await session.commit()

    async def list_scripts(self, test_case_id: str) -> list[ReplayScript]:
        """All script versions for a test case (ascending version), steps
        included and ordered."""
        async with self.session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ReplayScriptRow)
                        .where(ReplayScriptRow.test_case_id == test_case_id)
                        .order_by(ReplayScriptRow.version)
                    )
                )
                .scalars()
                .all()
            )
            scripts: list[ReplayScript] = []
            for row in rows:
                steps = await self._load_steps(session, row.script_id)
                scripts.append(
                    ReplayScript.model_validate({**row.payload, "steps": steps})
                )
            return scripts

    async def get_latest_script(self, test_case_id: str) -> ReplayScript | None:
        async with self.session_factory() as session:
            row = (
                (
                    await session.execute(
                        select(ReplayScriptRow)
                        .where(ReplayScriptRow.test_case_id == test_case_id)
                        .order_by(ReplayScriptRow.version.desc())
                        .limit(1)
                    )
                )
                .scalars()
                .first()
            )
            if row is None:
                return None
            steps = await self._load_steps(session, row.script_id)
            return ReplayScript.model_validate({**row.payload, "steps": steps})

    async def next_version(self, test_case_id: str) -> int:
        async with self.session_factory() as session:
            result = await session.execute(
                select(func.max(ReplayScriptRow.version)).where(
                    ReplayScriptRow.test_case_id == test_case_id
                )
            )
            current = result.scalar_one()
            return int(current or 0) + 1

    async def _load_steps(self, session: AsyncSession, script_id: str) -> list[dict]:
        rows = (
            (
                await session.execute(
                    select(ReplayStepRow)
                    .where(ReplayStepRow.script_id == script_id)
                    .order_by(ReplayStepRow.order_index)
                )
            )
            .scalars()
            .all()
        )
        return [r.payload for r in rows]

    # --- step statistics (the only replay-time write, spec Clarification 5)

    async def bump_step_stats(self, replay_step_id: str, *, passed: bool) -> None:
        """Update success/failure counters only — every target field of the
        stored payload stays byte-identical (ADR-005 read-only red line)."""
        async with self.session_factory() as session:
            row = await session.get(ReplayStepRow, replay_step_id)
            if row is None:
                return
            if passed:
                row.success_count += 1
            else:
                row.failure_count += 1
            payload = dict(row.payload)
            payload["success_count"] = row.success_count
            payload["failure_count"] = row.failure_count
            row.payload = payload
            await session.commit()

    async def get_step(self, replay_step_id: str) -> ReplayStep | None:
        async with self.session_factory() as session:
            row = await session.get(ReplayStepRow, replay_step_id)
            return ReplayStep.model_validate(row.payload) if row is not None else None

    # --- patches ----------------------------------------------------------

    async def save_patch(self, patch: ReplayPatch) -> None:
        async with self.session_factory() as session:
            session.add(
                ReplayPatchRow(
                    patch_id=patch.patch_id,
                    script_id=patch.script_id,
                    replay_step_id=patch.replay_step_id,
                    status=patch.status,
                    created_at=patch.created_at,
                    payload=patch.model_dump(mode="json"),
                )
            )
            await session.commit()

    async def list_patches(
        self, test_case_id: str, *, status: str | None = None
    ) -> list[ReplayPatch]:
        """Patches for every script version of a test case, oldest first."""
        async with self.session_factory() as session:
            script_ids = (
                (
                    await session.execute(
                        select(ReplayScriptRow.script_id).where(
                            ReplayScriptRow.test_case_id == test_case_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not script_ids:
                return []
            query = select(ReplayPatchRow).where(ReplayPatchRow.script_id.in_(script_ids))
            if status is not None:
                query = query.where(ReplayPatchRow.status == status)
            rows = (
                (await session.execute(query.order_by(ReplayPatchRow.patch_id)))
                .scalars()
                .all()
            )
            return [ReplayPatch.model_validate(r.payload) for r in rows]
