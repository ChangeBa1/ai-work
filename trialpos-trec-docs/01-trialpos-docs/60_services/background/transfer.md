---
title: 数据转送模块（Background.Business.Transfer）
layer: 60_services
module: Background.Business.Transfer
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/POS4UBackground/Business/Background.Business.Transfer/Transfer.cs
  - Application/Source/POS4UBackground/Business/Background.Business.Transfer/Controller.cs
  - Application/Source/POS4UBackground/Business/Background.Business.BackgroundCommon/Const/TransferStates.cs
verification: verified
related:
  services:
    - ./index.md
    - ./tranlog_service.md
    - ./schedule_queue.md
owner: jinianxiang
updated: 2026-07-14
---

# 数据转送模块（Background.Business.Transfer）

> `Background.Business.Transfer` 负责把交易日志（TransactionLog）与电子日志（EJournal）**从产生侧转送到消费侧**。同一插件组 `Transfer` 在两种部署下装载不同实现，方向不同。

---

## 1. 入口与调度

- `Transfer.cs:12` `class Transfer : ServiceTimerBase`：定时驱动，间隔取 `TransferIntervalMillisecond`（:20）；`OnSetup` → `new Controller(this)`（:25）；`OnExecute` → `Controller.Execute`（:48）。
- `Controller.cs:11`：`Factory.CreateGroupPairs(TransferPluginGroupIds.Transfer)`（:24）装载插件；`Execute` 把各插件的 `Transfer()` 放入并行 `Task` 并 `WaitAll`（:49-65）。
- 插件组常量 `Const/TransferPluginGroupIds.cs:13` `Transfer`（注释「上位転送（ストコン、AzureVM）」:11-12）。

---

## 2. 两种部署变体（同组 `Transfer`，方向不同）

| 变体 | 注册（XML） | 实现 | 方向 |
|---|---|---|---|
| **云端** | `PluginAdministrator.xml:314-323` | `TransferTLog`、`TransferEJournal` | **Master DB → Tran DB** 的站内转送（经队列） |
| **on-prem** | `PluginAdministrator_OnPremises.xml:77-87` | `TransferTransactionLogOnPremises`、`TransferEJournalOnPremises` | **店内 POS/机器 → 上位服务器**（经 WebService 上传） |

---

## 3. 云端逻辑（Master → Tran DB，经队列）

- `Logic/Cloud/TransferLogicBase.cs:8`（`abstract`，抽象 `Transfer()`）。
- `Logic/Cloud/TransferDataBase.cs:12`（`abstract`）：从队列取消息 `QueueMgr.GetMessageQueueObj`（:47）→ `DoJob` → 成功删队列 / 失败解锁（:71-78）。
- `Logic/Cloud/TransferTLog.cs:17`：用 `SummaryQueueManager`（:20），队列 `QueueNames.TransactionLog`（:39）；`DoJob`（:46）读 `TransactionLogTransferAccessor.GetTransactionLogInfo`（:55）→ `InsertReceivedTransactionLogForLogicService`（:66）→ `DeleteTransactionLog`（:69）。
- `Logic/Cloud/TransferEJournal.cs:16`：用 `EJournalQueueManager`（:19），队列 `QueueNames.EJournal`（:30）；经 `ITransferLogDataAccess` 插件判重（:44），`EJournalTransferAccessor.GetEJournalInfo / InsertReceivedEJournal / DeleteEJournalInfo`（:56/:59/:69）。

---

## 4. On-prem 逻辑（POS → 上位，经 WebService）

- `Logic/Local/TransferEJournalBase.cs:23`（`abstract`）：`Transfer()`（:51）基址取 `BackgroundSettingValues.TransactionServerAddress`（:53）；`EJournalTransferAccessor.GetTransferEJournal`（:106）取本地待送 → `BackgroundServiceAccessor.PutEJournal`（:169）上送 → `UpdateEJournalManagementTransferState`（:188）标记完成。
- `Logic/Local/TransferTransactionLogBase.cs:23`：`TransactionManagementAccessor.GetTransferTransactionLog`（:257）→ `BackgroundServiceAccessor.PutTransactionLogList`（:170）→ `UpdateTransactionManagementTransferState`（:189）。
- 单端末变体：`TransferEJournalPOS.cs:14`、`TransferTransactionLogPOS.cs:14`（`GetLast*` :23、`Get*TerminalList` :43）。控制器侧（全端末）`TransferEJournalOnPremises.cs` / `TransferTransactionLogOnPremises.cs`（存在并在 on-prem XML 注册，内部未逐行核查）。

> On-prem 上送经 `BackgroundServiceAccessor.PutEJournal` / `PutTransactionLogList`，对应边缘 API 的 `BackgroundService.svc/PutEJournal` / `PutTransactionLogList`（见 [edge-api/controllers.md §5](../edge-api/controllers.md)）。

---

## 5. 状态与类型枚举（`BackgroundCommon/Const/`）

- `TransferStates.cs`：`Untreated`=0（:9）、`Success`=1（:12）、`Error`=9（:15）。
- `UploadDataTypes.cs`：`Master`=1（:9）、`Module`=2（:12）、`MasterDifference`=3（:15）。

---

## 6. 数据依赖

- 读写表（经 Accessor / SP，Tran/Master 库）：TransactionLog / TransactionManagement、EJournal / EJournalManagement 及各 `ReceivedXxx`。
- 队列：`QueueNames.TransactionLog`（Summary 队列）、`QueueNames.EJournal`（EJournal 队列）—— 队列管理器见 [schedule_queue.md §3](./schedule_queue.md)。

---

## 7. 可信度与核查

`verification: verified`：入口/调度/两变体/云端·on-prem 逻辑的类与方法行号实测 最新发布。`QueueNames.*` 常量、`ServiceTimerBase`、`Factory` 属外部框架程序集（uncheckable，见 [index.md §5](./index.md)）。`TransferEJournalOnPremises` / `TransferTransactionLogOnPremises` 仅确认存在与注册，内部实现未逐行读。
