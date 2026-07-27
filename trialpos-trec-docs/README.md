# pj-trial-pos 知识库（trialpos-trec-docs）

> **一句话**：围绕 **POS4U（現行 TRIAL 自社 POS）→ ST-POS（新規・完全内製 POS）** 这条置换主线，汇集「源码分析文档 + 三处线上知识库镜像 + 代码对照精度核查」的本地档案。
>
> **密级**：🟡 **敏感 · 含未公开供应商（TrialPOS / POS4U）资料**。仅限本地 / 私有。**不得**接入公开仓库、不得对外发送（工作区跨仓铁律 §5）。
>
> **整理日**：2026-07-14 ｜ **维护人**：jinianxiang

---

## 0. 这是什么

本目录不是源码库，而是一个 **POS 领域知识档案库**。它服务于一个目标：**把現行自社 POS「POS4U」彻底摸清，为新系统「ST-POS」的完全内製化重构提供高精度、可追溯的业务与代码依据。**

档案由两类来源构成：

- **源码分析直接产物**（`01-`）：从 POS4U 真实源码（`trialpos-snapshots`）源码分析生成的结构化文档。
- **线上知识库镜像**（`10- / 11- / 12-`）：三处不同团队维护的 Confluence / GitLab 知识库的本地离线镜像。

外加一层 **代码对照精度核查**（`90-`），以真实代码为唯一真值，校验上述镜像的准确度。

### 术语速查

| 术语 | 含义 |
|---|---|
| **POS4U** | 現行運用中的 TRIAL 自社 POS，本库大多数文档的描述对象；其源码基准版本 最新发布 |
| **TRI-POS / 現行POS / 自社POS** | POS4U 的别称 |
| **ST-POS** | 新規・完全内製 POS，置换 POS4U 的目标系统（本工作区其它子仓库即其实装） |
| **POSSYS** | Confluence Cloud 上的空间名（"POS System"），即 `10-` 的来源 |
| **AIPOS** | 内网 GitLab 上的 POS 开发项目（`project-trial/aipos`），即 `12-` 的来源 |

---

## 1. 目录总览

当前共约 **1,350 个文件**（含新建 `00-` 体系 89 篇；删除 `12-` 的 git 履历后口径）。

| 目录 | 定位 | 来源 | 维护方 | 规模 | 入口 |
|---|---|---|---|---|---|
| `00-overview.md` | 知识域背景卡（TRI-POS/POS4U 是什么、术语、与 ST-POS 关系） | — | jinianxiang | 1 文件 | [00-overview.md](./00-overview.md) |
| `01-trialpos-docs/` ⭐ | **POS4U 源码分析文档体系（权威·当前）** — 代码锚定·单一真相源·可信度分级的 AS-IS 文档（11 层：门户/架构/框架/域22模块/数据/设备/服务/流程/决策/追溯/教程） | 重构自旧文档 + 回 `trialpos-snapshots` 核实 | jinianxiang | 93 篇 · 864K | [门户](./01-trialpos-docs/00_portal/README.md) |
| `10-confluence-cloud/` | **云上 Confluence 知识库镜像**（現行 POS 全套：業務/開発/品質/運用/保守） | `retailai.atlassian.net` · POSSYS 空间 | **日中两团队共同维护** | 461 页 + 304 附件 · 79M | [INDEX](./10-confluence-cloud/INDEX.md) |
| `11-confluence-trec/` | **自建 Confluence 知识库镜像**（ST-POS/AIPOS 开发过程：要件定義〜リリース、開発ルール、業務ロジック） | `documents.trechina.cn` · POSProduct 空间 | **中国团队单独维护** | 147 页 + 41 附件 · 13M | [INDEX](./11-confluence-trec/INDEX.md) |
| `12-gitlab-wiki/` | **GitLab 开发 Wiki 镜像**（POS4U 开发/环境搭建/業務知識/C# 知识点） | `code.trechina.cn` · AIPOS wiki | **中国开发团队单独维护** | 157 页 + 20 附件 · 3.0M | [home.md](./12-gitlab-wiki/home.md) · [README-SYNC](./12-gitlab-wiki/README-SYNC.md) |
| `90-verification/` | **代码对照精度核查**（以真实代码为唯一真值，校验 **10/11/12 + 01-** 的准确度） | 核查 `trialpos-snapshots` | jinianxiang | 7 报告 · 164K | [镜像主报告](./90-verification/kb-vs-code-accuracy-audit-2026-07-14.md) · [代码分析文档主报告](./90-verification/reverse-docs-vs-code-audit-2026-07-14.md) |

---

## 2. 各域详解

### `01-trialpos-docs/` — POS4U 源码分析文档体系（权威 · 当前）⭐
以 `trialpos-snapshots` 真实源码为唯一真值的**代码锚定文档体系**（2026-07-14 重构落地；接替了同名旧文档的目录名）。行业最佳实践（arc42/C4/Diátaxis/ADR/docs-as-code）+ 单一真相源 + 可信度分级（verified/unverified/uncheckable）+ 全程 file:line 锚定。共 **93 篇、11 层**：

- **00_portal**（门户/写作宪法/术语/代码地图）· **10_architecture**（C4 上下文·容器·部署·IPC·数据流）· **15_howto**（新建模块/画面/设备插件教程）· **20_framework**（WinPOS 引擎五要素）· **30_domain**（22 业务模块·单一真相源·全 verified）· **40_data**（SQL Server 双库表/SP/视图/枚举字典）· **50_devices**（78 设备族）· **60_services**（边缘 API 11 Controller/后台 16 项目/云 BO）· **70_flows**（端到端流程叙事）· **80_decisions**（代码分析 ADR + 缺陷调查）· **90_traceability**（映射矩阵/覆盖率/可信度）· **99_archive**（封存说明）
- 入口：[门户 README](./01-trialpos-docs/00_portal/README.md) · [写作宪法 conventions](./01-trialpos-docs/00_portal/conventions.md) · [架构方案](./01-trialpos-docs/00_portal/architecture-redesign-proposal.md)
- 可信度：**87 verified / 4 unverified（15_howto 教程，锚点均 verified）/ 2 uncheckable（Framework.dll 基类 + 封存说明）** · 零死链

> **关于"旧 01-"**：本目录名此前属 StackShift 自动分析的旧文档（5 卷册 107 页）。经 [`90-verification` 代码核查](./90-verification/reverse-docs-vs-code-audit-2026-07-14.md) 发现系统性定量造假、门面架构错误（端侧 DB 实为 SQL Server 而非"双 SQLite"，行数夸大 16~38 倍）等，已于 2026-07-14 **物理删除**（zip 忠实备份比对通过后），本重构体系改名接替 `01-` 目录名。旧文档备份见 `z-archive/trialpos-trec-docs/01-trialpos-docs.zip`。

### `10-confluence-cloud/` — 云 Confluence（日中共同）
POSSYS 空间 461 页的离线镜像，**現行 POS 全套知识**（顶层 7 分类：01業務知識 / 02開発 / 03品質 / 04運用 / 05保守 / 09その他 / 99.ST-POS関連）。
- `content/` 每页一个 `.md`，frontmatter 含 `confluence_id` / `version` / `source_url`
- `attachments/<pageId>/` 已离线 304 个附件；423 处 `type=external` 外部嵌入图未能取得（需回源页看）
- `_sync/` 同步状态与方法（`SYNC-LOG.md` / `sync-state.json`）

### `11-confluence-trec/` — 自建 Confluence（中国团队）
`documents.trechina.cn`（TRE China 自建 Confluence）POS開発树 147 页镜像。以 **ST-POS/AIPOS 开发过程文档**为主（要件定義・概要設計・詳細設計・機能一覧・API仕様・業務フロー・開発ルール等），日中文混合。结构同 `10-`（`content/` + `attachments/` + `_sync/` + `INDEX.md`）。

> ⚠️ 本库 61% 是 ST-POS/JOBManager 新案件（本地无实装、技术栈与 POS4U 不同），阅读时勿与 POS4U 現行行为混淆（见 `90-` 报告 02 节）。

### `12-gitlab-wiki/` — GitLab 开发 Wiki（中国开发团队）
内网 GitLab `aipos-wiki` 的镜像，157 页平铺 `.md`（POS4U 开发/环境搭建/業務知識/C# 知识点）+ `uploads/`（20 附件）+ `.gitlab/redirects.yml`。
- 文件名即 wiki slug：`_` 表层级、`.` 前缀表序号（如 `1_1_9.-オーダーキッチン.md`）
- **⚠️ git 履历已于 2026-07-14 移除**：本目录原为 wiki 仓库完整 git 克隆，现已删除 `.git/`，**只保留最新版本文件**（同步到提交 `cdd5951`，2025-08-19）。`README-SYNC.md` 里基于 `git pull` 的差分更新法**已不适用**；再同步需重新 `git clone` 远端。
- 已知源仓库自带瑕疵（忠实保留）：`*-[13.-rm商品api](.` 目录（坏 markdown 链接被误存成页面，4 字节）、`test.md`（2 字节残留）
- 图片/内链由 GitLab wiki 引擎解析，本地 markdown 阅读器不解析；本镜像定位为「原文归档 + grep 检索」

### `90-verification/` — 代码对照精度核查
以 `trialpos-snapshots`（POS4U 真实源码，基准 最新发布）为**唯一真值**，逐库核查 **10/11/12 与 01-** 的描述精度（连代码库自带的 `docs/` 也视作未验证二手材料）。分两条主线：

**① 线上镜像（10/11/12）** — [`kb-vs-code-accuracy-audit-2026-07-14.md`](./90-verification/kb-vs-code-accuracy-audit-2026-07-14.md) + 4 份逐 file:line 切片明细（`slice-01a/01b/02/03`）
- 结论：三库结构性描述可信度高，**未见系统性造假**；问题集中在①量化口径②路径/命名随版本重构过时③外链/空占位。评级：`10`=开发 B+/业务 A− ｜ `11`(B类) A− ｜ `12` B+；含 **6 类 P0 硬偏差**。
- **⚠️ 编号映射**：此报告成文于目录重编号之前，正文中的 **01/02/03 分别对应现在的 10/11/12**（≠ `01-trialpos-docs`）。

**② 源码分析文档（01-trialpos-docs）** — [`reverse-docs-vs-code-audit-2026-07-14.md`](./90-verification/reverse-docs-vs-code-audit-2026-07-14.md) + [`slice-reverse-docs-detail.md`](./90-verification/slice-reverse-docs-detail.md)（5 卷册逐 file:line）
- 结论：画像与镜像截然不同——**质的/算法级分析出众**（行号级命中、分析发现 2 个真实 Bug），**但被三类硬伤污染**：门面架构造假（端侧 DB 实为 **SQL Server（SQLEXPRESS）** 而非"双 SQLite"）、定量统计系统性捏造（卷二行数夸大 16~38 倍 + 虚假"未检出物理拉取"免责）、`Application/Source/` 链接全断。评级：卷四 B+/A− · 卷二核心 B− · 卷三 DB C+/设备·接口 B+ · 卷一 C+ · 卷五 C。含 **3 类 P0**。

---

## 3. 使用与维护

- **检索**：镜像库（10/11/12）主要用于 `grep` 全文检索与差分基线；浏览渲染请回各自线上源（frontmatter/README 里有 `source_url`）。
- **图片**：`10-`/`11-` 附件多已离线到 `attachments/`；`12-` 图片写作 wiki 根绝对路径，本地不渲染。
- **权威性顺序**：真实代码 > `90-` 核查结论 > 各线上镜像 > `01-` 代码分析文档（后者更新较早）。
- **再同步**：`10-`/`11-` 见各自 `_sync/SYNC-LOG.md`（按 `version` + `sync-state.json` 增量）；`12-` 需重新 clone（git 履历已移除）。

## 4. 安全与合规

- 本库含 **TrialPOS / POS4U 未公开供应商资料 + 内部基础设施信息**（内网主机 `*.trechina.cn`、私网 IP、运用密码等）。**保持本地/私有，勿接公开仓库、勿对外发送。**
- 2026-07-14 已做一次敏感信息处置：移除 `12-` git 履历；`01-构築手順` 页中误写的 GitHub token 明文已替换为占位符（该 token 仍需在 GitHub 侧撤销、并订正 Confluence Cloud 原页面）。
