"""Feature 021 integration tests: end-to-end `vnc-agent evolution export`
over a seeded temporary SQLite store (spec SC-002/SC-004, US1/US2)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import yaml
from typer.testing import CliRunner

from vnc_agent.api.cli import app
from vnc_agent.domain.action import (
    ExecutableAction,
    ExecutionResult,
    SemanticAction,
    TargetDescription,
)
from vnc_agent.domain.grounding import GroundingCandidate, GroundingResult
from vnc_agent.domain.observation import Region
from vnc_agent.domain.recovery import FailureType, RecoveryAttempt
from vnc_agent.domain.run import ActionIteration, StepRecord, TestRun
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.storage.database import init_db, make_engine, make_session_factory
from vnc_agent.storage.repositories import RunRepository

runner = CliRunner()

TABLES = (
    "test_runs",
    "step_records",
    "action_iterations",
    "recovery_attempts",
    "visual_experiences",
)


def _write_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "agent.yaml").write_text(
        yaml.safe_dump(
            {
                "artifacts": {
                    "db_path": (tmp_path / "data.db").as_posix(),
                    "root_dir": (tmp_path / "artifacts").as_posix(),
                }
            }
        ),
        encoding="utf-8",
    )
    return config_dir


def _iteration(
    *,
    index: int,
    confidence: float,
    bbox: tuple[int, int, int, int],
    passed: bool,
    click_point: tuple[int, int],
    target_region: tuple[int, int, int, int] | None = None,
    recovery: list[RecoveryAttempt] | None = None,
) -> ActionIteration:
    now = datetime.now(UTC)
    return ActionIteration(
        iteration_index=index,
        before_frame_id=f"f{index}",
        semantic_action=SemanticAction(
            action_id=f"a{index}",
            intent="click checkout",
            action_type="click",
            target=TargetDescription(
                text="会計", description="checkout button", nearby_texts=["小計"]
            ),
        ),
        grounding_result=GroundingResult(
            found=True,
            candidates=[GroundingCandidate(bbox=bbox, confidence=confidence)],
        ),
        executable_action=ExecutableAction(
            method="mouse", operation="click", coordinates=click_point
        ),
        execution_result=ExecutionResult(
            success=True,
            started_at=now,
            ended_at=now,
            actual_click_point=click_point,
            target_region=(
                Region(
                    x1=target_region[0],
                    y1=target_region[1],
                    x2=target_region[2],
                    y2=target_region[3],
                )
                if target_region
                else None
            ),
        ),
        verification_result=VerificationResult(
            status="passed" if passed else "failed",
            reason="ok" if passed else "no change",
        ),
        recovery_attempts=recovery or [],
    )


async def _seed(db_path: Path) -> None:
    engine = make_engine(str(db_path))
    await init_db(engine)
    repo = RunRepository(make_session_factory(engine))

    # Run A (recent): s1 = hard case that finally passed; s2 = clean pass.
    run_a = TestRun(
        run_id="run-a",
        test_case_id="tc-hard",
        status="passed",
        started_at=datetime(2026, 7, 10, tzinfo=UTC),
    )
    await repo.save_run(run_a)
    s1 = StepRecord(
        step_id="s1",
        final_status="passed",
        iterations=[
            _iteration(
                index=0,
                confidence=0.4,
                bbox=(90, 40, 110, 60),
                passed=False,
                click_point=(100, 50),
                recovery=[
                    RecoveryAttempt(
                        failure_type=FailureType.GROUNDING_LOW_CONFIDENCE,
                        strategy="second_candidate",
                        attempt_index=0,
                        max_retries=2,
                        resolved=True,
                    )
                ],
            ),
            _iteration(
                index=1,
                confidence=0.9,
                bbox=(150, 85, 170, 95),
                passed=True,
                click_point=(160, 90),
                target_region=(150, 85, 170, 95),
            ),
        ],
    )
    await repo.save_step("run-a", s1)
    s2 = StepRecord(
        step_id="s2",
        final_status="passed",
        iterations=[
            _iteration(
                index=0,
                confidence=0.95,
                bbox=(10, 10, 30, 30),
                passed=True,
                click_point=(20, 20),
            )
        ],
    )
    await repo.save_step("run-a", s2)

    # Run B (old): failed step with an unexpected dialog on the way.
    run_b = TestRun(
        run_id="run-b",
        test_case_id="tc-old",
        status="failed",
        started_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    await repo.save_run(run_b)
    s1b = StepRecord(
        step_id="s1",
        final_status="failed",
        failure_reason="no change",
        iterations=[
            _iteration(
                index=0,
                confidence=0.3,
                bbox=(5, 5, 25, 25),
                passed=False,
                click_point=(15, 15),
                recovery=[
                    RecoveryAttempt(
                        failure_type=FailureType.UNEXPECTED_DIALOG,
                        strategy="press_escape",
                        attempt_index=0,
                        max_retries=2,
                    )
                ],
            )
        ],
    )
    await repo.save_step("run-b", s1b)
    await engine.dispose()


def _table_counts(db_path: Path) -> dict[str, int]:
    con = sqlite3.connect(db_path)
    try:
        return {
            t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES
        }
    finally:
        con.close()


def _export(config_dir: Path, out: Path, *extra: str):
    return runner.invoke(
        app,
        ["evolution", "export", "--out", str(out), "--config", str(config_dir), *extra],
    )


def test_end_to_end_export_labels_and_summary(tmp_path: Path):
    config_dir = _write_config(tmp_path)
    asyncio.run(_seed(tmp_path / "data.db"))
    out = tmp_path / "dataset.jsonl"

    before = _table_counts(tmp_path / "data.db")
    result = _export(config_dir, out)
    assert result.exit_code == 0, result.output
    after = _table_counts(tmp_path / "data.db")
    assert before == after  # SC-004: export is read-only

    rows = [json.loads(line) for line in out.read_text("utf-8").splitlines()]
    assert len(rows) == 2
    by_key = {(r["run_id"], r["step_id"]): r for r in rows}
    assert set(by_key) == {("run-a", "s1"), ("run-b", "s1")}

    hard = by_key[("run-a", "s1")]
    assert hard["schema_version"] == "hard-case-v1"
    assert set(hard["criteria"]) == {
        "low_grounding_confidence",
        "mouse_verification_failed",
        "retry_then_success",
        "top2_promotion_success",
    }
    assert hard["test_case_id"] == "tc-hard"
    assert hard["correct_bbox"] == [150, 85, 170, 95]
    assert hard["wrong_candidates"] == [
        {
            "iteration_index": 0,
            "click_point": [100, 50],
            "candidates": [{"bbox": [90, 40, 110, 60], "confidence": 0.4}],
        }
    ]
    assert hard["target"]["text"] == "会計"
    assert hard["final_status"] == "passed"
    assert hard["iteration_count"] == 2
    assert hard["failure_types"] == ["grounding_low_confidence"]

    old = by_key[("run-b", "s1")]
    assert set(old["criteria"]) == {
        "low_grounding_confidence",
        "mouse_verification_failed",
        "failure_type_hit",
    }
    assert old["correct_bbox"] is None
    assert old["verification"]["status"] == "failed"

    summary = json.loads(result.stdout)
    assert summary["total_runs_scanned"] == 2
    assert summary["total_steps_scanned"] == 3
    assert summary["exported_samples"] == 2
    assert summary["criteria_counts"]["low_grounding_confidence"] == 2
    assert summary["criteria_counts"]["retry_then_success"] == 1
    assert summary["criteria_counts"]["top2_promotion_success"] == 1
    assert summary["criteria_counts"]["failure_type_hit"] == 1
    assert summary["criteria_counts"]["zoom_reground_used"] == 0
    assert summary["output"] == str(out)


def test_since_filter_limits_to_recent_runs(tmp_path: Path):
    config_dir = _write_config(tmp_path)
    asyncio.run(_seed(tmp_path / "data.db"))
    out = tmp_path / "recent.jsonl"

    result = _export(config_dir, out, "--since", "2026-07-01")
    assert result.exit_code == 0, result.output
    rows = [json.loads(line) for line in out.read_text("utf-8").splitlines()]
    assert [r["run_id"] for r in rows] == ["run-a"]
    summary = json.loads(result.stdout)
    assert summary["total_runs_scanned"] == 1
    assert summary["exported_samples"] == 1


def test_criteria_filter_selects_matching_samples_only(tmp_path: Path):
    config_dir = _write_config(tmp_path)
    asyncio.run(_seed(tmp_path / "data.db"))
    out = tmp_path / "filtered.jsonl"

    result = _export(config_dir, out, "--criteria", "top2_promotion_success")
    assert result.exit_code == 0, result.output
    rows = [json.loads(line) for line in out.read_text("utf-8").splitlines()]
    assert [(r["run_id"], r["step_id"]) for r in rows] == [("run-a", "s1")]
    # The full label list stays on the row even under a filter.
    assert "low_grounding_confidence" in rows[0]["criteria"]


def test_unknown_criterion_exits_2(tmp_path: Path):
    config_dir = _write_config(tmp_path)
    asyncio.run(_seed(tmp_path / "data.db"))
    result = _export(config_dir, tmp_path / "x.jsonl", "--criteria", "not_a_criterion")
    assert result.exit_code == 2


def test_bad_since_exits_2(tmp_path: Path):
    config_dir = _write_config(tmp_path)
    asyncio.run(_seed(tmp_path / "data.db"))
    result = _export(config_dir, tmp_path / "x.jsonl", "--since", "yesterday-ish")
    assert result.exit_code == 2


def test_empty_database_exports_zero_samples(tmp_path: Path):
    config_dir = _write_config(tmp_path)
    out = tmp_path / "empty.jsonl"
    result = _export(config_dir, out)
    assert result.exit_code == 0, result.output
    assert out.exists() and out.read_text("utf-8") == ""
    summary = json.loads(result.stdout)
    assert summary["exported_samples"] == 0
    assert summary["total_runs_scanned"] == 0
