---
title: 缺陷调查 · 手动小计折扣（合计不减折扣 + 落盘 NRE 崩溃）
layer: 80_decisions
module: Business.Sales / Business.TranLogMaker
audience: [重构开发, QA, 架构师]
genre: adr
code_baseline: latest
code_refs:
  - Application/Source/Business/Business.Sales/LineItem/LineItemBase.cs
  - Application/Source/Business/Business.TranLogMaker/Maker/DiscountMaker.cs
  - Application/Source/Business/Business.Sales/SalesTran.cs
verification: verified
verified_by: ../../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
related:
  flows: [../../70_flows/sale_end_to_end.md, ../../70_flows/price_change.md]
  domain: [../../30_domain/discount.md, ../../30_domain/sales.md]
owner: jinianxiang
updated: 2026-07-14
---

# 缺陷调查 · 手动小计折扣

> 分析 POS4U 时挖出的**两个真实 Bug**（非纸面推测，本页两处 `file:line` 均已亲核 最新发布 源码）。手动小计折扣（`ManualDiscountSubTotal`）功能**不可用**：金额算错在先，落盘崩溃在后。素材源 = `01-trialpos-docs/4_trial_specs/price_change/subtotal_discount_investigation_report.md`（其核心两点经本仓复核成立）。

## 缺陷 1（金额错）：`LineTotal` 漏减小计折扣分摊额

小计折扣注册、按单品比例分摊（`TotalDiscountSubTotalDivided`）、税额重算、积分排除**都正常工作**——但分摊结果**没有回流到行总额**。

**证据（已核）**：`Business/Business.Sales/LineItem/LineItemBase.cs:119-123`
```csharp
public decimal LineTotal
{
    get
    {
        return (this.UnitPriceForPurchase * this.Quantity) - this.DiscountTotal;
        // 缺陷：减了明细折扣 DiscountTotal，但漏减小计折扣分摊额 TotalDiscountSubTotalDivided
        // 应为：... - this.DiscountTotal - this.TotalDiscountSubTotalDivided;
    }
}
```

**影响链**：`LineTotal` 是应付总额的计算基石——
```
TotalAmountWithTaxes（应付）
 └─ TotalAmount = Σ LineItem.LineTotal   ← 每行都少减了分摊折扣
```
于是**顾客实付、画面合计、小票合计**全部未享受该折扣。

**对照（正确的一侧）**：`SalesTran.DiscountTotal`（`Business/Business.Sales/SalesTran.cs`）**正确**合并了小计折扣 + 明细折扣：
```csharp
return this.TranDiscountData.DiscountAmount + this.LineItems.Items.Sum(l => l.DiscountTotal);
```
但 `TotalAmountWithTaxes` 依赖的是**有缺陷的 `LineTotal` 累加**，而非这个正确的 `DiscountTotal`——所以应付额依旧错。

## 缺陷 2（崩溃）：落盘时 `NullReferenceException`

交易确定时向 `SalesDiscount` 表写折扣行，第一行就对**空表**取 `FirstOrDefault()` 再访问其属性 → NRE，收银台崩溃，TLog 无法持久化。

**证据（已核）**：`Business/Business.TranLogMaker/Maker/DiscountMaker.cs:19-34`
```csharp
public static void AddDiscountInfo(TranDataSet tranDs, SalesTran tran)
{
    var discountData = tran.GetTranDiscountData();
    if (discountData.Items.Count == 0) { return; }          // :23 有折扣才继续
    var discountTable = tranDs.SalesDiscount;
    foreach (var discount in discountData.Items)
    {
        TranDataSet.SalesDiscountRow discountRow = discountTable.NewSalesDiscountRow();  // :33 新行(未加入表)
        discountRow.TransactionNo = tranDs.SalesDiscount.FirstOrDefault().TransactionNo; // :34 ★ 空表!
        // ...
    }
}
```
**机理**：`:33` 用 `NewSalesDiscountRow()` 造了行但**尚未 `AddSalesDiscountRow` 加入表**；`:34` 却从**仍为空**的 `tranDs.SalesDiscount` 上 `FirstOrDefault()` → 返回 `null` → `.TransactionNo` 抛 `NullReferenceException`。第一条折扣就必触发（此时表恒空）。意图应是从头行/兄弟表取 `TransactionNo`，却错引了自己这张空表。

## 触发条件与现状

- **触发**：在 `Paying` 状态注册手动小计折扣（`Sales_DiscountManualSubTotal` → `DiscountManualSubTotalLogic.AddDiscountManualSubTotal`）后做交易确定。
- **现状**：功能**有骨架无闭环**。相关自动小计折扣（`DiscountSubTotalMaster` / `usp_GetDiscountSubTotal`）**仅 DB/SP 层就绪，C# Accessor/业务类/插件缺失**（未启用）；扫码优惠券整单折扣**完全不存在**（折扣系列主表无任何 barcode 字段）——素材报告 §2 的这两点属**待复核的 `01-` 结论**，本页不逐条亲核，引用前请回代码确认。

## 对新系统的含义

- 这是"UI/注册/分摊算得对，但**没接到合计与落盘**"的典型断链——新系统实现小计折扣时，务必让分摊额贯通到 `LineTotal`→应付→票据→TLog，并给折扣行正确的 `TransactionNo` 来源。
- 改价与手动折扣**互斥**（见 [price_change](../../70_flows/price_change.md) 闸门③）也与本缺陷同源背景。
- ST-POS 侧对应设计**不在本仓**，线索只外链 → [migration-hints](../../90_traceability/stpos-migration-hints.md)。

## 可信度

- **verified**：缺陷 1（`LineItemBase.cs:123`）、缺陷 2（`DiscountMaker.cs:34`）两处源码本仓亲核，成立。
- **unverified**：素材报告中"自动小计特卖仅 DB 层就绪""扫码券不存在"等结论未逐条亲核（列为待复核）。
