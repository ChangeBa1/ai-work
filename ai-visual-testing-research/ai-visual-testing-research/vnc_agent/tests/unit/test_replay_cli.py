"""Feature 016 unit tests: `vnc-agent replay scripts|patches` JSON queries
(spec FR-011) plus the `run --mode` override validation."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml
from typer.testing import CliRunner

from vnc_agent.api.cli import app
from vnc_agent.domain.action import ExecutableAction, SemanticAction
from vnc_agent.domain.memory import PageFingerprint
from vnc_agent.domain.replay import ReplayScript, ReplayStep, normalize_bbox
from vnc_agent.domain.verification import VerificationCondition, VerificationSpec
from vnc_agent.replay.patch import build_pending_patch
from vnc_agent.storage.database import init_db, make_engine, make_session_factory
from vnc_agent.storage.repositories import ReplayRepository

runner = CliRunner()
RESOLUTION = (300, 200)


def _write_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "agent.yaml").write_text(
        yaml.safe_dump(
            {"artifacts": {"db_path": str((tmp_path / "data.db").as_posix())}}
        ),
        encoding="utf-8",
    )
    return config_dir


def _script(version: int = 1) -> ReplayScript:
    bbox = (150, 85, 170, 95)
    step = ReplayStep(
        replay_step_id=str(uuid.uuid4()),
        step_id="s1",
        order_index=0,
        page_fingerprint=PageFingerprint(resolution=RESOLUTION),
        semantic_action=SemanticAction(action_id="a1", intent="click", action_type="click"),
        preferred_method="mouse",
        bbox=bbox,
        normalized_bbox=normalize_bbox(bbox, RESOLUTION),
        expected=VerificationSpec(
            operator="all",
            conditions=[VerificationCondition(type="text_appears", value="DONE")],
        ),
        version=version,
    )
    return ReplayScript(
        script_id=str(uuid.uuid4()),
        test_case_id="tc-cli",
        version=version,
        source_run_id=f"run-{version}",
        created_at=datetime.now(UTC),
        steps=[step],
    )


async def _seed(tmp_path: Path, *, with_patch: bool) -> ReplayScript:
    engine = make_engine(str(tmp_path / "data.db"))
    await init_db(engine)
    repo = ReplayRepository(make_session_factory(engine))
    script = _script(1)
    await repo.save_script(script)
    if with_patch:
        patch = build_pending_patch(
            script=script,
            step=script.steps[0],
            new_executable=ExecutableAction(
                method="mouse", operation="click", coordinates=(210, 125)
            ),
            reason="moved",
            before_image=None,
            after_image=None,
        )
        await repo.save_patch(patch)
    return script


def test_replay_scripts_command_outputs_json(tmp_path: Path):
    import asyncio

    config_dir = _write_config(tmp_path)
    script = asyncio.run(_seed(tmp_path, with_patch=False))

    result = runner.invoke(
        app, ["replay", "scripts", "tc-cli", "--config", str(config_dir)]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["script_id"] == script.script_id
    assert data[0]["version"] == 1
    assert data[0]["step_count"] == 1
    assert data[0]["steps"][0]["step_id"] == "s1"


def test_replay_patches_command_outputs_json(tmp_path: Path):
    import asyncio

    config_dir = _write_config(tmp_path)
    asyncio.run(_seed(tmp_path, with_patch=True))

    result = runner.invoke(
        app,
        ["replay", "patches", "tc-cli", "--status", "pending", "--config", str(config_dir)],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["status"] == "pending"
    assert data[0]["new_target"]["coordinates"] == [210, 125]


def test_run_mode_override_rejects_unknown_value(tmp_path: Path):
    case_file = tmp_path / "case.yaml"
    case_file.write_text(
        yaml.safe_dump(
            {
                "id": "tc",
                "name": "tc",
                "target_id": "t1",
                "mode": "explicit",
                "steps": [
                    {
                        "id": "s1",
                        "name": "s1",
                        "intent": "do",
                        "expected": {
                            "operator": "all",
                            "conditions": [{"type": "screen_changed"}],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["run", str(case_file), "--mode", "bogus", "--dry-run"])
    assert result.exit_code == 2


def test_replay_mode_testcase_yaml_loads(tmp_path: Path):
    """mode: replay is a valid declarative test case (FR-011 additive)."""
    case_file = tmp_path / "case.yaml"
    case_file.write_text(
        yaml.safe_dump(
            {
                "id": "tc",
                "name": "tc",
                "target_id": "t1",
                "mode": "replay",
                "steps": [
                    {
                        "id": "s1",
                        "name": "s1",
                        "intent": "do",
                        "expected": {
                            "operator": "all",
                            "conditions": [{"type": "screen_changed"}],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["run", str(case_file), "--dry-run"])
    assert result.exit_code == 0, result.output
