# 图片/附件 离线下载方案

## 问题

镜像正文（`content/*.md`）里的图片是 Confluence 编辑器的 **`blob:` 占位链接**（如 `blob:https://media.staging.atl-paas.net/?...&id=<mediaId>...`），只在登录的编辑器会话内有效，**本地/离线无法显示**。真正的二进制附件需要另行下载。

> 为什么本次同步没自动带下来：MCP 的 Confluence 授权范围只有 `read:page/space/comment`，**没有附件读取权限**，也没有下载工具；因此下载须用**你自己的 Atlassian API token** 在本地执行。

---

## 方案 A（最简单、最完整）：Confluence 空间导出

适合"只要一份完整离线副本、含所有图片"的场景。

1. 打开空间 [POS System](https://retailai.atlassian.net/wiki/spaces/POSSYS) → **Space settings → Content tools → Export**（需空间管理权限）。
2. 选 **HTML**（或 **PDF**）→ **Normal Export** → 下载 zip。
3. zip 内含全部页面 + `attachments/` 图片，可直接离线浏览。

- ✅ 一键、完整、含所有媒体。
- ⚠️ 是独立的一份导出，**不与本 markdown 镜像/差分体系集成**（图片不会进到我们的 `content/*.md` 里）。

---

## 方案 B（与本镜像集成、可差分）：API token 脚本

适合"图片要落到我们的镜像里、并能随差分同步一起维护"的场景。脚本已备好：[`download_attachments.py`](./download_attachments.py)。

### 1. 生成 API token
访问 https://id.atlassian.com/manage-profile/security/api-tokens → Create API token。

### 2. 运行
```bash
cd ".../pj-trial-pos/01-confluence-cloud/_sync"
export CONF_EMAIL="你的登录邮箱"
export CONF_API_TOKEN="刚生成的 token"

python3 download_attachments.py --dry-run   # 先干跑，看会下载什么
python3 download_attachments.py             # 正式下载 + 改写链接
```

### 3. 脚本做了什么
- 读 `sync-state.json` 的页面清单，对每个"正文含 blob 图片"的页面：
  - 调 `GET /wiki/rest/api/content/{pageId}/child/attachment` 列出附件（含 `extensions.fileId`＝blob 里的 `id`）；
  - 下载二进制到 `../attachments/<pageId>/<filename>`；
  - 把正文里能按 `fileId` 匹配上的 `![](blob:...)` **就地改写**为 `![](../attachments/<pageId>/<filename>)`；
  - 写 `attachments-manifest.json`（每页附件 + fileId，便于差分）。
- 幂等：已存在的文件默认跳过；`--force` 可重下、重扫全部页。

### 4. 注意
- 只用 Python 标准库，无需 pip。
- blob 的 `id` 与附件 `extensions.fileId` 通常一致；万一匹配不到，脚本**保留原 blob 链接**（不破坏正文），可事后人工核对。
- 附件量可能较大（461 页），建议先 `--dry-run` 评估。
- **只处理变更页**：`--pages id1,id2` 或 `--pages-file changed-pages.txt`（内容差分产出的变更页 id 列表）→ 只重取这些页的附件并改写链接（对指定页强制重下）。
- **差分集成**：见 [`SYNC-LOG.md`](./SYNC-LOG.md)。内容差分（Claude 经 MCP 执行）会把变更页 id 写入 `changed-pages.txt`，随后你跑 `download_attachments.py --pages-file changed-pages.txt` 增量补图；首次/全量则不带参数运行。

---

## 推荐

- 只想快速拿到含图的完整离线包 → **方案 A**。
- 想让图片进入本 markdown 镜像、纳入版本/差分管理 → **方案 B**（跑 `download_attachments.py`）。
