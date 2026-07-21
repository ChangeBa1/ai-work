"""Typer CLI: run / report (contracts/cli-contract.md)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer

from vnc_agent.config import load_config
from vnc_agent.domain.testcase import FieldValidationError, load_test_case
from vnc_agent.logging_setup import configure_logging, get_logger
from vnc_agent.runtime.exceptions import VNCConnectionError

app = typer.Typer(name="vnc-agent", help="VNC black-box GUI automation agent", no_args_is_help=True)
log = get_logger("cli")

# Exit codes (cli-contract.md)
EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_VALIDATION = 2
EXIT_CANCELLED = 3
EXIT_VNC = 4


def _run_async(coro):
    return asyncio.run(coro)


@app.command("run")
def run_cmd(
    test_case_file: Path = typer.Argument(..., exists=False, help="YAML test case path"),
    target: Optional[str] = typer.Option(None, "--target", help="Override target_id"),
    config: Path = typer.Option(Path("config"), "--config", help="Config directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate only, no VNC"),
    json_only: bool = typer.Option(False, "--json-only", help="Skip HTML report"),
) -> None:
    """Load and execute a declarative test case."""
    configure_logging()
    try:
        case = load_test_case(test_case_file)
    except FieldValidationError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(EXIT_VALIDATION) from e
    except Exception as e:
        typer.echo(f"Failed to load test case: {e}", err=True)
        raise typer.Exit(EXIT_VALIDATION) from e

    if target:
        case = case.model_copy(update={"target_id": target})

    if dry_run:
        typer.echo(f"OK: test case {case.id!r} with {len(case.steps)} step(s) is valid")
        raise typer.Exit(EXIT_PASSED)

    cfg = load_config(config)
    code = _run_async(_execute(case, cfg, json_only=json_only))
    raise typer.Exit(code)


async def _execute(case, cfg, *, json_only: bool = False) -> int:
    from vnc_agent.drivers.vncdotool_driver import VNCToolDriver
    from vnc_agent.models.provider import build_grounder, build_planner
    from vnc_agent.perception.pipeline import ObservationPipeline
    from vnc_agent.perception.stability import StabilityEngine
    from vnc_agent.reporting.report_builder import ReportBuilder
    from vnc_agent.runtime.agent_runtime import AgentRuntime
    from vnc_agent.storage.artifact_store import ArtifactStore
    from vnc_agent.storage.database import init_db, make_engine, make_session_factory
    from vnc_agent.storage.repositories import RunRepository

    target = cfg.vnc_targets.get(case.target_id)
    if target is None:
        typer.echo(f"Unknown target_id: {case.target_id}", err=True)
        return EXIT_VALIDATION

    password = target.resolve_password()
    driver = VNCToolDriver(
        host=target.host,
        port=target.port,
        password=password,
        connect_timeout_seconds=target.connect_timeout_seconds,
        reconnect_attempts=target.reconnect_attempts,
    )

    try:
        planner = build_planner(cfg.models)
        grounder = build_grounder(cfg.models)
    except Exception as e:
        typer.echo(f"Provider assembly failed: {e}", err=True)
        return EXIT_VALIDATION

    artifacts_root = cfg.agent.artifacts.root_dir
    store = ArtifactStore(
        artifacts_root, mask_regions=cfg.agent.security.mask_regions
    )
    engine = make_engine(cfg.agent.artifacts.db_path)
    await init_db(engine)
    repo = RunRepository(make_session_factory(engine))
    pipeline = ObservationPipeline(
        driver,
        artifacts_dir=artifacts_root,
        templates_dir="templates",
        planner=planner,
        ocr_enabled=cfg.agent.perception.ocr_enabled,
        template_enabled=cfg.agent.perception.template_enabled,
        vision_fallback=cfg.agent.perception.vision_fallback_enabled,
        diff_threshold=cfg.agent.wait.pixel_diff_threshold,
        mask_regions=cfg.agent.security.mask_regions,
    )
    stability = StabilityEngine(
        driver,
        artifacts_dir=artifacts_root,
        min_delay_ms=cfg.agent.wait.min_delay_ms,
        max_delay_ms=cfg.agent.wait.max_delay_ms,
        capture_interval_ms=cfg.agent.wait.capture_interval_ms,
        stable_frame_count=cfg.agent.wait.stable_frame_count,
        pixel_diff_threshold=cfg.agent.wait.pixel_diff_threshold,
        security_mask_regions=cfg.agent.security.mask_regions,
    )
    report_builder = ReportBuilder(store)
    # T100: pass --json-only through to ReportBuilder formats
    report_formats: tuple[str, ...] = ("json",) if json_only else ("json", "html")
    runtime = AgentRuntime(
        config=cfg,
        driver=driver,
        planner=planner,
        grounder=grounder,
        pipeline=pipeline,
        stability=stability,
        repo=repo,
        report_builder=report_builder,
        report_formats=report_formats,
    )

    try:
        ctx = await runtime.run(case)
    except VNCConnectionError:
        return EXIT_VNC
    finally:
        try:
            await driver.disconnect()
        except Exception:
            pass

    status = ctx.test_run.status

    if status == "passed":
        return EXIT_PASSED
    if status == "cancelled":
        return EXIT_CANCELLED
    return EXIT_FAILED


@app.command("report")
def report_cmd(
    run_id: str = typer.Argument(..., help="Existing run id"),
    format: str = typer.Option("both", "--format", help="json|html|both"),
    config: Path = typer.Option(Path("config"), "--config"),
) -> None:
    """Re-render report from persisted run data (no VNC / no re-execution)."""
    configure_logging()
    code = _run_async(_report(run_id, format, config))
    raise typer.Exit(code)


async def _report(run_id: str, fmt: str, config: Path) -> int:
    from vnc_agent.reporting.report_builder import ReportBuilder
    from vnc_agent.storage.artifact_store import ArtifactStore
    from vnc_agent.storage.database import init_db, make_engine, make_session_factory
    from vnc_agent.storage.repositories import RunRepository

    cfg = load_config(config)
    engine = make_engine(cfg.agent.artifacts.db_path)
    await init_db(engine)
    repo = RunRepository(make_session_factory(engine))
    run = await repo.get_run(run_id)
    if run is None:
        typer.echo(f"Run not found: {run_id}", err=True)
        return EXIT_FAILED
    store = ArtifactStore(
        cfg.agent.artifacts.root_dir, mask_regions=cfg.agent.security.mask_regions
    )
    builder = ReportBuilder(store)
    formats = ("json", "html") if fmt == "both" else (fmt,)
    builder.build(run, formats=formats)
    await repo.save_run(run)
    typer.echo(f"Report written for {run_id}")
    return EXIT_PASSED
