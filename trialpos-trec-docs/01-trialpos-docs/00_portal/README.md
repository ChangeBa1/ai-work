---
title: POS4U 源码分析文档体系 · 门户
layer: 00_portal
genre: meta
audience: [全体]
code_baseline: latest
verification: verified
owner: jinianxiang
updated: 2026-07-14
---

# POS4U 源码分析文档体系（`01-trialpos-docs`）

> **一句话**：以 **POS4U 真实源码**（`trialpos-snapshots`，基准 最新发布）为唯一真值，为現行 TRIAL 自社 POS（POS4U / TRI-POS）建立的**代码锚定、单一真相源、可信度分级**的完整 AS-IS 文档体系，服务于 **ST-POS 完全内製化重构**。
>
> **密级**：🟡 敏感（含未公开供应商资料）· 仅本地/私有。

---

## 0. 这是什么

本体系是**旧 `01-trialpos-docs`**（StackShift 自动分析的旧文档，已归档删除、备份见 `z-archive/`）的**架构级重构**，并已接替其占用 `01-` 目录名成为权威版本：把散落的"规格书/模块分析/专项深评"三种体裁，按 **C4/arc42 分层** 重整为单一真相源，全程回 `trialpos-snapshots` 代码核实。设计依据见 [`architecture-redesign-proposal.md`](./architecture-redesign-proposal.md)；写作契约见 [`conventions.md`](./conventions.md)。

**先读**：[`conventions.md`](./conventions.md)（9 原则 + 真值基线 + 模板）· [`code-map.md`](./code-map.md)（代码→文档地图）· [`reading-paths.md`](./reading-paths.md)（按角色的推荐动线）· [`glossary.md`](./glossary.md)（术语）。

---

## 1. 卷册地图

| 层 | 定位 | 体裁 | 入口 |
|---|---|---|---|
| **00_portal** | 门户 / 术语 / 代码地图 / 规范 | meta | 本页 |
| **10_architecture** | C4 上下文·容器·部署·运行时·IPC·数据流·横切 | explanation | [index](../10_architecture/) |
| **15_howto** | 新建模块/画面/设备插件 教程 | how-to | [index](../15_howto/) |
| **20_framework** | WinPOS 引擎五要素·状态机·基类·规约 | explanation | [index](../20_framework/index.md) |
| **30_domain ★** | 22 个 Business.* 模块权威单篇 | reference | [index](../30_domain/index.md) |
| **40_data** | SQL Server 双库 表/SP/视图/枚举字典 | reference | [index](../40_data/01_overview.md) |
| **50_devices** | 78 设备族总表 + 分族 | reference | [index](../50_devices/index.md) |
| **60_services** | 边缘 API / 后台 / 云 BO | reference | [edge](../60_services/edge-api/index.md) |
| **70_flows** | 端到端场景叙事（只链接不复制） | explanation | [index](../70_flows/index.md) |
| **80_decisions** | 代码分析 ADR + 缺陷调查 | adr | [index](../80_decisions/index.md) |
| **90_traceability** | 映射矩阵 / 覆盖率 / 可信度 | meta | [matrix](../90_traceability/matrix.md) |
| **99_archive** | 封存历史层 | — | [README](../99_archive/README.md) |

★ = 单一真相源层。

---

## 2. 九条原则（摘要）

单一真相源 · 代码锚定(file:line) · 版本无关链接(`Application/Source/`=最新版) · 可信度分级(verified/unverified/uncheckable) · 量化诚实 · 体裁分离 · 范围=POS4U AS-IS · 核查不能显式标注 · docs-as-code。**详见 [`conventions.md`](./conventions.md)。**

---

## 3. 权威性顺序

**真实代码 > 90-verification 核查结论 > 本体系（现 `01-`，已核实层）> 线上镜像(10/11/12) > 旧 `01-` 代码分析文档（已归档删除，备份见 `z-archive/`）**。

任何标 `verified` 的文档，其结论以 `../../90-verification/` 为精度基线。

---

## 4. 与相邻库的关系

- 旧 `01-trialpos-docs`（StackShift 自动分析）：本体系的**前身/素材源**，已于 2026-07-14 归档删除、备份为 `z-archive/trialpos-trec-docs/01-trialpos-docs.zip`；本体系接替 `01-` 目录名。
- `10/11/12-*`：Confluence/GitLab 的**线上镜像**（需与源保持同步，**不并入本体系**）；本体系仅在术语/背景处引用。
- `90-verification`：**代码核查基线**，本体系的可信度依据。
