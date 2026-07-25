"""T032: `vnc-agent ui-index query` CLI subcommand
(contracts/ui-index-consumer-interfaces.md §8)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vnc_agent.api.cli import app

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ui_index"
FORM_INPUT = FIXTURES / "fixture_form_input"
ICON_OVERLAY = FIXTURES / "fixture_icon_overlay"
INVALID = FIXTURES / "invalid"
runner = CliRunner()


def _invoke(*args: str):
    return runner.invoke(app, ["ui-index", "query", *args])


def test_cli_query_by_screen_json():
    result = _invoke("--bundle-dir", str(FORM_INPUT), "--screen", "screen.form_edit", "--json")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["screen_id"] == "screen.form_edit"


def test_cli_query_by_screen_miss_human_output_says_no_match():
    result = _invoke("--bundle-dir", str(FORM_INPUT), "--screen", "screen.does_not_exist")
    assert result.exit_code == 0
    assert "no match" in result.output


def test_cli_query_by_text_json():
    result = _invoke("--bundle-dir", str(FORM_INPUT), "--text", "Submit", "--json")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert any(el["element_id"] == "el.form.submit_btn" for el in data)


def test_cli_query_by_alias_json():
    result = _invoke("--bundle-dir", str(ICON_OVERLAY), "--alias", "help", "--json")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert [el["element_id"] for el in data] == ["el.ws.help_icon"]


def test_cli_query_by_role_json_returns_nonempty_list():
    result = _invoke("--bundle-dir", str(FORM_INPUT), "--role", "button", "--json")
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert isinstance(data, list) and data


def test_cli_query_by_role_miss_human_output_says_no_match():
    result = _invoke("--bundle-dir", str(FORM_INPUT), "--role", "no_such_role")
    assert result.exit_code == 0
    assert "no match" in result.output


def test_cli_query_transitions_by_from_screen_json():
    result = _invoke(
        "--bundle-dir", str(FORM_INPUT), "--transition-from", "screen.form_edit", "--json"
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert [t["transition_id"] for t in data] == ["tr.form.submit"]


def test_cli_query_transitions_combined_filters_json():
    result = _invoke(
        "--bundle-dir",
        str(FORM_INPUT),
        "--transition-from",
        "screen.form_edit",
        "--transition-trigger",
        "el.form.submit_btn",
        "--transition-to",
        "screen.form_done",
        "--json",
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert [t["transition_id"] for t in data] == ["tr.form.submit"]


def test_cli_query_requires_at_least_one_dimension():
    result = _invoke("--bundle-dir", str(FORM_INPUT))
    assert result.exit_code == 2


def test_cli_query_on_invalid_bundle_reports_validation_error_not_crash():
    result = _invoke(
        "--bundle-dir", str(INVALID / "duplicate_id"), "--screen", "screen.home", "--json"
    )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["issues"]


def test_cli_query_never_writes_to_bundle_dir(tmp_path: Path):
    import shutil

    bundle_dir = tmp_path / "bundle"
    shutil.copytree(FORM_INPUT, bundle_dir)
    before = {p: p.stat().st_mtime for p in bundle_dir.rglob("*") if p.is_file()}

    result = _invoke("--bundle-dir", str(bundle_dir), "--role", "button")
    assert result.exit_code == 0

    after = {p: p.stat().st_mtime for p in bundle_dir.rglob("*") if p.is_file()}
    assert before == after
