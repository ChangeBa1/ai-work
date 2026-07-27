# POS開発 (POSProduct) 镜像 · 同步日志与差分方法

本目录是 **TRE China 自建 Confluence**（`documents.trechina.cn`，Confluence Server/DC）空间「POS開発」中，以页面 **POS開発 主页** 为根的整棵页面树的本地镜像。与 `01-confluence-cloud/`（源自 Atlassian Cloud `retailai.atlassian.net`）是**两套不同的 Confluence 实例**。

## 源信息（复现同步所需）

| 项 | 值 |
| :--- | :--- |
| 站点 | `http://documents.trechina.cn`（自建 Confluence Server/DC）|
| 空间 | POS開発，key=`POSProduct` |
| 根页面 | 「POS開発 主页」，`pageId=18781665`（顶层页）|
| 认证 | HTTP **Basic Auth**（该实例未开启 Personal Access Token）；凭据文件 `~/.netrc_trec`（权限 600，**不入库、不进 iCloud**）|
| 拉取 | REST：正文 `GET /rest/api/content/{id}?expand=body.storage,version,space`；子页 `GET /rest/api/content/{id}/child/page?expand=version`（翻页 start/limit）|
| 正文转换 | 自研预处理（`ac:image`→本地图、`code/noformat`宏→代码块、`panel/expand/info` 等拆壳保留内容、`emoticon`→文字、`toc` 等无正文宏删除）后经 **pandoc html→gfm** |
| 脚本 | [`trec_sync.py`](./trec_sync.py)，三个子命令：`enum` / `fetch` / `download` |
| 进度档 | [`tree.json`](./tree.json)（枚举树）、[`sync-state.json`](./sync-state.json)（每页 id/title/parent/version/path）、[`attachments-manifest.json`](./attachments-manifest.json)（图片下载清单）、[`attachments-failed.json`](./attachments-failed.json)（下载失败清单）|

## 同步记录

| 日期 | 类型 | 页数 | 说明 |
| :--- | :--- | ---: | :--- |
| 2026-07-12 | 全量首次 | 147 | `body.storage`→预处理→pandoc gfm 落地至 `content/`；深度分布 root:1 / L1:12 / L2:48 / L3:53 / L4:33；空正文 **43** 页（分类/父节点）；正文引用图片 **41** 张全部离线下载至 `attachments/<pageId>/` 并改写为本地相对链接，失败 0 |

## 目录产物

- `content/<id>__<slug>.md` — 每页一文件，frontmatter 含 `confluence_id/title/parent_id/version/version_at/status/space/source_url/synced_at`。
- `attachments/<pageId>/<filename>` — 正文 `ac:image` 引用的附件图（按引用页 pageId 分目录）。
- `INDEX.md` — 按页面树缩进的目录，附各页版本号与相对链接。

## 差分同步方法（下次更新）

前提：`~/.netrc_trec` 存在且凭据有效。全部命令的 `<dest>` = 本镜像根目录 `02-confluence-trec`。

1. **重新枚举**：`python3 _sync/trec_sync.py enum 18781665 <dest>` → 覆盖 `_sync/tree.json`。
2. **比对版本**：将新 `tree.json` 与旧 `sync-state.json` 逐页比对 `version`：
   - 新增：id 不在旧档 → 新建页；
   - 更新：`version` 变大 → 覆盖 `.md`；
   - 删除：旧档有、本次枚举无 → 该页已删/移出，标记或移除。
3. **抓正文**：`python3 _sync/trec_sync.py fetch 18781665 <dest>`（当前为**全量覆盖式**重抓并重写 `sync-state.json`/`INDEX.md`/`attachments-manifest.json`；如需只重抓变更页，可按上一步的变更 id 列表扩展脚本）。
4. **下载附件**：`python3 _sync/trec_sync.py download 18781665 <dest>`（按清单增量下载，已存在文件自动跳过）。

## 已知限制

- **复杂表格**：带 `colspan`/富样式的表格由 pandoc 保留为**内嵌 HTML `<table>`**（GFM 允许，渲染正常），仅简单表格转为 Markdown 表格。
- **行内换行**：storage 里的 `<br>` 转为 GFM 行尾 `\`（硬换行），渲染正确但纯文本查看时可见 `\`。
- **Confluence 宏**：`code/noformat` 转为代码块（本次无）；`panel/info/note/warning/expand` 等**拆壳保留内容**，但框体/配色等展示语义丢失；`status/emoticon` 转为文字。
- **空正文页**：43 页正文为空，多为分类/父级节点，属正常。
- **外部/嵌入图**：drawio、Figma、外部 URL（如 `ri:url`）图**保留原链接未离线**；跨页引用图（`embedded-page` 形式）已尽力下载。
- **附件范围**：仅下载**正文中 `ac:image` 引用的图片**；页面「附件」列表中未在正文引用的其它文件（xlsx/pdf 等）未下载。
