"""US7: screen/region change verifiers."""

from datetime import datetime, timezone

from vnc_agent.domain.observation import Region, StructuredScreen
from vnc_agent.domain.verification import VerificationCondition
from vnc_agent.verification.screen_change_verifier import verify_screen_change


def test_screen_changed():
    s = StructuredScreen(
        frame_id="f",
        resolution=(100, 100),
        captured_at=datetime.now(timezone.utc),
        changed_since_last=True,
        changed_regions=[Region(x1=0, y1=0, x2=10, y2=10)],
    )
    assert (
        verify_screen_change(VerificationCondition(type="screen_changed"), s) == "passed"
    )
    s2 = s.model_copy(update={"changed_since_last": False, "changed_regions": []})
    assert (
        verify_screen_change(VerificationCondition(type="screen_changed"), s2) == "failed"
    )
