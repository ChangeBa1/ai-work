"""Feature 003 OCR-versus-grounding sanity-check tests (T031)."""

from datetime import UTC, datetime

from vnc_agent.domain.action import SemanticAction, TargetDescription
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.planning.action_policy import ActionPolicy


def _action() -> SemanticAction:
    return SemanticAction(
        action_id="bag",
        intent="点击レジ袋",
        action_type="click",
        target=TargetDescription(text="レジ袋"),
        action_kind="non_idempotent",
    )


def _screen(*, with_anchor: bool = True) -> StructuredScreen:
    return StructuredScreen(
        frame_id="f1",
        resolution=(1000, 1000),
        captured_at=datetime.now(UTC),
        ocr_items=(
            [OCRItem(text="レジ袋", bbox=(80, 80, 180, 130), confidence=0.99)]
            if with_anchor
            else []
        ),
    )


def _grounding() -> GroundingResult:
    return GroundingResult(
        found=True,
        candidates=[
            GroundingCandidate(
                bbox=(700, 700, 800, 800),
                raw_bbox=(700, 700, 800, 800),
                coordinate_space="pixel",
                confidence=0.99,
            )
        ],
    )


def test_ocr_mismatch_rejected() -> None:
    policy = ActionPolicy(ocr_sanity_check_ratio=0.10)
    result = policy._from_grounding(_action(), _screen(), _grounding())
    assert result.outcome == "stop_recover"
    assert result.executable is None


def test_absence_of_ocr_anchor_does_not_block() -> None:
    policy = ActionPolicy(ocr_sanity_check_ratio=0.10)
    result = policy._from_grounding(_action(), _screen(with_anchor=False), _grounding())
    assert result.outcome == "grounding"
    assert result.executable is not None
