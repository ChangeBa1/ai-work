---
title: 定时调度与队列基础设施（QueueScheduler / Schedule / QueueManager）
layer: 60_services
module: Background.Business.QueueScheduler / Schedule / BackgroundCommon
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/POS4UBackground/Business/Background.Business.QueueScheduler/QueueScheduler.cs
  - Application/Source/POS4UBackground/Business/Background.Business.Schedule/Schedule.cs
  - Application/Source/POS4UBackground/Business/Background.Business.Schedule/Const/SchedulePluginGroupIds.cs
  - Application/Source/POS4UBackground/Business/Background.Business.BackgroundCommon/Queue/
  - Application/Source/POS4UBackground/Business/Background.Business.BackgroundCommon/Schedule/
verification: verified
related:
  services:
    - ./index.md
    - ./transfer.md
    - ./tranlog_service.md
    - ./headquarters_transfer.md
owner: jinianxiang
updated: 2026-07-14
---

# 定时调度与队列基础设施

> 本文覆盖后台的「调度触发 + 队列消费 + 调度框架」：`QueueScheduler`（定时向队列投递触发消息）、`Schedule`（消费 Schedule 队列执行各调度任务），以及 `BackgroundCommon` 提供的 3 个队列管理器与 `ScheduleBase` 框架。它是 [transfer](./transfer.md)、[tranlog_service](./tranlog_service.md)、[headquarters_transfer](./headquarters_transfer.md) 共用的底座。

---

## 1. QueueScheduler（定时投递触发消息）

`Background.Business.QueueScheduler/QueueScheduler.cs:16` `class QueueScheduler : AdministratorModuleBase`：

- `OnSetup`（:30）读取 `QueueSchedule.xml`（`QueueScheduleXmlReader.Read` :32）。
- `OnStart`（:39）为每条计划建 `Timer`（:43），到点调 `ScheduleQueueAccessor.AddMessageQueue(MessageType, Message, DataAccessTypes.Tran)`（:46）投递触发消息，按 `CalcDueTime`（:106）/ `Interval` 周期触发；`RoundUp`（:137）时刻取整。
- `OnStop`（:62）释放 timers。
- **仅 on-prem 变体装载**（`PluginAdministrator_OnPremises.xml:49-52`）。

配置读取：`Utility/QueueScheduleXmlReader.cs:13` `Read`（:20）解析 `<Queue>`（Id/Name/MessageType/Message；`ExecuteTime` "HH:mm:ss" :64；`Interval` "dd.hh:mm:ss" :73）→ `QueueScheduleInfo[]`（`Const/Class/QueueScheduleInfo.cs:8`）。

配置文件 `POS4U.WindowsService.Administrator/Settings/QueueSchedule.xml`：**启用** `CyclicClear`（每日 03:00）、`MasterSyncPosBulk`（每日 02:00）；其余多为注释（HeadquartersTransfer Daily/Hourly、AddAfterPoint、MakeDailyMasterDownloadFile、MasterSyncBulk/Diff 等）。

---

## 2. Schedule（消费 Schedule 队列）

`Background.Business.Schedule/Schedule.cs:15` `class Schedule : QueueModuleBase`：

- `OnSetup`（:36）`Factory.CreateGroupPairs<ScheduleBase>(SchedulePluginGroupIds.Schedules.Id)` 装载调度插件。
- `GetQueueName()`（:42）`QueueNames.Schedule`。
- `DoJob`（:48）按消息 `ScheduleName` 选插件 → `Init` + `Start`。

**18 个调度组**（`Const/SchedulePluginGroupIds.cs`，实测 18 个）：`Schedules`(:14)、`CheckOtherVM`(:19)、`CheckVMManagement`(:24)、`CyclicClear`(:29)、`MakeRMReportFile`(:34)、`CerateStoreSchedule`(:39)、`CreateMasterSyncQueueSchedule`(:44)、`CheckScheduleAndVM`(:49)、`ResetTransferQueue`(:54)、`AddAfterPoint`(:59)、`MakeDailyMasterDownloadFile`(:64)、`EJournalBackup`(:69)、`BOCyclicClear`(:74)、`BOStoreCopy`(:79)、`CheckPosTerminalCapacity`(:84)、`MakeMobileUsageDataFile`(:89)、`MakeFaceMeUsageDataFile`(:94)、`TransferOfflineTranLogs`(:99)。

结构：`Logic/Schedule/*Schedule.cs`（`: ScheduleBase`，各对应一个调度组）+ `Logic/Task/*Task.cs`（`: ScheduleTaskBase`）。数据模型 `Model/AddAfterPointDataModel.cs:8`（CardNo/AccrualDateTime/StoreCode/TerminalNo/SequenceNo/ReasonCode/ReductionFlag/AddPoint）等。

> `QueueScheduler`（定时投递）与 `Schedule`（消费执行）的分工：前者按时钟把「该跑某调度」的消息塞进队列，后者从队列取出并实际执行。二者经 Schedule 队列解耦。

---

## 3. 三个队列管理器（`BackgroundCommon/Queue/`，均 `: IQueueManager`）

| 管理器（`Queue/*.cs:类行`） | 队列 | 默认 `DataAccessType` | 消费者 |
|---|---|---|---|
| `EJournalQueueManager.cs:13` | 电子日志队列 | `Master`（:25） | [TransferEJournal](./transfer.md) |
| `ScheduleQueueManager.cs:14` | Schedule 队列（消息序列化为 JSON，:45） | `Tran`（:26） | [Schedule](#2-schedule消费-schedule-队列) / [HeadquartersTransfer](./headquarters_transfer.md) |
| `SummaryQueueManager.cs:13` | 集计（取引日志）队列 | `Tran`（:25） | [TranLogService](./tranlog_service.md) / [TransferTLog](./transfer.md) |

- **后端可插拔**：队列的实际存储由 XML 变体决定——`ScheduleQueueManager` 在云端用 `Azure.Logic.StorageQueueAccessor`（`PluginAdministrator.xml:11-14`），on-prem 用 `SQLDatabaseScheduleQueueAccessor`（`PluginAdministrator_OnPremises.xml:11-14`）。即「Azure Storage Queue vs SQL 表」由部署切换。
- 部分 `ClearQueue` / `DeleteQueue`（及部分 `GetMessageQueueCount`）为 `NotImplementedException`（EJournal :103-125、Summary :103-124）。

---

## 4. 调度框架基类（`BackgroundCommon/Schedule/`）

- `ScheduleBase.cs:15` `abstract class ScheduleBase`：`TaskPlugins` 装载（:23）；`Start()`（:87 → 私有 :222）依次跑 Before/任务列表/After，写调度日志（`WriteLog` :132、`ScheduleLogDataAccessor.InsertScheduleLog` :181），支持 `IsScheduleTerminateRequired` 中断（:263）。
- `ScheduleTaskBase.cs:13` `abstract class ScheduleTaskBase`：`Execute`（:54）→ 抽象 `DoJob`（:91）；`WriteLog`（:99，LogType=Task）；超 `ScheduleTaskExecTimeLogThresholdMilliseconds` 阈值 Warn（:106）。
- `BatchResult.cs:11`：任务结果载体（TaskName / IsCompleted / IsSuccess / ReturnCode / Comment / ErrorMessage / Exception / StartTime / EndTime / `ElapsedTime` :41 / `IsScheduleTerminateRequired` :50）。

> `HeadquartersTransferBase`（[headquarters_transfer.md](./headquarters_transfer.md)）即继承 `ScheduleBase`，复用此框架跑 Daily/Hourly 任务。

---

## 5. 相关枚举（`BackgroundCommon/Const/`）

| 枚举 | 值 |
|---|---|
| `ScheduledTypes.cs` | `Regular`="01"（:9，定时执行）、`AnyTime`="02"（:12，随时执行） |
| `ScheduleLogTypes.cs` | `Schedule`=1（:9）、`Task`=2（:12） |
| `ScheduleStartEndFlags.cs` | `Start`=0（:9）、`End`=1（:12） |
| `SummaryStates.cs` | `Untreated`=0（:9）、`Success`=1（:12）、`Error`=9（:15）（底层类名 `SumamryState`，原文拼写） |
| `ProcessStatusTypes.cs` | `Available`=0（:11，可执行）、`Processing`=1（:16，处理中） |

---

## 6. 可信度与核查

`verification: verified`：`QueueScheduler` / `Schedule` 入口与方法行号、18 个调度组、3 个队列管理器的默认 `DataAccessType`、调度框架基类、枚举值均实测 最新发布（逐行核对）。`QueueSchedule.xml` 的启用/注释状态与队列后端可插拔取自 XML 侦察。`AdministratorModuleBase` / `QueueModuleBase` / `Factory` / `IQueueManager` / `QueueNames.*` / `ScheduleQueueAccessor` 属外部框架或 Data 层（本文只描述用法，框架内部 uncheckable）。
