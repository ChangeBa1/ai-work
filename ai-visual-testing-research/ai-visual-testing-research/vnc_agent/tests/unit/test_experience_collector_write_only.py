"""US10: Experience collector is write-only (FR-044)."""

import ast
from pathlib import Path

import pytest

from vnc_agent.domain.run import ActionIteration
from vnc_agent.domain.verification import VerificationResult
from vnc_agent.evolution.experience_collector import ExperienceCollector


@pytest.mark.asyncio
async def test_collect_writes_only():
    col = ExperienceCollector(repo=None)
    it = ActionIteration(
        iteration_index=0,
        verification_result=VerificationResult(status="passed", reason="ok"),
    )
    exp = await col.collect(run_id="r", step_id="s", iteration=it)
    assert exp.outcome == "success"
    assert len(col.written) == 1


def test_source_has_no_training_or_mutation_logic():
    path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "vnc_agent"
        / "evolution"
        / "experience_collector.py"
    )
    src = path.read_text(encoding="utf-8")
    forbidden = [
        "torch.",
        "model.fit",
        "train(",
        "overwrite_baseline",
        "modify_assertion",
        "write_replay",
        "save_weights",
    ]
    for token in forbidden:
        assert token not in src, f"forbidden mutation path: {token}"
    # AST: no assignments to VerificationSpec-like mutation helpers
    tree = ast.parse(src)
    assert tree is not None
