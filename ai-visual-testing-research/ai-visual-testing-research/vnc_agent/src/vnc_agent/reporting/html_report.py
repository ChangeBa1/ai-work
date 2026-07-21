"""HTML report via Jinja2 (same data source as JSON)."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Template

from vnc_agent.domain.run import TestRun
from vnc_agent.reporting.json_report import build_report_dict

_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>VNC Agent Report {{ report.run_id }}</title>
<style>
body{font-family:system-ui,sans-serif;margin:24px;background:#f6f7f9;color:#1a1a1a}
h1{font-size:1.4rem}.status{font-weight:700}
.status.passed{color:#0a7}.status.failed{color:#c22}.status.cancelled{color:#a60}
.step{background:#fff;border:1px solid #ddd;border-radius:8px;padding:12px 16px;margin:12px 0}
.iter{border-left:3px solid #88a;margin:8px 0 8px 8px;padding:8px 12px;background:#fafbff}
details{margin-top:6px} code{font-size:0.85em}
.warn-weak{
  background:#fff3cd;border:1px solid #e0a800;color:#664d03;
  padding:6px 10px;border-radius:4px;margin:6px 0;font-weight:600}
.label-effect-only{
  background:#e7f1ff;border:1px solid #6ea8fe;color:#084298;
  padding:6px 10px;border-radius:4px;margin:6px 0}
.label-trusted{
  background:#d1e7dd;border:1px solid #75b798;color:#0a3622;
  padding:6px 10px;border-radius:4px;margin:6px 0}
</style>
</head>
<body>
<h1>Test Run <code>{{ report.run_id }}</code></h1>
<p>Case: <code>{{ report.test_case_id }}</code></p>
<p>Status: <span class="status {{ report.status }}">{{ report.status }}</span></p>
<p>Started: {{ report.started_at }} · Ended: {{ report.ended_at }}</p>
{% for step in report.steps %}
<div class="step">
  <h2>Step {{ step.step_id }} —
    <span class="status {{ step.status }}">{{ step.status }}</span></h2>
  {% if step.weak_assertion_warning %}
  <div class="warn-weak" data-marker="weak_assertion_warning">
    ⚠ Weak assertion warning: only screen_changed / action-effect evidence —
    business result not verified (basis={{ step.basis }})
  </div>
  {% elif step.verification_label == 'effect_only_pass' %}
  <div class="label-effect-only" data-marker="effect_only_pass">
    Action effect only, not a verified business result (basis=action_effect_only)
  </div>
  {% elif step.verification_label == 'trusted_pass' %}
  <div class="label-trusted" data-marker="trusted_pass">
    Trusted pass — backed by business assertion (basis={{ step.basis }})
  </div>
  {% endif %}
  {% if step.failure_reason %}<p><strong>Failure:</strong> {{ step.failure_reason }}</p>{% endif %}
  {% for it in step.iterations %}
  <div class="iter">
    <strong>Iteration {{ it.iteration_index }}</strong>
    · verify: <code>{{ it.verification_result.status if it.verification_result else 'n/a' }}</code>
    {% if it.verification_result and it.verification_result.weak_assertion_warning %}
    · <span class="warn-weak" data-marker="weak_assertion_warning">weak assertion</span>
    {% endif %}
    {% if it.action_effect %}
    · action_effect: <code>{{ it.action_effect.status }}</code>
    {% endif %}
    <details>
      <summary>Evidence</summary>
      <p>Before: <code>{{ it.before_frame_path }}</code></p>
      <p>After: <code>{{ it.after_frame_path }}</code></p>
      <p>Action: <code>{{ it.semantic_action }}</code></p>
      <p>ActionEffect: <code>{{ it.action_effect }}</code></p>
      <p>Grounding: <code>{{ it.grounding_candidates }}</code></p>
      <p>Executable: <code>{{ it.executable_action }}</code></p>
      <p>Wait: <code>{{ it.wait_result }}</code></p>
      <p>Recovery: <code>{{ it.recovery_attempts }}</code></p>
    </details>
  </div>
  {% endfor %}
</div>
{% endfor %}
</body>
</html>
"""


def write_html_report(run: TestRun, path: str | Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    report = build_report_dict(run)
    html = Template(_TEMPLATE).render(report=report)
    path.write_text(html, encoding="utf-8")
    return str(path)
