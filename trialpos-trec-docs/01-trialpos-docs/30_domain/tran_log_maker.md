---
title: 交易日志生成域（Business.TranLogMaker）
layer: 30_domain
module: Business.TranLogMaker
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Business/Business.TranLogMaker/TranLogMakerBase.cs
  - Application/Source/Business/Business.TranLogMaker/VoidTranLogMaker.cs
  - Application/Source/Business/Business.BusinessCommon/CommonTranBase.cs
  - Application/Source/Common/Common.Const/TranLogTypes.cs
  - Application/Source/Azure/Azure.Logic/TranLogService/Converter/TranLogConverterBase.cs
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
related:
  data:     [../40_data/03_tran_tables.md, ../40_data/06_enums_constants.md]
  services: [../60_services/cloud/index.md, ../60_services/background/index.md]
  flows:    [../70_flows/tlog_persist_and_upload.md]
  domain:   [./sales.md, ./resales.md, ./payment.md]
owner: jinianxiang
updated: 2026-07-14
---

# 交易日志生成域（Business.TranLogMaker）

## 1. 模块定位

`Business.TranLogMaker` 把**内存中的交易对象**（`SalesTran`/`VoidTran`/…）组装成统一的 `TranDataSet`（多表数据集 = TLog），供本地 SQL Server（SQLEXPRESS）落盘。它是"交易确定 → 落盘"之间的**打包层**。

> **关键边界（本篇最重要的澄清）**：本模块只生成**正向** `TranDataSet`；**退货/作废的金额负数冲减（`Sign = -1`）不在此，而在云端上报转换器** `Azure.Logic/TranLogService/Converter/TranLogConverter*`（见 §4 BR-TLM-004）。上游 01- 稿把两者混为一谈。

- **系统角色**：基类 `CommonTranBase.FixTran()` 经插件工厂按 `TranType.Id` 取对应 `*TranLogMaker`，调 `ConvertToTranDataSet(this)` 得 `TranDataSet`，再由 `TransactionLogAccessor.InsertTransactionLog` 落盘。
- **上下游**（`Business.TranLogMaker.csproj`）：引用 **17** 个 `Business.*` 业务域（几乎全部），以便为各交易/明细/支付/会员/折扣/税组装对应 `Maker`。
- **规模**（实测）：**57** 个 `.cs`、**6035** 行；`Maker/` 子目录 37 个辅助 Maker（`MemberMaker` 721、`LineItemMaker` 517 最大）。

---

## 2. 代码结构

### 2.1 基类与装配

- `TranLogMakerBase<TTran>`（`Application/Source/Business/Business.TranLogMaker/TranLogMakerBase.cs:14`，`: ITranLogMaker where TTran : CommonTranBase`）：**具象** `ConvertToTranDataSet(CommonTranBase)`（`:22`）`new TranDataSet()` 后调**抽象** `OnConvertToTranDataSet(TranDataSet, TTran)`（`:35`）——子类实现后者。
- **装配 = XML 插件配置，按 `TranType.Id` 键**：`Application/Source/POS4ULogicService/Settings/Plugin.xml` 的 `<Group Id="TranLogMaker">`（`:202-236`，注释 `<!-- IdはTranType -->` `:204`）；WinPOS 侧同组在 `POS4U/Settings/PluginWinPOS.xml`。**非** C# attribute、**非** `SalesPluginIds` 常量。

### 2.2 顶层 `*TranLogMaker`（按 TranType）

| Maker | 路径:行 | 行 | 对应 TranType / TranLogType | 绑定/类型设定 |
|---|---|---|---|---|
| `SalesTranLogMaker` | `SalesTranLogMaker.cs:11` | 247 | Sales（复用于 SelfSales/OrderKitchen）/ `NormalSales=101` | Plugin.xml:206-208；类型经 `TransactionHeaderMaker.cs:46` |
| `VoidTranLogMaker` | `VoidTranLogMaker.cs` | 204 | Void / `NormalVoid=121` | Plugin.xml:222-224；显式 `NormalVoid.Number` `:50`(P 路径) |
| `ReturnTranLogMaker` | `ReturnTranLogMaker.cs` | 31 | Return / `NormalReturn=105` | Plugin.xml:214-216；`: SalesTranLogMaker` + `ReasonMaker.AddReason`(`:28`) |
| `ReSalesTranLogMaker` | `ReSalesTranLogMaker.cs:11` | 14 | ReSales / 同 Sales | Plugin.xml:218-220；**空壳** `: SalesTranLogMaker {}`，全权委托 |
| `EMoneyChargeVoidTranLogMaker` | `EMoneyChargeVoidTranLogMaker.cs` | 184 | EMoneyChargeVoid / `816` | Plugin.xml:230-232；显式 `EMoneyChargeVoid.Number` `:44`(P 路径) |
| `EvidenceReceiptTranLogMaker` | `EvidenceReceiptTranLogMaker.cs` | 148 | EvidenceReceipt | PluginWinPOS.xml:1857-1859 |

> 另有 `OpenCountTranLogMaker`/`CloseCountTranLogMaker`/`SignIn/SignOutTranLogMaker`/`CashInOutTranLogMaker`/`CashChanger*TranLogMaker`/`PaymentStationTranLogMaker`/`PowerOnTranLogMaker` 等覆盖非销售交易。

### 2.3 `Maker/` 辅助族（37 类，按关注点）

| 关注点 | 类 |
|---|---|
| Header | `TransactionHeaderMaker`(210) / `SalesHeaderMaker` / `TwoOperatorsHeaderMaker` / `HybridHeaderMaker` / `OriginalTransactionHeaderMaker` |
| 明细 | `LineItemMaker`(517) |
| 支付/卡 | `PaymentMaker`(300) / `DebitMaker` / `DebitSummaryMaker` / `CreditModeSelfMaker` / `CreditModeSelfDailyTotalMaker` / `CAFISArchLANCreditMaker` / `CAFISArchLANUnionPayMaker` / `CAFISArchLANDailyTotalMaker` |
| 会员/积分 | `MemberMaker`(721) |
| 折扣 | `DiscountMaker`(241) |
| 税 | `TaxMaker` |
| 其它 | `ReasonMaker` / `ApprovalAgeConfirmationMaker` / `RevenueStampMaker` / `RetailMediaMaker` / `EMoneyChargeMaker` / `EMoneyChargeVoidMaker` / `EvidenceReceiptMaker` / `OrderInfoMaker` / `TempMTranMaker` / `MasterDataMaker` / `SignInOutMaker` / `OpenCountMaker` / `CloseCountMaker` / `CashInOutMaker` / `CalculatedCashChangeMaker` / `CashChanger*Maker`×5 |

---

## 3. 状态机

**无**。本模块是无状态打包层。其核心跨模块锚点是 `TranLogType`（`Application/Source/Common/Common.Const/TranLogTypes.cs`），各 `*TranLogMaker` 为交易头写入对应 `TransactionType`（`TransactionHeaderMaker.cs:46`：`headerRow.TransactionType = tran.TranLogType.Number`；"ForCoupon" 变体按运行时类型分支 `:99-114`）。核心取值：`NormalSales=101` / `NormalReturn=105` / `NormalVoid=121` / `NormalEvidenceReceipt=161` / `EMoneyCharge=801` / `EMoneyChargeVoid=816`。全量 → [40_data/06_enums_constants.md](../40_data/06_enums_constants.md)。

---

## 4. 业务规则（BR）

### BR-TLM-001 落盘入口与按 TranType 装配（FixTran）

`CommonTranBase.FixTran()`（`Application/Source/Business/Business.BusinessCommon/CommonTranBase.cs:101`）：

```csharp
var tranLogMaker = Factory.CreatePlugin(BusinessCommonPluginGroupIds.TranLogMaker, this.TranType.Id);  // :104
var tranDs = tranLogMaker.ConvertToTranDataSet(this);                                                    // :105
...
TransactionLogAccessor.InsertTransactionLog(this.UserData.DataAccessParameter, tranDs);                  // :109
```

插件组常量 `BusinessCommonPluginGroupIds.TranLogMaker`（`Business.BusinessCommon/Const/BusinessCommonPluginGroupIds.cs:17`）。同样三段式亦见 `FixSumTran()`（`:135-143`）与 `GetTransactionData()`（`:174-176`，走 `ConvertToPTranDataSet`）。

### BR-TLM-002 作废日志的表排除与外键重构（VoidTranLogMaker）

作废是**全新逆向交易**（新 `TransactionNo`/`ReceiptNo`/`SystemDateTime`），不能原样复制原头/支付。`VoidTranLogMaker` 声明排除表 `excludeTables`（两处，对应两条转换路径）：

- `OnConvertToTranDataSet`（FixTran 路径）：`:115-126`，**9** 表（TransactionHeader/Payment/ValueCard/Member/TwoOperatorsHeader/CreditPayment/CreditLAN/UnionPayLAN/HybridHeader）。
- `ConvertToPTranDataSet`：`:32-44`，**10** 表（上者 + `MasterData`）。

非排除表逐行复制并把外键 `TransactionNo` 改写为作废新号（FixTran 路径 foreach `:150-175`，改写 `:162-164`；P 路径 `:57-82`，改写 `:69-71`）。

- 作废头交易类型：P 路径显式 `headerTable.TransactionType = TranLogTypes.NormalVoid.Number`（`:50`）。
- 销售头标记：`salesRow.IsCanceled = isCanceled`（`:195`）——**属性名是 `IsCanceled`（非 `IsVoided`）**，且值为计算值 `isCanceled = (tran.CurrentState == VoidTranStates.Canceled)`（`:113`），**非字面 `true`**。

> ⚠️ **订正 01-**：`04_return_persistence` 称此处标记为 `salesRow.IsCanceled = true`——实为赋计算值 `isCanceled`（仅当作废交易本身处 `Canceled` 态才为真）。

### BR-TLM-003 打直し = 空壳复用（ReSalesTranLogMaker）

`ReSalesTranLogMaker` 是 `SalesTranLogMaker` 的**空子类**（`ReSalesTranLogMaker.cs:11-13`，无覆写），故打直し的**新销售单**按普通销售组装（`NormalSales=101`）；其内嵌作废半程由 `VoidTranLogMaker` 单独产出 `NormalVoid=121`。即一次打直し落盘 **Void(121) + Sales(101) 两笔**。→ 见 [resales.md §5](./resales.md)。

### BR-TLM-004 云端上报的符号逆转（`Sign = -1`）—— 不在本模块

退货/作废/充值取消在**云端上报**时对金额/件数做负数冲减。判定在 `Application/Source/Azure/Azure.Logic/TranLogService/Converter/TranLogConverterBase.GetData`（`TranLogConverterBase.cs:93-95`）：

```csharp
Sign = tHeader.TransactionType == TranLogTypes.NormalReturn.Number       // 105
       || tHeader.TransactionType == TranLogTypes.EMoneyChargeVoid.Number // 816
       || tHeader.TransactionType == TranLogTypes.NormalVoid.Number       // 121
       ? -1 : 1;
```

逐表应用：
- 头（`TranLogConverterHeaderLogic.cs`）：`Sign * TotalAmount`(`:279`)、`Sign * TotalQuantity`(`:282`)、`Sign * TotalAmountWithTaxes`(`:285`)；充值/开精算类清零 `Sign * 0`(`:268-274`)；税行 `:1033-1036`。
- 明细（`TranLogConverterLineItemLogic.cs`）：`Sign * item.Quantity`(`:576`)、`Sign * unitPrice * item.Quantity`(`:579`)；折让 `-1 * Sign * ...`(`:666`/`:669`)；M&M `Sign * ... * -1`(`:701`/`:704`)。

> ⚠️ **订正 01-（本篇最关键）**：`04_return_persistence` 的代码块注释把编号写成 `NormalReturn=121 / EMoneyChargeVoid=125 / NormalVoid=122`——**全错**。实测 `TranLogTypes.cs`：**`NormalReturn=105`**（`:47`）、**`NormalVoid=121`**（`:67`）、**`EMoneyChargeVoid=816`**（`:147`）。其中 `122` 实为 `CanceledVoid`（`:72`），`125` 在整个枚举中**不存在**。代码本身（判定的字段引用）是对的，错的是注释里的数字。
>
> `TranLogConverterBase.IsReturn()`（`:247-258`）另用更宽集合（含 `CanceledReturn`/`TrainingReturn`/`TrainingVoid` 等）判定明细的"返品区分"标记。

### BR-TLM-005 云端转换器的位置与规模

7 个转换器（`Azure/Azure.Logic/TranLogService/Converter/`，共 6442 行）：`TranLogConverterLineItemLogic`(1686) / `TranLogConverterValueCardLogic`(1582) / `TranLogConverterHeaderLogic`(1040) / `TranLogConverterPointLogic`(799) / `TranLogConverterPaymentLogic`(609) / `TranLogConverterMMLogic`(458) / `TranLogConverterBase`(268)。它们属 `Azure/` 项目（云连接），文档区在 → [60_services/cloud](../60_services/cloud/index.md)，**非本域**。

---

## 5. 关键接口与契约

- `ITranLogMaker`（框架/BusinessCommon 侧）：`ConvertToTranDataSet(CommonTranBase)`；`TranLogMakerBase<TTran>` 实现之，子类实现 `OnConvertToTranDataSet`。
- 派生扩展契约：`IMTranLogMaker`/`IPTranLogMaker`（`SalesTranLogMaker.cs:11` 实现）——中间交易/P 型数据集。
- 产出 `TranDataSet` 落盘经 `TransactionLogAccessor`（`Data.Accessor`）→ [40_data/03_tran_tables.md](../40_data/03_tran_tables.md)。

---

## 6. 数据依赖

- **写**：`TranDataSet`（TransactionHeader/SalesHeader/SalesDetail/Payment/Member/Tax/… 多表）落盘 SQL Server 交易表族（五元组联合主键）。
- **下游**：本地 TLog 由后台同步服务（`POS4UBackground` / `Azure`）转 CSV/大对象上传云端，转换时应用 `Sign`（BR-TLM-004）→ [60_services/background](../60_services/background/index.md)。
- 表结构 → [40_data/03_tran_tables.md](../40_data/03_tran_tables.md)（不复制）。

---

## 7. 设备依赖

无直接设备依赖（打包层）。EJournal/小票印字由 `Business.RJ` 处理（`FixTran` 之后另行触发）。

---

## 8. 参与的端到端流程

- 交易落盘 + 云端上传（含 Sign 冲减）→ [70_flows/tlog_persist_and_upload.md](../70_flows/tlog_persist_and_upload.md)
- 作废/打直し日志生成 → [70_flows/return_void.md](../70_flows/return_void.md)

---

## 9. 可信度与核查

- **verified**：57 文件/6035 行、`TranLogMakerBase` 抽象/具象分工、`FixTran` 三段式（`CommonTranBase.cs:101-109`）、插件按 `TranType.Id` 装配（Plugin.xml）、`VoidTranLogMaker` 排除表/外键重构/`IsCanceled`、`ReSalesTranLogMaker` 空壳、**Sign 判定 `105/816/121`**（`TranLogConverterBase.cs:93-95` + `TranLogTypes.cs`）均实测。
- **uncheckable**：`ITranLogMaker`/`Factory`/`PluginGroupId` 在 `POS4U.Framework(.Library).dll`；Azure 上传的基幹侧接收行为为外部系统。
- **本篇订正的 01- 造假**：01- return-04 的 Sign 编号注释 `121/125/122` → 实测 `105/816/121`（`122=CanceledVoid`，`125` 不存在）；`salesRow.IsCanceled=true` → 实为计算值。

---

## 10. ST-POS 迁移提示

> ST-POS 的 TLog 生成在 kugelpos `cart`→`tranlog` 服务（tranlog master 快照持久化、ADR-0001/0004/0005），退货以赤黒方式（ADR-0015）用**独立负交易**表达，取代 POS4U 的"云端 Sign 翻转"。→ `stpos-backend-kugelpos` tranlog/ADR（只外链）。
