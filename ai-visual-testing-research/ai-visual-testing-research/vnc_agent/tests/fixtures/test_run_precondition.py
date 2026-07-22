"""Feature 003 T018: declarative run precondition evaluation (FR-024/025/026).

Reuses the exact same VerificationSpec/VerificationEngine mechanism as
step-level business assertions — no business-specific extraction function.
"""

from datetime import UTC, datetime

import pytest

from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.domain.run import DeclaredFact, RunPrecondition
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.verification.business_resolver import evaluate_precondition
from vnc_agent.verification.engine import VerificationEngine


def _screen(texts: list[str]) -> StructuredScreen:
    return StructuredScreen(
        frame_id="first",
        resolution=(300, 200),
        captured_at=datetime.now(UTC),
        ocr_items=[
            OCRItem(text=t, bbox=(i * 50, 0, i * 50 + 40, 20), confidence=0.99)
            for i, t in enumerate(texts)
        ],
    )


def _precondition(value: str) -> RunPrecondition:
    return RunPrecondition(
        facts=[
            DeclaredFact(
                key="example_state",
                spec=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="text_appears", value=value)],
                ),
            )
        ]
    )


@pytest.mark.asyncio
async def test_declared_fact_matched_observation_passes() -> None:
    result = await evaluate_precondition(
        _precondition("ready"), _screen(["ready", "idle"]), VerificationEngine()
    )
    assert result.status == "passed"
    assert result.fact_evaluations[0].key == "example_state"
    assert result.fact_evaluations[0].result.status == "passed"
    assert result.checked_at is not None


@pytest.mark.asyncio
async def test_declared_fact_mismatched_observation_fails() -> None:
    result = await evaluate_precondition(
        _precondition("ready"), _screen(["busy"]), VerificationEngine()
    )
    assert result.status == "failed"
    assert result.fact_evaluations[0].result.status == "failed"


@pytest.mark.asyncio
async def test_multiple_declared_facts_any_failure_fails_overall() -> None:
    precondition = RunPrecondition(
        facts=[
            DeclaredFact(
                key="fact_a",
                spec=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="text_appears", value="a")],
                ),
            ),
            DeclaredFact(
                key="fact_b",
                spec=VerificationSpec(
                    operator="all",
                    conditions=[VerificationCondition(type="text_appears", value="b")],
                ),
            ),
        ]
    )
    result = await evaluate_precondition(
        precondition, _screen(["a"]), VerificationEngine()
    )
    assert result.status == "failed"
    statuses = {fe.key: fe.result.status for fe in result.fact_evaluations}
    assert statuses == {"fact_a": "passed", "fact_b": "failed"}


@pytest.mark.asyncio
async def test_no_precondition_declared_is_not_required() -> None:
    result = await evaluate_precondition(None, _screen(["anything"]), VerificationEngine())
    assert result.status == "not_required"
    assert result.fact_evaluations == []
    assert result.checked_at is None


@pytest.mark.asyncio
async def test_empty_facts_list_is_not_required() -> None:
    result = await evaluate_precondition(
        RunPrecondition(facts=[]), _screen(["anything"]), VerificationEngine()
    )
    assert result.status == "not_required"
