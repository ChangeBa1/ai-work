---
title: 枚举与常量字典 · Common.Const（PaymentTypes / TranTypes / TranLogTypes / NodeTypes / State 族）
layer: 40_data
module: Common.Const
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Common/Common.Const/PaymentTypes.cs
  - Application/Source/Common/Common.Const/TranTypes.cs
  - Application/Source/Common/Common.Const/TranLogTypes.cs
  - Application/Source/Common/Common.Const/NodeTypes.cs
  - Application/Source/Common/Common.Const/SettingMasterKeys.cs
  - Application/Source/Common/Common.Const/State/SalesTranStates.cs
verification: verified
verified_by: ./01_overview.md
related:
  data: [./01_overview.md, ./02_master_tables.md, ./03_tran_tables.md]
  domain: [../30_domain/rj.md]
owner: jinianxiang
updated: 2026-07-14
---

# 枚举与常量字典（`Common.Const`）

> 命名空间 `ForYouApplications.POS4U.Common.Const`（[`PaymentTypes.cs:6`](Application/Source/Common/Common.Const/PaymentTypes.cs)）。DB 里的 `int`/`nvarchar` 码列（如 `TransactionLog.TransactionType`、`PaymentMaster` 的支付码）语义由本层常量收敛。**它们不是 C# `enum`**，而是**强类型常量对象**：`new PaymentType(nameof(Cash), "01")`——每个值带 `name` + `code`，定义类在 [`Common.Const/Class/`](Application/Source/Common/Common.Const/Class/)（`PaymentType.cs`/`TranType.cs`/`NodeType.cs`/`TranLogType.cs`…）。

## 1. `PaymentTypes` — 支払い種別（实测 25 值）

[`Application/Source/Common/Common.Const/PaymentTypes.cs`](Application/Source/Common/Common.Const/PaymentTypes.cs)，`code` 为 2 桁字符串：

| code | 值 | | code | 值 |
|---|---|---|---|---|
| 01 | `Cash` 現金 | | 11 | `CashInput` 現金(手入力) |
| 02 | `Credit` クレジット | | 12 | `CreditLAN` クレジット(LAN) |
| 03 | `ECash` 電子マネー | | 20 | `Debit` デビット |
| 04 | `ExchangeTicket` 商品券 | | 21 | `DebitLAN` デビット(LAN) |
| 05 | `Point` ポイント | | 23 | `UnionPayLAN` 銀聯(LAN) |
| 06 | `ValueCard` バリューカード | | 24 | `OfflineCredit` オフラインクレジット |
| 07 | `AccountsReceivable` 売掛 | | 31 | `BeerTicketBarCode` ビール券バーコード |
| 08 | `PointPaymentStation` 支払機ポイント | | 32 | `CashInOut` 入出金 |
| 09 | `ValueCardPaymentStation` 支払機VC | | 50-54 | QR: `PayPay`50 / `RakutenPay`51 / `Docomo`52 / `Alipay`53 / `WeChatPay`54 |
| 10 | `TrialCoupon` お試し引換券 | | | |

## 2. `TranTypes` — 取引種別（实测 29 值 · 仅 name 无 code）

[`Application/Source/Common/Common.Const/TranTypes.cs`](Application/Source/Common/Common.Const/TranTypes.cs)（`new TranType(nameof(X))`，无数字 code）：

`Sales`(売上,:13) · `SelfSales`(:18) · `Return`(返品,:23) · `OpenCount`(開設,:28) · `CloseCount`(精算,:33) · `PowerOn`(:38) · `SignIn`/`SignOut`(:43/:48) · `MainMenu`(:53) · `EMoneyCharge`/`EMoneyChargeVoid`/`EMoneyChargeEmployee`/`EMoneyChargeSelfSales`(:58-73) · `PaymentStation`(支払機,:78) · `CashChangerRecover`/`CashChangerReplenish`/`CashChangerExchangeMoney`(:83-98) · `EntryCalculatedCash`(在高登録,:93) · `Lock`(:103) · `DeviceSetting`(:108) · `Void`(取消,:113) · `ReSales`(打ち直し,:118) · `CashIn`/`CashOut`(:123/:128) · `EJournalSearch`(:133) · `EntryNonCash`(:138) · `EvidenceReceipt`(領収書,:143) · `OrderKitchen`(:148) · `MTranDelete`(:153)。

## 3. `TranLogTypes` — 取引ログ種別（实测 58 值 · 带 int code）

[`Application/Source/Common/Common.Const/TranLogTypes.cs`](Application/Source/Common/Common.Const/TranLogTypes.cs)（`new TranLogType(name, <int>)`）。这是落进 `TransactionLog.TransactionType` 的实际码。按段划分：

| 段 | 代表值 |
|---|---|
| 0 | `None`=0（:22） |
| 101-108 売上/返品 | `NormalSales`=101 · `CanceledSales`=102 · `TrainingSales`=103 · `NormalReturn`=105 · `TrainingCanceledReturn`=108 |
| 121-124 取消 | `NormalVoid`=121 · `TrainingCanceledVoid`=124 |
| 161-162 領収書 | `NormalEvidenceReceipt`=161 · `TrainingEvidenceReceipt`=162 |
| 201-206 管理系 | `OpenCount`=201 · `CloseCount`=202 · `PowerOn`=203 · `SignIn`=205 · `SignOut`=206 |
| 301-304 セルフ売上 | `NormalSelfSales`=301 · `TrainingCanceledSelfSales`=304 |
| 801-816 电子マネー/支払機/釣銭机/入出金 | `EMoneyCharge`=801 · `PaymentStation`=802 · `CashChangerRecover`=803 · `EMoneyInquiry`=804 · `CashChangerReplenish`=806 · `EntryCalculatedCash`=809 · `CashChangerExchangeMoney`=810 · `CashIn`=813 · `CashOut`=814 · `EntryNonCash`=815 · `EMoneyChargeVoid`=816 |
| 821-822 训练支払機 | `TrainingPaymentStation`=821 · `TrainingCanceledPaymentStation`=822 |
| 9001-9017 Report_ 报表 | `Report_CalculatedCash`=9001 · `Report_CloseCount`=9004 · `Report_SalesFlash`=9005 · `Report_CAFISArch*`=9007-9016 · `Report_CloseCountSimple`=9017 |

## 4. `NodeTypes` — ノード種別（实测 17 值）

[`Application/Source/Common/Common.Const/NodeTypes.cs`](Application/Source/Common/Common.Const/NodeTypes.cs)（端末形态，2 桁 code）：

`AllTerminal`00 · `GoCart`01 · `GoSelf`02 · `OrderKitchen`03 · `GoCashRegister`04 · `CashPaymentStation`05 · `Mobile`06 · `GoSemiSelfRegister`07 · `GoSemiSelfPaymentStation`08 · `GoFullSelf`09 · `LocalPOS`10 · `OTCDrugPOS`11 · `LocalOrderKitchen`12 · `TwoOperatorsPOS`13 · `LaneSelf`14 · `LaneSelfPlusPaymentStation`15 · `EMoneyChargeStation`50。

## 5. Setting 键族

| 常量类 | 实测键数 | file | 对应表 |
|---|---|---|---|
| `SettingMasterKeys` | **161** | [`SettingMasterKeys.cs`](Application/Source/Common/Common.Const/SettingMasterKeys.cs) | `SettingMaster`（端末別 KVS，[02_master_tables §4](./02_master_tables.md)） |
| `SettingServerMasterKeys` | **39** | [`SettingServerMasterKeys.cs`](Application/Source/Common/Common.Const/SettingServerMasterKeys.cs) | `SettingServerMaster`（全店共通） |
| `SettingValues` | **68** | [`SettingValues.cs`](Application/Source/Common/Common.Const/SettingValues.cs) | 设定值定数 |

`SettingMasterKeys` 代表键（`SettingMasterKey<T>` 泛型，带值类型）：`PointNormalRate`<decimal> · `PointBaseAmount`<decimal> · `IsOTCDrugSales`<bool> · `IsPointCalcAmountWithNoTaxes`<bool> · `ValueCardDealServiceURL`<string> · `PointServiceIPAddress`<string> …（[`SettingMasterKeys.cs:14-`](Application/Source/Common/Common.Const/SettingMasterKeys.cs)）。

## 6. State 族（状态机常量 · `Common.Const/State/`）

[`Application/Source/Common/Common.Const/State/`](Application/Source/Common/Common.Const/State/) 实测 **31 个文件**（含 `StatePrefixes.cs` 前缀定义 + `TwoOperatorsStates.cs`）。每类是一台状态机的节点集，元素为 `new TranState(...)` 或 `new State(...)`。主要几台：

| 状态集 | 实测成员数 | 口径 |
|---|---|---|
| `SalesTranStates` | **28**（18 `TranState` + 10 `State`） | 売上取引主状态机 |
| `SelfStates` | **39** | セルフ精算状态 |
| `PaymentStates` | **24** | 支払状态 |
| `CloseCountTranStates` | **27 `TranState`** | 精算取引状态（见下方口径注） |
| `LineItemStates` | 5 | 明細行状态 |
| `ReturnTranStates` / `VoidTranStates` / `OpenCountTranStates` / `MainMenuTranStates` / `EMoneyChargeTranStates` … | 各自定义 | 见对应 `.cs` |

> 📏 **口径注（CloseCountTranStates）**：`grep 'new TranState('` 实测 **27** 个状态成员；`grep 'public static'` 得 28（多出的 1 行是 `public static class CloseCountTranStates` 类声明本身）。[conventions §2](../00_portal/conventions.md) 记 28 系后者口径。本篇状态成员以 **27** 为准（可复现）。`SalesTranStates` 两口径均得 28（无类声明干扰差），故一致。

> 命名前缀规约见 `StatePrefixes.cs`；`SalesTranStates` 的完整迁移边（状态图）属 [30_domain/sales](../30_domain/) 职责，本篇只给成员计数与 file，不复制状态图。

## 7. 其他常量（顶层 `Common.Const/*.cs`，实测约 70 文件）

`DiscountTypes` · `DiscountMethods` · `DiscountMixMatchTypes` · `TaxTypes` · `DepartmentTypes` · `AgeConfirmTypes` · `ReasonTypes` · `PrintTypes` · `ReceiptMessageTypes` · `MemberTypes` · `PointStateTypes` · `EventCodes` · `MessageIds` · `QueueNames` · `ServiceTypes` · `StoreTypes` · `PriceTypes` · `ItemEntryTypes` … 各回同名 `.cs`。

## 8. 可信度与核查

- **verified**：§1-6 计数与关键值均带 `file:line`，`code`/`int` 值直接摘自源码定义行。
- CloseCountTranStates 的两种口径已显式说明；顶层常量（§7）为清单级导航，单个值须回 `.cs`。

## 9. ST-POS 迁移提示

> 🔀 POS4U 的强类型常量（name+code 对象）对应 ST-POS 的 `commons` 枚举/常量与错误码表；`PaymentTypes`/`TranTypes` 的码值映射外链团队内部设计库。
