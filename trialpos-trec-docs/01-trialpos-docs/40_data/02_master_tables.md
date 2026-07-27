---
title: 主数据表字典 · Master 域分组 + 核心表（ItemMaster / SettingMaster）
layer: 40_data
module: database
audience: [重构开发, 读码, DBA]
genre: reference
code_baseline: latest
code_refs:
  - Application/Database/01_Tables/00_CreateOrder4Master.txt
  - Application/Database/01_Tables/dbo.ItemMaster.Table.sql
  - Application/Database/01_Tables/dbo.SettingMaster.Table.sql
  - Application/Database/01_Tables/dbo.MDHierarchyMaster.Table.sql
verification: verified
verified_by: ./01_overview.md
related:
  data: [./01_overview.md, ./03_tran_tables.md, ./05_stored_procedures.md, ./06_enums_constants.md, ./07_master_sync.md]
  domain: [../30_domain/rj.md]
owner: jinianxiang
updated: 2026-07-14
---

# 主数据表字典（Master 域）

> 主数据物理上主要落在 **`POS4U_Trial_Master`** 库（[`00_CreateOrder4Master.txt`](Application/Database/01_Tables/00_CreateOrder4Master.txt) 实测引用 99 表，其中约 60 张为 `*Master` 后缀主数据）。本篇按业务域分组给出清单 + 两张核心表的字段字典。库拓扑见 [01_overview §2](./01_overview.md)。

## 1. 命名约定（实测）

- 真主数据表名以 **`Master` 结尾**（如 `ItemMaster`），**无 `T_`/`T_D_` 前缀**——`T_D_*` 仅为 BI 桥接**视图**约定（见 [04_views](./04_views.md)），`T_*` 前缀在本库表中不存在。
- `BO*` 前缀表属 BackOffice 后端，落 **Tran 库**（见 [03_tran_tables](./03_tran_tables.md)）。
- `Reserve*` 前缀 = 主数据差分同步的"预约/暂存"表（见 [07_master_sync](./07_master_sync.md)）。

> ⚠️ **订正**：早期素材出现的 `T_BusinessCounter` 属虚构；真实表名为 `BusinessCounter`（[`dbo.BusinessCounter.Table.sql`](Application/Database/01_Tables/dbo.BusinessCounter.Table.sql)），无前缀。

## 2. 按域分组清单（Master 库主数据）

> 表名均可回 `Application/Database/01_Tables/dbo.<名>.Table.sql`。计数为该域实测表数。

| 域 | 代表表 |
|---|---|
| **商品 Item** | `ItemMaster`·`ItemMasterMaintenance`·`ItemImageMaster`·`ItemCreditProhibitionMaster`·`ItemWeightMaster`·`ItemWeightExclusionPatternMaster`·`NonBarcodeOtherItemMaster`·`NonBarcodeOtherItemCategoryMaster`·`BarcodeConvertMaster`·`BarcodeConvertSubMaster`·`BestBeforeDateMaster`·`BestBeforeMarkDownMaster` |
| **商品阶层 MDHierarchy** | `MDHierarchyMaster`·`MDHierarchyLevelMaster` |
| **价格·促销 Price** | `SpecialPriceMaster`·`DynamicPricingMaster`·`PromotionMaster` |
| **折扣 Discount** | `DiscountTypeMaster`·`DiscountManualMaster`·`DiscountSubTotalMaster`·`DiscountAutoItemMaster`·`DiscountAutoMDHierarchyMaster`·`DiscountMDHierarchyMaster`·`DiscountMixMatchMaster`·`DiscountMixMatchDetailMaster`·`DiscountMixMatchSetItemMaster`·`DiscountGroupSetMaster`·`DiscountGroupSetDetailMaster`·`DiscountGroupSetItemMaster` |
| **税 Tax** | `TaxCodeMaster`·`TaxGroupMaster`·`TaxGroupDetailMaster` |
| **支付·金券 Payment** | `PaymentMaster`·`PaymentSummaryGroupMaster`·`PaymentPointScheduleMaster`·`PaymentTicketMaster`·`PaymentTicketBarCodeMaster`·`RevenueStampMaster`·`RevenueStampGroupMaster` |
| **积分·会员 Point** | `PointRateItemMaster`·`PointRateMDHierarchyMaster`·`PointRankMaster`·`PointRankScheduleMaster`·`PointRankStageMaster`·`PointECouponMaster`·`PointMemberECouponMaster`·`PointMemberECouponDetailMaster`·`ChargePointCalculateMaster` |
| **组织·端末 Org** | `CompanyMaster`·`StoreInformationMaster`·`AreaMaster`·`NodeMaster`·`TerminalMaster`※·`OperationLimitMaster` |
| **员工 Employee** | `EmployeeMaster`·`EmployeeRoleMaster`·`EmployeesAffiliationMaster` |
| **画面·菜单·文言 UI** | `FunctionMenuMaster`·`FunctionMenuButtonMaster`·`PresetMenuMaster`·`PresetMenuButtonMaster`·`LineDisplayMessageMaster`·`ReceiptMessageMaster` |
| **现金·钱箱 Cash** | `CashChangerCheckMaster`·`CashDenominationMaster`·`CashInOutMaster` |
| **事件·事由 Event/Reason** | `EventGroupMaster`·`EventGroupDetailMaster`·`EventConvertMaster`·`ReasonMaster` |
| **设定 Setting** | `SettingMaster`·`SettingServerMaster` |
| **其他** | `BudgetedSalesMaster`·`ActivationMaster`·`VersionManagement`·`EnterpriseSystemInfoMaster`※ |

※ `TerminalMaster`、`EnterpriseSystemInfoMaster` = 物理存在但两库 `CreateOrder` 未引用的孤儿表（见 [01_overview §4](./01_overview.md)）。

## 3. 核心表：`ItemMaster`（商品マスタ）

来源 [`Application/Database/01_Tables/dbo.ItemMaster.Table.sql`](Application/Database/01_Tables/dbo.ItemMaster.Table.sql)。**PK = 三元组 `CompanyCode / StoreCode / ItemCode`（CLUSTERED，`:49-54`）**；仅此一个聚集索引，无附加非聚集索引。

主要字段（实测，节选）：

| 字段 | 类型 | Null | 行 | 说明 |
|---|---|---|---|---|
| `CompanyCode` | nvarchar(10) | NOT NULL | :13 | PK |
| `StoreCode` | nvarchar(10) | NOT NULL | :14 | PK |
| `ItemCode` | nvarchar(26) | NOT NULL | :15 | PK · 商品コード（26 桁） |
| `ParentCode` | nvarchar(10) | NOT NULL | :16 | 親商品コード |
| `Description` / `DescriptionShort` / `DescriptionLong` | nvarchar(50/25/100) | NULL | :17-19 | 品名（3 種長さ） |
| `DepartmentTypeCode` | nvarchar(2) | NULL | :21 | 部門種別 → [DepartmentTypes](./06_enums_constants.md) |
| **`UnitPrice`** | **`[money]`** | **NOT NULL** | **:23** | **売単価** |
| `HeadquartersIndicationPrice` | money | NULL | :24 | 本部指示売価 |
| `CostPrice` | money | NULL | :25 | 原価 |
| `MarkupRatio` | numeric(5,2) | NULL | :26 | 値入率 |
| `TaxGroupCode` | nvarchar(2) | NULL | :27 | → `TaxGroupMaster` |
| `IsCashOnly` / `IsItemManualDiscountProhibition` / `IsSubTotalDiscountProhibition` / `IsChangePriceProhibition` | bit | NULL | :30-33 | 各種禁止フラグ |
| `IsAutoDiscountProhibition` | bit | NOT NULL | :34 | 自動値引禁止 |
| `AgeConfirmationType` | nvarchar(3) | NULL | :35 | 年齢確認種別 |
| `OTCDrugType` | nvarchar(2) | NULL | :36 | OTC 医薬品区分 |
| `IsPointProhibition` | bit | NULL | :37 | ポイント付与禁止 |
| **`PointRate`** | **`[numeric](3,1)`** | **NULL** | **:38** | **ポイント付与率** |
| `IsCollectionTargetItem` | bit | NOT NULL | :40 | 回収対象 |
| `IsTaxFreeProhibition` / `SalesCertificateType` / `IsDutyFree` | nvarchar(2/3) | NULL | :46-48 | 免税・販売証明区分 |
| `EntryDate` / `LastUpdateDate` / `HeadquartersLastUpdateDate` | datetime2 | :43-45 | 登録・更新・本部更新日時 |

> 类型要点：金額列一律 **`[money]`**（非 decimal），付与率 **`[numeric](3,1)`**（小数 1 桁）。重构时的精度/舍入规约以此为准。

## 4. 核心表：`SettingMaster`（端末別設定・KVS）

来源 [`Application/Database/01_Tables/dbo.SettingMaster.Table.sql`](Application/Database/01_Tables/dbo.SettingMaster.Table.sql)。键值对（KVS）结构，**PK = 四元组 `CompanyCode / StoreCode / TerminalNo / Key`（CLUSTERED，`:18-24`）**。

| 字段 | 类型 | Null | 行 |
|---|---|---|---|
| `CompanyCode` | nvarchar(10) | NOT NULL | :13 |
| `StoreCode` | nvarchar(10) | NOT NULL | :14 |
| `TerminalNo` | int | NOT NULL | :15 |
| `Key` | nvarchar(100) | NOT NULL | :16 |
| `Value` | nvarchar(1000) | NOT NULL | :17 |

- `TerminalNo` 入 PK ⇒ 设定**可精确到端末**（`TerminalNo=0` 常表全端末缺省，按业务约定）。
- `Key` 的取值域由强类型常量 `SettingMasterKeys`（实测 161 键）枚举收敛，全店共通设定另有 `SettingServerMaster`（对应 `SettingServerMasterKeys` 39 键）。→ 键清单见 [06_enums_constants §Setting 族](./06_enums_constants.md)。

## 5. 可信度与核查

- **verified**：ItemMaster / SettingMaster 全字段与 PK 带 `file:line`；域分组表名逐一可回 `.Table.sql`。
- 各域的具体列/外键关系（本篇未逐表展开者）须以对应 `.Table.sql` 为准，未核到列级前不得断言字段名（红线）。

## 6. ST-POS 迁移提示

> 🔀 `ItemMaster` 的店别三元组主键与 `[money]` 单价，对应 ST-POS `item_master` 的 `tenant_id/store_code/item_code` 与 decimal 价格模型；映射细节外链团队内部设计库，不在本体系。
