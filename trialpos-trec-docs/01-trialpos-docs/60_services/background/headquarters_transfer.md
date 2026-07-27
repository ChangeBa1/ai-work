---
title: 本部转送模块（Background.Business.HeadquartersTransfer）
layer: 60_services
module: Background.Business.HeadquartersTransfer
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/POS4UBackground/Business/Background.Business.HeadquartersTransfer/HeadquartersTransfer.cs
  - Application/Source/POS4UBackground/Business/Background.Business.HeadquartersTransfer/HeadquartersTransferBase.cs
  - Application/Source/POS4UBackground/Business/Background.Business.HeadquartersTransfer/Logic/
  - Application/Source/POS4UBackground/Business/Background.Business.HeadquartersTransfer/Const/HeadquartersTranferConvertDataByType.cs
  - Application/Source/POS4UBackground/Business/Background.Business.HeadquartersTransfer/Utility/Compressor.cs
verification: verified
related:
  services:
    - ./index.md
    - ./tranlog_service.md
    - ./schedule_queue.md
owner: jinianxiang
updated: 2026-07-14
---

# 本部转送模块（Background.Business.HeadquartersTransfer）

> `Background.Business.HeadquartersTransfer` 把店内的交易日志、电子日志、各类精算数据**生成为本部（HQ）约定格式的定宽文本文件、压缩为 ZIP 后转送**。分 Daily / Hourly 两种调度。

---

## 1. 入口与分发

- `HeadquartersTransfer.cs:15` `class HeadquartersTransfer : QueueModuleBase`：队列 `QueueNames.HeadquartersTransfer`（:49）；`OnSetup`（:39）登记 Daily/Hourly（:41-42）；`DoJob`（:55，带重试）→ `ExecuteTransfer`（:93）按消息 `ScheduleName` 实例化 `HeadquartersTransferDaily` / `Hourly` 并 `.Execute()`（:97-99）。
- `HeadquartersTransferBase.cs:12` `abstract : ScheduleBase`：`CreateParam`（:27，BusinessDate 缺省=前一日 :37）；`ExecuteInternal`（:49）并行跑各 task 插件（:78-89）并 `WriteLog`。
- `HeadquartersTransferDaily.cs:16`：任务组 `HeadquartersTransferDaily`（:28）；`Execute`（:33）先 `CheckSummaryError`（:62，若有未集计/集计错误则中止并发邮件通知 :47-48），否则 `ExecuteInternal`。
- `HeadquartersTransferHourly.cs:9`：任务组 `HeadquartersTransferHourly`（:21）；`Execute`（:26）直接 `CreateParam` + `ExecuteInternal`。

> Daily 依赖 [TranLogService](./tranlog_service.md) 的集计完成（`CheckSummaryError`）；未集计完成不转送。

---

## 2. 产出文件（Logic → 文件 → SP）

各 task 插件 `: HeadquartersTransferLogicBase`（或 `*TotalFileLogicBase`），通过 `override FileName` / `SendDailyFileDataPrefix` 声明文件名，`override SpName` 声明转送状态更新 SP。文件为**定宽文本**（各类源码内附定宽记录样例），归档为 `{店铺4位}{时间戳}{编号}.ZIP`。

| Logic（`Logic/*.cs:类行`） | 内容 | 文件名 / 前缀 | 归档 | SP（转送状态） | 组 |
|---|---|---|---|---|---|
| `HeadquartersTransferTransactionLogDataFile.cs:20` | 取引日志数据 | 前缀 `WBRT9085`（:29） | `…WBRT9085.ZIP`（:118） | `usp_UpdateTransactionManagementHeadquartersTransferState`（:26） | Daily |
| `HeadquartersTransferEJournalDataFile.cs:20` | 电子日志数据 | `JL`+日期+端末4位+`.DAT` | `…WBRT5102.ZIP`（:108） | `usp_UpdateEJournalManagementHeadquartersTransferState`（:26） | Daily |
| `HeadquartersTransferEJournalDifferenceDataFile.cs:21` | 电子日志(取引日志)差分 | `WBRT0088`（:30）+ 全取引 `WBRT9085`（:36） | ZIP（:178） | `usp_SetSendHourlyFileManagement`（:27） | Hourly |
| `HeadquartersTransferOperatorTotalFile.cs:11` | 责任者精算数据 | `WBRT5080.TXT`（:20） | ZIP（`IsArchive`:23） | `TotalFileTypes.OperatorTotalFile` | Daily |
| `HeadquartersTransferTimeZoneTotalFile.cs:11` | 时间帯精算数据 | `WBRT5083.TXT`（:20） | ZIP | `TotalFileTypes.TimeZoneTotalFile` | Daily |
| `HeadquartersTransferTerminalTotalFile.cs:12` | 收银机别取引别精算 | `WBRT0042.TXT`（:21） | ZIP | `TotalFileTypes.TerminalTotalFile` | Daily |
| `HeadquartersTransferPriceChangeLogDataFile.cs:12` | 单价变更日志数据 | `WBRT2047.TXT`（:21） | ZIP | `TotalFileTypes.PriceChangeLogDataFile` | Daily |

基类：`Logic/HeadquartersTransferLogicBase.cs:24`（`Compressor.CompressFilesToZip` :170，产出 `.END` 触发文件）；`HeadquartersTransferTotalFileLogicBase.cs:15`（`OutputDirectory` 取 `LocalOutputDirectoryPath` :39，`IsArchive` 时归档 :67）。值对象 `EJournalDataValue.cs` / `EJournalDifferenceDataValue.cs` / `TransactionLogDataValue.cs`。

> 注册：云端 `PluginAdministrator.xml` 的 `HeadquartersTransferDaily` 组（TransactionLog/EJournal/Operator/PriceChange/Terminal/TimeZone）与 `HeadquartersTransferHourly` 组（EJournalDifference）；on-prem / BO 变体无此模块。

---

## 3. 精算码 → 数据类型转换

`Const/HeadquartersTranferConvertDataByType.cs:8`：把精算码映射为本部数据类型并输出定宽 CSV 记录。

- `CodeTypePairs` 字典（:11-192）：如 `Sales→B`、`CashPayment→F`、`TransactionTime→H` 等。
- `enum EnumDataCode`（:212）：精算码枚举（`Sales=0001`、`CashPayment=0129`、`CreditPayment=0346` 等）。
- `enum EnumDataType`（:414）：数据类型 A–I。
- `ToString()`（:464-485）：输出定宽 CSV 记录；`ConvertToH`（:492）秒→时刻。

---

## 4. 压缩

`Utility/Compressor.cs:14` `static class Compressor`：基于 `System.IO.Compression` 的 `ZipFile.Open(outFile, ZipArchiveMode.Create)`（:86）+ `CreateEntryFromFile`（:90）；`CompressFilesToZip` 多重载（:25/:39/:55/:72）；`cleanup=true` 时删除源文件（:98-101）。

---

## 5. 常量枚举（`Const/`）

- `HeadquartersTransferTypes.cs`：`Hourly`="HQTransferHourly"（:9）、`Daily`="HQTransferDaily"（:12）。
- `HeadquartersTransferDataFileTypes.cs`：`TransactionLogDataFile`（:9）、`EJournalDataFile`（:12）、`EJournalDifferenceDataFile`（:15）。
- `HeadquartersTransferTotalFileTypes.cs`：`OperatorTotalFile`（:9）、`TimeZoneTotalFile`（:12）、`TerminalTotalFile`（:15）、`PriceChangeLogDataFile`（:18）。

---

## 6. 异常与通知

`HeadquartersTransferDaily.CheckSummaryError`（:62）检测到未集计/集计错误时，经 `Notification.SendNotification` 发邮件（:47-48）并中止当日转送。通知插件 `BackgroundCommon/Const/BackgroundCommonPluginIds.cs:13` `Notification`（`INotification` → `NotificationMail`）。

---

## 7. 可信度与核查

`verification: verified`：入口/分发、7 个产出文件的类行 / 文件名 / SP、转换类型表、Compressor、枚举均实测 最新发布（WBRT 文件名与 `SpName` 抽样逐行核对）。WBRT 编号的本部侧含义（外部约定）不作解释。`QueueModuleBase` / `ScheduleBase` / `Factory` / `QueueNames` 属外部框架（uncheckable）；on-prem/BO 变体不含本模块。
