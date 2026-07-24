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


# --- Feature 005 (T014): batch_repeat_key declaration --------------------


def test_batch_repeat_key_valid_declaration():
    step = TestStep(
        id="s",
        name="s",
        intent="clear field",
        expected=_spec(),
        batch_repeat_key={"key": "backspace", "count": 20},
    )
    assert step.batch_repeat_key is not None
    assert step.batch_repeat_key.count == 20
    assert step.batch_repeat_key.interval_ms is None


def test_batch_repeat_key_modifier_rejected():
    with pytest.raises(ValidationError):
        TestStep(
            id="s",
            name="s",
            intent="x",
            expected=_spec(),
            batch_repeat_key={"key": "shift", "count": 5},
        )


def test_batch_repeat_key_unknown_key_rejected():
    with pytest.raises(ValidationError):
        TestStep(
            id="s",
            name="s",
            intent="x",
            expected=_spec(),
            batch_repeat_key={"key": "nope", "count": 5},
        )


@pytest.mark.parametrize("count", [0, 51])
def test_batch_repeat_key_out_of_range_count_rejected(count):
    with pytest.raises(ValidationError):
        TestStep(
            id="s",
            name="s",
            intent="x",
            expected=_spec(),
            batch_repeat_key={"key": "backspace", "count": count},
        )


@pytest.mark.parametrize("interval_ms", [-1, 501])
def test_batch_repeat_key_out_of_range_interval_rejected(interval_ms):
    with pytest.raises(ValidationError):
        TestStep(
            id="s",
            name="s",
            intent="x",
            expected=_spec(),
            batch_repeat_key={"key": "backspace", "count": 5, "interval_ms": interval_ms},
        )


def test_batch_repeat_key_omitted_defaults_to_none():
    step = TestStep(id="s", name="s", intent="i", expected=_spec())
    assert step.batch_repeat_key is None
