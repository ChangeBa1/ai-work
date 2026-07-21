"""Template appears/disappears verifiers."""

from __future__ import annotations

from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.verification import VerificationCondition, VerificationStatus


def verify_template(
    condition: VerificationCondition, screen: StructuredScreen
) -> VerificationStatus:
    needle = (condition.value or "").strip().lower()
    if not needle:
        return "uncertain"
    found = any(
        needle in m.template_id.lower() or needle == m.template_id.lower()
        for m in screen.template_matches
    )
    if condition.type == "template_appears":
        return "passed" if found else "failed"
    if condition.type == "template_disappears":
        return "passed" if not found else "failed"
    return "uncertain"
