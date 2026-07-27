from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .api import ApiError, TopReportClient, matches_person, normalize_week


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="top-report", description="通过 HTTP API 查看 TOP 报告和周报"
    )
    root.add_argument("--json", action="store_true", help="输出完整 JSON")
    root.add_argument("--no-detail", action="store_true", help="只输出列表，不请求详情")
    sub = root.add_subparsers(dest="command", required=True)

    sub.add_parser("weeks", help="列出 API 提供的周次")

    current = sub.add_parser("current", help="查看一个或多个人的本周报告")
    current.add_argument("people", nargs="+", help="员工编号或姓名片段")
    current.add_argument("--type", choices=["weekly", "top", "both"], default="weekly")
    current.add_argument("--week", help="覆盖当前周，例如 2026-30")

    person = sub.add_parser("person", help="查看某人的所有历史报告")
    person.add_argument("person", help="员工编号或姓名片段")
    person.add_argument("--type", choices=["weekly", "top", "both"], default="weekly")
    person.add_argument("--week", action="append", help="只查指定周；可重复")
    return root


def report_types(value: str) -> list[str]:
    return ["top", "weekly"] if value == "both" else [value]


def attach_details(
    client: TopReportClient, rows: list[dict[str, Any]], report_type: str, enabled: bool
) -> list[dict[str, Any]]:
    if not enabled:
        return rows
    enriched = []
    for row in rows:
        item = dict(row)
        item["detail"] = client.report_detail(row, report_type)
        enriched.append(item)
    return enriched


def print_human(items: list[dict[str, Any]]) -> None:
    if not items:
        print("没有找到匹配的报告。", file=sys.stderr)
        return
    for item in items:
        print(
            f"[{item['_report_type']}] {item.get('yearweek', '-')} "
            f"{item.get('code', '-')} {item.get('name', '-')} "
            f"提交: {item.get('regDate', '未提交')}"
        )
        detail = item.get("detail")
        if detail:
            print(json.dumps(detail, ensure_ascii=False, indent=2))


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    client = TopReportClient.from_env()
    if args.command == "weeks":
        weeks = client.weeks()
        print(json.dumps(weeks, ensure_ascii=False, indent=2) if args.json else "\n".join(weeks))
        return 0

    selectors = args.people if args.command == "current" else [args.person]
    if args.command == "current":
        weeks = [normalize_week(args.week)] if args.week else []
    else:
        weeks = [normalize_week(w) for w in args.week] if args.week else client.weeks()

    output: list[dict[str, Any]] = []
    for report_type in report_types(args.type):
        if args.command == "current" and not weeks:
            _, current_rows = client.latest_report_week(report_type)
            report_batches = [current_rows]
        else:
            report_batches = [client.list_reports(report_type, week) for week in weeks]
        for batch in report_batches:
            rows = [row for row in batch if matches_person(row, selectors)]
            rows = attach_details(client, rows, report_type, not args.no_detail)
            for row in rows:
                row["_report_type"] = report_type
            output.extend(rows)

    output.sort(key=lambda row: str(row.get("yearweek", "")), reverse=True)
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_human(output)
    return 0 if output else 1


def main() -> None:
    try:
        raise SystemExit(run())
    except (ApiError, ValueError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
