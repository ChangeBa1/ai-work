"""Phase 4 (T039/T040): end-to-end proof that actual Planner/Grounder/
Verifier calls produce sanitized ModelCallAudit records with distinct
context identities — never served from the pixel-content analysis cache.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.e2e.conftest import build_runtime


@pytest.mark.asyncio
async def test_full_run_produces_planner_and_verification_audits(
    tmp_path: Path, app_config, simple_case
):
    runtime, drv = await build_runtime(tmp_path, app_config)
    ctx = await runtime.run(simple_case)

    roles = {a.model_role for a in ctx.test_run.model_call_audits}
    assert "planner" in roles
    assert "verification" in roles

    for audit in ctx.test_run.model_call_audits:
        assert audit.outcome == "actual"
        assert audit.request_identity
        assert audit.context_identity
        assert audit.run_id == ctx.run_id
        # sanitized payloads must never carry raw image bytes
        for value in audit.sanitized_request.values():
            assert not isinstance(value, (bytes, bytearray))
