# API reference

Base URL: `https://tr3.trial-net.co.jp/Apps/TopReportNew/`

All query values use this transformation independently:

1. Convert to string; JSON-serialize objects compactly.
2. Apply JavaScript-compatible `encodeURIComponent`.
3. Base64-encode the UTF-8 bytes.
4. URL-encode the resulting Base64 value in the query string.

Authenticated requests use:

- `Authorization: Bearer <token>`
- `Userid: <authorized employee ID>`
- `X-Requested-With: XMLHttpRequest`

Read-only endpoints used by the script:

- `generateToken?userId=...`
- `DateService/GetYearWeekAtBegin`
- `TopService/GetToplist`
- `TopService/getOneTopDetails?topid=<employee>_<YYYY_WW>&userid=<caller>`
- `WeeklyService/getOneWeeklyDetails?topid=<employee>_<YYYY_WW>&userid=<caller>`
- `TopService/getAttributeTop?value=<organization ID>&level=<tree level>&year=...&week=...`

`GetToplist` parameters include `flg`, `start`, `page`, `limit`, `filter`, `employeecode`, and `order`. The filter is a compact JSON array with `yearweek`, `person`, and `keyword`. Query a week without server-side person filtering, then match employee code or name locally; the site's person-search representation is not a plain name or employee ID.

Successful responses normally use `Code: "000"`. List rows are in `Table0`. Detail content is typically HTML in `Table0[0].remark`.

Organization names and levels are resolved dynamically. Fetch level 1 with `EmployeeService/getCompanyList?empcode=...`, then traverse levels using `getJurisdiction`, `getDeploy`, `getSection`, `getArea`, and `getStore`. The selected node's tree depth is the `level` passed to `getAttributeTop`. For example, `T.R.E.-China` currently resolves as a level-1 company, but do not hardcode its ID.

## Interactive login bootstrap

When `TOP_REPORT_USER_ID` is absent, open `https://tr3.trial-net.co.jp/#/app/TOPReport` in an Orca embedded-browser tab. The unauthenticated route redirects to `auth.trial-net.co.jp/LoginAPI`. After the user logs in and the page returns to the TR3 origin, evaluate only this fixed local expression:

```javascript
window.loginApi?.apiLogin?.id || window.tCloud?.userData?.empcode || null
```

Use the resulting employee ID only in memory, then obtain a short-lived API token. Do not inspect form fields, passwords, unrelated page content, cookies, or browser storage.
