#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

BASE = "https://tr3.trial-net.co.jp/Apps/TopReportNew/"
LOGIN_URL = "https://tr3.trial-net.co.jp/#/app/TOPReport"


class Error(RuntimeError):
    pass


def encode(value: Any) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    quoted = urllib.parse.quote(str(value), safe="~()*!.'-")
    return base64.b64encode(quoted.encode()).decode()


def week(value: str) -> str:
    value = value.strip().replace("-W", "_").replace("-", "_")
    if "_" not in value and len(value) >= 6:
        value = value[:4] + "_" + value[4:]
    year, number = value.split("_", 1)
    return f"{int(year):04d}_{int(number):02d}"


def plain_text(value: str) -> str:
    value = re.sub(r"<\s*br\s*/?\s*>", "\n", value, flags=re.I)
    value = re.sub(r"</\s*p\s*>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value).replace("\xa0", " ")
    return "\n".join(line.rstrip() for line in value.splitlines() if line.strip())


class Client:
    def __init__(self, browser_login: bool = False, login_timeout: int = 300) -> None:
        self.user = os.getenv("TOP_REPORT_USER_ID", "").strip()
        self.base = os.getenv("TOP_REPORT_BASE_URL", BASE)
        self.token = os.getenv("TOP_REPORT_TOKEN") or None
        if browser_login or not self.user:
            self.user = interactive_browser_login(login_timeout)

    def get(self, path: str, params: dict[str, Any] | None = None, auth: bool = True) -> dict[str, Any]:
        query = urllib.parse.urlencode({k: encode(v) for k, v in (params or {}).items()})
        request = urllib.request.Request(urllib.parse.urljoin(self.base, path) + ("?" + query if query else ""))
        request.add_header("Accept", "*/*")
        request.add_header("X-Requested-With", "XMLHttpRequest")
        if auth:
            if not self.token:
                self.authenticate()
            request.add_header("Authorization", "Bearer " + str(self.token))
            request.add_header("Userid", self.user)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            raise Error(f"API HTTP {exc.code}") from exc
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise Error(f"API request failed: {exc}") from exc
        if str(result.get("Code", "000")) not in {"0", "000"}:
            raise Error(str(result.get("Message") or result.get("Code")))
        return result

    def authenticate(self) -> None:
        token = self.get("generateToken", {"userId": self.user}, auth=False).get("token")
        if not token:
            raise Error("generateToken returned no token")
        self.token = str(token)

    def weeks(self) -> list[str]:
        data = self.get("DateService/GetYearWeekAtBegin")
        return [week(str(row["yearweek"])) for row in data.get("Table0", [])]

    def reports(self, kind: str, report_week: str, limit: int = 500) -> list[dict[str, Any]]:
        flag = 10 if kind == "top" else 15
        filters = [
            {"property": "yearweek", "value": week(report_week)},
            {"property": "person", "value": ""},
            {"property": "keyword", "value": ""},
        ]
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.get("TopService/GetToplist", {
                "keywordsearch": 0, "flg": flag, "start": (page - 1) * limit,
                "page": page, "limit": limit, "filter": filters,
                "employeecode": self.user, "order": "",
            })
            batch = data.get("Table0") or []
            rows.extend(batch)
            if len(batch) < limit:
                return rows
            page += 1

    def detail(self, row: dict[str, Any], kind: str) -> dict[str, Any]:
        path = "TopService/getOneTopDetails" if kind == "top" else "WeeklyService/getOneWeeklyDetails"
        return self.get(path, {"topid": f"{row['code']}_{week(str(row['yearweek']))}", "userid": self.user})

    def organization_roots(self) -> list[dict[str, Any]]:
        data = self.get("EmployeeService/getCompanyList", {"empcode": self.user})
        return [
            {
                "id": str(row["company_code"]),
                "name": str(row["company_name"]),
                "level": 1,
                "company_code": str(row["company_code"]),
                "has_children": str(row.get("nextLevel", "false")).lower() == "true",
            }
            for row in data.get("Table0", [])
        ]

    def organization_children(self, node: dict[str, Any]) -> list[dict[str, Any]]:
        level = int(node["level"])
        specifications = {
            1: ("EmployeeService/getJurisdiction", "belong1code", "belong1name", {"company_code": node["id"]}),
            2: ("EmployeeService/getDeploy", "belong2code", "belong2name", {
                "company_code": node["company_code"], "belong1code": node["id"]}),
            3: ("EmployeeService/getSection", "belong3code", "belong3name", {
                "company_code": node["company_code"], "belong1code": node["belong1code"],
                "belong2code": node["id"]}),
            4: ("EmployeeService/getArea", "areacode", "areaname", {
                "company_code": node["company_code"], "belong1code": node["belong1code"],
                "belong2code": node["belong2code"], "belong3code": node["id"]}),
            5: ("EmployeeService/getStore", "storecode", "storename", {
                "company_code": node["company_code"], "belong1code": node["belong1code"],
                "belong2code": node["belong2code"], "belong3code": node["belong3code"],
                "areacode": node["id"]}),
        }
        if level not in specifications or not node.get("has_children"):
            return []
        path, code_key, name_key, params = specifications[level]
        rows = self.get(path, params).get("Table0", [])
        children = []
        for row in rows:
            child = dict(node)
            child.update({
                "id": str(row[code_key]), "name": str(row[name_key]), "level": level + 1,
                "has_children": level < 5 and str(row.get("nextLevel", "false")).lower() == "true",
            })
            if level == 1:
                child["belong1code"] = child["id"]
            elif level == 2:
                child["belong2code"] = child["id"]
            elif level == 3:
                child["belong3code"] = child["id"]
            elif level == 4:
                child["areacode"] = child["id"]
            children.append(child)
        return children

    def find_organization(self, selector: str) -> dict[str, Any]:
        needle = selector.strip().casefold()
        if not needle:
            raise Error("organization name must not be empty")
        queue = self.organization_roots()
        partial: list[dict[str, Any]] = []
        while queue:
            node = queue.pop(0)
            name = str(node["name"]).strip().casefold()
            if needle == name or (selector.isdigit() and selector == str(node["id"])):
                return node
            if needle in name:
                partial.append(node)
            queue.extend(self.organization_children(node))
        if len(partial) == 1:
            return partial[0]
        if partial:
            names = ", ".join(str(item["name"]) for item in partial[:10])
            raise Error(f"organization name is ambiguous: {names}")
        raise Error(f"organization not found: {selector}")

    def organization_reports(
        self, organization: dict[str, Any], report_week: str, limit: int = 1000
    ) -> list[dict[str, Any]]:
        year, number = week(report_week).split("_")
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.get("TopService/getAttributeTop", {
                "value": organization["id"], "level": organization["level"],
                "year": year, "week": number, "empcode": self.user,
                "start": (page - 1) * limit, "page": page, "limit": limit,
            })
            batch = data.get("Table0") or []
            rows.extend(batch)
            if len(batch) < limit:
                return rows
            page += 1


def matches(row: dict[str, Any], selectors: list[str]) -> bool:
    code = str(row.get("code", "")).strip().casefold()
    name = str(row.get("name", "")).strip().casefold()
    return any(s.strip().casefold() == code if s.strip().isdigit() else s.strip().casefold() in name for s in selectors if s.strip())


def orca_command() -> str:
    configured = os.getenv("ORCA_CLI_COMMAND", "").strip()
    if configured:
        return configured
    if os.getenv("ORCA_DEV_REPO_ROOT") and shutil.which("orca-dev"):
        return "orca-dev"
    if sys.platform.startswith("linux") and shutil.which("orca-ide"):
        return "orca-ide"
    if shutil.which("orca"):
        return "orca"
    raise Error("Orca CLI is required for interactive browser login")


def run_orca(command: str, *args: str) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [command, *args, "--json"], text=True, capture_output=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise Error(f"Orca browser command failed: {exc}") from exc
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise Error(completed.stderr.strip() or "Orca returned invalid output") from exc
    if not result.get("ok"):
        message = result.get("error", {}).get("message", "unknown Orca error")
        raise Error(str(message))
    return result


def interactive_browser_login(timeout: int) -> str:
    command = orca_command()
    status = run_orca(command, "status")
    if not status.get("result", {}).get("runtime", {}).get("reachable"):
        run_orca(command, "open")
    created = run_orca(command, "tab", "create", "--url", LOGIN_URL)
    page_id = created.get("result", {}).get("browserPageId")
    if not page_id:
        raise Error("Orca did not return a browser page ID")
    print(
        "TOP Report login opened in Orca. Complete login in the browser; "
        "this process will continue automatically.",
        file=sys.stderr,
        flush=True,
    )
    expression = "window.loginApi?.apiLogin?.id || window.tCloud?.userData?.empcode || null"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            observed = run_orca(
                command, "eval", "--page", str(page_id), "--expression", expression
            )
            employee_id = observed.get("result", {}).get("result")
            origin = str(observed.get("result", {}).get("origin", ""))
            if employee_id and "tr3.trial-net.co.jp" in origin:
                print("TOP Report login detected; continuing with direct API requests.", file=sys.stderr)
                return str(employee_id).strip()
        except Error:
            pass
        time.sleep(2)
    raise Error(f"TOP Report login was not completed within {timeout} seconds")


def kinds(value: str) -> list[str]:
    return ["top", "weekly"] if value == "both" else [value]


def build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Read TOP and weekly reports through direct APIs")
    root.add_argument("--json", action="store_true")
    root.add_argument("--no-detail", action="store_true")
    root.add_argument("--browser-login", action="store_true", help="force interactive login in Orca")
    root.add_argument("--login-timeout", type=int, default=300, help="browser login timeout in seconds")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("weeks")
    organization = sub.add_parser("organization", help="latest TOP reports for an organization")
    organization.add_argument("organization", help="organization name or exact organization code")
    organization.add_argument("--week", help="specific report week, for example 2026-29")
    for name in ("latest", "history"):
        p = sub.add_parser(name)
        p.add_argument("person")
        p.add_argument("--type", choices=("top", "weekly", "both"), default="weekly")
        p.add_argument("--week", action="append")
    p = sub.add_parser("current")
    p.add_argument("people", nargs="+")
    p.add_argument("--type", choices=("top", "weekly", "both"), default="weekly")
    p.add_argument("--week")
    return root


def add_detail(client: Client, row: dict[str, Any], kind: str, enabled: bool) -> dict[str, Any]:
    item = dict(row)
    item["_report_type"] = kind
    if enabled:
        detail = client.detail(row, kind)
        item["detail"] = detail
        tables = detail.get("Table0") or []
        if tables and tables[0].get("remark"):
            item["content"] = plain_text(str(tables[0]["remark"]))
    return item


def run() -> int:
    args = build_parser().parse_args()
    client = Client(browser_login=args.browser_login, login_timeout=args.login_timeout)
    if args.command == "weeks":
        result = client.weeks()
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else "\n".join(result))
        return 0
    if args.command == "organization":
        organization = client.find_organization(args.organization)
        selected_weeks = [week(args.week)] if args.week else client.weeks()
        rows: list[dict[str, Any]] = []
        selected_week = ""
        for report_week in selected_weeks:
            rows = client.organization_reports(organization, report_week)
            if rows or args.week:
                selected_week = report_week
                break
        output = [add_detail(client, row, "top", not args.no_detail) for row in rows]
        if args.json:
            print(json.dumps({
                "organization": {"id": organization["id"], "name": organization["name"],
                                 "level": organization["level"]},
                "week": selected_week, "count": len(output), "reports": output,
            }, ensure_ascii=False, indent=2))
        elif output:
            print(f"Organization: {organization['name']} ({organization['id']}, level {organization['level']})")
            print(f"Week: {selected_week}; reports: {len(output)}")
            for item in output:
                print(f"[top] {item.get('yearweek')} {item.get('code')} {item.get('name')} {item.get('regDate', '')}")
                if item.get("content"):
                    print(item["content"])
        else:
            print("No TOP reports found for the organization.", file=sys.stderr)
        return 0 if output else 1
    selectors = args.people if args.command == "current" else [args.person]
    output: list[dict[str, Any]] = []
    for kind in kinds(args.type):
        available = client.weeks()
        selected = ([week(w) for w in args.week] if args.command != "current" and args.week
                    else [week(args.week)] if args.command == "current" and args.week else available)
        for report_week in selected:
            rows = client.reports(kind, report_week)
            if args.command == "current" and not args.week and not rows:
                continue
            found = [row for row in rows if matches(row, selectors)]
            output.extend(add_detail(client, row, kind, not args.no_detail) for row in found)
            if args.command in {"latest", "current"}:
                if found or (args.command == "current" and rows):
                    break
    output.sort(key=lambda row: str(row.get("yearweek", "")), reverse=True)
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    elif output:
        for item in output:
            print(f"[{item['_report_type']}] {item.get('yearweek')} {item.get('code')} {item.get('name')} {item.get('regDate', '')}")
            if item.get("content"):
                print(item["content"])
    else:
        print("No matching report found.", file=sys.stderr)
    return 0 if output else 1


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (Error, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
