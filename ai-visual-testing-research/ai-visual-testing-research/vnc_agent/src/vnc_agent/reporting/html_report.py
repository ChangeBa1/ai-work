"""HTML report via Jinja2 (same data source as JSON; report-contract.md).

Feature 004: fully localized to zh-CN by default via
`reporting/localization.py` — the template calls small lookup functions
(`status_display`, `verification_display`, ...) registered as Jinja
globals; it never contains an enum/error translation if/elif chain itself.
Autoescape is on; evidence links only ever point at an already-resolved,
zero-copy safe path (`safe_image_path`/`before_frame_path`/
`after_frame_path` as produced by `json_report.build_report_dict`) — a
`None` path renders as a localized "unavailable" notice, never a link.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment

from vnc_agent.domain.reporting_tags import ActionTagRule
from vnc_agent.domain.run import TestRun
from vnc_agent.reporting.json_report import build_report_dict
from vnc_agent.reporting.localization import display, localize_error, resource_text
from vnc_agent.reporting.safe_evidence import SafeEvidenceResolver

HTML_TEMPLATE_SOURCE = """<!DOCTYPE html>
<html lang="{{ locale }}">
<head>
<meta charset="utf-8"/>
<title>{{ t('report.title') }} {{ report.run_id }}</title>
<style>
body{font-family:system-ui,sans-serif;margin:24px;background:#f6f7f9;color:#1a1a1a}
h1{font-size:1.4rem}.status{font-weight:700}
.status-passed{color:#0a7}.status-failed{color:#c22}.status-cancelled{color:#a60}
.status-running{color:#06c}.status-created{color:#888}
.step{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:12px 0}
.iter{border-left:3px solid #88a;margin:8px 0 8px 8px;padding:8px 12px;background:#fafbff}
details{margin-top:6px} code{font-size:0.85em}
.warn-weak{background:#fff3cd;border:1px solid #e0a800;color:#664d03;padding:6px 10px;border-radius:4px;margin:6px 0;font-weight:600}
.label-effect-only{background:#e7f1ff;border:1px solid #6ea8fe;color:#084298;padding:6px 10px;border-radius:4px;margin:6px 0}
.label-trusted{background:#d1e7dd;border:1px solid #75b798;color:#0a3622;padding:6px 10px;border-radius:4px;margin:6px 0}
.evidence-unavailable{color:#a33;font-style:italic}
.perf-table{border-collapse:collapse}
.perf-table td,.perf-table th{border:1px solid #ddd;padding:4px 10px;text-align:left}
</style>
</head>
<body>
<h1>{{ t('report.title') }} <code>{{ report.run_id }}</code></h1>
<p>{{ t('report.case') }}: <code>{{ report.test_case_id }}</code></p>
<p>{{ t('report.status') }}:
  <span class="status {{ status_display(report.status).css_class }}" data-status="{{ report.status }}">
    {{ status_display(report.status).display_value }}
  </span>
  ({{ report.display_status }})
</p>
<p>{{ t('report.started_at') }}: {{ report.started_at or t('report.none') }} ·
   {{ t('report.ended_at') }}: {{ report.ended_at or t('report.none') }}</p>
{% if report.localized_message %}<p><strong>{{ report.localized_message }}</strong></p>{% endif %}

<details open>
  <summary>{{ t('report.precondition') }} / {{ t('report.action_audit') }}</summary>
  <p>{{ t('report.human_confirmed_facts') }}: <code>{{ report.human_confirmed_facts }}</code></p>
  <p>{{ t('report.precondition') }}: <code>{{ precondition_display(report.precondition_evaluation.status).display_value }}</code></p>
  <p>{{ t('report.declared_tag_counts') }}: <code>{{ report.declared_tag_counts }}</code></p>
  <p>{{ t('report.action_audit') }}: <code>{{ report.executed_action_log }}</code></p>
</details>

<details open>
  <summary>{{ t('report.performance_summary') }}</summary>
  <table class="perf-table">
    <tr><th>{{ t('performance.total_capture_count') }}</th><td>{{ report.performance_summary.total_capture_count }}</td></tr>
    <tr><th>{{ t('performance.unique_frame_count') }}</th><td>{{ report.performance_summary.unique_frame_count }}</td></tr>
    <tr><th>{{ t('performance.duplicate_frame_count') }}</th><td>{{ report.performance_summary.duplicate_frame_count }}</td></tr>
    <tr><th>{{ t('performance.dedup_ratio') }}</th><td>{{ report.performance_summary.dedup_ratio if report.performance_summary.dedup_ratio is not none else t('report.none') }}</td></tr>
    <tr><th>{{ t('performance.physical_image_count') }}</th><td>{{ report.performance_summary.physical_image_count }}</td></tr>
    <tr><th>{{ t('performance.avoided_write_count') }}</th><td>{{ report.performance_summary.avoided_write_count }}</td></tr>
    <tr><th>{{ t('performance.actual_model_call_count') }}</th><td>{{ report.performance_summary.actual_model_call_count }}</td></tr>
    <tr><th>{{ t('performance.skipped_model_call_count') }}</th><td>{{ report.performance_summary.skipped_model_call_count }}</td></tr>
    <tr><th>{{ t('performance.memory_hit_count') }}</th><td>{{ report.performance_summary.memory_hits.element_memory }}</td></tr>
    <tr><th>{{ t('performance.replay_locate_methods') }}</th><td>{{ report.performance_summary.replay_locate_methods }}</td></tr>
    <tr><th>{{ t('performance.replay_patch_count') }}</th><td>{{ report.performance_summary.replay_patch_count }}</td></tr>
    <tr><th>{{ t('performance.completeness') }}</th><td data-completeness="{{ report.performance_summary.completeness }}">{{ completeness_display(report.performance_summary.completeness).display_value }}</td></tr>
  </table>
  {% if report.performance_summary.consistency_errors %}
  <p class="evidence-unavailable">{{ t('performance.consistency_errors') }}: {{ report.performance_summary.consistency_errors }}</p>
  {% endif %}
</details>

{% for step in report.steps %}
<div class="step">
  <h2>{{ t('report.step') }} {{ step.step_id }} —
    <span class="status {{ status_display(step.status).css_class }}" data-status="{{ step.status }}">{{ status_display(step.status).display_value }}</span></h2>
  {% if step.weak_assertion_warning %}
  <div class="warn-weak" data-marker="weak_assertion_warning">
    ⚠ {{ verification_label_display('weak_assertion_warning').display_value }}
  </div>
  {% elif step.verification_label == 'effect_only_pass' %}
  <div class="label-effect-only" data-marker="effect_only_pass">
    {{ verification_label_display('effect_only_pass').display_value }}
  </div>
  {% elif step.verification_label == 'trusted_pass' %}
  <div class="label-trusted" data-marker="trusted_pass">
    {{ verification_label_display('trusted_pass').display_value }}
  </div>
  {% endif %}
  {% if step.failure_reason %}<p><strong>{{ t('report.failure_reason') }}:</strong> {{ error_text(step.failure_reason) }}</p>{% endif %}
  {% for it in step.iterations %}
  <div class="iter">
    <strong>{{ t('report.iteration') }} {{ it.iteration_index }}</strong>
    · {{ t('report.verification_result') }}:
    <code data-status="{{ it.verification_result.status if it.verification_result else 'uncertain' }}">
      {{ verification_display(it.verification_result.status if it.verification_result else 'uncertain').display_value }}
    </code>
    {% if it.verification_result and it.verification_result.weak_assertion_warning %}
    · <span class="warn-weak" data-marker="weak_assertion_warning">{{ verification_label_display('weak_assertion_warning').display_value }}</span>
    {% endif %}
    {% if it.action_effect %}
    · {{ t('report.action_effect') }}:
    <code data-status="{{ it.action_effect.status }}">{{ action_effect_display(it.action_effect.status).display_value }}</code>
    {% endif %}
    <details>
      <summary>{{ t('report.canonical_action_identity') }} / {{ t('report.coordinate_space_audit') }}</summary>
      <p>{{ t('report.canonical_action_identity') }}: <code>{{ it.canonical_action_identity or t('report.none') }}</code></p>
      <p>{{ t('report.coordinate_space_audit') }}: <code>{{ it.coordinate_space_audit }}</code></p>
    </details>
    <details>
      <summary>{{ t('report.evidence') }}</summary>
      <p>{{ t('report.evidence_before') }}:
        {% if it.before_frame_path %}<a href="{{ relative_link(it.before_frame_path) }}"><code>{{ relative_link(it.before_frame_path) }}</code></a>
        {% else %}<span class="evidence-unavailable" data-marker="evidence_unavailable">{{ t('report.unavailable') }}</span>{% endif %}
      </p>
      <p>{{ t('report.evidence_after') }}:
        {% if it.after_frame_path %}<a href="{{ relative_link(it.after_frame_path) }}"><code>{{ relative_link(it.after_frame_path) }}</code></a>
        {% else %}<span class="evidence-unavailable" data-marker="evidence_unavailable">{{ t('report.unavailable') }}</span>{% endif %}
      </p>
      <p>{{ t('report.semantic_action') }}: <code>{{ it.semantic_action }}</code></p>
      <p>{{ t('report.action_effect') }}: <code>{{ it.action_effect }}</code></p>
      <p>{{ t('report.grounding_candidates') }}: <code>{{ it.grounding_candidates }}</code></p>
      <p>{{ t('report.executable_action') }}: <code>{{ it.executable_action }}</code></p>
      <p>{{ t('report.wait_result') }}:
        {% if it.wait_result %}
        {% set wr = wait_display(it.wait_result.end_reason) %}
        <code data-status="{{ it.wait_result.end_reason }}">{{ wr.display_value }}</code>
        {% else %}{{ t('report.none') }}{% endif %}
      </p>
      <p>{{ t('report.recovery_attempts') }}: <code>{{ it.recovery_attempts }}</code></p>
    </details>
  </div>
  {% endfor %}
</div>
{% endfor %}

<details>
  <summary>{{ t('report.stage_measurements') }}</summary>
  <table class="perf-table">
    <tr>
      <th>{{ t('report.step') }}</th><th>stage</th>
      <th>{{ t('report.status') }}</th><th>ms</th>
    </tr>
    {% for m in report.stage_measurements %}
    <tr>
      <td>{{ m.step_id or t('report.none') }}</td>
      <td data-stage="{{ m.stage }}">{{ stage_name_display(m.stage).display_value }}</td>
      <td data-status="{{ m.status }}">{{ stage_status_display(m.status).display_value }}</td>
      <td>{{ m.duration_ms if m.duration_ms is not none else t('report.unavailable') }}</td>
    </tr>
    {% endfor %}
  </table>
</details>

<details>
  <summary>{{ t('report.frames') }}</summary>
  <table class="perf-table">
    <tr><th>seq</th><th>{{ t('report.status') }}</th><th>{{ t('report.evidence') }}</th></tr>
    {% for f in report.frames %}
    <tr>
      <td>{{ f.capture_sequence }}</td>
      {% set dedup_marker = '重复' if f.deduplicated else '唯一' %}
      <td data-deduplicated="{{ f.deduplicated | lower }}">{{ dedup_marker }}</td>
      <td>
        {% if f.safe_image_path %}
        {% set link = relative_link(f.safe_image_path) %}
        <a href="{{ link }}"><code>{{ link }}</code></a>
        {% else %}
        <span class="evidence-unavailable" data-marker="evidence_unavailable">{{ t('report.unavailable') }}</span>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </table>
</details>
</body>
</html>
"""


def _view_functions(locale: str, run_dir: str):
    resolved_run_dir = Path(run_dir).resolve()

    def t(key: str) -> str:
        return resource_text(locale, key)

    def relative_link(path: str) -> str:
        # `path` comes from the safe evidence resolver, which always
        # returns a resolved absolute path — resolve run_dir the same way
        # so relative_to() reliably finds the true nested bundle path
        # (bundles/<bundle_id>/safe_evidence.png), never silently
        # collapsing to just the filename.
        try:
            return str(Path(path).resolve().relative_to(resolved_run_dir)).replace("\\", "/")
        except ValueError:
            return Path(path).name

    def error_text(code: str | None) -> str:
        return localize_error(locale, code, None)

    return {
        "t": t,
        "status_display": lambda v: display(locale, "status", v),
        "verification_display": lambda v: display(locale, "verification", v),
        "verification_label_display": lambda v: display(locale, "verification_label", v),
        "action_effect_display": lambda v: display(locale, "action_effect", v),
        "wait_display": lambda v: display(locale, "wait", v),
        "stage_status_display": lambda v: display(locale, "stage_status", v),
        "stage_name_display": lambda v: display(locale, "stage_name", v),
        "completeness_display": lambda v: display(locale, "completeness", v),
        "precondition_display": lambda v: display(locale, "precondition", v),
        "relative_link": relative_link,
        "error_text": error_text,
    }


def render_html_from_dict(report: dict, *, locale: str = "zh-CN", run_dir: str) -> str:
    """Pure rendering from an already-built report dict — used by
    `ReportBuilder` so `report_build` never computes the machine dict twice."""
    env = Environment(autoescape=True)
    env.globals.update(_view_functions(locale, run_dir))
    template = env.from_string(HTML_TEMPLATE_SOURCE)
    return template.render(report=report, locale=locale)


def render_html_report(
    run: TestRun,
    *,
    action_tags: list[ActionTagRule] | None = None,
    safe_evidence_resolver: SafeEvidenceResolver | None = None,
    locale: str = "zh-CN",
    run_dir: str,
) -> str:
    report = build_report_dict(
        run, action_tags=action_tags, safe_evidence_resolver=safe_evidence_resolver, locale=locale
    )
    return render_html_from_dict(report, locale=locale, run_dir=run_dir)


def write_html_report(
    run: TestRun,
    path,
    *,
    action_tags: list[ActionTagRule] | None = None,
    safe_evidence_resolver: SafeEvidenceResolver | None = None,
    locale: str = "zh-CN",
) -> str:
    from pathlib import Path as PathCls

    path = PathCls(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    html = render_html_report(
        run,
        action_tags=action_tags,
        safe_evidence_resolver=safe_evidence_resolver,
        locale=locale,
        run_dir=str(path.parent),
    )
    path.write_text(html, encoding="utf-8")
    return str(path)
