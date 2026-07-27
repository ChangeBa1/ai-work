#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POSSYS 镜像：附件/图片 离线下载 + markdown 图片链接改写
--------------------------------------------------------
现状：content/*.md 里的图片是 Confluence 编辑器 `blob:` 占位符，本地不显示。
本脚本对每个页面调用 Confluence REST 列出附件、下载二进制到 attachments/<pageId>/，
并把正文里能按 fileId 匹配上的 blob 图片链接改写成本地相对路径。

只用 Python 标准库。需要 Atlassian API token（Confluence Cloud 用 Basic Auth：email + token）。
  生成 token：https://id.atlassian.com/manage-profile/security/api-tokens

用法（在本 _sync/ 目录或任意位置执行均可，脚本自定位）：
  export CONF_EMAIL="you@company.com"
  export CONF_API_TOKEN="xxxxx"
  python3 download_attachments.py            # 下载 + 改写（首次/全量，增量跳过已存在）
  python3 download_attachments.py --dry-run  # 只列出将下载什么，不写盘
  python3 download_attachments.py --force    # 重下已存在文件、并对所有页重扫
  python3 download_attachments.py --pages-file changed-pages.txt  # 差分：只处理变更页
  python3 download_attachments.py --pages 123,456                 # 差分：只处理指定页 id

读取同目录 sync-state.json 的页面清单；产物：
  ../attachments/<pageId>/<filename>         下载的附件
  ./attachments-manifest.json                每页附件清单（含 fileId，便于差分）
  （并就地改写 ../content/<...>.md 中可匹配的 blob 图片链接）
"""
import os, sys, re, json, base64, time, datetime, urllib.request, urllib.error

BASE = "https://retailai.atlassian.net/wiki"
HERE = os.path.dirname(os.path.abspath(__file__))     # .../01-confluence-cloud/_sync
ROOT = os.path.dirname(HERE)                          # .../01-confluence-cloud
CONTENT = os.path.join(ROOT, "content")
ATT = os.path.join(ROOT, "attachments")
STATE = os.path.join(HERE, "sync-state.json")

DRY = "--dry-run" in sys.argv
FORCE = "--force" in sys.argv


def _argval(flag):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


# 差分：只处理指定页面（内容同步产出的"变更页 id"列表）
TARGET_IDS = None
_pages_arg = _argval("--pages")
_pages_file = _argval("--pages-file")
if _pages_arg:
    TARGET_IDS = set(x.strip() for x in _pages_arg.split(",") if x.strip())
elif _pages_file:
    _raw = open(_pages_file, encoding="utf-8").read().strip()
    try:
        _d = json.loads(_raw)
        if isinstance(_d, dict):
            _d = _d.get("changed") or _d.get("ids") or []
        TARGET_IDS = set(str(x) for x in _d)
    except Exception:
        TARGET_IDS = set(x.strip() for x in _raw.replace(",", "\n").splitlines() if x.strip())

EMAIL = os.environ.get("CONF_EMAIL")
TOKEN = os.environ.get("CONF_API_TOKEN")
if not (EMAIL and TOKEN):
    if DRY:
        print("[dry-run] 未设置 CONF_EMAIL/CONF_API_TOKEN；仅演示流程。")
    else:
        sys.exit("错误：请先设置环境变量 CONF_EMAIL 与 CONF_API_TOKEN（见文件头）。")
AUTH = "Basic " + base64.b64encode(f"{EMAIL}:{TOKEN}".encode()).decode() if (EMAIL and TOKEN) else None


def _headers(extra=None):
    h = dict(extra or {})
    if AUTH:
        h["Authorization"] = AUTH
    return h


def api_get(url):
    req = urllib.request.Request(url, headers=_headers({"Accept": "application/json"}))
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def download(url, dest):
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        f.write(r.read())


def list_attachments(page_id):
    """列出页面全部附件：filename / fileId(=blob 里的 id) / mediaType / download 路径。"""
    out, start, limit = [], 0, 100
    while True:
        url = f"{BASE}/rest/api/content/{page_id}/child/attachment?expand=extensions&limit={limit}&start={start}"
        data = api_get(url)
        for a in data.get("results", []):
            ext = a.get("extensions") or {}
            out.append({
                "filename": a.get("title"),
                "fileId": ext.get("fileId"),
                "mediaType": ext.get("mediaType"),
                "download": (a.get("_links") or {}).get("download"),
            })
        results = data.get("results", [])
        if len(results) < limit:
            break
        start += limit
    return out


def safe(name):
    return re.sub(r'[\\/:\*\?"<>\|]+', "_", (name or "file")).strip() or "file"


def main():
    state = json.load(open(STATE, encoding="utf-8"))
    pages = state.get("pages", [])
    manifest, n_dl, n_pages = {}, 0, 0

    for p in pages:
        pid = p["id"]
        if TARGET_IDS is not None and pid not in TARGET_IDS:
            continue
        force_page = FORCE or (TARGET_IDS is not None)  # 差分指定页 → 强制重取
        mdpath = os.path.join(ROOT, p["path"])
        if not os.path.exists(mdpath):
            continue
        md = open(mdpath, encoding="utf-8").read()
        if ("blob:" not in md) and not force_page:
            continue  # 该页正文无图片占位
        try:
            atts = list_attachments(pid) if AUTH else []
        except urllib.error.HTTPError as e:
            print(f"[WARN] page {pid}: attachment 列表 HTTP {e.code}")
            continue
        except Exception as e:
            print(f"[WARN] page {pid}: {e}")
            continue
        if not atts:
            continue
        n_pages += 1
        by_fileid = {a["fileId"]: a for a in atts if a.get("fileId")}
        pdir = os.path.join(ATT, pid)
        if not DRY:
            os.makedirs(pdir, exist_ok=True)

        saved = []
        for a in atts:
            fn = safe(a["filename"])
            dest = os.path.join(pdir, fn)
            dl = a.get("download")
            if dl:
                durl = (BASE + dl) if dl.startswith("/") else dl
                if DRY:
                    print(f"  would download {pid}/{fn}")
                elif force_page or not os.path.exists(dest):
                    try:
                        download(durl, dest)
                        n_dl += 1
                        time.sleep(0.05)
                    except Exception as e:
                        print(f"[WARN] 下载失败 {pid}/{fn}: {e}")
            saved.append({"filename": fn, "fileId": a.get("fileId"), "mediaType": a.get("mediaType")})

        # 按 blob 里的 id=<fileId> 改写图片链接为本地相对路径
        def repl(m):
            blob = m.group(0)
            mid = re.search(r'[?&]id=([0-9a-fA-F-]{36})', blob)
            if mid and mid.group(1) in by_fileid:
                fn = safe(by_fileid[mid.group(1)]["filename"])
                return f"![{fn}](../attachments/{pid}/{fn})"
            return blob  # 匹配不到则原样保留（安全）
        new_md = re.sub(r'!\[[^\]]*\]\(blob:[^)]*\)', repl, md)
        if (new_md != md) and not DRY:
            open(mdpath, "w", encoding="utf-8").write(new_md)
        manifest[pid] = saved

    if not DRY:
        json.dump({"downloadedAt": datetime.date.today().isoformat(),
                   "attachmentsByPage": manifest},
                  open(os.path.join(HERE, "attachments-manifest.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    print(f"done. 含附件页数={n_pages}, 下载文件数={n_dl}, dry_run={DRY}, force={FORCE}")


if __name__ == "__main__":
    main()
