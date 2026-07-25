"""T043: existing testcase regression — feature 007 must not change
`--dry-run` behavior for pre-existing testcases when no ui_index bundle is
configured (spec.md FR-011, "silent/passthrough when unconfigured")."""

from __future__ import annotations

from pathlib import Path

import pytest
import structlog
from typer.testing import CliRunner

from vnc_agent.api.cli import app
from vnc_agent.domain.testcase import load_test_case

TESTCASES_DIR = Path(__file__).resolve().parents[3] / "testcases"
EXISTING_TESTCASES = [
    "pos-buy-bag-checkout.yaml",
    "pos-click-icon.yaml",
    "pos-hover-probe.yaml",
]
runner = CliRunner()


@pytest.fixture(autouse=True)
def _restore_structlog_after_cli_invoke():
    """`run_cmd()` calls `configure_logging()` unconditionally (even under
    `--dry-run`), which binds structlog's PrintLogger to whatever `sys.stderr`
    is active at that moment. Under `CliRunner.invoke()` that is a
    temporarily-captured stream that gets closed once the invocation
    context exits — leaving structlog pointed at a dead file object for
    every *other* test that runs afterward in the same session. Reset to
    structlog's defaults (which re-reads the live `sys.stderr`) after each
    test here so this file never poisons unrelated tests."""
    yield
    structlog.reset_defaults()


def test_existing_testcase_files_are_present():
    """Sanity: fail loudly (not silently skip) if these fixtures move."""
    for name in EXISTING_TESTCASES:
        assert (TESTCASES_DIR / name).is_file(), name


def test_load_test_case_still_succeeds_for_existing_testcases():
    for name in EXISTING_TESTCASES:
        case = load_test_case(TESTCASES_DIR / name)
        assert case.id
        assert len(case.steps) >= 1


def test_dry_run_still_exits_zero_for_existing_testcases():
    for name in EXISTING_TESTCASES:
        result = runner.invoke(app, ["run", str(TESTCASES_DIR / name), "--dry-run"])
        assert result.exit_code == 0, (name, result.output)
        assert "OK" in result.output


def test_dry_run_reports_correct_step_count_for_existing_testcases():
    for name in EXISTING_TESTCASES:
        case = load_test_case(TESTCASES_DIR / name)
        result = runner.invoke(app, ["run", str(TESTCASES_DIR / name), "--dry-run"])
        assert result.exit_code == 0
        assert str(len(case.steps)) in result.output


def test_dry_run_never_touches_config_or_ui_index(monkeypatch):
    """Contract: `--dry-run` validates the YAML only — it MUST return
    before `load_config()` (and therefore before any ui_index preflight)
    is ever invoked, for every existing testcase."""
    import vnc_agent.api.cli as cli_mod

    called = {"count": 0}

    def _fail_if_called(*args, **kwargs):
        called["count"] += 1
        raise AssertionError("load_config must not be called during --dry-run")

    monkeypatch.setattr(cli_mod, "load_config", _fail_if_called)

    for name in EXISTING_TESTCASES:
        result = runner.invoke(app, ["run", str(TESTCASES_DIR / name), "--dry-run"])
        assert result.exit_code == 0, (name, result.output)
    assert called["count"] == 0
