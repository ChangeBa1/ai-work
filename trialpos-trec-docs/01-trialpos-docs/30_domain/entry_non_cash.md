---
title: 非现金在高确认域（Business.EntryNonCash）
layer: 30_domain
module: Business.EntryNonCash
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Business/Business.EntryNonCash/EntryNonCashTran.cs
  - Application/Source/Business/Business.EntryNonCash/EntryNonCashDataGroup.cs
verification: verified
related:
  data:  [../40_data/06_enums_constants.md]
  domain: [../30_domain/open_close.md, ../30_domain/payment.md, ../30_domain/report.md]
owner: jinianxiang
updated: 2026-07-14
---

# 非现金在高确认域（Business.EntryNonCash）

> `verification: verified`——2 个业务源码文件（527 loc）逐条核实（最新发布）。`TranBase` 属 Framework DLL（`uncheckable`）。

## 1. 模块定位

生成**现金以外 tender（現金外）在高确认**的数据载体（小票文言「現金外在高確認」）。**实测本模块不做手工逐笔录入、不依赖任何外设**：其 `EntryNonCashDataGroup` 直接从当日**日計取引コード集計**（`DailyDeal`）按取引コード读取各非现金金种的**回数/枚数与金额**，供精算前非现金资产盘点与报表使用。

- 命名空间：`ForYouApplications.POS4U.Business.EntryNonCash`
- ProjectReference（`Business.EntryNonCash.csproj` 实测）：`Business.BusinessCommon`、`Business.Member`、`Business.Payment`、`Common.Const`、`Data.Accessor`、`Data.Container`、`Device.DeviceCommon`、`Device.DeviceDefine`。
  > ⚠️ 订正：`Business.Member` / `Business.Payment` / `Device.*` 仅出现在 csproj 引用中，**两个源码文件均未实际使用**（`grep` 实测 0 处引用）。原稿"依赖 Business.Payment（tender 定义）与 Business.Member""录入设备"缺源码依据，已改。

## 2. 代码结构

3 个 `.cs`（含 `AssemblyInfo`）；核心 2 类。

| 类型 | file:line | 说明 |
|---|---|---|
| `EntryNonCashTran` | [`EntryNonCashTran.cs:12`](Application/Source/Business/Business.EntryNonCash/EntryNonCashTran.cs) | `[Serializable] : CommonTranBase`。ctor(:17) 置 `CurrentState = EntryNonCashTranStates.Neutral`；`TranType`→`TranTypes.EntryNonCash`(:29)、`TranLogType`→`TranLogTypes.EntryNonCash`(:43)。`StartTran()`(:61) 新建 `EntryNonCashDataGroup(UserData)`；`EndTran()`(:74) 空体（仅 return true） |
| `EntryNonCashDataGroup` | [`EntryNonCashDataGroup.cs:11`](Application/Source/Business/Business.EntryNonCash/EntryNonCashDataGroup.cs) | 非现金在高明细载体。ctor(:17)→`Initialize()`。34 个属性（17 金种 × {回数/枚数, 金额}）。`Initialize()`(:197) 读日計并按 DealCode 填充 |

## 3. 状态机

`EntryNonCashTranStates`（[`Common/Common.Const/State/EntryNonCashTranStates.cs`](Application/Source/Common/Common.Const/State/EntryNonCashTranStates.cs)）仅 2 节点，均 `StatePrefixes.EntryNonCashTran`：

- `Neutral`（:13）——ctor 与 `StartTran()` 的初始态
- `Fixed`（:18）——确定态

`TranState` 的迁移由 `CommonTranBase`→`TranBase` 骨架驱动（`uncheckable`）；本模块源码内仅显式设置 `Neutral`（`EntryNonCashTran.cs:19,63`），未见到向 `Fixed` 的显式迁移调用（推测在框架 FixTran 内，`uncheckable`）。

## 4. 业务规则

- **BR-ENTRYNONCASH-001（数据源＝日計集計）**：`Initialize` 取 `BusinessStateAccessor.GetBusinessStateRow` 的 `BusinessDate`（为空则取 `now+1 日`），以固定 `DealCodes` 数组（22 个取引コード，`EntryNonCashDataGroup.cs:342-388`）调 `DailyDealAccessor.GetDailyDealList(param, businessDate, searchList)`。`EntryNonCashDataGroup.cs:197-210`。
- **BR-ENTRYNONCASH-002（DealCode→金种映射）**：遍历结果按 `DealCode` 分派到各属性。实测映射（`EntryNonCashDataGroup.cs:212-336`）：

  | DealCode | 金种 | 写入属性 |
  |---|---|---|
  | 260 / 10019 | 商品券（金额/枚数） | `ExchangeTicketAmount` / `ExchangeTicketCount` |
  | 261 / 10020 | 金券（金额/枚数） | `CashTicketAmount` / `CashTicketCount` |
  | 263 / 10021 | ビール券 | `BeerTicketAmount` / `BeerTicketCount` |
  | 269 / 10022 | ビール券バーコード | `BeerBarcodeTicketAmount` / `BeerBarcodeTicketCount` |
  | 262 | ポイント | `PointCount` / `PointAmount` |
  | 259 | 売掛 | `AccountsReceivable{Count,Amount}` |
  | 2566 | プリペイド | `ValueCard{Count,Amount}` |
  | 345 / 10023 | クーポン | `TrialCouponAmount` / `TrialCouponCount` |
  | 346 | クレジット | `Credit{Count,Amount}` |
  | 264 | オフラインクレジット | `CreditOffline{Count,Amount}` |
  | 347 | デビット | `Debit{Count,Amount}` |
  | 10050 / 10051 / 10052 | QR決済 PayPay / 楽天ﾍﾟｲ / d払い | `PayPay*` / `RakutenPay*` / `Docomo*` |
  | 10053 / 10054 | アリペイ / ウィチャットペイ | `Alipay*` / `WeChatPay*` |
  | 144 | 現金外計 | `NonCashTotal{Count,Amount}` |

- **BR-ENTRYNONCASH-003（Tran 本体为轻量壳）**：`EntryNonCashTran` 不含金额/校验逻辑——`StartTran` 仅构造 DataGroup（触发上述读取），`EndTran` 为空。真正的聚合在 `EntryNonCashDataGroup.Initialize`。`EntryNonCashTran.cs:61-77`。

> ⚠️ 订正：原稿"各非现金金种的具体录入/校验规则未深度核查"——实测**无录入/校验**，本域是对日計集計的只读快照。

## 5. 关键接口与契约

- `EntryNonCashTran : CommonTranBase`（源码 [`Business.BusinessCommon/CommonTranBase.cs:19`](Application/Source/Business/Business.BusinessCommon/CommonTranBase.cs)），提供 `StartTran`/`EndTran` 覆写。
- `EntryNonCashDataGroup`：34 个 public 属性（17 金种类别 × 回数/枚数 + 金额），是本域对外输出的契约对象；被报表域 `ReportEntryNonCash` 消费（[`report.md`](../30_domain/report.md)）。

## 6. 数据依赖

- `DailyDealAccessor.GetDailyDealList`（[`Data/Data.Accessor/DailyDealAccessor.cs:20`](Application/Source/Data/Data.Accessor/DailyDealAccessor.cs)）→ SP `dbo.usp_GetDailyDealList`（`Data.Container/ReportDataSet.xsd`）。
- `BusinessStateAccessor.GetBusinessStateRow`（营业日）。
- TranLogType `EntryNonCash` = 815（[`Common.Const/TranLogTypes.cs:227`](Application/Source/Common/Common.Const/TranLogTypes.cs)）。取引コード语义 → [40_data/枚举与常量](../40_data/06_enums_constants.md)（不复制全表）。

## 7. 设备依赖

**无**。csproj 虽引用 `Device.DeviceCommon`/`Device.DeviceDefine`，两个源码文件均未使用任何设备 API（实测）。

## 8. 参与的端到端流程

精算前的非现金资产盘点、`ReportEntryNonCash` 小票输出 → 详见 [开闭店精算域](../30_domain/open_close.md)、[报表生成域](../30_domain/report.md)、[开闭店精算流程](../70_flows/open_close_count.md)。

## 9. 可信度与核查

- **verified**：`EntryNonCashTran`（基类/TranType/TranLogType=815/StartTran/EndTran 空体）、`EntryNonCashDataGroup`（DailyDeal 数据源 + 22 DealCode 映射）、2 状态节点、SP `usp_GetDailyDealList` 依赖，逐条实测。
- **uncheckable**：`TranBase` / `CommonTranBase.FixTran` 状态迁移内部（Framework DLL）。
- 订正：删除"依赖 Payment/Member、录入设备、手工录入/校验"等无源码依据的旧表述，改为日計集計只读快照模型。

## 10. ST-POS 迁移提示

> ST-POS 后端非现金资产盘点独立实现。对照仅供参考（外链）。
