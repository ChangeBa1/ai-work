"""Typer CLI: run / report (contracts/cli-contract.md)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import typer

from vnc_agent.config import load_config
from vnc_agent.domain.run import HumanConfirmedFact
from vnc_agent.domain.testcase import FieldValidationError, TestCase, load_test_case
from vnc_agent.logging_setup import configure_logging, get_logger
from vnc_agent.runtime.exceptions import ReplayUnavailableError, VNCConnectionError
from vnc_agent.ui_index.cli import ui_index_app
from vnc_agent.ui_index.repository import UiIndexValidationError

app = typer.Typer(name="vnc-agent", help="VNC black-box GUI automation agent", no_args_is_help=True)
app.add_typer(ui_index_app, name="ui-index")
# Feature 016 (FR-011): replay script/patch inspection commands (JSON output).
replay_app = typer.Typer(name="replay", help="Replay script / patch queries", no_args_is_help=True)
app.add_typer(replay_app, name="replay")
# Feature 021 (FR-005): offline hard-case dataset export (read-only, no VNC).
evolution_app = typer.Typer(
    name="evolution", help="Offline evolution/training-data tools", no_args_is_help=True
)
app.add_typer(evolution_app, name="evolution")
log = get_logger("cli")

# Exit codes (cli-contract.md)
EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_VALIDATION = 2
EXIT_CANCELLED = 3
EXIT_VNC = 4


def _run_async(coro):
    return asyncio.run(coro)


def _parse_confirm_precondition(
    case: TestCase, raw_pairs: list[str], screenshot: Path | None
) -> list[HumanConfirmedFact]:
    """Feature 003 (FR-024): parse generic `key=value` pairs and validate each
    key against the testcase's declared precondition facts before connecting."""
    declared_keys = {fact.key for fact in (case.precondition.facts if case.precondition else [])}
    facts: list[HumanConfirmedFact] = []
    now = datetime.now(UTC)
    for pair in raw_pairs:
        if "=" not in pair:
            typer.echo(
                f"--confirm-precondition expects key=value, got: {pair!r}", err=True
            )
            raise typer.Exit(EXIT_VALIDATION)
        key, value = pair.split("=", 1)
        if key not in declared_keys:
            typer.echo(
                f"--confirm-precondition key {key!r} is not declared in this "
                "test case's precondition.facts",
                err=True,
            )
            raise typer.Exit(EXIT_VALIDATION)
        facts.append(
            HumanConfirmedFact(
                key=key,
                confirmed_value=value,
                confirmed_at=now,
                screenshot_ref=str(screenshot) if screenshot else None,
            )
        )
    return facts


@app.command("run")
def run_cmd(
    test_case_file: Path = typer.Argument(  # noqa: B008 - Typer declares CLI metadata here
        ..., exists=False, help="YAML test case path"
    ),
    target: str | None = typer.Option(None, "--target", help="Override target_id"),
    config: Path = typer.Option(  # noqa: B008 - Typer declares CLI metadata here
        Path("config"), "--config", help="Config directory"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate only, no VNC"),
    json_only: bool = typer.Option(False, "--json-only", help="Skip HTML report"),
    mode: str | None = typer.Option(
        None,
        "--mode",
        help="Override test case mode: explicit (exploration) or replay "
        "(run the latest recorded script; feature 016)",
    ),
    confirm_precondition: list[str] = typer.Option(  # noqa: B008
        [],
        "--confirm-precondition",
        help="Human-confirmed key=value for a declared precondition fact (repeatable)",
    ),
    confirm_screenshot: Path | None = typer.Option(  # noqa: B008
        None, "--confirm-screenshot", help="Evidence screenshot for --confirm-precondition"
    ),
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

    if mode is not None:
        if mode not in ("explicit", "replay"):
            typer.echo(f"--mode must be 'explicit' or 'replay', got {mode!r}", err=True)
            raise typer.Exit(EXIT_VALIDATION)
        case = case.model_copy(update={"mode": mode})

    human_confirmed_facts = _parse_confirm_precondition(
        case, confirm_precondition, confirm_screenshot
    )

    if dry_run:
        typer.echo(f"OK: test case {case.id!r} with {len(case.steps)} step(s) is valid")
        raise typer.Exit(EXIT_PASSED)

    cfg = load_config(config)
    code = _run_async(
        _execute(
            case,
            cfg,
            json_only=json_only,
            human_confirmed_facts=human_confirmed_facts,
        )
    )
    raise typer.Exit(code)


async def _execute(
    case,
    cfg,
    *,
    json_only: bool = False,
    human_confirmed_facts: list[HumanConfirmedFact] | None = None,
) -> int:
    import uuid

    from vnc_agent.drivers.vncdotool_driver import VNCToolDriver
    from vnc_agent.models.provider import build_grounder, build_planner
    from vnc_agent.perception.cache import AnalysisResultCache
    from vnc_agent.perception.ocr.engine import configure_ocr
    from vnc_agent.perception.pipeline import ObservationPipeline
    from vnc_agent.perception.screenshot import FrameCaptureService
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

    # Feature 010: apply OCR language/model settings at the composition root,
    # before any VNC connection — a missing configured model asset fails
    # fast here with the offending path named (FR-005/SC-004).
    try:
        configure_ocr(
            lang=cfg.agent.perception.ocr_lang,
            rec_model_path=cfg.agent.perception.ocr_rec_model_path,
            rec_keys_path=cfg.agent.perception.ocr_rec_keys_path,
        )
    except (ValueError, FileNotFoundError) as e:
        typer.echo(f"OCR configuration invalid: {e}", err=True)
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

    # Feature 019 (planner-request-slimming): deliver the agent.yaml
    # `planning:` slimming knobs to the HTTP planner without changing
    # build_planner's signature (offline tests monkeypatch it with
    # single-argument stubs). Planners without the hook (stubs) are skipped.
    configure_planning = getattr(planner, "configure_planning", None)
    if callable(configure_planning):
        configure_planning(cfg.agent.planning)

    artifacts_root = cfg.agent.artifacts.root_dir
    store = ArtifactStore(
        artifacts_root, mask_regions=cfg.agent.security.mask_regions
    )
    engine = make_engine(cfg.agent.artifacts.db_path)
    await init_db(engine)
    repo = RunRepository(make_session_factory(engine))

    # Feature 004: exactly one FrameCaptureService for the whole execute
    # path, shared by ObservationPipeline and StabilityEngine — the single
    # recorder for TestRun.frames. `test_run` is attached once AgentRuntime
    # creates its RunContext (run_id is generated here so both share it).
    run_id = str(uuid.uuid4())
    capture_service = FrameCaptureService(
        driver,
        run_id=run_id,
        vnc_session_id=str(uuid.uuid4()),
        test_run=None,
        artifact_store=store,
        mask_regions=cfg.agent.security.mask_regions,
        private_persistence_allowed=True,
    )
    analysis_cache = AnalysisResultCache(max_frames=cfg.agent.perception.cache_max_frames)
    pipeline = ObservationPipeline(
        capture_service,
        templates_dir="templates",
        planner=planner,
        ocr_enabled=cfg.agent.perception.ocr_enabled,
        template_enabled=cfg.agent.perception.template_enabled,
        vision_fallback=cfg.agent.perception.vision_fallback_enabled,
        diff_threshold=cfg.agent.wait.pixel_diff_threshold,
        cache=analysis_cache,
    )
    stability = StabilityEngine(
        capture_service,
        min_delay_ms=cfg.agent.wait.min_delay_ms,
        max_delay_ms=cfg.agent.wait.max_delay_ms,
        capture_interval_ms=cfg.agent.wait.capture_interval_ms,
        stable_frame_count=cfg.agent.wait.stable_frame_count,
        pixel_diff_threshold=cfg.agent.wait.pixel_diff_threshold,
    )
    action_tags = list(cfg.agent.reporting.action_tags) + list(case.action_tags)
    report_builder = ReportBuilder(
        store, action_tags=action_tags, locale=cfg.agent.reporting.locale
    )
    # T100: pass --json-only through to ReportBuilder formats
    report_formats: tuple[str, ...] = ("json",) if json_only else ("json", "html")
    runtime = AgentRuntime(
        config=cfg,
        driver=driver,
        planner=planner,
        grounder=grounder,
        pipeline=pipeline,
        stability=stability,
        capture_service=capture_service,
        artifact_store=store,
        repo=repo,
        report_builder=report_builder,
        report_formats=report_formats,
    )

    try:
        ctx = await runtime.run(
            case, human_confirmed_facts=human_confirmed_facts
        )
    except VNCConnectionError:
        return EXIT_VNC
    except ReplayUnavailableError as e:
        # Feature 016 (FR-005 / spec Clarification 11): a mode:"replay" run
        # that cannot start (disabled / no script / step mismatch) fails
        # fast before any VNC connection — validation-grade exit code.
        typer.echo(f"Replay unavailable: {e}", err=True)
        return EXIT_VALIDATION
    except UiIndexValidationError as e:
        # FR-012: an explicitly configured but invalid ui_index bundle fails
        # the run before any test step executes (Planner/Grounder/Executor
        # are never invoked).
        typer.echo(f"UI index validation failed: {e.report.bundle_dir}", err=True)
        for issue in e.report.issues:
            typer.echo(
                f"  [{issue.error_code.value}] file={issue.file} line={issue.line}: "
                f"{issue.message}",
                err=True,
            )
        return EXIT_VALIDATION
    finally:
        try:
            await driver.disconnect()
        except Exception:
            pass
        # Feature 017 (httpx-client-reuse): release the providers' long-lived
        # httpx connection pools on every exit path (success, failure,
        # exception). Duck-typed so stub providers without aclose() are fine;
        # close failures must never mask the run's real outcome.
        for provider in (planner, grounder):
            aclose = getattr(provider, "aclose", None)
            if aclose is None:
                continue
            try:
                await aclose()
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
    config: Path = typer.Option(Path("config"), "--config"),  # noqa: B008
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
    builder = ReportBuilder(store, locale=cfg.agent.reporting.locale)
    formats = ("json", "html") if fmt == "both" else (fmt,)
    builder.build(run, formats=formats)
    await repo.save_run(run)
    typer.echo(f"Report written for {run_id}")
    return EXIT_PASSED


# ---------------------------------------------------------------------------
# Feature 016 (FR-011): replay script / patch JSON queries (no VNC involved)
# ---------------------------------------------------------------------------


async def _replay_repo(config: Path):
    from vnc_agent.storage.database import init_db, make_engine, make_session_factory
    from vnc_agent.storage.repositories import ReplayRepository

    cfg = load_config(config)
    engine = make_engine(cfg.agent.artifacts.db_path)
    await init_db(engine)
    return ReplayRepository(make_session_factory(engine))


async def _list_scripts(test_case_id: str, config: Path) -> str:
    import json

    repo = await _replay_repo(config)
    scripts = await repo.list_scripts(test_case_id)
    out = [
        {
            "script_id": s.script_id,
            "test_case_id": s.test_case_id,
            "version": s.version,
            "source_run_id": s.source_run_id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "step_count": len(s.steps),
            "steps": [
                {
                    "replay_step_id": st.replay_step_id,
                    "step_id": st.step_id,
                    "preferred_method": st.preferred_method,
                    "direct_fallback_only": st.direct_fallback_only,
                    "success_count": st.success_count,
                    "failure_count": st.failure_count,
                }
                for st in s.steps
            ],
        }
        for s in scripts
    ]
    return json.dumps(out, ensure_ascii=False, indent=2)


async def _list_patches(test_case_id: str, status: str | None, config: Path) -> str:
    import json

    repo = await _replay_repo(config)
    patches = await repo.list_patches(test_case_id, status=status)
    return json.dumps(
        [p.model_dump(mode="json") for p in patches], ensure_ascii=False, indent=2
    )


# ---------------------------------------------------------------------------
# Feature 021 (FR-005): offline hard-case dataset export (specs/021-…).
# Read-only over the run store; zero runtime impact — the miner/exporter
# modules are imported only inside this command path (FR-007).
# ---------------------------------------------------------------------------


async def _evolution_export(
    *,
    out: Path,
    db: str | None,
    config: Path,
    artifacts_root: str | None,
    since: str | None,
    criteria: list[str],
) -> str:
    import json

    from vnc_agent.evolution.dataset_exporter import (
        UnknownCriterionError,
        export_hard_cases,
        validate_criteria_filter,
    )
    from vnc_agent.storage.database import init_db, make_engine, make_session_factory

    cfg = load_config(config)

    try:
        validate_criteria_filter(criteria)
    except UnknownCriterionError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(EXIT_VALIDATION) from e

    since_dt = None
    if since is not None:
        from datetime import datetime as _dt

        try:
            since_dt = _dt.fromisoformat(since)
        except ValueError as e:
            typer.echo(f"--since expects an ISO date/datetime, got: {since!r}", err=True)
            raise typer.Exit(EXIT_VALIDATION) from e

    engine = make_engine(db or cfg.agent.artifacts.db_path)
    await init_db(engine)
    try:
        summary = await export_hard_cases(
            make_session_factory(engine),
            out_path=out,
            evolution_cfg=cfg.agent.evolution,
            sensitive_fields=cfg.agent.security.sensitive_field_names,
            artifacts_root=artifacts_root or cfg.agent.artifacts.root_dir,
            since=since_dt,
            criteria_filter=criteria or None,
        )
    finally:
        await engine.dispose()
    return json.dumps(summary.to_json_dict(), ensure_ascii=False, indent=2)


@evolution_app.command("export")
def evolution_export_cmd(
    out: Path = typer.Option(  # noqa: B008 - Typer declares CLI metadata here
        ..., "--out", help="Output JSONL dataset path"
    ),
    db: str | None = typer.Option(
        None, "--db", help="SQLite db path (default: config artifacts.db_path)"
    ),
    config: Path = typer.Option(Path("config"), "--config"),  # noqa: B008
    artifacts_root: str | None = typer.Option(
        None,
        "--artifacts-root",
        help="Artifacts root for relative screenshot paths "
        "(default: config artifacts.root_dir)",
    ),
    since: str | None = typer.Option(
        None, "--since", help="Only runs started at/after this ISO date/datetime (UTC)"
    ),
    criteria: list[str] = typer.Option(  # noqa: B008
        [],
        "--criteria",
        help="Only export samples matching at least one named criterion (repeatable)",
    ),
) -> None:
    """Mine hard-case steps from historical runs into a JSONL dataset.

    Offline and read-only (overall_design.md §12.3/§12.4): scans the run
    store, applies the hard-case criteria, writes one JSON object per sample
    to --out and prints a JSON summary (totals + per-criterion hit counts).
    """
    configure_logging()
    typer.echo(
        _run_async(
            _evolution_export(
                out=out,
                db=db,
                config=config,
                artifacts_root=artifacts_root,
                since=since,
                criteria=criteria,
            )
        )
    )


@replay_app.command("scripts")
def replay_scripts_cmd(
    test_case_id: str = typer.Argument(..., help="Test case id"),
    config: Path = typer.Option(Path("config"), "--config"),  # noqa: B008
) -> None:
    """List recorded replay script versions for a test case (JSON)."""
    configure_logging()
    typer.echo(_run_async(_list_scripts(test_case_id, config)))


@replay_app.command("patches")
def replay_patches_cmd(
    test_case_id: str = typer.Argument(..., help="Test case id"),
    status: str | None = typer.Option(
        None, "--status", help="Filter by status: pending|approved|rejected"
    ),
    config: Path = typer.Option(Path("config"), "--config"),  # noqa: B008
) -> None:
    """List replay self-heal candidate patches for a test case (JSON)."""
    configure_logging()
    typer.echo(_run_async(_list_patches(test_case_id, status, config)))
