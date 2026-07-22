# TRI-POS（現行 TRIAL 自社POS） · 知识卡

> **结构索引 / 各目录导航请看 [README.md](./README.md)**；本卡聚焦「这些文档描述的是什么系统、业务背景、与 ST-POS 的关系」。
>
> **来源**：POSSYS「POS System」Confluence 空间镜像 + Payment/POS 系统台帳 + ST-POS 报告间接线索
> **基准时点**：2026-07 ｜ **整理日**：2026-07-07（**结构更新** 2026-07-14）
> **维护人**：jinianxiang ｜ **密级**：🟡 敏感（含未公开供应商资料）

---

## 0. 一句话概要

本库是 **現行 TRIAL 自社 POS（POS4U ＝ TRI-POS）** 的知识档案库，也是 **ST-POS（新規・完全内製 POS）** 要置换/内製化的对象系统的知识载体。

内容由四部分组成（详见 [README.md](./README.md) 目录总览）：

1. **[`01-trialpos-docs/`](./01-trialpos-docs/00_portal/README.md)** ⭐ — POS4U 源码分析文档体系（**权威·当前**）：代码锚定·单一真相源·可信度分级的 AS-IS 文档（93 篇·11 层）。2026-07-14 重构落地，接替同名旧文档的目录名（旧 StackShift 5 卷册已删除，备份见 `z-archive/`）
2. **[`10-confluence-cloud/`](./10-confluence-cloud/INDEX.md)** — 云 Confluence（POSSYS 空间，**日中两团队共同维护**）461 页镜像 —— 現行 POS 全套知识主体
3. **[`11-confluence-trec/`](./11-confluence-trec/INDEX.md)** — 自建 Confluence（**中国团队单独维护**）147 页镜像 —— ST-POS/AIPOS 开发过程文档
4. **[`12-gitlab-wiki/`](./12-gitlab-wiki/home.md)** — GitLab AIPOS Wiki（**中国开发团队单独维护**）157 页镜像 —— POS4U 开发/环境/C# 知识

## 1. 关键事实

| 项 | 内容 |
| :--- | :--- |
| 系统别称 | TRI-POS ／ 自社POS ／ 現行POS ／ POS4U |
| 状态 | 🟢 運用中（現行） |
| 主责 | 増岡 学（Payment/POS）／ 菊池 ほか |
| 主知识来源 | Confluence 空间 [POS System (POSSYS)](https://retailai.atlassian.net/wiki/spaces/POSSYS)（→ `10-confluence-cloud/`） |
| 云镜像页数 | **461**（7 层层级；顶层 01業務知識/02開発/03品質/04運用/05保守/09その他/99.ST-POS関連） |
| 源码真值 | `trialpos-snapshots`（POS4U 真实源码，基准版本 最新发布）|
| 关联 | **ST-POS**（置换本系统的新規完全内製 POS，本工作区其它子仓库即其实装）· **Payment/POS 25系统台帳**（TRI-POS 及周辺系统资料整备；原知识库台帳，本库外） |

## 2. 本库导航

- 📚 **[README.md](./README.md)** — 全库结构索引 / 各目录定位 / 使用与维护（**主入口**）
- 🧬 **[POS4U 源码分析文档体系（`01-` · 权威）](./01-trialpos-docs/00_portal/README.md)** — 11 层·93 篇·代码锚定·单一真相源·零死链
- ☁️ **[POSSYS 云镜像目录树（INDEX）](./10-confluence-cloud/INDEX.md)** — 461 页完整层级导航
  - 页面正文：[`10-confluence-cloud/content/`](./10-confluence-cloud/content/)（每页一 `.md`，frontmatter 含 `confluence_id`/`version`/`source_url`）
  - [同步进度与差分方法](./10-confluence-cloud/_sync/SYNC-LOG.md) ｜ [图片/附件离线方案](./10-confluence-cloud/_sync/ATTACHMENTS.md)
- 🏭 **[自建 Confluence（POS開発）镜像 INDEX](./11-confluence-trec/INDEX.md)** — 147 页，源自 `documents.trechina.cn`（TRE China 自建 Confluence），ST-POS/AIPOS 开发过程文档；同步方法见 [`11-confluence-trec/_sync/SYNC-LOG.md`](./11-confluence-trec/_sync/SYNC-LOG.md)
- 🛠️ **[GitLab AIPOS Wiki 镜像](./12-gitlab-wiki/home.md)** — 157 页开发 wiki；维护说明见 [`README-SYNC.md`](./12-gitlab-wiki/README-SYNC.md)（⚠️ git 履历已于 2026-07-14 移除，仅存最新版本）
- ✅ **[代码对照精度核查（90-verification）](./90-verification/)** — 逐库对照 POS4U 真实源码的精度核查，两条主线：
  - **[线上镜像 10/11/12](./90-verification/kb-vs-code-accuracy-audit-2026-07-14.md)**：结构层可信度高（`10` 开发 B+/业务 A− ｜ `11`(B类) A− ｜ `12` B+），6 类须修正硬偏差。**注：该报告正文的 01/02/03 = 现在的 10/11/12（≠ `01-trialpos-docs`）。**
  - **[源码分析文档 01-trialpos-docs](./90-verification/reverse-docs-vs-code-audit-2026-07-14.md)**：质的/算法级分析出众（挖出 2 个真实 Bug），但门面架构造假（端侧 DB 实为 SQL Server 非"双 SQLite"）、定量统计系统性捏造、`Application/Source/` 链接全断；含 3 类 P0。

## 3. 镜像说明与已知限制

- **云 Confluence 首次同步**：2026-07-07，461 页全量拉取（详见 `10-confluence-cloud/_sync/SYNC-LOG.md`）。
- ✅ **图片/附件已离线**（2026-07-07）：**304** 个附件下载至 `10-confluence-cloud/attachments/<pageId>/`，80 页图片链接已改写为本地路径。**例外**：423 处 `type=external` 外部嵌入图（导出时丢失原始 URL）无法经附件 API 取得，仍为占位——需要时回源页看（frontmatter `source_url`）。
- ⚠️ **宏/特殊块**：Confluence 宏（面板、状态、任务列表等）经 markdown 导出可能简化或丢失格式。
- ⚠️ **`12-gitlab-wiki` git 履历已移除**（2026-07-14）：原为 wiki 仓库完整 git 克隆，现只保留最新版本文件（提交 `cdd5951`）；再同步需重新 `git clone`，不再能 `git pull` 差分。
- **差分同步**：`10-`/`11-` 靠每页 `version` 号与 `sync-state.json` 比对即可增量更新。

## 4. 与 ST-POS 的关系

- POS4U（TRI-POS）＝**現行**；ST-POS＝**新規・完全内製**，目标是替换本系统并统一 TRIAL×西友。
- ST-POS 能走フルスクラッチ的最大依仗，正是"我们自己握有現行 POS 开发团队"——本库（現行 POS 知识 + 源码分析 + 精度核查）即该依仗的知识载体。
- POSSYS 空间内还有 `99.ST-POS関連` 分类，部分 ST-POS 内容也沉淀在 `10-` 中。

## 5. 待补充 / 后续

- [x] 云 Confluence 图片/附件离线（2026-07-07，304 文件；`type=external` 外部嵌入图除外）
- [x] 代码对照精度核查 · 线上镜像 10/11/12（2026-07-14，见 `90-verification/kb-vs-code-accuracy-audit`）
- [x] 代码对照精度核查 · 代码分析文档 01-trialpos-docs（2026-07-14，见 `90-verification/reverse-docs-vs-code-audit`）
- [ ] `90-` 报告列出的硬偏差回写修正：10/11/12 的 6 类 P0 → 回写各镜像；01- 的 3 类 P0（SQLite→SQL Server、`Application/Source/` 链接、定量统计捏造）→ 回写代码分析文档
- [ ] 定期差分同步（`10-`/`11-` 见各自 SYNC-LOG；`12-` 需重新 clone）
