# POSSYS 镜像 · 同步日志与差分方法

## 源信息（复现同步所需）

| 项 | 值 |
| :--- | :--- |
| 站点 cloudId | `7e21d8bb-9d67-44e0-bec9-9ca2ed976bbb`（或主机名 `retailai.atlassian.net`）|
| 空间 | POS System，key=`POSSYS`，spaceId=`2968682558`，homepageId=`2968682809` |
| 拉取工具 | MCP `getPagesInConfluenceSpace`（`contentFormat=markdown`，`limit=250`，翻页 cursor）|
| 进度档 | [`sync-state.json`](./sync-state.json)（每页 `id`/`title`/`parentId`/`version`/`versionAt`/`path`）|

## 同步记录

| 日期 | 类型 | 页数 | 说明 |
| :--- | :--- | ---: | :--- |
| 2026-07-07 | 全量首次 | 461 | batch1 250 + batch2 211；正文 markdown 落地至 `content/`，生成 INDEX + sync-state |
| 2026-07-07 | 附件全量 | 81 页 | 下载 **304** 个附件至 `attachments/`，80 页图片链接改写为本地；余 **423** 处为 `type=external` 外部嵌入（丢失原始 URL，无法经附件 API 取得）；见 `attachments-manifest.json` |

## 差分同步方法（下次更新时）

分两段：**A. 内容差分（由 Claude 经 MCP 执行）** → **B. 附件差分（你带 API token 跑脚本）**。

**A. 内容差分（Claude / MCP）**
1. 重新用 `getPagesInConfluenceSpace(spaceId=2968682558, contentFormat=markdown, limit=250)` 翻页拉取全部页面（id + version）。
2. 与本目录 `sync-state.json` 逐页比对 `version`：
   - **新增**：id 不在旧档 → 新建 `content/<id>__<slug>.md`。
   - **更新**：`version` 变大 → 覆盖对应 `.md`。
   - **删除**：旧档有、本次拉取无 → 该页在源已删/移出，标记或移除。
3. 更新 `sync-state.json`（新 version/versionAt/syncedAt）与 `INDEX.md`；把本次**变更页 id** 写入 `_sync/changed-pages.txt`；并在上表追加一行同步记录。

**B. 附件差分（你 / API token）**
4. `python3 download_attachments.py --pages-file changed-pages.txt` → 只对变更页重取附件并改写图片链接（详见 [ATTACHMENTS.md](./ATTACHMENTS.md)）。首次/全量刷新则不带参数：`python3 download_attachments.py`（增量跳过已存在）。

> 为什么分两段：markdown 正文由 MCP 转换而来（REST 原生只给 storage/ADF），故内容差分走 MCP；附件下载需 attachment 权限，走你的 API token。首次全量脚本参考：`scratchpad/sync_possys.py`。

## 已知限制

- **图片**：页面附件已离线下载并改写为本地链接（2026-07-07，304 文件；见 [`ATTACHMENTS.md`](./ATTACHMENTS.md)）。仅 `type=external` 外部嵌入图（导出丢失原始 URL）仍为 blob 占位，需回源页面查看。
- **附件**：源空间「ファイル」页所列附件未下载。
- **宏/富块**：Confluence 宏（面板/状态/任务列表/展开块等）经 markdown 导出可能简化或丢失。
- **空正文页**：约 111 页正文为空（多为分类/父级节点），属正常。
