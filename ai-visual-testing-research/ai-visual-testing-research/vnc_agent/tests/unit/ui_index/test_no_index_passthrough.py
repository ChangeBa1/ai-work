"""T039: build_hints() no-op passthrough when no bundle is configured
(FR-011, research.md §9)."""

from __future__ import annotations

from datetime import datetime, timezone

from vnc_agent.config import UiIndexConfig
from vnc_agent.domain.observation import StructuredScreen
from vnc_agent.ui_index.audit import IndexUsageAuditRecord
from vnc_agent.ui_index.runtime_adapter import build_hints


def _empty_screen() -> StructuredScreen:
    return StructuredScreen(
        frame_id="frame-1",
        resolution=(1000, 1000),
        captured_at=datetime.now(timezone.utc),
    )


def test_build_hints_with_none_bundle_returns_empty_hints_and_candidates():
    hints, candidates, audit = build_hints(None, _empty_screen(), UiIndexConfig())
    assert hints == []
    assert candidates == []
    assert isinstance(audit, IndexUsageAuditRecord)
    assert audit.outcome == "not_configured"


def test_build_hints_with_none_bundle_audit_has_no_bundle_identity():
    _hints, _candidates, audit = build_hints(None, _empty_screen(), UiIndexConfig())
    assert audit.bundle_id is None
    assert audit.schema_version is None
    assert audit.matched_screen_id is None
    assert audit.hint_element_ids == []
    assert audit.candidate_transition_ids == []
    assert audit.no_match_reason is None


def test_build_hints_with_none_bundle_is_independent_of_screen_content():
    """Contract: bundle=None is a hard short-circuit — the outcome does not
    depend at all on what's in current_screen (no OCR matching attempted)."""
    from vnc_agent.domain.observation import OCRItem

    screen_with_text = StructuredScreen(
        frame_id="frame-2",
        resolution=(1000, 1000),
        captured_at=datetime.now(timezone.utc),
        ocr_items=[OCRItem(text="anything at all", bbox=(0, 0, 10, 10), confidence=0.9)],
    )
    hints, candidates, audit = build_hints(None, screen_with_text, UiIndexConfig())
    assert hints == []
    assert candidates == []
    assert audit.outcome == "not_configured"
