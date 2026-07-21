"""Text appears/disappears verifiers."""

from __future__ import annotations

from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.domain.verification import VerificationCondition, VerificationStatus


def verify_text(condition: VerificationCondition, screen: StructuredScreen) -> VerificationStatus:
    needle = (condition.value or "").strip().lower()
    if not needle:
        return "uncertain"
    found = any(
        needle in i.normalized_text or needle in i.text.lower() for i in screen.ocr_items
    )
    if condition.type == "text_appears":
        return "passed" if found else "failed"
    if condition.type == "text_disappears":
        return "passed" if not found else "failed"
    return "uncertain"
