"""Feature 003 domain and persistence schema contract tests (T002)."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.action_identity import CanonicalActionIdentity
from vnc_agent.domain.grounding import GroundingCandidate
from vnc_agent.domain.repeat_guard import RepeatGuardDecision
from vnc_agent.domain.run import (
    ActionIteration,
    FactEvaluation,
    HumanConfirmedFact,
    PreconditionEvaluation,
    StepRecord,
    TestRun,
)
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.storage.database import init_db, make_engine, make_session_factory
from vnc_agent.storage.repositories import RunRepository


def _identity() -> CanonicalActionIdentity:
    return CanonicalActionIdentity(
        step_id="add-shopping-bag",
        action_type="click",
        action_id="act-1",
        normalized_target="レジ袋",
    )


def test_feature003_domain_fields_and_reason_values() -> None:
    candidate = GroundingCandidate(
        bbox=(257, 630, 415, 720),
        raw_bbox=(251, 402, 405, 459),
        coordinate_space="normalized_1000",
        confidence=0.95,
    )
    iteration = ActionIteration(iteration_index=0, canonical_identity=_identity())

    assert candidate.raw_bbox == (251, 402, 405, 459)
    assert candidate.coordinate_space == "normalized_1000"
    assert iteration.canonical_identity == _identity()

    for reason in (
        "dangerous_drift",
        "legitimate_micro_action",
        "ambiguous_fail_safe",
        "no_effect_confirmed_normalized_target",
        "blocked_effect_pending_normalized_target",
        "blocked_uncertain_normalized_target",
    ):
        assert RepeatGuardDecision(allowed=False, reason=reason).reason == reason

    with pytest.raises(ValidationError):
        RepeatGuardDecision(allowed=True, reason="different_action")


def test_test_run_precondition_types_round_trip() -> None:
    now = datetime.now(UTC)
    run = TestRun(
        run_id="feature-003-schema",
        test_case_id="generic-case",
        precondition_evaluation=PreconditionEvaluation(
            status="passed",
            fact_evaluations=[
                FactEvaluation(
                    key="example_state",
                    result=VerificationResult(status="passed", reason="matched"),
                )
            ],
            checked_at=now,
        ),
        human_confirmed_facts=[
            HumanConfirmedFact(
                key="example_state",
                confirmed_value="0",
                confirmed_at=now,
                screenshot_ref="before.png",
            )
        ],
        steps=[
            StepRecord(
                step_id="add-shopping-bag",
                iterations=[
                    ActionIteration(
                        iteration_index=0,
                        semantic_action=SemanticAction(
                            action_id="act-1",
                            intent="点击レジ袋",
                            action_type="click",
                            target=TargetDescription(text="レジ袋"),
                        ),
                        canonical_identity=_identity(),
                    )
                ],
            )
        ],
    )

    restored = TestRun.model_validate(run.model_dump(mode="json"))
    assert restored == run


@pytest.mark.asyncio
async def test_repository_round_trip_preserves_canonical_identity(tmp_path) -> None:
    engine = make_engine(str(tmp_path / "feature003.db"))
    await init_db(engine)
    repo = RunRepository(make_session_factory(engine))
    run = TestRun(
        run_id="feature-003-repo",
        test_case_id="case",
        steps=[
            StepRecord(
                step_id="s1",
                iterations=[ActionIteration(iteration_index=0, canonical_identity=_identity())],
            )
        ],
    )

    await repo.save_run(run)
    restored = await repo.get_run(run.run_id)
    await engine.dispose()

    assert restored is not None
    assert restored.steps[0].iterations[0].canonical_identity == _identity()
