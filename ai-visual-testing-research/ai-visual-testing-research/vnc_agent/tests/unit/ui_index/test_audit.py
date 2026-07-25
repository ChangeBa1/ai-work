"""T037: record_index_usage() writes ActionIteration + structured log
(contracts §7, data-model.md §4.2, FR-013)."""

from __future__ import annotations

from vnc_agent.domain.run import ActionIteration
from vnc_agent.ui_index.audit import IndexUsageAuditRecord, record_index_usage

EXPECTED_FIELDS = {
    "bundle_id",
    "schema_version",
    "outcome",
    "matched_screen_id",
    "hint_element_ids",
    "candidate_transition_ids",
    "no_match_reason",
    "grounder_outcome",
}


def test_index_usage_audit_record_field_set():
    assert EXPECTED_FIELDS.issubset(set(IndexUsageAuditRecord.model_fields.keys()))


def _sample_audit() -> IndexUsageAuditRecord:
    return IndexUsageAuditRecord(
        bundle_id="bundle-1",
        schema_version="1.0",
        outcome="hit",
        matched_screen_id="screen.home",
        hint_element_ids=["el.a", "el.b"],
        candidate_transition_ids=["tr.a"],
        no_match_reason=None,
        grounder_outcome="succeeded",
    )


def test_record_index_usage_writes_iteration_field():
    iteration = ActionIteration(iteration_index=0)
    audit = _sample_audit()
    assert iteration.ui_index_audit is None

    record_index_usage(iteration, audit)

    assert iteration.ui_index_audit is not None
    assert iteration.ui_index_audit.outcome == "hit"
    assert iteration.ui_index_audit.bundle_id == "bundle-1"
    assert iteration.ui_index_audit.hint_element_ids == ["el.a", "el.b"]


def test_record_index_usage_emits_structured_log_event(monkeypatch):
    captured = {}

    def fake_log_event(event_name, **fields):
        captured["event_name"] = event_name
        captured["fields"] = fields

    import vnc_agent.ui_index.audit as audit_mod

    monkeypatch.setattr(audit_mod, "log_event", fake_log_event)

    iteration = ActionIteration(iteration_index=1)
    audit = _sample_audit()
    record_index_usage(iteration, audit)

    assert captured["event_name"] == "ui_index_usage"
    fields = captured["fields"]
    # The two write paths (iteration field + structured log) MUST reflect
    # the exact same audit content — no path can diverge from the other.
    assert fields["outcome"] == iteration.ui_index_audit.outcome
    assert fields["bundle_id"] == iteration.ui_index_audit.bundle_id
    assert fields["schema_version"] == iteration.ui_index_audit.schema_version
    assert fields["matched_screen_id"] == iteration.ui_index_audit.matched_screen_id
    assert fields["hint_element_ids"] == iteration.ui_index_audit.hint_element_ids
    assert (
        fields["candidate_transition_ids"] == iteration.ui_index_audit.candidate_transition_ids
    )
    assert fields["no_match_reason"] == iteration.ui_index_audit.no_match_reason
    assert fields["grounder_outcome"] == iteration.ui_index_audit.grounder_outcome


def test_record_index_usage_not_configured_outcome_is_independently_readable():
    iteration = ActionIteration(iteration_index=0)
    audit = IndexUsageAuditRecord(outcome="not_configured")
    record_index_usage(iteration, audit)

    assert iteration.ui_index_audit.outcome == "not_configured"
    assert iteration.ui_index_audit.matched_screen_id is None
    assert iteration.ui_index_audit.hint_element_ids == []
    assert iteration.ui_index_audit.candidate_transition_ids == []
    assert iteration.ui_index_audit.no_match_reason is None
    assert iteration.ui_index_audit.grounder_outcome == "not_attempted"


def test_record_index_usage_never_writes_log_without_iteration_field(monkeypatch):
    """Contract: the two writes are two necessary results of one call —
    there is no code path that logs without also setting the field."""
    calls = {"log": 0}

    import vnc_agent.ui_index.audit as audit_mod

    def fake_log_event(event_name, **fields):
        calls["log"] += 1

    monkeypatch.setattr(audit_mod, "log_event", fake_log_event)

    iteration = ActionIteration(iteration_index=0)
    record_index_usage(iteration, IndexUsageAuditRecord(outcome="no_match"))

    assert calls["log"] == 1
    assert iteration.ui_index_audit is not None
