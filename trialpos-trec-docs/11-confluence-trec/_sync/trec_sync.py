#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TRE China 自建 Confluence (documents.trechina.cn) 页面树同步工具。

凭据从 ~/.netrc_trec 读取（netrc 格式），不接受命令行明文密码。
用法:
  python3 trec_sync.py enum     <root_id> <outdir>   # 枚举整棵树 -> _sync/tree.json
  python3 trec_sync.py fetch    <root_id> <destdir>  # 抓正文(storage)/建索引/状态档/附件清单
  python3 trec_sync.py download <root_id> <destdir>  # 按清单下载附件到 attachments/
正文用 body.storage，预处理 ac:image/code/panel 宏后经 pandoc 转 gfm。
"""
import sys, os, re, json, base64, time, subprocess, datetime, html as htmllib
import netrc, urllib.request, urllib.error, urllib.parse
from urllib.parse import quote

HOST = "documents.trechina.cn"
BASE = f"http://{HOST}"
NETRC = os.path.expanduser("~/.netrc_trec")
TODAY = datetime.date.today().isoformat()

def auth_header():
    n = netrc.netrc(NETRC)
    login, _, password = n.authenticators(HOST)
    tok = base64.b64encode(f"{login}:{password}".encode()).decode()
    return "Basic " + tok

AUTH = auth_header()

def api(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 * (attempt + 1)); continue
            raise
        except urllib.error.URLError:
            if attempt < 3:
                time.sleep(2 * (attempt + 1)); continue
            raise

# ---------- 枚举 ----------
def get_children(pid):
    out, start, limit = [], 0, 100
    while True:
        d = api(f"/rest/api/content/{pid}/child/page",
                {"expand": "version", "limit": limit, "start": start})
        res = d.get("results", [])
        for p in res:
            out.append({"id": p["id"], "title": p["title"],
                        "version": p.get("version", {}).get("number"),
                        "version_at": p.get("version", {}).get("when")})
        if len(res) < limit:
            break
        start += limit
    return out

def enumerate_tree(root_id):
    root = api(f"/rest/api/content/{root_id}", {"expand": "version,space"})
    nodes, order = {}, []
    rootnode = {"id": root["id"], "title": root["title"], "parent": None, "depth": 0,
                "version": root.get("version", {}).get("number"),
                "version_at": root.get("version", {}).get("when"),
                "space": root.get("space", {}).get("key")}
    nodes[root["id"]] = rootnode; order.append(root["id"])
    queue = [(root["id"], 0)]
    while queue:
        pid, depth = queue.pop(0)
        for c in get_children(pid):
            if c["id"] in nodes:
                continue
            c.update({"parent": pid, "depth": depth + 1, "space": rootnode["space"]})
            nodes[c["id"]] = c; order.append(c["id"])
            queue.append((c["id"], depth + 1))
        sys.stderr.write(f"\r枚举中… 已发现 {len(order)} 页"); sys.stderr.flush()
    sys.stderr.write("\n")
    return [nodes[i] for i in order]

# ---------- storage 预处理 ----------
EMOTICONS = {"tick": "✅", "cross": "❌", "warning": "⚠️", "information": "ℹ️",
             "question": "❓", "thumbs-up": "👍", "thumbs-down": "👎",
             "check": "✅", "star": "⭐", "plus": "➕", "minus": "➖"}

def preprocess_storage(raw, page_id, downloads):
    """把 Confluence storage(XHTML+宏) 处理成 pandoc 能吃的普通 HTML。
    图片改写为本地相对路径并把待下载项 append 到 downloads。"""
    h = raw

    # 1) code 宏 -> <pre><code>（先处理，保护 CDATA 内代码）
    def repl_code(m):
        body = m.group(1)
        return "<pre><code>" + htmllib.escape(body) + "</code></pre>"
    h = re.sub(
        r'<ac:structured-macro[^>]*ac:name="code".*?<ac:plain-text-body>\s*<!\[CDATA\[(.*?)\]\]>\s*</ac:plain-text-body>.*?</ac:structured-macro>',
        repl_code, h, flags=re.S)
    # noformat 宏同理
    h = re.sub(
        r'<ac:structured-macro[^>]*ac:name="noformat".*?<ac:plain-text-body>\s*<!\[CDATA\[(.*?)\]\]>\s*</ac:plain-text-body>.*?</ac:structured-macro>',
        repl_code, h, flags=re.S)

    # 2) ac:image -> <img src=本地相对>（记录下载项）
    def repl_image(m):
        block = m.group(0)
        att = re.search(r'ri:filename="([^"]*)"', block)
        if not att:
            urlm = re.search(r'ri:value="([^"]*)"', block)
            if urlm:
                u = htmllib.unescape(urlm.group(1))
                return f'<img src="{htmllib.escape(u)}" alt=""/>'
            return ""
        fn = htmllib.unescape(att.group(1))
        pg_sp = re.search(r'ri:space-key="([^"]*)"', block)
        pg_ti = re.search(r'ri:content-title="([^"]*)"', block)
        local_rel = f"../attachments/{page_id}/{quote(fn)}"
        local_abs = os.path.join("attachments", str(page_id), fn)
        if pg_sp and pg_ti:
            space = htmllib.unescape(pg_sp.group(1)); title = htmllib.unescape(pg_ti.group(1))
            dl = f"{BASE}/download/attachments/embedded-page/{quote(space)}/{quote(title)}/{quote(fn)}?api=v2"
        else:
            dl = f"{BASE}/download/attachments/{page_id}/{quote(fn)}"
        downloads.append({"url": dl, "local": local_abs, "filename": fn, "page_id": str(page_id)})
        return f'<img src="{local_rel}" alt="{htmllib.escape(fn)}"/>'
    h = re.sub(r'<ac:image\b[^>]*>.*?</ac:image>', repl_image, h, flags=re.S)

    # 3) emoticon -> 文字
    def repl_emo(m):
        name = re.search(r'ac:name="([^"]*)"', m.group(0))
        return EMOTICONS.get(name.group(1) if name else "", "")
    h = re.sub(r'<ac:emoticon\b[^>]*/>', repl_emo, h)

    # 4) status 宏 -> [title]
    def repl_status(m):
        t = re.search(r'ac:name="title"[^>]*>([^<]*)<', m.group(0))
        return f"<strong>[{t.group(1)}]</strong>" if t else ""
    h = re.sub(r'<ac:structured-macro[^>]*ac:name="status".*?</ac:structured-macro>',
               repl_status, h, flags=re.S)

    # 5) toc / children / anchor 等无正文宏 -> 删除整体
    for name in ("toc", "children", "anchor", "pagetree", "recently-updated",
                 "contentbylabel", "detailssummary", "livesearch"):
        h = re.sub(rf'<ac:structured-macro[^>]*ac:name="{name}".*?</ac:structured-macro>',
                   "", h, flags=re.S)
        h = re.sub(rf'<ac:structured-macro[^>]*ac:name="{name}"[^>]*/>', "", h)

    # 6) 删除剩余宏的参数元数据（<ac:parameter>...</ac:parameter>）
    h = re.sub(r'<ac:parameter\b[^>]*>.*?</ac:parameter>', "", h, flags=re.S)
    h = re.sub(r'<ac:parameter\b[^>]*/>', "", h)

    # 7) 内部链接 ac:link：保留 link-body / plain-text-link-body 文本
    h = re.sub(r'<ac:link\b[^>]*>', "", h)
    h = re.sub(r'</ac:link>', "", h)

    # 8) 去掉所有剩余 ac:/ri: 结构标签壳（保留其间内容），如 rich-text-body、expand、panel、info…
    h = re.sub(r'</?ac:[a-zA-Z0-9\-]+[^>]*>', "", h)
    h = re.sub(r'</?ri:[a-zA-Z0-9\-]+[^>]*>', "", h)

    # 9) 残留 CDATA 包裹去除
    h = h.replace("<![CDATA[", "").replace("]]>", "")
    return h

def html_to_md(html):
    p = subprocess.run(["pandoc", "-f", "html", "-t", "gfm", "--wrap=none"],
                       input=html.encode("utf-8"), stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL)
    md = p.stdout.decode("utf-8")
    md = re.sub(r"\n{3,}", "\n\n", md)  # 压缩多余空行
    return md.strip()

# ---------- 抓正文 ----------
def slugify(t):
    t = (t or "").strip()
    t = re.sub(r'[\\/:*?"<>|\r\n\t]+', " ", t)
    t = re.sub(r"\s+", "-", t).strip("-")
    return (t[:120] or "untitled")

def fm_escape(s):
    return (s or "").replace('"', '\\"')

def fetch_all(root_id, dest):
    sync_dir = os.path.join(dest, "_sync")
    content_dir = os.path.join(dest, "content")
    os.makedirs(sync_dir, exist_ok=True)
    os.makedirs(content_dir, exist_ok=True)

    tree_path = os.path.join(sync_dir, "tree.json")
    if os.path.exists(tree_path):
        tree = json.load(open(tree_path, encoding="utf-8"))
    else:
        tree = enumerate_tree(root_id)
        json.dump(tree, open(tree_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    by_id = {n["id"]: n for n in tree}
    state, downloads = {}, []
    total = len(tree)
    for i, n in enumerate(tree, 1):
        pid = n["id"]
        d = api(f"/rest/api/content/{pid}", {"expand": "body.storage,version,space"})
        title = d.get("title", n["title"])
        ver = d.get("version", {}).get("number")
        when = d.get("version", {}).get("when")
        space = d.get("space", {}).get("key")
        raw = d.get("body", {}).get("storage", {}).get("value", "") or ""
        page_dl = []
        html = preprocess_storage(raw, pid, page_dl) if raw.strip() else ""
        md = html_to_md(html) if html.strip() else ""
        downloads.extend(page_dl)

        slug = slugify(title)
        fname = f"{pid}__{slug}.md"
        fpath = os.path.join(content_dir, fname)
        parent = n.get("parent")
        src = f"{BASE}/pages/viewpage.action?pageId={pid}"
        front = [
            "---",
            f"confluence_id: {pid}",
            f'title: "{fm_escape(title)}"',
            f"parent_id: {parent or ''}",
            f"version: {ver}",
            f"version_at: {when}",
            "status: current",
            f"space: {space}",
            f"source_url: {src}",
            f"synced_at: {TODAY}",
            "---",
            "",
            f"# {title}",
            "",
            md,
            "",
        ]
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("\n".join(front))
        state[pid] = {"id": pid, "title": title, "parent": parent,
                      "depth": n.get("depth"), "version": ver, "version_at": when,
                      "space": space, "path": f"content/{fname}",
                      "body_empty": (md == ""), "images": len(page_dl)}
        sys.stderr.write(f"\r抓取中… {i}/{total}  ({title[:28]})" + " " * 12)
        sys.stderr.flush()
    sys.stderr.write("\n")

    json.dump({"root_id": root_id, "host": HOST, "synced_at": TODAY,
               "count": total, "pages": state},
              open(os.path.join(sync_dir, "sync-state.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    json.dump(downloads,
              open(os.path.join(sync_dir, "attachments-manifest.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    build_index(tree, by_id, dest)
    empty = sum(1 for v in state.values() if v["body_empty"])
    print(f"完成: {total} 页写入 content/；空正文 {empty} 页；待下载图片 {len(downloads)} 个"
          f"（去重 {len(set(x['url'] for x in downloads))}）。")

def build_index(tree, by_id, dest):
    children = {}
    for n in tree:
        children.setdefault(n.get("parent"), []).append(n)
    lines = ["# POS開発 (POSProduct) · Confluence 镜像目录", "",
             f"> 源: {BASE}/pages/viewpage.action?pageId={tree[0]['id']}　|　共 {len(tree)} 页　|　基准时点 {TODAY}",
             ""]
    def walk(node, indent):
        slug = slugify(node["title"])
        rel = f"content/{node['id']}__{slug}.md"
        lines.append(f"{'  '*indent}- [{node['title']}]({quote(rel)}) `v{node['version']}`")
        for c in children.get(node["id"], []):
            walk(c, indent + 1)
    walk(tree[0], 0)
    open(os.path.join(dest, "INDEX.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

# ---------- 附件下载 ----------
def download_attachments(root_id, dest):
    man = os.path.join(dest, "_sync", "attachments-manifest.json")
    items = json.load(open(man, encoding="utf-8"))
    seen, ok, skip, fail = set(), 0, 0, []
    faillog = []
    total = len(items)
    for i, it in enumerate(items, 1):
        url, local = it["url"], os.path.join(dest, it["local"])
        key = url
        if key in seen:
            continue
        seen.add(key)
        if os.path.exists(local) and os.path.getsize(local) > 0:
            skip += 1; continue
        os.makedirs(os.path.dirname(local), exist_ok=True)
        code = subprocess.run(
            ["curl", "-sS", "-m", "60", "--netrc-file", NETRC, "-o", local,
             "-w", "%{http_code}", url],
            stdout=subprocess.PIPE).stdout.decode().strip()
        if code == "200" and os.path.exists(local) and os.path.getsize(local) > 0:
            ok += 1
        else:
            if os.path.exists(local):
                os.remove(local)
            fail.append(url); faillog.append({"url": url, "http": code, "file": it["filename"]})
        sys.stderr.write(f"\r下载附件… {i}/{total}  成功{ok} 跳过{skip} 失败{len(fail)}")
        sys.stderr.flush()
    sys.stderr.write("\n")
    json.dump(faillog, open(os.path.join(dest, "_sync", "attachments-failed.json"), "w",
                            encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"附件下载完成: 成功 {ok}，跳过(已存在) {skip}，失败 {len(fail)}（详见 _sync/attachments-failed.json）")

# ---------- CLI ----------
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "enum"
    root_id = sys.argv[2] if len(sys.argv) > 2 else "18781665"
    outdir = sys.argv[3] if len(sys.argv) > 3 else "."
    if cmd == "enum":
        tree = enumerate_tree(root_id)
        os.makedirs(os.path.join(outdir, "_sync"), exist_ok=True)
        json.dump(tree, open(os.path.join(outdir, "_sync", "tree.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"总页数: {len(tree)}")
    elif cmd == "fetch":
        fetch_all(root_id, outdir)
    elif cmd == "download":
        download_attachments(root_id, outdir)
