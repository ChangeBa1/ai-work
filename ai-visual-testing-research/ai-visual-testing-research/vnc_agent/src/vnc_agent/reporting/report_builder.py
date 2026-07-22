"""Report builder orchestration (FR-040~042/049)."""

from __future__ import annotations

from pathlib import Path

from vnc_agent.domain.reporting_tags import ActionTagRule
from vnc_agent.domain.run import TestRun
from vnc_agent.reporting.html_report import write_html_report
from vnc_agent.reporting.json_report import write_json_report
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

        if "json" in formats or "both" in formats:
            jp = run_dir / "report.json"
            run.report_json_path = write_json_report(
                run, jp, action_tags=self.action_tags
            )
        if "html" in formats or "both" in formats:
            hp = run_dir / "report.html"
            run.report_html_path = write_html_report(
                run, hp, action_tags=self.action_tags
            )
        return run
