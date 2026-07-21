"""US7: Compound assertion uncertain contagion (FR-033)."""

from vnc_agent.domain.verification import aggregate_conditions


def test_all_failed_beats_uncertain():
    assert aggregate_conditions("all", ["passed", "failed", "uncertain"]) == "failed"


def test_all_uncertain_propagates():
    assert aggregate_conditions("all", ["passed", "uncertain"]) == "uncertain"


def test_all_passed():
    assert aggregate_conditions("all", ["passed", "passed"]) == "passed"


def test_any_passed_beats_uncertain():
    assert aggregate_conditions("any", ["failed", "passed", "uncertain"]) == "passed"


def test_any_uncertain_propagates():
    assert aggregate_conditions("any", ["failed", "uncertain"]) == "uncertain"


def test_any_all_failed():
    assert aggregate_conditions("any", ["failed", "failed"]) == "failed"
