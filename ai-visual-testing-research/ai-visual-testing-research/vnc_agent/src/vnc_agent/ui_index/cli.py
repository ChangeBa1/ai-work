"""`vnc-agent ui-index validate|query` (contracts §8).

Both subcommands are read-only — neither ever writes to `bundle_dir`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from vnc_agent.config import UiIndexConfig
from vnc_agent.ui_index import query as query_mod
from vnc_agent.ui_index.errors import ValidationReport
from vnc_agent.ui_index.repository import UiIndexBundle, UiIndexValidationError
from vnc_agent.ui_index.validator import validate_bundle

ui_index_app = typer.Typer(
    name="ui-index", help="Read/validate/query external UI-analysis bundles", no_args_is_help=True
)


def _echo_report_human(report: ValidationReport) -> None:
    if report.ok:
        typer.echo(f"OK: bundle {report.bundle_dir!r} passed validation (0 issues)")
        return
    typer.echo(f"FAILED: bundle {report.bundle_dir!r} has {len(report.issues)} issue(s):")
    for issue in report.issues:
        typer.echo(
            f"  [{issue.error_code.value}] file={issue.file} line={issue.line} "
            f"field_path={issue.field_path}: {issue.message}"
        )


@ui_index_app.command("validate")
def validate_cmd(
    bundle_dir: Path = typer.Argument(..., help="Path to the bundle directory"),  # noqa: B008
    json_output: bool = typer.Option(False, "--json", help="Emit ValidationReport as JSON"),
) -> None:
    """Run the full FR-002 validation over `bundle_dir`."""
    report = validate_bundle(bundle_dir, UiIndexConfig())
    if json_output:
        typer.echo(report.model_dump_json())
    else:
        _echo_report_human(report)
    raise typer.Exit(0 if report.ok else 1)


def _dump(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, list):
        return json.dumps([item.model_dump(mode="json") for item in value], ensure_ascii=False)
    return value.model_dump_json()


@ui_index_app.command("query")
def query_cmd(
    bundle_dir: Path = typer.Option(  # noqa: B008
        ..., "--bundle-dir", help="Path to a bundle directory that already passes validation"
    ),
    screen: str | None = typer.Option(None, "--screen", help="Query by screen_id"),
    text: str | None = typer.Option(None, "--text", help="Query elements by visible text"),
    alias: str | None = typer.Option(None, "--alias", help="Query elements by alias"),
    role: str | None = typer.Option(None, "--role", help="Query elements by role"),
    transition_from: str | None = typer.Option(
        None, "--transition-from", help="Query transitions by from_screen_id"
    ),
    transition_trigger: str | None = typer.Option(
        None, "--transition-trigger", help="Query transitions by trigger_element_id"
    ),
    transition_to: str | None = typer.Option(
        None, "--transition-to", help="Query transitions by to_screen_id"
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit result as JSON"),
) -> None:
    """Query a validated bundle along exactly one dimension."""
    has_transition_dim = any((transition_from, transition_trigger, transition_to))
    provided = [screen, text, alias, role]
    if not any(v is not None for v in provided) and not has_transition_dim:
        typer.echo(
            "at least one of --screen/--text/--alias/--role/"
            "--transition-from/--transition-trigger/--transition-to is required",
            err=True,
        )
        raise typer.Exit(2)

    try:
        bundle = UiIndexBundle.load(bundle_dir, UiIndexConfig())
    except UiIndexValidationError as exc:
        if json_output:
            typer.echo(exc.report.model_dump_json())
        else:
            _echo_report_human(exc.report)
        raise typer.Exit(1) from exc

    result: Any
    if screen is not None:
        result = query_mod.query_screen(bundle, screen)
    elif text is not None:
        result = query_mod.query_by_text(bundle, text)
    elif alias is not None:
        result = query_mod.query_by_alias(bundle, alias)
    elif role is not None:
        result = query_mod.query_by_role(bundle, role)
    else:
        result = query_mod.query_transitions(
            bundle,
            from_screen_id=transition_from,
            trigger_element_id=transition_trigger,
            to_screen_id=transition_to,
        )

    if json_output:
        typer.echo(_dump(result))
    elif result is None:
        typer.echo("no match")
    elif isinstance(result, list):
        if not result:
            typer.echo("no match")
        for item in result:
            typer.echo(item.model_dump_json())
    else:
        typer.echo(result.model_dump_json())
