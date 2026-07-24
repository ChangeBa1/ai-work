"""VisionUnderstandingResponse must tolerate common model answer aliases."""

from vnc_agent.models.provider import VisionUnderstandingResponse


def test_not_passed_coerces_to_failed() -> None:
    r = VisionUnderstandingResponse(
        mode="answer_question",
        answer="not_passed",
        reason="cart empty",
        confidence=0.9,
        model_name="stub",
    )
    assert r.answer == "failed"


def test_pass_yes_aliases_to_passed() -> None:
    assert (
        VisionUnderstandingResponse(
            mode="answer_question", answer="pass", reason="ok", model_name="s"
        ).answer
        == "passed"
    )
    assert (
        VisionUnderstandingResponse(
            mode="answer_question", answer="yes", reason="ok", model_name="s"
        ).answer
        == "passed"
    )


def test_unknown_answer_becomes_uncertain() -> None:
    r = VisionUnderstandingResponse(
        mode="answer_question",
        answer="maybe-later",
        reason="ambiguous",
        model_name="stub",
    )
    assert r.answer == "uncertain"
