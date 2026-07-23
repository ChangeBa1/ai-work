"""Report builder orchestration (FR-040~042/049).

Feature 004 (telemetry-contract.md "Report build boundary"): `report_build`
times safe-evidence resolution + machine dict/HTML draft assembly only —
never the final encode/atomic write, which is the separate `report_output`
stage. A `report_output` failure keeps its real observed duration and never
corrupts already-recorded run facts.

NOTE: masking still uses the legacy `copy_masked_for_report` report-copy
path; feature 004 User Story 4 (T056) replaces this with a zero-copy safe
evidence resolver — this two-phase timing boundary is written so that
replacement only has to change what happens *inside* the `report_build`
block, not the boundary itself.
"""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Template

from vnc_agent.domain.reporting_tags import ActionTagRule
from vnc_agent.domain.run import TestRun
from vnc_agent.reporting.html_report import _TEMPLATE
from vnc_agent.reporting.json_report import build_report_dict
from vnc_agent.runtime.telemetry import measure_stage
from vnc_agent.storage.artifact_store import ArtifactStore


class ReportBuilder:
    def __init__(
        self,
        artifact_store: ArtifactStore,
        *,
        action_tags: list[ActionTagRule] | None = None,
    ) -> None:
        self.store = artifact_store
        self.action_tags = action_tags

    def build(
        self,
        run: TestRun,
        *,
        formats: tuple[str, ...] = ("json", "html"),
    ) -> TestRun:
        run_dir = self.store.run_dir(run.run_id)
        want_json = "json" in formats or "both" in formats
        want_html = "html" in formats or "both" in formats

        with measure_stage(run, stage="report_build", run_id=run.run_id):
            # Mask sensitive frames referenced in iterations for report display
            for step in run.steps:
                for it in step.iterations:
                    if it.before_frame_id and Path(it.before_frame_id).exists():
                        masked = self.store.copy_masked_for_report(
                            it.before_frame_id,
                            run.run_id,
                            f"{step.step_id}_{it.iteration_index}_before.png",
                        )
                        it.before_frame_id = masked
                    if it.after_frame_id and Path(it.after_frame_id).exists():
                        masked = self.store.copy_masked_for_report(
                            it.after_frame_id,
                            run.run_id,
                            f"{step.step_id}_{it.iteration_index}_after.png",
                        )
                        it.after_frame_id = masked

            json_dict = build_report_dict(run, action_tags=self.action_tags)
            html_text = (
                Template(_TEMPLATE).render(report=json_dict) if want_html else None
            )

        with measure_stage(run, stage="report_output", run_id=run.run_id):
            if want_json:
                jp = run_dir / "report.json"
                jp.parent.mkdir(parents=True, exist_ok=True)
                jp.write_text(
                    json.dumps(json_dict, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                run.report_json_path = str(jp)
            if want_html:
                hp = run_dir / "report.html"
                hp.parent.mkdir(parents=True, exist_ok=True)
                hp.write_text(html_text, encoding="utf-8")
                run.report_html_path = str(hp)
        return run
