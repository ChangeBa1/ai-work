"""Persistence repositories for TestRun / StepRecord / iterations / recovery."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vnc_agent.domain.run import StepRecord, TestRun, VisualExperience
from vnc_agent.storage.database import (
    ActionIterationRow,
    RecoveryAttemptRow,
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
