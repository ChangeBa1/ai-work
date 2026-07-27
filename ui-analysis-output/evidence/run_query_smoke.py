from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(r"D:\POJ\NodeMaster")
BUNDLE = ROOT / "ui-analysis-output" / "ui-analysis-bundle-v1"
EVIDENCE = ROOT / "ui-analysis-output" / "evidence"


def query(name: str, option: str, value: str) -> object:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [
            "uv", "run", "vnc-agent", "ui-index", "query",
            "--bundle-dir", str(BUNDLE), option, value, "--json",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{name}: {result.stderr}")
    value_json = json.loads(result.stdout)
    (EVIDENCE / name).write_bytes(
        (json.dumps(value_json, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    return value_json


callcenter_app = (
    "screen.pos4ucloud.source.pos4ubo.pos4ubackoffice.views."
    "callcentermenu.applogdownload"
)
callcenter_setting = (
    "screen.pos4ucloud.source.pos4ubo.pos4ubackoffice.views."
    "callcentermenu.settingmaintenance"
)
backoffice_index = (
    "screen.pos4ucloud.source.pos4ubo.pos4ubackoffice.views."
    "backofficemenu.index"
)
main_menu = (
    "screen.source.winpos.ui.winpos.ui.mainmenuview.winpos.ui."
    "mainmenuview.mainmenuview"
)

screen_result = query("query-screen.json", "--screen", callcenter_app)
query("query-screen-setting-maintenance.json", "--screen", callcenter_setting)
query("query-alias-element.json", "--alias", "dummy")
query("query-alias-mainmenu.json", "--alias", "OpenCount_ChangeDisplay")
query("query-role-button.json", "--role", "button")
query("query-role-text-field.json", "--role", "text_field")
query("query-text.json", "--text", "検索")
query("query-transition-from.json", "--transition-from", backoffice_index)
query("query-transition-from-mainmenu.json", "--transition-from", main_menu)

cloud_transitions = json.loads((BUNDLE / "transitions.jsonl").read_text(encoding="utf-8").splitlines()[0])
all_transitions = [
    json.loads(line)
    for line in (BUNDLE / "transitions.jsonl").read_text(encoding="utf-8").splitlines()
]
cloud_transitions = next(
    row for row in all_transitions
    if row["from_screen_id"] == backoffice_index
    and row["to_screen_id"] != row["from_screen_id"]
)
query(
    "query-transition-trigger.json",
    "--transition-trigger",
    cloud_transitions["trigger_element_id"],
)
query(
    "query-transition-to-callcenter-app.json",
    "--transition-to",
    callcenter_app,
)

screens = [
    json.loads(line)
    for line in (BUNDLE / "screens.jsonl").read_text(encoding="utf-8").splitlines()
]
screen_alias_matches = [
    row for row in screens if "/CallCenterMenu/AppLogDownload" in row["aliases"]
]
elements = [
    json.loads(line)
    for line in (BUNDLE / "elements.jsonl").read_text(encoding="utf-8").splitlines()
]
host_ids = {
    row["screen_id"]: sorted(
        item["element_id"] for item in elements
        if item["screen_id"] == row["screen_id"]
        and item.get("metadata", {}).get("source_path", "").endswith(
            r"Views\Shared\_AppLogDownload.cshtml"
        )
    )
    for row in screens
    if row["screen_id"].endswith(
        (".backofficemenu.applogdownload", ".callcentermenu.applogdownload")
    )
}
custom = {
    "screen_alias": {
        "alias": "/CallCenterMenu/AppLogDownload",
        "matches": screen_alias_matches,
    },
    "shared_partial_host_ids": host_ids,
    "host_id_sets_disjoint": (
        len(host_ids) == 2
        and not set.intersection(*(set(value) for value in host_ids.values()))
    ),
}
(EVIDENCE / "query-custom-semantic.json").write_bytes(
    (json.dumps(custom, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
)
print(json.dumps(custom, ensure_ascii=False, indent=2))
