---
title: 税额计算域（Business.Tax）
layer: 30_domain
module: Business.Tax
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Business/Business.Tax/TaxManager.cs
  - Application/Source/Business/Business.Tax/Tax.cs
  - Application/Source/Common/Common.Const/TaxTypes.cs
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
related:
  data:   [../40_data/06_enums_constants.md, ../40_data/03_tran_tables.md]
  flows:  [../70_flows/sale_end_to_end.md]
  domain: [./sales.md, ./payment.md]
owner: jinianxiang
updated: 2026-07-14
---

# 税额计算域（Business.Tax）

> 本篇无对应 01- 稿，直接依 最新发布 代码分析撰写。

## 1. 模块定位

`Business.Tax` 是一个**无状态的税额计算服务**：为 `SalesTran` 按税组聚合课税对象额、区分内税/外税/非課税计算税额、把税额按明细与支付渠道案分、并处理书籍等特殊税价。它以插件形式实现 `Business.Sales` 定义的 `ITaxManager` 契约。

- **系统角色**：`SalesTran` 重算（`ReCalcSalesTran`）时经 `Factory.CreatePlugin(SalesPluginIds.TaxManager)` 调用本模块的 `TaxManager.Calc(tran)`。
- **上下游**（`Business.Tax.csproj`）：依赖 `Business.Sales`（接口 + 仓储扩展）、`Business.Payment`（支付案分）、`Business.BusinessCommon`、`Common.Const`、`Data.*`、`Device.DeviceDefine`。被 `Business.ReSales` 引用。
- **规模**（实测）：**8** 个 `.cs`（含 `Properties/AssemblyInfo.cs`）、**922** 行；核心 `TaxManager.cs` **511** 行。

---

## 2. 代码结构

| 类 | 路径:行 | 行数 | 职责 |
|---|---|---|---|
| `TaxManager` | `Application/Source/Business/Business.Tax/TaxManager.cs:17` | 511 | 税计算引擎；`: ITaxManager`（接口在 `Business.Sales/Tax/ITaxManager.cs:12`） |
| `Tax` | `Application/Source/Business/Business.Tax/Tax.cs:16` | 106 | 单条税明细（`[Serializable]`）；`Apply()` 算税额 |
| `Taxes` | `Application/Source/Business/Business.Tax/Taxes.cs:15` | 70 | 税明细集合；`: ITaxes` |
| `TaxParameter` | `Application/Source/Business/Business.Tax/TaxParameter.cs` | 29 | `Apply()` 入参（TaxRow/TargetAmount/TargetQuantity） |
| `LineItemBaseExtensionMethods` | `Application/Source/Business/Business.Tax/ExtensionMethods/LineItemBaseExtensionMethods.cs` | 128 | 明细内税拆出（`:72`）/外税附加（`:107`） |

### `TaxManager` 公开方法（= `ITaxManager` 四方法）

| 方法 | 行 | 职责 |
|---|---|---|
| `Calc(SalesTran tran)` | 43 | 清空旧税 → 按税码聚合课税额 → 建 `Tax` → 录入/支付阶段把税额案分到明细 |
| `ConvertToBookUnitPrice(...)` | 140 | 书籍价 → 内税込单价（见 BR-TAX-003） |
| `CalcPaymentTaxDevided(PaymentObject, ...)` | 177 | 税额按支付渠道案分（含印紙对象额、端数残差调整） |
| `GetChangedTaxGroupCode(LineItemBase)` | 290 | 軽減⇄标准 税组码互换（见 BR-TAX-002） |

私有辅助：`SearchTaxCodeTargets`(`:314`)、`TaxDivide`(`:350`)、`RestAmountDivide`(`:419`)；内嵌 `TaxCodeTarget`(`:445`)/`TaxTarget`(`:473`)。构造函数（`:32`）读 `FrameworkLibrarySettingValues.CurrencyDecimalDigits` 得币种小数位 `_digits`。

`Tax` 关键属性（均 `Apply()` 时从 master row 复制，`Tax.cs`）：`TaxCode`(21)/`TaxTypeCode`(26)/`Description`(31)/`Rate`(36)/`RoundDigit`(41)/`RoundMethod`(46)/`TargetAmount`(51)/`TargetQuantity`(56)/`TaxAmount`(61)。`Taxes` 集合成员：`Items`(25)/`ClearTaxes`(36)/`AddTax`(45)/`GetTaxAmount(TaxType)`(55)/`GetUnitPriceForPurchaseWithNoTaxes`(65)。

---

## 3. 状态机

**无**。`Business.Tax` 是无状态计算服务，不定义任何 `*TranStates`。

---

## 4. 业务规则（BR / 合规）

### BR-TAX-001 内税 / 外税 / 非課税 三区分与税额公式

税区分 `Application/Source/Common/Common.Const/TaxTypes.cs`（**3** 种）：`ExcludedTax`外税`"01"`(:16) / `IncludedTax`内税`"02"`(:21) / `ExemptTax`非課税`"03"`(:26)。

`Tax.Apply()`（`Tax.cs:67-104`）按区分算税额（`Rate`/`RoundMethod`/`RoundDigit` 均取自 master row，`:71-74`）：

```csharp
if (this.TaxTypeCode == TaxTypes.ExcludedTax.Code)        // 外税
    before = (this.TargetAmount / 100m) * this.Rate;                 // :82
else if (this.TaxTypeCode == TaxTypes.IncludedTax.Code)   // 内税
    before = (this.TargetAmount / (100 + this.Rate)) * this.Rate;    // :86
else if (this.TaxTypeCode == TaxTypes.ExemptTax.Code)     // 非課税
    before = 0m;                                                     // :90
```

即：外税=按 100 分之率**外加**；内税=从含税额中**逆算**内含税（÷(100+率)×率）；非課税=0。

### BR-TAX-002 軽減税率（8% / 10%）—— 税组码切换而非硬编码率

- **规则**：多税率通过**税组码**区分（各组码解析到 master 中带 `Rate` 的税行）；**税率数值不硬编码**，来自 master `taxRow.Rate`（`Tax.cs:72`）。
- **切换**：`GetChangedTaxGroupCode`（`TaxManager.cs:290-312`）在軽減⇄标准间互换税组码（代码注释即 8%/10% 语义，**百分比本身仍来自 master**）：
  | 原税组 | → 新税组 | 注释（源码） |
  |---|---|---|
  | `"01"` | `"04"` | 外税 8% → 外税 10% |
  | `"02"` | `"05"` | 内税 8% → 内税 10% |
  | `"04"` | `"01"` | 外税 10% → 外税 8% |
  | `"05"` | `"02"` | 内税 10% → 内税 8% |
  | 其它 | `null` | — |
- ⚠️ **注意代码空间区分**：税组码 `01/02/04/05`（此处）与 `TaxTypes` 的区分码 `01/02/03`（BR-TAX-001）是**两套不同的编码**，勿混。
- **合规背景**：日本消費税軽減税率（食品等 8% vs 标准 10%）。

### BR-TAX-003 书籍税价换算（ConvertToBookUnitPrice）

`TaxManager.cs:140-169`：

- 若书籍 JAN2 以 `"191"` 开头（`:144`），条码内含 **3% 税旧价**，先换算为税抜额：`RoundManager.Round(RoundAwayFromZero, targetAmount * 3 / 103, _digits)`（`:148`）。
- 随后遍历该明细税组的 master 行（`:155`），对 `IncludedTax` 行（`:160`）附加内税 `Round(RoundAwayFromZero, (amount/100)*rate, _digits)`（`:164`），返回税抜额 + 内含税。
- **书籍恒用四捨五入**（`RoundAwayFromZero`），无视一般端数设置（注释 `:147`/`:162`）。

### BR-TAX-004 端数处理（Rounding）

- 端数由框架 `RoundManager.Round(method, value, digit)` 执行（**在 `POS4U.Framework(.Library).dll`，uncheckable**；`Business.Tax.csproj:43-48` 引用）。模式常量 `RoundTypes`：`RoundToFloor`（切舍）/`RoundAwayFromZero`（四捨五入）/`None`。
- 每税行：`Tax.Apply()` 用 master 的 `RoundMethod`+`RoundDigit`（`:73-74`）调 `RoundManager.Round`（`:100`）；`None` 或空则不舍入（`:93-96`）。
- `TaxManager` 内：`RoundToFloor` 用于单价折让/印紙对象/案分单价（`:85`/`:191`/`:392`）；`RoundAwayFromZero` 用于书籍税与支付案分（`:148`/`:164`/`:202`）。

---

## 5. 关键接口与契约

- `ITaxManager`（`Application/Source/Business/Business.Sales/Tax/ITaxManager.cs:12`）：`Calc` / `ConvertToBookUnitPrice` / `CalcPaymentTaxDevided` / `GetChangedTaxGroupCode`。`TaxManager` 是唯一实现，经插件装配（`SalesPluginIds.TaxManager`）。
- `ITaxes`（`Business.Sales/Tax/ITaxes.cs`）：`Taxes` 集合实现，挂在 `SalesTran` 上供税额查询。
- **税额产出**：进入 `TranDataSet` 由 `Business.TranLogMaker` 的 `TaxMaker` 组装 → [tran_log_maker.md](./tran_log_maker.md)。

---

## 6. 数据依赖

- **税 master**：经 `TaxMasterAccessor`（`Application/Source/Data/Data.Accessor/TaxMasterAccessor.cs:28`）的 `TaxMasterTableAdapter` 查 **`TaxMaster`** 表（typed DataSet，**无手写 SP**）。取行入口 `GetRowsByTaxGroupCode(...)` 实际在 `Business.Sales/ExtensionMethods/SalesTranRepositoryExtensionMethods.cs:147`（`→ :157` 调 `TaxMasterAccessor`）——`Business.Tax` 自身的同名扩展文件是**空壳**（`SalesTranRepositoryExtensionMethods.cs:14-16`）。
- 表结构/字段字典 → [40_data/03_tran_tables.md](../40_data/03_tran_tables.md)；枚举 `TaxTypes` → [40_data/06_enums_constants.md](../40_data/06_enums_constants.md)（不复制）。

---

## 7. 设备依赖

无直接设备依赖（纯计算）。

---

## 8. 参与的端到端流程

- 销售重算中的税额计算段 → [70_flows/sale_end_to_end.md](../70_flows/sale_end_to_end.md)
- 支付税额案分（印紙判定）→ [70_flows/payment_mixed.md](../70_flows/payment_mixed.md)

---

## 9. 可信度与核查

- **verified**：8 文件/922 行、`TaxManager : ITaxManager`、`TaxTypes=3`、内/外税公式（`Tax.cs:80-91`）、軽減税率税组切换（`TaxManager.cs:290-312`）、书籍税价、税 master 访问路径均实测。
- **uncheckable**：`RoundManager`/`RoundTypes`、`FrameworkLibrarySettingValues` 在 `POS4U.Framework(.Library).dll`（无源码）——本篇只核到"调用层/模式常量名"。税率**数值**本身来自运行时 master 数据（非代码常量）。

---

## 10. ST-POS 迁移提示

> ST-POS 税制以 kugelpos `master-data` 的 tax master + `cart` 的税计算为准（近期有税码变更 SDD、ADR-0001/0004/0005 税快照划分）。内税/外税/軽減税率语义可对照，但案分/端数实现不同 → `stpos-backend-kugelpos` tax SDD（只外链）。
