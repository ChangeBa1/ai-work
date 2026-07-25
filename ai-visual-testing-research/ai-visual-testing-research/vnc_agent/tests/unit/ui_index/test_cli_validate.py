"""T025: `vnc-agent ui-index validate` CLI subcommand
(contracts/ui-index-consumer-interfaces.md §8)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vnc_agent.api.cli import app
from vnc_agent.ui_index.errors import UiIndexErrorCode

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ui_index"
VALID_MINIMAL = FIXTURES / "valid_minimal"
FORM_INPUT = FIXTURES / "fixture_form_input"
INVALID = FIXTURES / "invalid"
runner = CliRunner()


def test_cli_validate_ok_exit_code_zero():
    result = runner.invoke(app, ["ui-index", "validate", str(VALID_MINIMAL)])
    assert result.exit_code == 0, result.output


def test_cli_validate_ok_human_output_mentions_ok():
    result = runner.invoke(app, ["ui-index", "validate", str(FORM_INPUT)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_cli_validate_ok_json_output_is_valid_report_with_no_issues():
    result = runner.invoke(app, ["ui-index", "validate", str(VALID_MINIMAL), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["ok"] is True
    assert data["issues"] == []


def test_cli_validate_invalid_exit_code_one():
    result = runner.invoke(app, ["ui-index", "validate", str(INVALID / "duplicate_id")])
    assert result.exit_code == 1, result.output


def test_cli_validate_invalid_json_output_contains_error_codes():
    result = runner.invoke(
        app,
        ["ui-index", "validate", str(INVALID / "duplicate_id"), "--json"],
    )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["issues"]
    codes = {issue["error_code"] for issue in data["issues"]}
    assert UiIndexErrorCode.DUPLICATE_ID.value in codes


def test_cli_validate_invalid_human_output_lists_each_issue():
    result = runner.invoke(app, ["ui-index", "validate", str(INVALID / "missing_file")])
    assert result.exit_code == 1
    assert "FAILED" in result.output
    assert UiIndexErrorCode.CONTENT_FILE_MISSING.value in result.output


def test_cli_validate_missing_bundle_dir_reports_error_not_crash():
    result = runner.invoke(app, ["ui-index", "validate", str(FIXTURES / "does_not_exist_dir")])
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_cli_validate_missing_bundle_dir_json_reports_bundle_dir_not_found():
    result = runner.invoke(
        app,
        ["ui-index", "validate", str(FIXTURES / "does_not_exist_dir"), "--json"],
    )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    codes = {issue["error_code"] for issue in data["issues"]}
    assert UiIndexErrorCode.BUNDLE_DIR_NOT_FOUND.value in codes


def test_cli_validate_never_writes_to_bundle_dir(tmp_path: Path):
    """Contract: validate is read-only over bundle_dir."""
    import shutil

    bundle_dir = tmp_path / "bundle"
    shutil.copytree(VALID_MINIMAL, bundle_dir)
    before = {p: p.stat().st_mtime for p in bundle_dir.rglob("*") if p.is_file()}

    result = runner.invoke(app, ["ui-index", "validate", str(bundle_dir)])
    assert result.exit_code == 0

    after = {p: p.stat().st_mtime for p in bundle_dir.rglob("*") if p.is_file()}
    assert before == after


def test_cli_validate_is_mounted_under_ui_index_subcommand():
    result = runner.invoke(app, ["ui-index", "--help"])
    assert result.exit_code == 0
    assert "validate" in result.output
    assert "query" in result.output
