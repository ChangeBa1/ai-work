---
title: 存储过程索引 · 405 SP 的前缀 / 域 / 库归属
layer: 40_data
module: database
audience: [重构开发, 读码, DBA]
genre: reference
code_baseline: latest
code_refs:
  - Application/Database/04_StoredProcedures/00_CreateOrder4Master.txt
  - Application/Database/04_StoredProcedures/00_CreateOrder4Tran.txt
  - Application/Database/04_StoredProcedures/dbo.usp_GetChargePointCalculateMaster.sql
verification: verified
verified_by: ./01_overview.md
related:
  data: [./01_overview.md, ./02_master_tables.md, ./03_tran_tables.md, ./07_master_sync.md]
owner: jinianxiang
updated: 2026-07-14
---

# 存储过程索引

> 实测 **405 个 SP**（`04_StoredProcedures/*.StoredProcedure.sql`）+ **8 个命名不规范的漏计 SP** = 真实下限 **413**。数据访问层高度 SP 化，业务读写基本经 SP 而非直接 SQL。本篇给**前缀体系 / 库归属 / 域分组 / 代表 SP**，不逐个展开（405 条明细以文件为准）。

## 1. 前缀体系（实测）

| 前缀 | 计数 | 含义 |
|---|---|---|
| `usp_*` | **321** | 店端标准 SP（含读 `usp_Get*`、写 `usp_Update*/Set*/Insert*/Merge*`、删 `usp_Delete*`） |
| `usp_BO*` | **84** | BackOffice 后端 SP（BO 维护/下发主数据、`usp_BODelete*`/`usp_BOGet*`/`usp_BOMerge*`） |
| 部署序号 `01_`/`02_`/`03_` | 6 | 建立顺序前缀（依赖优先建），如 `01_dbo.usp_RaiseError`、`02_dbo.usp_GetSpecialPrice` |

> ⚠️ **前缀订正**：BO 后端前缀是 **`usp_BO`（无第二下划线）**，如 `usp_BODeleteFunctionMenuButtonMaster`。任务/素材写的 `usp_BO_` 在本库**匹配数为 0**（实测），不存在该形式。

### 1.1 8 个命名不规范的漏计 SP（真实 SP，未被标准 glob 统计）

后缀不是标准 `.StoredProcedure.sql`，但内部均为 `CREATE PROCEDURE`（经 `sp_executesql` 动态创建），实测例 [`dbo.usp_GetChargePointCalculateMaster.sql:1`](Application/Database/04_StoredProcedures/dbo.usp_GetChargePointCalculateMaster.sql)：

- `dbo.usp_BOGetDailyPosTerminalCapacity.sql`
- `dbo.usp_DeleteRegisterMTransactionManagement.sql`
- `dbo.usp_GetChargePointCalculateMaster.sql`
- `dbo.usp_GetEJournalReprintReceiptData.sql`
- `dbo.usp_InsertMemberReceiptHistory.sql`
- `dbo.usp_UpdateMTransactionManagement.StoredProcedureOperationState.sql`
- `dbo.usp_UpdateReserveMasterSyncItemMasterManagement.StoredProcedure..sql`（双点）
- `dbo.usp_UpdateSendDailyFileManagementAppendState.sql`

> 重构迁移/清点脚本若只 glob `*.StoredProcedure.sql` 会漏掉这 8 个，务必按 `CREATE PROCEDURE` 内容核实。

## 2. 库归属（Master / Tran 双 CreateOrder）

SP 同样按库分建，两份部署清单（含 UDT/UDF 行）：

- [`04_StoredProcedures/00_CreateOrder4Master.txt`](Application/Database/04_StoredProcedures/00_CreateOrder4Master.txt)：实测 259 行（含 16 UDT + 1 UDF）
- [`04_StoredProcedures/00_CreateOrder4Tran.txt`](Application/Database/04_StoredProcedures/00_CreateOrder4Tran.txt)：实测 228 行

Master SP 偏"取价/取主数据/交易落盘/状态更新"，Tran SP 偏"集计/传输/BO/排程"。

## 3. 业务域分组（导航用）

> 下表为**文件名含关键词的计数**，域间有重叠（如 `usp_GetPointRateItem` 同时命中 Point/Item），**仅供按域定位**，非互斥统计。

| 域 | 含该词 SP（实测） | 代表 SP |
|---|---|---|
| 主数据 Master 取得/维护 | ~140 | `usp_GetBarcodeConvertMaster`·`usp_GetCashChangerCheckMaster` |
| BackOffice | 85 | `usp_BODeleteFunctionMenuMaster`·`usp_BOGetDailyPosTerminalCapacity` |
| 商品 Item | 59 | `usp_GetPointRateItem`·`usp_GetSpecialPrice` |
| 交易 Transaction | 46 | `usp_UpdateTransactionLogState`·`usp_DeleteMTransactionManagement` |
| 电子日志 EJournal | 43 | `usp_UpdateEJournalState`·`usp_GetEJournalReprintReceiptData` |
| 积分 Point | 29 | `usp_GetPointRateItem`·`usp_GetChargePointCalculateMaster` |
| 日次集计 Daily | 25 | （`DailyPosSalesTotal` 等集计 SP） |
| 折扣 Discount | 15 | （Discount 系读写） |
| 支付 Payment | 9 | — |
| 精算 Close | 6 | — |
| 主数据同步 Sync | 4 | `usp_UpdateReserveMasterSyncItemMasterManagement` → [07_master_sync](./07_master_sync.md) |
| 会员/钱箱/税 | 4/4/2 | `usp_InsertMemberReceiptHistory` |

### 3.1 基础/优先建立 SP（部署序号前缀）

| SP | 序号 | 职责 |
|---|---|---|
| `usp_RaiseError` | 01_ | 统一错误抛出（被其他 SP 依赖） |
| `usp_GetPointRateItem` / `usp_GetSpecialPrice` | 02_ | 取积分率 / 取特价 |
| `usp_UpdateEJournalState` / `usp_UpdateTransactionLogState` | 02_ | 日志/流水状态更新 |
| `usp_UpdateVersionManagement` | 03_ | 版本管理更新 |

### 3.2 BI 扩展 SP

`Application/Database/10_BI/04_StoredProcedures/` 另有 ~13 个 `usp_GetBISalesFlash*` / `usp_Get*TimeZoneTotal` / `usp_SetBI*`（销售速报），不计入 405 主口径（见 [01_overview §4](./01_overview.md)）。

## 4. 可信度与核查

- **verified**：前缀计数、库归属行数、8 漏计 SP、代表 SP 名均可复现（glob/grep）。
- 域分组计数为关键词匹配（有重叠），已显式标注；单个 SP 的**入参/业务逻辑**须回其 `.sql` 文件核实。

## 5. ST-POS 迁移提示

> 🔀 POS4U 的 SP 化数据访问层（含 `sp_executesql` 动态 SP）在 ST-POS 侧被服务层业务逻辑 + MongoDB 聚合替代，无 SP 对等物。迁移映射外链团队内部设计库。
