from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from vnc_agent.ui_index.repository import UiIndexBundle


ROOT = Path(r"D:\POJ\NodeMaster")
OUTPUT = ROOT / "ui-analysis-output"
BUNDLE = OUTPUT / "ui-analysis-bundle-v1"
EVIDENCE = OUTPUT / "evidence"
REPORT = OUTPUT / "validation-report.json"
ALLOWED_FILES = {
    "manifest.yaml",
    "screens.jsonl",
    "elements.jsonl",
    "transitions.jsonl",
    "flows.jsonl",
    "diagnostics.jsonl",
}
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


issues: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        issues.append(message)


def load_jsonl(name: str) -> tuple[list[dict], dict]:
    path = BUNDLE / name
    raw = path.read_bytes()
    check(not raw.startswith(b"\xef\xbb\xbf"), f"{name}: UTF-8 BOM is forbidden")
    check(b"\r" not in raw, f"{name}: CR/CRLF newline found")
    check(not raw or raw.endswith(b"\n"), f"{name}: missing final LF")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        issues.append(f"{name}: invalid UTF-8: {exc}")
        text = raw.decode("utf-8", errors="replace")
    rows: list[dict] = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(f"{name}:{line_number}: invalid JSON: {exc}")
            continue
        check(isinstance(value, dict), f"{name}:{line_number}: row is not an object")
        if isinstance(value, dict):
            rows.append(value)
    return rows, {
        "sha256": hashlib.sha256(raw).hexdigest(),
        "record_count": len(rows),
        "utf8_no_bom": not raw.startswith(b"\xef\xbb\xbf"),
        "lf_only": b"\r" not in raw,
    }


def no_duplicates(values: list, label: str) -> None:
    check(len(values) == len(dict.fromkeys(values)), f"{label}: duplicate list values")


def detect_parent_cycles(records: list[dict], id_key: str, parent_key: str, label: str) -> None:
    parents = {
        record[id_key]: record.get(parent_key)
        for record in records
        if record.get(parent_key)
    }
    for start in parents:
        seen: set[str] = set()
        node: str | None = start
        while node in parents:
            if node in seen:
                issues.append(f"{label}: parent cycle involving {start}")
                break
            seen.add(node)
            node = parents.get(node)


def query_result(name: str):
    path = EVIDENCE / name
    check(path.exists(), f"missing query evidence: {name}")
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        issues.append(f"{name}: invalid query evidence: {exc}")
        return None


def evidence_paths(value: str | None) -> list[str]:
    result: list[str] = []
    for part in (value or "").split(";"):
        match = re.match(r"\s*(.+?\.(?:xaml|cs|cshtml|html|htm|xml)):(\d+)", part, re.I)
        if match:
            result.append(match.group(1).strip())
    return result


def main() -> int:
    actual_files = {path.name for path in BUNDLE.iterdir() if path.is_file()}
    check(actual_files == ALLOWED_FILES, f"bundle file set mismatch: {sorted(actual_files)}")
    check(
        not any(path.is_dir() for path in BUNDLE.iterdir()),
        "bundle contains a nested directory",
    )
    manifest_raw = (BUNDLE / "manifest.yaml").read_bytes()
    check(
        not manifest_raw.startswith(b"\xef\xbb\xbf"),
        "manifest.yaml: UTF-8 BOM is forbidden",
    )
    check(b"\r" not in manifest_raw, "manifest.yaml: CR/CRLF newline found")
    manifest = yaml.safe_load(manifest_raw.decode("utf-8"))

    rows: dict[str, list[dict]] = {}
    file_audit: dict[str, dict] = {}
    for name in (
        "screens.jsonl",
        "elements.jsonl",
        "transitions.jsonl",
        "flows.jsonl",
        "diagnostics.jsonl",
    ):
        rows[name], file_audit[name] = load_jsonl(name)
        entry = manifest["content_files"][name]
        check(
            entry["sha256"] == file_audit[name]["sha256"],
            f"{name}: manifest sha256 mismatch",
        )
        check(
            entry["record_count"] == file_audit[name]["record_count"],
            f"{name}: manifest record_count mismatch",
        )

    screens = rows["screens.jsonl"]
    elements = rows["elements.jsonl"]
    transitions = rows["transitions.jsonl"]
    flows = rows["flows.jsonl"]
    diagnostics = rows["diagnostics.jsonl"]
    screen_ids = {row["screen_id"] for row in screens}
    element_ids = {row["element_id"] for row in elements}
    element_by_id = {row["element_id"]: row for row in elements}
    screen_by_id = {row["screen_id"]: row for row in screens}
    transition_ids = {row["transition_id"] for row in transitions}

    for name, data, key in (
        ("screens", screens, "screen_id"),
        ("elements", elements, "element_id"),
        ("transitions", transitions, "transition_id"),
        ("flows", flows, "flow_id"),
        ("diagnostics", diagnostics, "diagnostic_id"),
    ):
        ids = [row[key] for row in data]
        check(len(ids) == len(set(ids)), f"{name}: duplicate IDs")
        for value in ids:
            check(bool(ID_PATTERN.fullmatch(value)), f"{name}: invalid ID {value!r}")

    detect_parent_cycles(screens, "screen_id", "parent_screen_id", "screens")
    detect_parent_cycles(elements, "element_id", "parent_element_id", "elements")
    for screen in screens:
        no_duplicates(screen["visible_titles"], f"{screen['screen_id']}.visible_titles")
        no_duplicates(screen["aliases"], f"{screen['screen_id']}.aliases")
        check(
            screen.get("parent_screen_id") in screen_ids
            if screen.get("parent_screen_id")
            else True,
            f"{screen['screen_id']}: dangling parent screen",
        )
        check(bool(screen["aliases"]), f"{screen['screen_id']}: evidence-backed screen aliases empty")
        for path in evidence_paths(screen.get("source_evidence")):
            check((ROOT / path).is_file(), f"{screen['screen_id']}: source evidence missing {path}")

    role_action_failures: list[str] = []
    for element in elements:
        check(element["screen_id"] in screen_ids, f"{element['element_id']}: dangling screen")
        check(
            element.get("parent_element_id") in element_ids
            if element.get("parent_element_id")
            else True,
            f"{element['element_id']}: dangling parent element",
        )
        for key in (
            "visible_texts",
            "aliases",
            "supported_actions",
            "anchors",
            "expected_effects",
        ):
            no_duplicates(element.get(key, []), f"{element['element_id']}.{key}")
        for anchor in element.get("anchors", []):
            check(anchor in element_ids, f"{element['element_id']}: dangling anchor {anchor}")
        neighbor_keys: list[tuple[str, str]] = []
        for neighbor in element.get("neighbors", []):
            target = neighbor["element_id"]
            check(target in element_ids, f"{element['element_id']}: dangling neighbor {target}")
            neighbor_keys.append((neighbor["direction"], target))
        no_duplicates(neighbor_keys, f"{element['element_id']}.neighbors")
        actions = set(element["supported_actions"])
        required = {
            "text_field": {"type_text", "set_value"},
            "combobox": {"select"},
            "list_view": {"select", "scroll"},
        }.get(element["role"])
        if required and not required.intersection(actions):
            role_action_failures.append(element["element_id"])
        named_interactive = bool(element.get("metadata", {}).get("stable_locator")) and bool(actions)
        check(
            not named_interactive or bool(element["aliases"]),
            f"{element['element_id']}: named interactive element aliases empty",
        )
        for path in evidence_paths(element.get("source_evidence")):
            check((ROOT / path).is_file(), f"{element['element_id']}: source evidence missing {path}")
        related = ([element.get("parent_element_id")] + element.get("anchors", [])
                   + [row["element_id"] for row in element.get("neighbors", [])])
        for related_id in [value for value in related if value]:
            if related_id in element_by_id:
                check(
                    element_by_id[related_id]["screen_id"] == element["screen_id"],
                    f"{element['element_id']}: cross-host relationship {related_id}",
                )
    check(not role_action_failures, f"role/action coverage failures: {len(role_action_failures)}")

    for transition in transitions:
        check(
            transition["from_screen_id"] in screen_ids,
            f"{transition['transition_id']}: dangling from screen",
        )
        check(
            transition["to_screen_id"] in screen_ids,
            f"{transition['transition_id']}: dangling to screen",
        )
        check(
            transition["trigger_element_id"] in element_ids,
            f"{transition['transition_id']}: dangling trigger",
        )
        if transition["trigger_element_id"] in element_by_id:
            check(
                element_by_id[transition["trigger_element_id"]]["screen_id"]
                == transition["from_screen_id"],
                f"{transition['transition_id']}: trigger does not belong to from_screen",
            )
        transition_blob = json.dumps(transition, ensure_ascii=False).lower()
        check(
            not (
                transition["from_screen_id"] == transition["to_screen_id"]
                and transition["transition_type"] == "state_change"
                and any(token in transition_blob for token in (
                    "navigate", "url.action", "window.location", "redirect", "request/"
                ))
            ),
            f"{transition['transition_id']}: navigation encoded as self state_change",
        )
        for path in evidence_paths(transition.get("source_evidence")):
            check((ROOT / path).is_file(), f"{transition['transition_id']}: source evidence missing {path}")
        for guard in transition.get("guards", []):
            if "element_id" in guard:
                check(
                    guard["element_id"] in element_ids,
                    f"{transition['transition_id']}: dangling guard",
                )
    for flow in flows:
        check(flow["start_screen_id"] in screen_ids, f"{flow['flow_id']}: dangling start")
        check(
            flow["completion_screen_id"] in screen_ids,
            f"{flow['flow_id']}: dangling completion",
        )
        check(bool(flow["steps"]), f"{flow['flow_id']}: empty steps")
        for step in flow["steps"]:
            if "transition_id" in step:
                check(step["transition_id"] in transition_ids, f"{flow['flow_id']}: dangling step")
            if "element_id" in step:
                check(step["element_id"] in element_ids, f"{flow['flow_id']}: dangling element step")

    for diagnostic in diagnostics:
        check(
            diagnostic["confidence"]["level"] != "confirmed",
            f"{diagnostic['diagnostic_id']}: confirmed diagnostic",
        )
        target = diagnostic.get("target_ref") or {}
        for key, namespace in (
            ("screen_id", screen_ids),
            ("element_id", element_ids),
            ("transition_id", transition_ids),
        ):
            if target.get(key):
                check(target[key] in namespace, f"{diagnostic['diagnostic_id']}: dangling target")

    confirmed_records = sum(
        1
        for group in (screens, elements, transitions, flows, diagnostics)
        for row in group
        if row["confidence"]["level"] == "confirmed"
    )
    check(confirmed_records == 0, "source-only bundle contains confirmed records")
    direct_transitions = sum(
        1 for row in transitions if row["from_screen_id"] != row["to_screen_id"]
    )
    check(bool(transitions), "transitions file is analytically empty")
    check(direct_transitions > 0, "no cross-screen transition was analyzed")
    check(bool(flows), "flows file is empty")

    inventory = json.loads((EVIDENCE / "ui-inventory.json").read_text(encoding="utf-8"))
    inventory_paths = [row["source_path"] for row in inventory]
    no_duplicates(inventory_paths, "inventory.source_path")
    valid_statuses = {
        "screen",
        "component",
        "resource_template",
        "dynamic_diagnostic",
        "excluded",
    }
    check(
        all(row["status"] in valid_statuses for row in inventory),
        "inventory has an undisposed status",
    )
    for row in inventory:
        if row["status"] in {"screen", "component", "dynamic_diagnostic"}:
            check(
                row.get("mapped_screen_id") in screen_ids,
                f"inventory mapping missing/dangling: {row['source_path']}",
            )
        for mapped in row.get("mapped_screen_ids", []):
            check(mapped in screen_ids, f"inventory multi-host mapping dangling: {row['source_path']}")

    element_counts = Counter(row["screen_id"] for row in elements)
    callcenter_partial_pages = [
        row for row in screens
        if "\\Views\\CallCenterMenu\\".lower()
        in row.get("metadata", {}).get("source_path", "").lower()
    ]
    for screen in callcenter_partial_pages:
        check(
            element_counts[screen["screen_id"]] > 0,
            f"CallCenter shared-partial host has zero elements: {screen['screen_id']}",
        )
    shared_partial_rows = [
        row for row in inventory
        if row["status"] == "component"
        and "\\Views\\Shared\\_".lower() in row["source_path"].lower()
        and len(row.get("mapped_screen_ids", [])) > 1
    ]
    check(bool(shared_partial_rows), "no shared partial has an evidenced M:N host mapping")
    inventory_by_path = {row["source_path"].lower(): row for row in inventory}
    for row in inventory:
        if row["status"] != "component" or "\\views\\shared\\_" not in row["source_path"].lower():
            continue
        partial_name = Path(row["source_path"]).stem
        explicit_wrappers = []
        for screen in screens:
            source_path = screen.get("metadata", {}).get("source_path")
            if not source_path or not source_path.lower().endswith(".cshtml"):
                continue
            text = (ROOT / source_path).read_text(encoding="utf-8-sig", errors="ignore")
            if re.search(rf"['\"]{re.escape(partial_name)}['\"]", text, re.I):
                explicit_wrappers.append(screen["screen_id"])
        if len(set(explicit_wrappers)) > 1:
            check(
                set(explicit_wrappers).issubset(set(row.get("mapped_screen_ids", []))),
                f"shared partial mapped to only one/subset of explicit hosts: {row['source_path']}",
            )

    transition_elements = {row["trigger_element_id"] for row in transitions}
    diagnostic_elements = {
        (row.get("target_ref") or {}).get("element_id")
        for row in diagnostics
        if row["category"] == "uncertain_transition"
    }
    for element in elements:
        if element.get("metadata", {}).get("static_destination"):
            check(
                element["element_id"] in transition_elements
                or element["element_id"] in diagnostic_elements,
                f"route/navigation evidence has neither transition nor diagnostic: {element['element_id']}",
            )

    query_screen = query_result("query-screen.json")
    query_text = query_result("query-text.json")
    query_button = query_result("query-role-button.json")
    query_text_field = query_result("query-role-text-field.json")
    query_from = query_result("query-transition-from.json")
    query_trigger = query_result("query-transition-trigger.json")
    query_alias_element = query_result("query-alias-element.json")
    query_alias_mainmenu = query_result("query-alias-mainmenu.json")
    query_custom = query_result("query-custom-semantic.json")
    check(isinstance(query_screen, dict) and bool(query_screen), "screen query returned empty")
    for label, value in (
        ("text", query_text),
        ("role=button", query_button),
        ("role=text_field", query_text_field),
        ("transition-from", query_from),
        ("transition-trigger", query_trigger),
        ("alias-element", query_alias_element),
        ("alias-mainmenu", query_alias_mainmenu),
    ):
        check(isinstance(value, list) and len(value) > 0, f"{label} query returned empty")
    check(
        isinstance(query_custom, dict)
        and len(query_custom.get("screen_alias", {}).get("matches", [])) == 1,
        "screen alias semantic query did not return exactly one screen",
    )
    check(
        isinstance(query_custom, dict) and query_custom.get("host_id_sets_disjoint") is True,
        "shared partial host-specific ID sets overlap",
    )

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    validator = subprocess.run(
        [
            "uv",
            "run",
            "vnc-agent",
            "ui-index",
            "validate",
            str(BUNDLE),
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
        check=False,
    )
    check(validator.returncode == 0, "official validator exit code is nonzero")
    check("0 issues" in validator.stdout, "official validator did not report 0 issues")

    try:
        loaded = UiIndexBundle.load(BUNDLE)
        load_result = {
            "ok": True,
            "bundle_id": loaded.manifest.bundle_id,
            "schema_version": loaded.manifest.schema_version,
            "counts": {
                "screens": len(loaded.screens),
                "elements": len(loaded.elements),
                "transitions": len(loaded.transitions),
                "flows": len(loaded.flows),
                "diagnostics": len(loaded.diagnostics),
            },
        }
    except Exception as exc:
        issues.append(f"UiIndexBundle.load failed: {exc}")
        load_result = {"ok": False, "error": repr(exc)}

    stability = json.loads(
        (EVIDENCE / "stability-report.json").read_text(encoding="utf-8-sig")
    )
    check(stability["stable"] is True, "repeat-generation stability failed")

    state_nonempty = sum(1 for row in elements if row.get("state_conditions"))
    effects_nonempty = sum(1 for row in elements if row.get("expected_effects"))
    anchors_nonempty = sum(1 for row in elements if row.get("anchors"))
    neighbors_nonempty = sum(1 for row in elements if row.get("neighbors"))
    bounds_nonnull = sum(1 for row in elements if row.get("normalized_bounds") is not None)
    calibration_screen_ids = {
        (row.get("target_ref") or {}).get("screen_id")
        for row in diagnostics
        if row["category"] == "requires_runtime_calibration"
    }
    check(
        screen_ids.issubset(calibration_screen_ids),
        "source-only null geometry is not covered by per-screen calibration diagnostics",
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ok": len(issues) == 0,
        "issues": issues,
        "official_validator": {
            "command": f"uv run vnc-agent ui-index validate {BUNDLE}",
            "stdout": validator.stdout.strip(),
            "stderr": validator.stderr.strip(),
            "exit_code": validator.returncode,
            "issue_count": 0 if validator.returncode == 0 else None,
        },
        "ui_index_bundle_load": load_result,
        "bundle_files": sorted(actual_files),
        "content_file_audit": file_audit,
        "inventory": {
            "total": len(inventory),
            "unique_files": len(set(inventory_paths)),
            "disposed": len(inventory),
            "disposition_rate": 1.0,
            "by_status": dict(sorted(Counter(row["status"] for row in inventory).items())),
        },
        "semantic_audit": {
            "direct_cross_screen_transitions": direct_transitions,
            "state_change_transitions": len(transitions) - direct_transitions,
            "flows": len(flows),
            "elements_with_state_conditions": state_nonempty,
            "elements_with_expected_effects": effects_nonempty,
            "elements_with_anchors": anchors_nonempty,
            "elements_with_neighbors": neighbors_nonempty,
            "region_distribution": dict(sorted(Counter(row["region"] for row in elements).items())),
            "normalized_bounds_nonnull": bounds_nonnull,
            "runtime_calibration_diagnostic_screens": len(calibration_screen_ids & screen_ids),
            "confirmed_records": confirmed_records,
            "role_action_failures": len(role_action_failures),
        },
        "query_smoke_tests": {
            "screen_id": {"ok": isinstance(query_screen, dict), "result_count": 1 if query_screen else 0},
            "visible_text": {"ok": bool(query_text), "result_count": len(query_text or [])},
            "role_button": {"ok": bool(query_button), "result_count": len(query_button or [])},
            "role_text_field": {"ok": bool(query_text_field), "result_count": len(query_text_field or [])},
            "transition_from": {"ok": bool(query_from), "result_count": len(query_from or [])},
            "transition_trigger": {"ok": bool(query_trigger), "result_count": len(query_trigger or [])},
            "alias_element": {"ok": bool(query_alias_element), "result_count": len(query_alias_element or [])},
            "alias_mainmenu": {"ok": bool(query_alias_mainmenu), "result_count": len(query_alias_mainmenu or [])},
            "screen_alias": {
                "ok": bool((query_custom or {}).get("screen_alias", {}).get("matches")),
                "result_count": len((query_custom or {}).get("screen_alias", {}).get("matches", [])),
                "note": "Official CLI --alias is element-only; screen alias was checked on the loaded screen records.",
            },
        },
        "repeat_generation": stability,
        "safety": {
            "runtime_instance_used": False,
            "actions_performed": [],
            "operations_not_performed": [
                "production/test process injection",
                "payment/refund/void/settlement",
                "physical device operation",
                "physical click or keyboard injection",
            ],
            "geometry_policy": (
                "No test runtime was identified, so normalized_bounds are null rather "
                "than fabricated; every screen has requires_runtime_calibration."
            ),
        },
    }
    REPORT.write_bytes(
        (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
