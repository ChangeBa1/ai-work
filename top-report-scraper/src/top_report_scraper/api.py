from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable


BASE_URL = "https://tr3.trial-net.co.jp/Apps/TopReportNew/"


class ApiError(RuntimeError):
    pass


def encode_parameter(value: Any) -> str:
    """Match the web app's encodeURIComponent -> Base64 query encoding."""
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    encoded = urllib.parse.quote(str(value), safe="~()*!.'-")
    return base64.b64encode(encoded.encode("utf-8")).decode("ascii")


def normalize_week(value: str) -> str:
    value = value.strip().replace("-W", "_").replace("-", "_")
    if "_" not in value and len(value) >= 6:
        value = f"{value[:4]}_{int(value[4:]):02d}"
    year, week = value.split("_", 1)
    return f"{int(year):04d}_{int(week):02d}"


@dataclass
class TopReportClient:
    user_id: str
    base_url: str = BASE_URL
    timeout: float = 30.0
    token: str | None = None

    @classmethod
    def from_env(cls) -> "TopReportClient":
        user_id = os.getenv("TOP_REPORT_USER_ID", "").strip()
        if not user_id:
            raise ApiError("请设置环境变量 TOP_REPORT_USER_ID（你的员工编号）")
        return cls(
            user_id=user_id,
            base_url=os.getenv("TOP_REPORT_BASE_URL", BASE_URL),
            token=os.getenv("TOP_REPORT_TOKEN") or None,
        )

    def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        query = urllib.parse.urlencode(
            {key: encode_parameter(value) for key, value in (params or {}).items()}
        )
        url = urllib.parse.urljoin(self.base_url, path)
        if query:
            url += "?" + query
        request = urllib.request.Request(url)
        request.add_header("Accept", "*/*")
        request.add_header("X-Requested-With", "XMLHttpRequest")
        if authenticated:
            if not self.token:
                self.authenticate()
            request.add_header("Authorization", f"Bearer {self.token}")
            request.add_header("Userid", self.user_id)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:500]
            raise ApiError(f"API HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"无法连接 TOP Report API: {exc.reason}") from exc
        try:
            result = json.loads(raw.decode("utf-8", "replace"))
        except json.JSONDecodeError as exc:
            raise ApiError("API 返回了非 JSON 数据") from exc
        code = str(result.get("Code", "000"))
        if code not in {"0", "000"}:
            raise ApiError(str(result.get("Message") or f"API Code={code}"))
        return result

    def authenticate(self) -> None:
        result = self._request(
            "generateToken", {"userId": self.user_id}, authenticated=False
        )
        token = result.get("token")
        if not isinstance(token, str) or not token:
            raise ApiError("generateToken 没有返回有效令牌")
        self.token = token

    def weeks(self) -> list[str]:
        result = self._request("DateService/GetYearWeekAtBegin")
        return [normalize_week(str(row["yearweek"])) for row in result.get("Table0", [])]

    def current_week(self) -> str:
        weeks = self.weeks()
        if not weeks:
            raise ApiError("API 没有返回可用周次")
        return weeks[0]

    def latest_report_week(self, report_type: str) -> tuple[str, list[dict[str, Any]]]:
        """Return the newest week that actually has reports and its already-fetched rows."""
        for week in self.weeks():
            rows = self.list_reports(report_type, week)
            if rows:
                return week, rows
        raise ApiError(f"没有找到任何 {report_type} 报告周")

    def list_reports(
        self,
        report_type: str,
        week: str,
        *,
        page_size: int = 200,
    ) -> list[dict[str, Any]]:
        report_type = report_type.lower()
        if report_type not in {"top", "weekly"}:
            raise ValueError("report_type 必须是 top 或 weekly")
        week = normalize_week(week)
        flag = 10 if report_type == "top" else 15
        rows: list[dict[str, Any]] = []
        page = 1
        while True:
            filters = [
                {"property": "yearweek", "value": week},
                {"property": "person", "value": ""},
                {"property": "keyword", "value": ""},
            ]
            result = self._request(
                "TopService/GetToplist",
                {
                    "keywordsearch": 0,
                    "flg": flag,
                    "start": (page - 1) * page_size,
                    "page": page,
                    "limit": page_size,
                    "filter": filters,
                    "employeecode": self.user_id,
                    "order": "",
                },
            )
            batch = result.get("Table0") or []
            rows.extend(batch)
            if len(batch) < page_size:
                break
            page += 1
        return rows

    def report_detail(self, report: dict[str, Any], report_type: str) -> dict[str, Any]:
        week = normalize_week(str(report["yearweek"]))
        code = str(report["code"])
        if report_type == "weekly":
            path = "WeeklyService/getOneWeeklyDetails"
        elif report_type == "top":
            path = "TopService/getOneTopDetails"
        else:
            raise ValueError("report_type 必须是 top 或 weekly")
        return self._request(path, {"topid": f"{code}_{week}", "userid": self.user_id})


def matches_person(report: dict[str, Any], selectors: Iterable[str]) -> bool:
    code = str(report.get("code", "")).strip().casefold()
    name = str(report.get("name", "")).strip().casefold()
    for selector in selectors:
        needle = selector.strip().casefold()
        if needle and (needle == code or needle in name):
            return True
    return False
