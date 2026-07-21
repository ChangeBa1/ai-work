"""US1: TestCase / TestStep validation."""

import pytest
from pydantic import ValidationError

from vnc_agent.domain.testcase import FieldValidationError, TestCase, TestStep, load_test_case
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec


def _spec() -> VerificationSpec:
    return VerificationSpec(
        operator="all",
        conditions=[VerificationCondition(type="text_appears", value="ok")],
    )


def test_missing_required_fields_rejected():
    with pytest.raises(ValidationError):
        TestCase.model_validate({"id": "x"})  # missing name, target_id, mode, steps


def test_mode_non_explicit_rejected():
    with pytest.raises((ValidationError, ValueError)):
        TestCase(
            id="a",
            name="n",
            target_id="t",
            mode="goal_driven",  # type: ignore[arg-type]
            steps=[
                TestStep(id="s", name="s", intent="i", expected=_spec()),
            ],
        )


def test_max_retries_negative_rejected():
    with pytest.raises(ValidationError):
        TestStep(id="s", name="s", intent="i", expected=_spec(), max_retries=-1)


def test_valid_testcase():
    tc = TestCase(
        id="a",
        name="n",
        target_id="t",
        mode="explicit",
        steps=[TestStep(id="s", name="s", intent="i", expected=_spec())],
    )
    assert tc.mode == "explicit"
    assert len(tc.steps) == 1
