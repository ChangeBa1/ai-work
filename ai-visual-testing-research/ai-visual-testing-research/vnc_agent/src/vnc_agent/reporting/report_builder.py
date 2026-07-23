"""Report builder orchestration (FR-040~042/049).

Feature 004 (telemetry-contract.md "Report build boundary";
report-contract.md "Safe evidence contract"): `report_build` times safe
evidence resolution + machine dict/HTML draft assembly only — never the
final encode/atomic write, which is the separate `report_output` stage. A
`report_output` failure keeps its real observed duration and never corrupts
already-recorded run facts. Evidence is resolved zero-copy — no
`copy_masked_for_report`/report-copy path exists anymore; ActionIteration's
`before_frame_id`/`after_frame_id` are read-only inputs, never mutated.
"""

from __future__ import annotations

import json

from vnc_agent.domain.reporting_tags import ActionTagRule
from vnc_agent.domain.run import TestRun
from vnc_agent.reporting.html_report import render_html_from_dict
from vnc_agent.reporting.json_report import build_report_dict
from vnc_agent.reporting.localization import UnknownLocaleError, registered_locales
from vnc_agent.reporting.safe_evidence import SafeEvidenceResolver
from vnc_agent.runtime.telemetry import derive_performance_summary, measure_stage
from vnc_agent.storage.artifact_store import ArtifactStore


class ReportBuilder:
    def __init__(
        self,
        artifact_store: ArtifactStore,
        *,
        action_tags: list[ActionTagRule] | None = None,
        locale: str = "zh-CN",
    ) -> None:
        if locale not in registered_locales():
            raise UnknownLocaleError(f"unregistered reporting locale {locale!r}")
        self.store = artifact_store
        self.action_tags = action_tags
        self.locale = locale

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
            resolver = SafeEvidenceResolver(self.store)
            run.performance_summary = derive_performance_summary(run)
            json_dict = build_report_dict(
                run,
                action_tags=self.action_tags,
                safe_evidence_resolver=resolver,
                locale=self.locale,
            )
            html_text = (
                render_html_from_dict(json_dict, locale=self.locale, run_dir=str(run_dir))
                if want_html
                else None
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
