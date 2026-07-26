"""US7: Compound assertion uncertain contagion (FR-033).

Feature 011: weak-negative evidence classification + arbitration threshold
config unit coverage (aggregate_conditions semantics stay untouched — the 011
arbitration is a policy layer above aggregation).
"""

import pytest
from pydantic import ValidationError

from vnc_agent.config import AgentConfig, VerificationConfig
from vnc_agent.domain.verification import (
    VerificationCondition,
    VerificationResult,
    VerificationSpec,
    aggregate_conditions,
)
from vnc_agent.verification.business_resolver import (
    WEAK_NEGATIVE_TYPES,
    _failed_deterministic_all_weak_negative,
)


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


# ---------------------------------------------------------------------------
# Feature 011 — evidence-strength classification (FR-001)
# ---------------------------------------------------------------------------


def _spec(*conds: VerificationCondition) -> VerificationSpec:
    return VerificationSpec(operator="all", conditions=list(conds))


def _result(failed: list[str]) -> VerificationResult:
    return VerificationResult(status="failed", failed_conditions=failed)


def test_weak_negative_types_is_ocr_miss_only():
    assert WEAK_NEGATIVE_TYPES == frozenset({"text_appears"})


def test_all_failed_weak_negative_true_for_text_appears_only():
    spec = _spec(
        VerificationCondition(type="text_appears", value="A"),
        VerificationCondition(type="text_appears", value="B"),
        VerificationCondition(type="visual_question", value="q?"),
    )
    result = _result(["text_appears:A", "text_appears:B"])
    assert _failed_deterministic_all_weak_negative(spec, result) is True


def test_strong_negative_text_disappears_blocks_classification():
    spec = _spec(
        VerificationCondition(type="text_appears", value="A"),
        VerificationCondition(type="text_disappears", value="ERR"),
        VerificationCondition(type="visual_question", value="q?"),
    )
    result = _result(["text_appears:A", "text_disappears:ERR"])
    assert _failed_deterministic_all_weak_negative(spec, result) is False


def test_strong_negative_template_blocks_classification():
    spec = _spec(
        VerificationCondition(type="template_appears", value="marker"),
        VerificationCondition(type="visual_question", value="q?"),
    )
    result = _result(["template_appears:marker"])
    assert _failed_deterministic_all_weak_negative(spec, result) is False


def test_no_deterministic_failure_is_not_weak_negative_only():
    spec = _spec(
        VerificationCondition(type="text_appears", value="A"),
        VerificationCondition(type="visual_question", value="q?"),
    )
    result = VerificationResult(status="passed", failed_conditions=[])
    assert _failed_deterministic_all_weak_negative(spec, result) is False


# ---------------------------------------------------------------------------
# Feature 011 — arbitration threshold config (FR-007)
# ---------------------------------------------------------------------------


def test_verification_config_default_threshold():
    assert VerificationConfig().visual_override_confidence_threshold == 0.8
    assert AgentConfig().verification.visual_override_confidence_threshold == 0.8


def test_verification_config_yaml_value_loads():
    cfg = AgentConfig.model_validate(
        {"verification": {"visual_override_confidence_threshold": 0.9}}
    )
    assert cfg.verification.visual_override_confidence_threshold == 0.9


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_verification_config_threshold_bounds(bad):
    with pytest.raises(ValidationError):
        VerificationConfig(visual_override_confidence_threshold=bad)
