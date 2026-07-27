---
title: 流水·集计表字典 · TransactionLog / TransactionManagement（Tran 域）
layer: 40_data
module: database
audience: [重构开发, 读码, DBA]
genre: reference
code_baseline: latest
code_refs:
  - Application/Database/01_Tables/00_CreateOrder4Tran.txt
  - Application/Database/01_Tables/dbo.TransactionLog.Table.sql
  - Application/Database/01_Tables/dbo.TransactionManagement.Table.sql
verification: verified
verified_by: ./01_overview.md
related:
  data: [./01_overview.md, ./02_master_tables.md, ./04_views.md, ./06_enums_constants.md, ./07_master_sync.md]
  flows: [../70_flows/sale_end_to_end.md, ../70_flows/return_void.md]
  portal: [../00_portal/glossary.md]
owner: jinianxiang
updated: 2026-07-14
---

# 流水·集计表字典（Tran 域）

> 交易流水与集计物理上主要落 **`POS4U_Trial_Tran`** 库（[`00_CreateOrder4Tran.txt`](Application/Database/01_Tables/00_CreateOrder4Tran.txt) 实测引用 73 表）；核心交易表在 Master/Tran **两库各建一份**（[01_overview §2](./01_overview.md)）。本篇给分域清单 + 两张核心表字典。

## 1. 按域分组清单（Tran 库）

> 表名可回 `Application/Database/01_Tables/dbo.<名>.Table.sql`。

| 域 | 代表表 |
|---|---|
| **交易核心（两库共建）** | `TransactionLog`·`TransactionManagement`·`TransactionSummary`·`TransactionResponse`·`TransactionLogQueue`·`TransactionLogState`·`VoidTransactionManagement`·`MemberReceiptHistory`·`EvidenceReceiptTransactionManagement` |
| **日次集计 Daily** | `DailyPosSalesTotal`·`DailyOperatorSalesTotal`·`DailyOperatorTimeTotal`·`DailyTimeZoneTotal`·`DailyReasonTypeTotal`·`DailyStampTypeTotal`·`DailyTicketPointPaymentTotal`·`DailyDealCodeTotal`·`DailyCreditPaymentTotal`·`DailyPosTerminalCapacity`·`DailyPosTerminalCapacityThreshold`·（+`*SystemDate` 变体） |
| **电子日志 EJournal** | `EJournal`·`EJournalManagement`·`EJournalReceipt`·`EJournalState`·`EJournalBackupManagement` |
| **现金·钱箱** | `CashTotal`·`CashChangerStatus`·`CashChangerStatusAtClose` |
| **积分离线** | `PointOffline`·`PointInfinityOffline`·`RMCouponPoint`·`RMCouponStampPoint`·`RMLoginPoint` |
| **传输·发送** | `SendDailyFileManagement`·`SendHourlyFileManagement`·`TransactionTicketPointPaymentDetail` |
| **主数据同步** | `MasterSyncManagement`·`MasterUpdateLog`·`PosMasterUpdateManagement`·`ReserveMasterSyncItemMasterManagement`·`BOReceiveMasterHistory` → 详见 [07_master_sync](./07_master_sync.md) |
| **排程·机器管理** | `ScheduleQueue`·`ScheduleLog`·`AdministoratorModuleManagement`·`VMManagement`·`VMModuleUploadManagement`·`OnPremisesMachineManagement`·`OnPremisesMachineModuleUploadManagement`·`MaintenanceFileManagement`·`DynamicPricingMasterFileManagement` |
| **BackOffice 后端** | `BOAreaMaster`·`BOAreaStoreMaster`·`BOSession`·`BOStoreManagement`·`BOUserMaster`·`BOBrandCodeMaster`·`BOCodeMaster`·`BOMessageManagement`·`BORoleMaster`·`BORoleAbilityMaster`·`BOAbilityMaster`·`BOStoreCalendarManagement`·`BOScheduleDateTimeManagement` |
| **Reserve（非条码差分）** | `ReserveNonBarcodeOtherItemManagement`·`ReserveNonBarcodeOtherItemMaster`·`ReserveNonBarcodeOtherItemCategoryMaster`·`ReserveItemImageMaster` |
| **状态·使用数据** | `BusinessState`·`MobileUsageData`·`FaceMeUsageData`·`NodeMaster`（共建） |

## 2. 核心表：`TransactionLog`（取引ログ · `[xml]` 一体化落盘）

来源 [`Application/Database/01_Tables/dbo.TransactionLog.Table.sql`](Application/Database/01_Tables/dbo.TransactionLog.Table.sql)。**PK = 五元组（CLUSTERED，`:25-32`）**；另有附加索引 [`zz_IDX_TransactionLog_1.sql`](Application/Database/01_Tables/zz_IDX_TransactionLog_1.sql)。

| 字段 | 类型 | Null | 行 | 说明 |
|---|---|---|---|---|
| `CompanyCode` | nvarchar(10) | NOT NULL | :13 | PK① |
| `StoreCode` | nvarchar(10) | NOT NULL | :14 | PK② |
| `TerminalNo` | int | NOT NULL | :15 | PK③ 端末番号 |
| `ManagedNo` | int | NOT NULL | :16 | PK④ 管理番号 |
| `TransactionNo` | bigint | NOT NULL | :17 | PK⑤ 取引番号 |
| `PATransactionNo` | bigint | NOT NULL | :18 | 支払機取引番号 |
| `GenerateDateTime` | datetime2 | NOT NULL | :19 | 生成日時 |
| `BusinessDate` | datetime2 | NOT NULL | :20 | 営業日 |
| `BusinessCount` | bigint | NOT NULL | :21 | 営業回数 |
| `TransactionType` | int | NOT NULL | :22 | 取引種別 → [TranLogTypes](./06_enums_constants.md)（101/105/121/201…） |
| `ReceiptNo` | bigint | NOT NULL | :23 | レシート番号 |
| **`TransactionData`** | **`[xml]`** | **NOT NULL** | **:24** | **取引全体（明細/税/支払/値引）を XML シリアライズして 1 列に格納** |

> 🔑 **架构要点**：一笔交易的完整树（商品明细、税、支付、折扣、积分…）被序列化为单列 `[xml]`（`:24`），而非展开成多张明细表。下游集计/传输经视图 [`vTLogTransfer`](./04_views.md)（引用 `TransactionLog`+`TransactionManagement`）异步抽取。术语 TLog 见 [glossary](../00_portal/glossary.md)；交易生成流程见 [sale_end_to_end](../70_flows/sale_end_to_end.md)。

## 3. 核心表：`TransactionManagement`（取引の集计·传输状态机）

来源 [`Application/Database/01_Tables/dbo.TransactionManagement.Table.sql`](Application/Database/01_Tables/dbo.TransactionManagement.Table.sql)。与 `TransactionLog` **同五元组 PK（CLUSTERED，`:27-34`）**——一条日志对应一条管理状态。

| 字段 | 类型 | Null | 行 | 说明 |
|---|---|---|---|---|
| 五元组 PK | — | NOT NULL | :13-17 | 同 TransactionLog |
| `SummaryState` | int | NOT NULL | :18 | 集计状态 |
| `TransferState` | int | NOT NULL | :19 | 传输（上传）状态 |
| `HeadquartersTransferState` | int | NOT NULL | :20 | 本部传输状态 |
| `UpdateDateTime` | datetime2 | NOT NULL | :21 | 更新日時 |
| `SummaryStateUpdateDateTime` / `TransferStateUpdateDateTime` / `HeadquartersTransferStateUpdateDateTime` | datetime2 | NULL | :22-24 | 各状态更新时刻 |
| `AddAfterPointState` | int | NULL | :25 | 後付ポイント状态 |
| `AddAfterPointStateUpdateDateTime` | datetime2 | NULL | :26 | 同上更新时刻 |

- 三个 `*State`（`int`）驱动"集计 → 端末上传 → 本部传输"的分阶段异步流转；每阶段各带独立更新时刻，支持断点重试。
- 相关状态常量族见 [06_enums_constants](./06_enums_constants.md)；异常/未确定交易另有 `UnknownStatusTransactionManagement`、`MTransactionManagement`（中间取引）。

## 4. 可信度与核查

- **verified**：两张核心表全字段 / PK / 附加索引带 `file:line`；分域清单逐表可回 `.Table.sql`。
- `*State` 各字段的**具体取值语义**须回对应 C# 状态常量或消费 SP 核实，本篇仅给字段与类型，未断言 int 值含义。

## 5. ST-POS 迁移提示

> 🔀 POS4U `[xml]` 一体化落盘 + 三段 `*State` 传输状态机，对应 ST-POS `tranlog` 文档 + Cart→Cloud 转发链路；两者语义映射外链团队内部设计库，不在本体系。
