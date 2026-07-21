"""Region / whole-screen change verifiers."""

from __future__ import annotations

from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.verification import VerificationCondition, VerificationStatus


def verify_screen_change(
    condition: VerificationCondition, screen: StructuredScreen
) -> VerificationStatus:
    if condition.type == "screen_changed":
        return "passed" if screen.changed_since_last else "failed"
    if condition.type == "region_changed":
        if condition.region is None:
            return "uncertain"
        r = condition.region
        for cr in screen.changed_regions:
            # overlap?
            if not (cr.x2 <= r.x1 or cr.x1 >= r.x2 or cr.y2 <= r.y1 or cr.y1 >= r.y2):
                return "passed"
        return "failed" if screen.changed_regions or not screen.changed_since_last else "failed"
    return "uncertain"
