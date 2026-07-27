---
title: 视图字典 · 24 视图清单与 BI/连携桥接
layer: 40_data
module: database
audience: [重构开发, 读码, DBA]
genre: reference
code_baseline: latest
code_refs:
  - Application/Database/03_Views/dbo.T_D_PosSales.View.sql
  - Application/Database/03_Views/dbo.vTLogTransfer.View.sql
  - Application/Database/03_Views/dbo.T_D_SaleTrade.View.sql
verification: verified
verified_by: ./01_overview.md
related:
  data: [./01_overview.md, ./03_tran_tables.md]
owner: jinianxiang
updated: 2026-07-14
---

# 视图字典

> 实测 **24 个视图**（`Application/Database/03_Views/*.View.sql`）。目录另有 2 个 `00_CreateOrder*.txt` 与 1 个非标准命名的 `dbo.CashChangerLog.sql`（未计入 24，见 [01_overview §4](./01_overview.md)）。视图主要作 **BI/上位连携系统的读取桥接**——把 POS4U 内部表名/列名映射为外部系统口径（`BranchCode`/`PosNumber`/`FixedCost`/`TradeCode` 等）。

## 1. 实测特征（两点须知）

1. **UTF-16LE 编码**：视图脚本为 UTF-16LE + BOM（非 UTF-8）。用文本工具直读会显示"字符间夹空格"，须先转码（`iconv -f UTF-16LE`）。
2. **动态创建**：视图经 `EXEC dbo.sp_executesql @statement = N'CREATE view …'` **动态建立**（实测 [`dbo.T_D_SaleTrade.View.sql`](Application/Database/03_Views/dbo.T_D_SaleTrade.View.sql)），而非直接 `CREATE VIEW`。这与 8 个命名不规范 SP 的建法一致（[05_stored_procedures](./05_stored_procedures.md)）。

## 2. 24 视图清单（按用途分组）

### 2.1 `T_D_*` — BI/连携桥接视图（12）

| 视图 | 底层来源（实测 FROM/JOIN） |
|---|---|
| `T_D_PosSales` | `DailyPosSalesTotal` + `NodeMaster`（[`dbo.T_D_PosSales.View.sql`](Application/Database/03_Views/dbo.T_D_PosSales.View.sql)） |
| `T_D_PosSalesKind` | `CashChangerStatus` + `CashChangerStatusAtClose` |
| `T_D_PosStatus` | `BusinessState` + `NodeMaster` |
| `T_D_SaleTrade` | 日次集计表（列别名 `TradeCode`/`FixedCost`/`FixedQty`） |
| `T_D_SCSaleTrade` | セルフ売上集计 |
| `T_D_Prod` · `T_D_ProdDiff` · `T_D_ProdHistory` | 商品别集计/差分/履历 |
| `T_D_CreditSales` · `T_D_CreditSalesDetail` | クレジット売上/明细 |
| `T_D_BeerOther` · `T_D_BeerOtherDetail` | ビール券等売上/明细 |

### 2.2 `TB_*` — 日次集计视图（5）

`TB_CAS_PDT_DAY_RST_1` · `TB_CAS_PDT_DAY_RST_2` · `TB_REASON_DIV_DAY_RST` · `TB_STAMP_DIV_DAY_RST` · `TB_REGI_MST`
（`_DAY_RST` = 日次结果，`REGI_MST` = レジ基本；命名沿用上位基幹系统口径。）

### 2.3 `v*` — 传输/集计视图（3）

| 视图 | 底层来源 | 用途 |
|---|---|---|
| `vTLogTransfer` | `TransactionLog` + `TransactionManagement`（[`dbo.vTLogTransfer.View.sql`](Application/Database/03_Views/dbo.vTLogTransfer.View.sql)） | 流水上传抽取（配合三段 `*State`，见 [03_tran_tables §3](./03_tran_tables.md)） |
| `vTLogSummary` | `TransactionLog` 集计 | 流水汇总 |
| `vEJournalTransfer` | `EJournal` 系 | 电子日志传输抽取 |

### 2.4 工具视图（4）

`DepartmentLevel` · `MTransactionInfo` · `PointOfflineInfo` · `REGI_NO`（`REGI_NO` 引用 `NodeMaster`）。

## 3. "失效视图"问题：订正与可核性

> 任务/`01-` 素材举例的"失效视图 **`T_D_PosSalesDetail`**"——经实测 `Application/Database/03_Views/` 下 **不存在该文件**（`find` 结果为空），现存 24 视图无此名。**不得将其记录为现存对象**（红线：不给不存在的对象名）。素材该条疑为已删对象或笔误。

- **静态可核部分（verified）**：24 视图 `FROM/JOIN` 引用的标识符（去 `sys.`/`dbo.` 前缀后）**全部命中 160 表清单**——即不存在"引用了已删表"型的破损视图。
- **运行时不可核部分（uncheckable）**：某视图是否仍被上位 BI/连携系统实际消费、是否已停用，属**外部系统运行事实**，静态代码扫描无法判定（conventions §8）。因此本篇**不对任何视图断言"失效/在用"**，仅给结构与来源。

## 4. 可信度与核查

- **verified**：24 视图计数、编码、动态创建机制、引用表存在性均可复现。
- **uncheckable**：视图的运行时消费状态、上位系统连携口径语义。

## 5. ST-POS 迁移提示

> 🔀 POS4U 用 SQL 视图做外部系统口径桥接；ST-POS 侧对应能力为服务层 API/聚合管道，无直接视图对等物。迁移取舍外链团队内部设计库。
