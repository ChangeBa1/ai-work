"""T042: Verifier independence from the UI index (FR-008/010/019,
Constitution Principle IV, quickstart.md §2, SC-005).

`VerificationEngine.verify()`'s pass/fail decision must depend only on the
`Transition.expected_visible`/`expected_hidden`/`expected_state_changes`
declarations translated into `VerificationCondition`s and the *actual*
observed `StructuredScreen` — never on whether a ui_index bundle was
consulted, matched, or missed for the action that produced that screen.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path

from vnc_agent.config import UiIndexConfig
from vnc_agent.domain.observation import OCRItem, StructuredScreen
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.ui_index.repository import UiIndexBundle
from vnc_agent.ui_index.runtime_adapter import build_hints
from vnc_agent.verification.engine import VerificationEngine

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ui_index"
FORM_INPUT = FIXTURES / "fixture_form_input"
VERIFICATION_SRC = (
    Path(__file__).resolve().parents[3] / "src" / "vnc_agent" / "verification"
)


def _screen(texts: list[str]) -> StructuredScreen:
    return StructuredScreen(
        frame_id="frame-1",
        resolution=(1000, 1000),
        captured_at=datetime.now(timezone.utc),
        ocr_items=[OCRItem(text=t, bbox=(0, 0, 10, 10), confidence=0.95) for t in texts],
    )


def _spec_from_transition() -> VerificationSpec:
    """Mirrors what a hand-authored testcase would declare for
    tr.form.submit's expected_visible=["Thank You"] /
    expected_hidden=["Contact Form"] — built independently of any
    ui_index/bundle object, using only plain strings."""
    return VerificationSpec(
        operator="all",
        conditions=[
            VerificationCondition(type="text_appears", value="Thank You"),
            VerificationCondition(type="text_disappears", value="Contact Form"),
        ],
    )


def test_verification_package_never_imports_ui_index():
    """Static guarantee: no file under verification/ imports anything from
    vnc_agent.ui_index or references IndexUsageAuditRecord/VisibleElementHint."""
    violations: list[str] = []
    for path in sorted(VERIFICATION_SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(text, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and "ui_index" in node.module:
                violations.append(f"{path.name}: imports {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "ui_index" in alias.name:
                        violations.append(f"{path.name}: imports {alias.name}")
        for banned in ("IndexUsageAuditRecord", "VisibleElementHint", "UiIndexBundle"):
            if banned in text:
                violations.append(f"{path.name}: references {banned}")
    assert not violations, violations


async def test_verify_passes_on_matching_screen_regardless_of_index_lookup():
    engine = VerificationEngine()
    spec = _spec_from_transition()
    screen_after_submit = _screen(["Thank You", "Submission Complete"])

    # Path A: no ui_index bundle involved at all for this run.
    result_without_index = await engine.verify(spec, screen_after_submit)

    # Path B: a bundle WAS consulted earlier for planning this exact step
    # (hits screen.form_edit) — this must have zero bearing on verify().
    bundle = UiIndexBundle.load(FORM_INPUT)
    pre_action_screen = _screen(
        ["Contact Form", "Edit Details", "Form Page", "Name", "Submit"]
    )
    _hints, _candidates, audit = build_hints(bundle, pre_action_screen, UiIndexConfig())
    assert audit.outcome == "hit"  # sanity: the index really was consulted
    result_with_index_consulted = await engine.verify(spec, screen_after_submit)

    assert result_without_index.status == result_with_index_consulted.status == "passed"
    assert result_without_index.matched_conditions == result_with_index_consulted.matched_conditions
    assert result_without_index.failed_conditions == result_with_index_consulted.failed_conditions


async def test_verify_fails_on_screen_still_showing_old_content():
    engine = VerificationEngine()
    spec = _spec_from_transition()
    # Action produced no visible change — expected_hidden text still present,
    # expected_visible text absent.
    stale_screen = _screen(["Contact Form", "Edit Details"])

    result = await engine.verify(spec, stale_screen)
    assert result.status == "failed"
    assert "text_appears:Thank You" in result.failed_conditions
    assert "text_disappears:Contact Form" in result.failed_conditions


async def test_verify_outcome_identical_whether_index_hit_or_no_match():
    """Whether build_hints() for the *preceding* action returns outcome="hit"
    or outcome="no_match" must not change the verify() outcome for the same
    post-action screen and the same declared conditions."""
    engine = VerificationEngine()
    spec = _spec_from_transition()
    post_action_screen = _screen(["Thank You"])

    bundle = UiIndexBundle.load(FORM_INPUT)
    _hints, _candidates, hit_audit = build_hints(
        bundle,
        _screen(["Contact Form", "Edit Details", "Form Page", "Name", "Submit"]),
        UiIndexConfig(),
    )
    assert hit_audit.outcome == "hit"
    result_after_hit = await engine.verify(spec, post_action_screen)

    _hints2, _candidates2, no_match_audit = build_hints(
        bundle, _screen(["totally unrelated content"]), UiIndexConfig()
    )
    assert no_match_audit.outcome == "no_match"
    result_after_no_match = await engine.verify(spec, post_action_screen)

    assert result_after_hit.status == result_after_no_match.status == "passed"
