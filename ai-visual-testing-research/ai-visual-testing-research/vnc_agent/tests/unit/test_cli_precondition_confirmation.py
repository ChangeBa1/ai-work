"""CLI declarative precondition-confirmation contract tests (Feature 003 T019).

Replaces the old test_cli_start_state_confirmation.py (fixed
--confirmed-cart-items/--confirmed-cart-amount flags) with the generic
--confirm-precondition key=value mechanism (FR-024).
"""

from pathlib import Path

from typer.testing import CliRunner

from vnc_agent.api import cli
from vnc_agent.runtime.run_context import RunContext

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[2]
FIXTURE_CASE = ROOT / "tests" / "fixtures" / "testcases" / "generic-precondition-example.yaml"


def test_confirm_precondition_flags_populate_run_context(monkeypatch, tmp_path: Path) -> None:
    screenshot = tmp_path / "start.png"
    screenshot.write_bytes(b"fixed")
    captured = {}

    async def fake_execute(case, cfg, *, json_only=False, human_confirmed_facts=None):
        captured["human_confirmed_facts"] = human_confirmed_facts
        captured["ctx"] = RunContext(case, human_confirmed_facts=human_confirmed_facts)
        return cli.EXIT_PASSED

    monkeypatch.setattr(cli, "_execute", fake_execute)
    monkeypatch.setattr(cli, "load_config", lambda _path: object())
    result = runner.invoke(
        cli.app,
        [
            "run",
            str(FIXTURE_CASE),
            "--confirm-precondition",
            "cart_item_count=0",
            "--confirm-precondition",
            "cart_amount=0",
            "--confirm-screenshot",
            str(screenshot),
        ],
    )
    assert result.exit_code == 0, result.output
    facts = captured["ctx"].test_run.human_confirmed_facts
    by_key = {f.key: f.confirmed_value for f in facts}
    assert by_key == {"cart_item_count": "0", "cart_amount": "0"}
    assert all(f.screenshot_ref == str(screenshot) for f in facts)


def test_omitted_confirmation_leaves_empty_list(monkeypatch) -> None:
    captured = {}

    async def fake_execute(case, cfg, *, json_only=False, human_confirmed_facts=None):
        captured["human_confirmed_facts"] = human_confirmed_facts
        return cli.EXIT_PASSED

    monkeypatch.setattr(cli, "_execute", fake_execute)
    monkeypatch.setattr(cli, "load_config", lambda _path: object())
    result = runner.invoke(
        cli.app,
        ["run", str(FIXTURE_CASE)],
    )
    assert result.exit_code == 0, result.output
    assert captured["human_confirmed_facts"] == []


def test_confirm_precondition_key_not_declared_fails_before_execute(monkeypatch) -> None:
    called = False

    async def fake_execute(*_args, **_kwargs):
        nonlocal called
        called = True
        return cli.EXIT_PASSED

    monkeypatch.setattr(cli, "_execute", fake_execute)
    result = runner.invoke(
        cli.app,
        [
            "run",
            str(FIXTURE_CASE),
            "--confirm-precondition",
            "not_a_declared_key=0",
        ],
    )
    assert result.exit_code == cli.EXIT_VALIDATION
    assert called is False


def test_confirm_precondition_malformed_pair_fails_before_execute(monkeypatch) -> None:
    called = False

    async def fake_execute(*_args, **_kwargs):
        nonlocal called
        called = True
        return cli.EXIT_PASSED

    monkeypatch.setattr(cli, "_execute", fake_execute)
    result = runner.invoke(
        cli.app,
        [
            "run",
            str(FIXTURE_CASE),
            "--confirm-precondition",
            "no_equals_sign_here",
        ],
    )
    assert result.exit_code == cli.EXIT_VALIDATION
    assert called is False
