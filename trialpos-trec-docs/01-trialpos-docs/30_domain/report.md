---
title: 报表生成域（Business.Report）
layer: 30_domain
module: Business.Report
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Business/Business.Report/ReportBase.cs
  - Application/Source/Business/Business.Report/Report/ReportCalculatedCash.cs
  - Application/Source/Business/Business.Report/Report/ReportCloseCount.cs
  - Application/Source/Business/Business.Report/Report/ReportSalesFlash.cs
  - Application/Source/Business/Business.Report/Report/ReportSaveMTransaction.cs
  - Application/Source/Business/Business.Report/Report/ReportCAFISArchDebitSalesError.cs
verification: verified
related:
  data:  [../40_data/06_enums_constants.md]
  domain: [../30_domain/rj.md, ../30_domain/open_close.md, ../30_domain/business_common.md, ../30_domain/entry_non_cash.md]
  devices: [../50_devices/index.md]
  flows: [../70_flows/open_close_count.md]
owner: jinianxiang
updated: 2026-07-14
---

# 报表生成域（Business.Report）

> `verification: verified`——`ReportBase` 全部、18 个具体报表的声明/继承/TranLogType（含数值）/`CanExecute` 门控/`AddBody` 数据源与产出表，逐条实测于 最新发布（20 `.cs` / 4063 loc）。`TranBase`、`ReportDataSet` 生成代码、CAFIS/釣銭機设备内部标 `uncheckable`。

## 1. 模块定位

把各类**报告数据**装入 `ReportDataSet`（`Data.Container`），交 `Business.RJ` 排版打印（→ [收据·日志域](../30_domain/rj.md)）。三大族：

1. **精算/在高/速报族**：釣銭在高、精算（关店）、簡易精算、売上フラッシュ（速报）、現金外在高、中間取引保存——数据源是当日日計集計 `DailyDeal` + 总计/营业状态表 + 釣銭機。
2. **外部卡机族（CAFIS）**：CAFIS Debit / CAFIS-LAN Credit / UnionPay / 全日計 的错误·予約(プリカサーバー障害控え)·未了清单——数据源是**设备事件结果对象**（非 DB）。

- 命名空间：`ForYouApplications.POS4U.Business.Report`
- 全体实现 `IReport`、继承 `ReportBase`。
- ProjectReference（`Business.Report.csproj` 实测）：`Business.BusinessCommon`、`Business.EntryNonCash`、`Business.Operator`、`Common.Const`、`Data.Accessor`、`Data.Container`、`Device.CAFISArchLAN`、`Device.DeviceCommon`、`Device.DeviceDefine`。

## 2. 代码结构

20 个 `.cs`（`ReportBase` + `Report/` 子目录 18 具体报表 + `AssemblyInfo`）。

### 2.1 基类 `ReportBase`

[`ReportBase.cs:15`](Application/Source/Business/Business.Report/ReportBase.cs) `public abstract class ReportBase : IReport`。

| 成员 | file:line | 职责 |
|---|---|---|
| `TranLogType`（abstract） | `:20` | 子类各自绑定 |
| `TranDataSet`（protected） | `:25` | 部分报表的输入取引集 |
| `IsReceiptNoCountUp`（virtual, 默认 true） | `:31` | 是否推进レシート番号 |
| `CreateReportDataSet(userData, additionalData)` | `:45` | 模板方法：`AddHeader` → `AddBody` → 返 `ReportDataSet` |
| `CanExecute(userData, additionalData)`（virtual, 默认 true） | `:61` | 执行可否门控（子类覆写做设备/集計检查） |
| `AddHeader`（virtual） | `:72` | 填 `ReportHeader`（见下） |
| `AddBody`（abstract） | `:112` | 各报表主体 |

`AddHeader` 实测填充：`CompanyCode`/`StoreCode`/`TerminalNo`（来自 `userData`）、`ManagedNo`(`SettingValues.ManagedNo`)、`SystemDateTime`、`BusinessDate`（营业日为空则 `now+1 日`，`:85`）、`BusinessCount`、`EJournalType`（当 `additionalData=="SalesFlash"` 取 `Report_SalesFlash.Number`，否则取本报表 `TranLogType.Number`，`:87`）、`IsTrainingMode`、`ReceiptNo`（`IsReceiptNoCountUp ? BusinessCounter.NumberingCount(CounterCodes.ReceiptNo) : 0`，`:89`）、`OperatorCode`/`OperatorName`（来自 `userData.GetCashier()`，即 [Business.Operator](../30_domain/operator.md)）。

### 2.2 精算 / 在高 / 速报 / 保存 族

| 类（`Report/*.cs`） | class:line | 基类 | TranLogType（值） | 说明 |
|---|---|---|---|---|
| `ReportCalculatedCash` | `:19` | `ReportBase` | `Report_CalculatedCash`（9001） | 在高レポート |
| `ReportCloseCountCalculatedCash` | `:11` | `ReportCalculatedCash` | `Report_CloseCountCalculatedCash`（9002） | 精算在高 |
| `ReportEntryCalculatedCash` | `:13` | `ReportCalculatedCash` | **`EntryCalculatedCash`（809）** ⚠非 `Report_*` | 在高登録 |
| `ReportCloseCount` | `:13` | `ReportBase` | `Report_CloseCount`（9004） | 精算レポート |
| `ReportSalesFlash` | `:12` | `ReportBase` | `Report_SalesFlash`（9005） | 売上フラッシュ（速报） |
| `ReportCloseCountSimple` | `:12` | `ReportBase` | `Report_CloseCountSimple`（9017） | 簡易精算 |
| `ReportEntryNonCash` | `:20` | `ReportBase` | **`EntryNonCash`（815）** ⚠非 `Report_*` | 現金外在高 |
| `ReportSaveMTransaction` | `:19` | `ReportBase` | `Report_SaveMTransaction`（9003） | 中間取引保存 |

> ⚠️ 订正：原稿称"全体 TranLogType 属 `Report_*`（9000 段）"——实测 **`ReportEntryNonCash`=`EntryNonCash`(815)**、**`ReportEntryCalculatedCash`=`EntryCalculatedCash`(809)** 复用取引侧种别，非 9000 段。`Report_*` 号段为 9001–9017（**9006 缺号**）。

### 2.3 外部卡机族（CAFIS，`: ReportBase`；Unfinished 再派生）

| 家族 | Error | ErrorUnfinished（`: *Error`） | Reserve |
|---|---|---|---|
| CAFIS Debit | `...DebitSalesError` `:13` / 9007 | `...DebitSalesErrorUnfinished` `:9` / 9008 | `...DebitSalesReserve` `:13` / 9009 |
| CAFIS-LAN Credit | `...LANCreditSalesError` `:14` / 9011 | `...LANCreditSalesErrorUnfinished` `:9` / 9012 | `...LANCreditSalesReserve` `:13` / 9010 |
| CAFIS-LAN UnionPay | `...LANUnionPaySalesError` `:14` / 9014 | `...LANUnionPaySalesErrorUnfinished` `:9` / 9015 | `...LANUnionPaySalesReserve` `:13` / 9013 |
| CAFIS-LAN 全日計 | `...LANDailyTotalError` `:14` / 9016 | — | — |

（各 `*ErrorUnfinished` 仅覆写 `TranLogType` 为 `Report_*ErrorUnfinished`，其余承 `*Error`。例 [`ReportCAFISArchDebitSalesErrorUnfinished.cs:14-20`](Application/Source/Business/Business.Report/Report/ReportCAFISArchDebitSalesErrorUnfinished.cs)。）

## 3. 状态机

报表是**无状态数据生成器**——`Common/Common.Const/State/` 无 Report 专属 `*TranStates.cs`（实测）。生命周期只是 `CanExecute` → `CreateReportDataSet`（`AddHeader`+`AddBody`）。

## 4. 业务规则

### 4.1 执行门控（`CanExecute`）

- **BR-REPORT-001（集計完了门控）**：`ReportCloseCount` / `ReportSalesFlash` / `ReportCloseCountSimple` 均要求 `TransactionLogAccessor.GetCountSummaryRow(...).SummaryNotCompleted == 0`，否则报 `MessageIds.ErrorSummaryNotCompleted` 并拒绝。`ReportCloseCount.cs:26-37`、`ReportSalesFlash.cs:25-37`、`ReportCloseCountSimple.cs:25-37`。
- **BR-REPORT-002（釣銭機门控）**：`ReportCalculatedCash.CanExecute` 经 `DeviceManager` 取 `DeviceIds.CashChanger`，未初始化则尝试 `InitDevice`；连接/读取失败时——若本报表是 `EntryCalculatedCash` 则**容错返回 true**，否则报 `ErrorDeviceNotConnect`/`ErrorCashChanger` 拒绝。`ReportCalculatedCash.cs:48-88`。
- **BR-REPORT-003（CAFIS 设备门控）**：CAFIS 报表要求相应设备存在——Debit 系取 `DeviceIds.CAFISArch as ICAFISArchNoOperation`（`ReportCAFISArchDebitSalesError.cs:49-58`）；全日計取 `DeviceIds.CAFISArchLAN` + `DeviceIds.PaymentService as IPaymentServiceModeSelf`（`ReportCAFISArchLANDailyTotalError.cs:50-54`）。
- **BR-REPORT-004（保存报表门控）**：`ReportSaveMTransaction.CanExecute` 要求 `additionalData` 为携有 `SalesHeader`、`TwoOperatorsHeader[0].MTransactionId`、`TempMTranDataSet.MTranAddInfo` 的 `TranDataSet`。`ReportSaveMTransaction.cs:50-68`。

### 4.2 数据来源与产出（`AddBody`）

- **BR-REPORT-010（釣銭在高聚合）**：`ReportCalculatedCash.AddBody` 从釣銭機读数按金种（10000…1 円）分列填 `CashChanger*Count`（收纳部）与 `*Count`（回收部 OverCount），`CashTotal=Σ面额×枚数`；再 `TotalAccessor.GetCashTotalRow`（计算在高/釣銭準備金/回収）与 `GetCalculatedCashTotalRow(businessCount)` 补在高登録信息；违算 `IsUncertain` 经 `CashChangerCommon.IsUncertain`。精算变体 `businessCount-1`（`:265-272`），且精算时**跳过**在高登録补填（`:274`）。产出 `ds.CalculatedCash`。`ReportCalculatedCash.cs:97-315`。
  - `ReportCloseCountCalculatedCash` 追加读 `SettingMaster.IsCloseCountReceiptSimplePrint` 写入行（`ReportCloseCountCalculatedCash.cs:30-55`）。
- **BR-REPORT-011（精算/速报聚合）**：`ReportCloseCount` 与 `ReportSalesFlash` 结构同构——读 `BusinessStateAccessor.GetLastCloseBusinessDateRow` 定位营业日，`DailyDealAccessor.GetDailyDealList` 后按 `(DealCode, DealSubCode)` 大量分派填 `ds.CloseCount`（`CloseRowInit` 初始化）。速报仅在 header 侧以 `additionalData=="SalesFlash"` 改 `EJournalType`（BR 见 §2.1 / `ReportBase.cs:87`）。`ReportCloseCount.cs:48-`、`ReportSalesFlash.cs:47-`。
- **BR-REPORT-012（簡易精算）**：`ReportCloseCountSimple` 仅当 `IsCloseCountReceiptSimplePrint` 为真时，取 DealCode `0097`(レジマイナス)/`0098`(返品)/`2570`(プリカチャージ取消)（均 `DealSubCode==1`）填 `ds.CloseCountSimple`。`ReportCloseCountSimple.cs:45-117`。
- **BR-REPORT-013（現金外在高）**：`ReportEntryNonCash` 直接 `new EntryNonCashDataGroup(userData)`（复用 [Business.EntryNonCash](../30_domain/entry_non_cash.md) 的日計集計）逐金种映射到 `ds.NonCash`。`ReportEntryNonCash.cs:39-152`。
- **BR-REPORT-014（中間取引保存）**：`ReportSaveMTransaction.AddBody` **不查 DB**，从 `TranDataSet`（`additionalData`）取 `SalesHeader`/`LineItem`/`Payment`/`TwoOperatorsHeader[0].MTransactionId`/`Member.PointCardNo`，产出 `ds.SaveMTransaction`+`SaveMTranLineItem`（跳过 `IsCanceled`）+`SaveMTranPayment`。`IsReceiptNoCountUp=false`。`ReportSaveMTransaction.cs:36,76-143`。
- **BR-REPORT-015（CAFIS 错误分支）**：CAFIS Error 报表把 `additionalData`（`CAFISArchDeviceEventResultNoOperation` 等设备事件结果）分三支——通信错误 `AddBodyErrorCommunication`→`ds.*ErrorCommunication`；印字情報なし（其他错误，`ProcResult==OtherError`）`AddBodyErrorOther`→`ds.*ErrorOther`；印字情報あり `AddBodyError`→`ds.*Error`；并附 `AddBodyErrorAddInfo`→`ds.*AddInfo`。`IsReceiptNoCountUp=false`。`ReportCAFISArchDebitSalesError.cs:67-264`。Reserve 系产出 `ds.*Reserve`（プリカサーバー障害时的加盟店/お客様控え）。

## 5. 关键接口与契约

- `IReport`（[`Business.BusinessCommon/IReport.cs:9`](Application/Source/Business/Business.BusinessCommon/IReport.cs)，3 成员：`TranLogType` / `CreateReportDataSet` / `CanExecute`）→ 详见 [业务公共域](../30_domain/business_common.md)。
- 派发键 = `CreateReportDataSet` 的 `additionalData`：`"SalesFlash"` 字串 / `TranDataSet` / `CAFISArch*DeviceEventResult*`（不同族约定不同类型）。
- 产出 `ReportDataSet`（`Data.Container`；表如 `ReportHeader`/`CalculatedCash`/`CloseCount`/`CloseCountSimple`/`NonCash`/`SaveMTransaction`/`SaveMTranLineItem`/`SaveMTranPayment`/`CAFISArch*Error|ErrorOther|ErrorCommunication|AddInfo|Reserve`）→ 交 `Business.RJ` 打印。

```mermaid
flowchart LR
  A["调用方"] -->|"additionalData"| B["ReportBase.CreateReportDataSet"]
  B --> C["CanExecute（门控）"]
  C --> D["AddHeader（ReportHeader）"]
  D --> E["AddBody（各报表）"]
  E --> F["ReportDataSet"]
  F --> G["Business.RJ 排版打印"]
```

## 6. 数据依赖

只链接不复制字典 → [40_data/枚举与常量](../40_data/06_enums_constants.md)。实测 Accessor / SP：

- `DailyDealAccessor.GetDailyDealList` → SP `dbo.usp_GetDailyDealList`（日計集計；精算/速报/簡易/現金外共用）。
- `TotalAccessor.GetCashTotalRow` → `usp_GetCashTotal`；`GetCalculatedCashTotalRow` → `usp_GetCalculatedCashTotal`。
- `TransactionLogAccessor.GetCountSummaryRow` → `usp_GetCountSummary`（集計完了门控）。
- `BusinessStateAccessor`：`GetBusinessStateRow` / `GetBusinessCount` / `GetLastCloseBusinessDateRow` / `GetDailyCloseBusinessCount`。
- `SettingMasterAccessor.GetValues`（`IsCloseCountReceiptSimplePrint`）；`BusinessCounter.NumberingCount(CounterCodes.ReceiptNo)`。
- TranLogType `Report_*`(9001–9017, 9006 缺) + `EntryCalculatedCash`(809) + `EntryNonCash`(815)（[`Common.Const/TranLogTypes.cs`](Application/Source/Common/Common.Const/TranLogTypes.cs)）。

## 7. 设备依赖

- **釣銭機 CashChanger**（在高族）→ `DeviceIds.CashChanger`。
- **CAFIS**：`DeviceIds.CAFISArch`（`ICAFISArchNoOperation`，Debit 系）、`DeviceIds.CAFISArchLAN`（Credit/UnionPay/全日計）、`DeviceIds.PaymentService`（`IPaymentServiceModeSelf`，全日計）；数据类型 `Device.CAFISArchLAN`。

→ 详见 [50_devices](../50_devices/index.md)。设备内部实现 `uncheckable`。

## 8. 参与的端到端流程

- 关店精算报表、速报打印、CAFIS 卡机错误/控え打印 → 详见 [开闭店精算流程](../70_flows/open_close_count.md)、[开闭店精算域](../30_domain/open_close.md)。

## 9. 可信度与核查

- **verified**：`ReportBase` 全成员（含 `AddHeader` 字段与 `EJournalType`/`ReceiptNo` 逻辑）、18 具体报表的类/继承/`TranLogType`+数值、`CanExecute` 门控四类、`AddBody` 数据源与产出表、Accessor→SP 映射，逐条实测。
- **uncheckable**：`TranBase`、`ReportDataSet` 自动生成器内部、釣銭機/CAFIS 设备内部、SP 内部 SQL。
- **unverified（残）**：精算/速报的完整 `(DealCode,DealSubCode)`→列 映射逐条对应关系（数十条）未全量枚举，仅确认结构与代表条目；如需全表请回 `ReportCloseCount.cs:145-` / `ReportSalesFlash.cs:142-`。
- 订正：原稿"全体 TranLogType 属 Report_*(9000段)"——补入 809/815 两例外与 9006 缺号；补齐三大门控、各族数据源（DB vs 设备事件对象）与产出表。

## 10. ST-POS 迁移提示

> ST-POS 报表/日结统计在后端 `report` 等服务重构，卡机控え等外设报表不适用。对照仅供参考（外链）。
