---
title: 数据层总览 · 引擎 / 双库 / 主键规约 / 对象口径
layer: 40_data
module: database
audience: [重构开发, 读码, DBA]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Data/Data.Container/app.config
  - Application/Database/01_Tables/dbo.TransactionLog.Table.sql
  - Application/Database/01_Tables/00_CreateOrder4Master.txt
  - Application/Database/01_Tables/00_CreateOrder4Tran.txt
verification: verified
verified_by: ../00_portal/conventions.md
related:
  data: [./02_master_tables.md, ./03_tran_tables.md, ./04_views.md, ./05_stored_procedures.md, ./06_enums_constants.md, ./07_master_sync.md]
  portal: [../00_portal/code-map.md, ../00_portal/glossary.md]
owner: jinianxiang
updated: 2026-07-14
---

# 数据层总览

> 本篇是 `40_data/` 的入口，负责数据库**引擎 / 库拓扑 / 主键规约 / 对象口径**四件事的单一真相源；表/SP/视图/枚举明细各有专篇（见 frontmatter `related`）。

## 1. 引擎：SQL Server（SQLEXPRESS），不是 SQLite

店舗端 DB 引擎是 **Microsoft SQL Server（SQLEXPRESS 实例）**。

- 连接串实测（[`Application/Source/Data/Data.Container/app.config:13`](Application/Source/Data/Data.Container/app.config)）：`Data Source=(local)\SQLEXPRESS;Initial Catalog=POS4U_Trial_Master;Integrated Security=True`。
- 脚本全部是 T-SQL 方言：`sys.objects` / `OBJECT_ID` / `PRIMARY KEY CLUSTERED` / `sp_executesql` / `[money]` / `datetime2` / `[xml]` 等（见 [`Application/Database/01_Tables/dbo.TransactionLog.Table.sql:1`](Application/Database/01_Tables/dbo.TransactionLog.Table.sql)），均为 SQL Server 专属，SQLite 不支持。

> ⚠️ **口径订正**：`01-trialpos-docs/3_technical_specs/Application/Database/` 早期素材曾以 SQLite 描述本库（后已订正）。真值以 T-SQL 脚本与 `app.config` 连接串为准：**SQL Server SQLEXPRESS**。术语见 [glossary](../00_portal/glossary.md)。

## 2. 库拓扑：Master / Tran 双库（+ 本地开发单库）

同一 SQLEXPRESS 实例下并存两个业务库，由部署脚本 [`Application/Database/CreateDatabaseScript/00_CreateDatabaseScript4Master.bat`](Application/Database/CreateDatabaseScript/) 与 `...4Tran.bat` 分别建立：

| 逻辑库 | Catalog 名 | 定位 | 建库对象清单 |
|---|---|---|---|
| **Master 库** | `POS4U_Trial_Master`（[`app.config:13`](Application/Source/Data/Data.Container/app.config)） | 主数据 + 当前端末的交易落盘 | [`01_Tables/00_CreateOrder4Master.txt`](Application/Database/01_Tables/00_CreateOrder4Master.txt)：实测引用 **99** 表 |
| **Tran 库** | `POS4U_Trial_Tran`（[`app.config:16`](Application/Source/Data/Data.Container/app.config)） | 集计 / 传输 / BO 后端 / 排程 | [`01_Tables/00_CreateOrder4Tran.txt`](Application/Database/01_Tables/00_CreateOrder4Tran.txt)：实测引用 **73** 表 |
| 本地开发单库 | `POS4U_Trial`（[`app.config:7`](Application/Source/Data/Data.Container/app.config)） | `.\SQLEXPRESS` 本地一体化开发 | — |

- **两库共建 14 张同名表**（实测：两 `CreateOrder` 交集）：`EJournal` / `EJournalManagement` / `EJournalReceipt` / `EJournalState` / `EvidenceReceiptTransactionManagement` / `MemberReceiptHistory` / `NodeMaster` / `TransactionLog` / `TransactionLogQueue` / `TransactionLogState` / `TransactionManagement` / `TransactionResponse` / `TransactionSummary` / `VoidTransactionManagement`。即交易/日志/领収書一类表在两库各建一份（Master 作落盘源，Tran 作传输/集计侧）。
- 表分域明细见 [02_master_tables](./02_master_tables.md) 与 [03_tran_tables](./03_tran_tables.md)。

## 3. 主键规约：五元组联合主键

交易类表的联合主键实测为**五元组**（[`dbo.TransactionLog.Table.sql:25-32`](Application/Database/01_Tables/dbo.TransactionLog.Table.sql) `PK_TransactionLog … PRIMARY KEY CLUSTERED`）：

```
CompanyCode(nvarchar 10) · StoreCode(nvarchar 10) · TerminalNo(int) · ManagedNo(int) · TransactionNo(bigint)
```

- 列名带 `Code` 后缀（`CompanyCode`/`StoreCode`），非 `Company`/`Store`。
- `TransactionManagement` 用同一五元组 PK（[`dbo.TransactionManagement.Table.sql:27-34`](Application/Database/01_Tables/dbo.TransactionManagement.Table.sql)）。
- 主数据/设定表用其子集：`ItemMaster` 三元组 `CompanyCode/StoreCode/ItemCode`（[`dbo.ItemMaster.Table.sql:49-54`](Application/Database/01_Tables/dbo.ItemMaster.Table.sql)）；`SettingMaster` 四元组 `CompanyCode/StoreCode/TerminalNo/Key`（[`dbo.SettingMaster.Table.sql:18-24`](Application/Database/01_Tables/dbo.SettingMaster.Table.sql)）。
- 术语（五元组 / 採番 / TLog）见 [glossary](../00_portal/glossary.md)，本篇不复述。

## 4. 对象口径：目录裸文件数 ≠ 真实对象数

> **量化诚实基线**（实测 最新发布 `Application/Database/`）。"真实对象数"按 SSMS 导出的标准文件后缀 glob 统计，与目录裸文件数存在差额，差额来源如下表。

| 对象 | 真实对象数（实测） | glob 依据 | 目录裸文件 | 差额构成 |
|---|---|---|---|---|
| 表 Table | **160** | `01_Tables/*.Table.sql` | 185 | + 23 个 `zz_*.sql`（独立索引脚本）+ 2 个 `00_CreateOrder*.txt` |
| 存储过程 SP | **405** | `04_StoredProcedures/*.StoredProcedure.sql` | 434 | + 8 个命名不规范但真实的 SP（见下）+ 18 UDT + 1 UDF + 2 txt |
| 视图 View | **24** | `03_Views/*.View.sql` | 27 | + 2 个 `00_CreateOrder*.txt` + 1 个 `dbo.CashChangerLog.sql` |
| 自定义类型 UDT | **19** | 全库 `CREATE TYPE` | — | 主库 `04_StoredProcedures/` 18 个 + `10_BI/` 1 个 |
| 自定义函数 UDF | **5** | `ufn_*` | — | 主库 `04_StoredProcedures/` 1 个 + `10_BI/` 4 个 |

**关键订正点**：

1. **SP 真实数 ≈ 413，非 405**。`405` 是严格 `*.StoredProcedure.sql` glob；`04_StoredProcedures/` 另有 **8 个命名不规范的 SP 文件**（后缀写成 `.sql` / `.StoredProcedure..sql` 双点 / `.StoredProcedureOperationState.sql` 等），经核实内部均为 `CREATE PROCEDURE`（实测 [`Application/Database/04_StoredProcedures/dbo.usp_GetChargePointCalculateMaster.sql:1`](Application/Database/04_StoredProcedures/dbo.usp_GetChargePointCalculateMaster.sql) 起 `EXEC dbo.sp_executesql @statement = N'CREATE PROCEDURE …'`）。本体系沿用 **405** 作为可复现基线，并注明真实下限 413。详见 [05_stored_procedures](./05_stored_procedures.md)。
2. **UDT 实测 19，非 ~27**。早期基线/素材记 "~27"，实测全库 `CREATE TYPE` 仅 **19**（主库 18 + `10_BI` 1）。本篇以 19 为准。
3. **2 张"孤儿表"**：物理存在 `*.Table.sql` 但两库 `CreateOrder` 均未引用——`EnterpriseSystemInfoMaster`、`TerminalMaster`（实测 160 物理 vs 158 被引用；`99 Master + 73 Tran − 14 共建 = 158`）。它们可能为历史遗留或运行时按需建，重构须核实其部署路径。

> ⚙️ **BI 扩展**：`Application/Database/10_BI/`（[目录实测](Application/Database/10_BI/)）另含 1 表（`BISalesHeaders`）、~13 SP、1 UDT、4 UDF 及动态建表脚本（`BILineItems` 按公司分表），面向销售速报，不计入上述店端主口径。

## 5. 可信度与核查

- **verified**：引擎、双库 Catalog、五元组 PK、各类对象计数、8 个漏计 SP、2 张孤儿表——均带 `file:line` 或可复现 glob/`comm` 比对。
- 全部计数命令可复现（如 `ls Application/Database/01_Tables/*.Table.sql | wc -l`）。
- 汇总真值另见 [conventions §2](../00_portal/conventions.md) 与 [90_traceability](../90_traceability/verification-status.md)。

## 6. ST-POS 迁移提示

> 🔀 POS4U 的 SQL Server 双库 + `[xml]` 一体化交易落盘，与 ST-POS（KugelPOS）的 MongoDB `db_{service}_{tenant_id}` 文档模型是两套范式。迁移映射不在本体系范围，仅外链团队内部设计库。
