"""Phase 6 (T052): JSON backward compatibility
(report-contract.md "Backward compatibility rule", "Compatibility tests").

Non-path fields/keys/types/enums/null-vs-default/array-order/status
aggregation are byte-for-byte unchanged from features 001-003.
`before_frame_path`/`after_frame_path` are validated separately: type/null,
readability, safe purpose, before/after association, and (when resolvable)
physical-identity/content-hash equivalence — never the literal old
`report_frames` text value.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.support.legacy_report_consumer import legacy_business_result
from vnc_agent.domain.run import ActionIteration, StepRecord, TestRun
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.perception.screenshot import FrameCaptureService
from vnc_agent.reporting.json_report import build_report_dict
from vnc_agent.reporting.report_builder import ReportBuilder
from vnc_agent.storage.artifact_store import ArtifactStore

FIXTURES = Path(__file__).resolve().parent / "images" / "frame_dedup"
MANIFEST = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))

# The exact top-level key set produced by features 001-003 — must remain a
# subset of the new output (additive only).
_LEGACY_TOP_LEVEL_KEYS = {
    "run_id", "test_case_id", "status", "started_at", "ended_at",
    "precondition_evaluation", "human_confirmed_facts", "executed_action_log",
    "declared_tag_counts", "steps",
}
_LEGACY_ITERATION_KEYS = {
    "iteration_index", "before_frame_path", "after_frame_path", "semantic_action",
    "grounding_candidates", "selected_candidate", "executable_action",
    "execution_result", "wait_result", "verification_result", "action_effect",
    "repeat_guard_decision", "canonical_action_identity", "coordinate_space_audit",
    "recovery_attempts", "ui_index_audit", "planner_skipped_reason",
    # Feature 015 (FR-010): additive memory direct-click marker.
    "memory_hit",
    # Feature 016 (FR-012): additive replay-attempt marker.
    "replay_audit",
    # Feature 022 (FR-B04): additive wrong-click evidence + upgraded
    # failure attribution.
    "wrong_target_evidence",
    "failure_attribution",
}
_LEGACY_STEP_KEYS = {
    "step_id", "status", "iterations", "model_names", "raw_model_response_refs",
    "stage_durations_ms", "failure_reason", "weak_assertion_warning", "basis",
    "verification_label",
}


class SequenceDriver:
    def __init__(self, names: list[str]):
        self._bytes = [(FIXTURES / MANIFEST[n]["file"]).read_bytes() for n in names]
        self._i = 0
        meta = MANIFEST[names[0]]
        self._resolution = (meta["width"], meta["height"])

    @property
    def resolution(self):
        return self._resolution

    async def capture_screen(self) -> bytes:
        data = self._bytes[min(self._i, len(self._bytes) - 1)]
        self._i += 1
        return data

    async def capture_region(self, x, y, w, h) -> bytes:
        return await self.capture_screen()


def _bare_run() -> TestRun:
    run = TestRun(
        run_id="compat-r1", test_case_id="compat-tc", status="passed",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        ended_at=datetime(2026, 1, 1, 0, 0, 5, tzinfo=UTC),
    )
    step = StepRecord(step_id="s1", final_status="passed")
    step.iterations.append(
        ActionIteration(iteration_index=0, verification_result=VerificationResult(status="passed"))
    )
    run.steps.append(step)
    return run


def test_top_level_keys_are_superset_of_legacy_and_additive_only(tmp_path: Path):
    run = _bare_run()
    data = build_report_dict(run)
    assert _LEGACY_TOP_LEVEL_KEYS.issubset(data.keys())
    new_keys = set(data.keys()) - _LEGACY_TOP_LEVEL_KEYS
    assert new_keys == {
        "frames", "stage_measurements", "performance_summary",
        "display_status", "localized_message",
    }


def test_step_and_iteration_keys_unchanged(tmp_path: Path):
    run = _bare_run()
    data = build_report_dict(run)
    step = data["steps"][0]
    assert _LEGACY_STEP_KEYS.issubset(step.keys())
    iteration = step["iterations"][0]
    assert set(iteration.keys()) == _LEGACY_ITERATION_KEYS


def test_null_and_default_semantics_preserved_for_missing_evidence(tmp_path: Path):
    """No frame was ever captured for this iteration — before/after paths
    are null exactly like the old "no observation happened" semantics."""
    run = _bare_run()
    data = build_report_dict(run)
    it = data["steps"][0]["iterations"][0]
    assert it["before_frame_path"] is None
    assert it["after_frame_path"] is None
    assert it["selected_candidate"] is None
    assert it["grounding_candidates"] == []
    assert it["coordinate_space_audit"] == []
    assert it["recovery_attempts"] == []


def test_status_aggregation_rules_unchanged():
    from vnc_agent.reporting.json_report import build_report_dict as build

    run = _bare_run()
    run.status = "not_a_valid_status"  # type: ignore[assignment]
    data = build(run)
    assert data["status"] == "failed"  # unrecognized -> failed, same as before

    run.steps[0].final_status = "pending"  # type: ignore[assignment]
    data2 = build(run)
    assert data2["steps"][0]["status"] == "failed"  # pending/running -> failed


@pytest.mark.asyncio
async def test_valid_before_after_paths_resolve_to_safe_physical_identity(tmp_path: Path):
    test_run = TestRun(run_id="compat-r2", test_case_id="compat-tc", status="passed")
    store = ArtifactStore(tmp_path)
    svc = FrameCaptureService(
        SequenceDriver(["baseline_full", "baseline_full"]),
        run_id="compat-r2", vnc_session_id="s1", test_run=test_run, artifact_store=store,
    )
    o1 = await svc.capture(step_id="s1", capture_source="observation")
    o2 = await svc.capture(step_id="s1", capture_source="post_action_verification")
    step = StepRecord(step_id="s1", final_status="passed")
    step.iterations.append(
        ActionIteration(
            iteration_index=0,
            before_frame_id=o1.frame.image_path,
            after_frame_id=o2.frame.image_path,
            verification_result=VerificationResult(status="passed"),
        )
    )
    test_run.steps.append(step)

    from vnc_agent.reporting.safe_evidence import SafeEvidenceResolver

    resolver = SafeEvidenceResolver(store)
    data = build_report_dict(test_run, safe_evidence_resolver=resolver)
    it = data["steps"][0]["iterations"][0]
    assert it["before_frame_path"] is not None
    assert it["after_frame_path"] is not None
    assert Path(it["before_frame_path"]).is_file()
    # before/after are an exact duplicate pair -> same physical identity
    assert it["before_frame_path"] == it["after_frame_path"]
    # no report_frames copy was ever created
    assert not (tmp_path / "runs" / "compat-r2" / "report_frames").exists()


def test_representative_legacy_consumer_reads_new_report_successfully(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    run = _bare_run()
    ReportBuilder(store).build(run, formats=("json",))
    raw = json.loads(Path(run.report_json_path).read_text(encoding="utf-8"))
    result = legacy_business_result(raw)
    assert result["run_id"] == "compat-r1"
    assert result["status"] == "passed"
    assert result["passed_steps"] == ["s1"]
    assert result["failed_steps"] == []
    assert result["weak_assertion_steps"] == []


def test_json_ensure_ascii_false_and_utf8_encoding(tmp_path: Path):
    store = ArtifactStore(tmp_path)
    run = _bare_run()
    run.test_case_id = "中文用例名称"
    ReportBuilder(store).build(run, formats=("json",))
    raw_text = Path(run.report_json_path).read_text(encoding="utf-8")
    assert "中文用例名称" in raw_text  # not \uXXXX-escaped
    assert "\\u4e2d\\u6587" not in raw_text


_LEGACY_PROJECTION_PATH = (
    Path(__file__).resolve().parent / ".." / "snapshots" / "report_legacy_projection.json"
).resolve()


_ADDITIVE_KEYS = {
    "frames", "stage_measurements", "performance_summary",
    "display_status", "localized_message",
}


def _project_legacy_non_path_fields(data: dict) -> dict:
    """Recursive projection dropping only the feature-004 additive
    top-level keys and the two path fields (validated separately) —
    everything else must compare byte-for-byte across regenerations."""
    projected = {k: v for k, v in data.items() if k not in _ADDITIVE_KEYS}
    for step in projected.get("steps", []):
        for it in step.get("iterations", []):
            it.pop("before_frame_path", None)
            it.pop("after_frame_path", None)
    return projected


def test_legacy_non_path_projection_golden_snapshot(tmp_path: Path):
    run = _bare_run()
    data = build_report_dict(run)
    projected = _project_legacy_non_path_fields(data)

    if not _LEGACY_PROJECTION_PATH.exists():
        _LEGACY_PROJECTION_PATH.write_text(
            json.dumps(projected, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        pytest.skip("golden legacy projection did not exist — created it for review")

    golden = json.loads(_LEGACY_PROJECTION_PATH.read_text(encoding="utf-8"))
    assert json.dumps(projected, sort_keys=True) == json.dumps(golden, sort_keys=True)
