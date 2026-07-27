---
name: trial-top-reports
description: Query Trial's internal TOP Report system through its read-only HTTP APIs for employee and organization TOP reports and weekly reports, with interactive browser login when credentials are unavailable. Use when Codex needs to fetch, display, summarize, or export a person's latest or historical TOP report/周报, retrieve several employees' current reports, fetch every latest TOP report under an 所属/organization such as T.R.E.-China, list reporting weeks, distinguish TOP reports from weekly reports, or open a login browser and continue automatically. Use browser automation only to establish identity; retrieve report data through direct APIs.
---

# Trial TOP Reports

Use the bundled script to retrieve reports directly from the API. Use the browser only if authentication discovery must be repeated; never use it as the report-fetching implementation.

## Setup

If the caller's authorized employee number is already available, set it to skip interactive login:

```bash
export TOP_REPORT_USER_ID='employee-number'
```

Never print, persist, or commit the employee number or generated Bearer token. The script obtains a short-lived token from `generateToken`. Accept `TOP_REPORT_TOKEN` only when the user explicitly supplies an existing token.

If `TOP_REPORT_USER_ID` is missing, run the requested command normally. The script must open the TOP Report login page in Orca, wait up to five minutes for the user to authenticate, read the current employee ID from the authenticated page, obtain the API token, and continue automatically. The user enters credentials only in the browser; never ask the user to paste a password into the terminal or conversation.

Force a fresh interactive login even when the environment variable exists with `--browser-login`. Change the wait using `--login-timeout SECONDS`.

Set the script path relative to this Skill directory:

```bash
python3 scripts/top_reports.py --help
```

## Choose the operation

- Latest report for one person: `latest PERSON --type top|weekly`
- Current reporting week's reports for several people: `current PERSON... --type top|weekly`
- All available history for one person: `history PERSON --type top|weekly|both`
- Specific week: add `--week YYYY-WW`
- Machine-readable output: add the global `--json` flag before the subcommand
- List metadata only: add the global `--no-detail` flag
- Available weeks: `weeks`
- Latest TOP reports for an organization: `organization ORG_NAME`

Treat a numeric selector as an exact employee-code match. Treat other selectors as case-insensitive name substrings. For “latest”, scan reporting weeks newest to oldest until that employee has a report. For “current”, use the newest week that contains any report data; the calendar's newest week can be empty immediately after a week boundary.

## Examples

```bash
python3 scripts/top_reports.py latest 10191842 --type top
python3 scripts/top_reports.py --browser-login latest 10191842 --type top
python3 scripts/top_reports.py --json current 1560 10191842 --type weekly
python3 scripts/top_reports.py history 1560 --type weekly
python3 scripts/top_reports.py latest 1560 --type weekly --week 2026-29
python3 scripts/top_reports.py --json organization 'T.R.E.-China'
python3 scripts/top_reports.py --no-detail organization 'T.R.E.-China' --week 2026-29
```

Keep TOP and weekly requests distinct:

- TOP list flag: `10`; detail: `TopService/getOneTopDetails`
- Weekly list flag: `15`; detail: `WeeklyService/getOneWeeklyDetails`
- Organization TOP list: `TopService/getAttributeTop`; resolve organization names through the EmployeeService hierarchy

For an organization request, resolve the organization name to its ID and tree level without hardcoding it. Scan weeks newest to oldest and use the first week with organization TOP reports. Return all reports in that organization subtree; request each TOP detail unless `--no-detail` is specified.

Do not call write endpoints such as likes, comments, favorites, history insertion, or modification. Report retrieval is read-only. Browser automation is permitted only for login and identity discovery; all report data must still come from HTTP APIs. Preserve the source language when the user asks for report content; strip HTML presentation tags for readable text. Summarize only when requested.

Read [references/api.md](references/api.md) only when debugging the API, changing request behavior, or adding endpoints.
