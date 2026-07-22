---
title: 端到端流程篇 · 索引
layer: 70_flows
genre: explanation
audience: [重构开发, QA, 架构师]
code_baseline: latest
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
owner: jinianxiang
updated: 2026-07-14
---

# 端到端流程篇（`70_flows`）

> **体裁 = explanation。** 本层只做**跨模块端到端叙事**——把一件事从 UI 事件、Command、Business 交易实体、数据落盘到设备/云端串成一条线，说明"谁先谁后、为何如此"。
>
> **单一真相源纪律**：每一步只 `→ 详见` 链接到它的"家"（[30_domain](../30_domain/index.md) 业务规则 / [40_data](../40_data/01_overview.md) 表 SP / [50_devices](../50_devices/index.md) 设备 / [60_services](../60_services/edge-api/index.md) 服务），**绝不在此复制其正文**。流程篇里的 `file:line` 只用于锚定"这一步在哪触发"，规则细节回域篇。

---

## 流程清单

| 流程 | 一句话 | 主参与模块 |
|---|---|---|
| [sale_end_to_end](./sale_end_to_end.md) | 扫码→小计→结算→落盘→打印 的通常销售主线 | Sales · Discount · Tax · Payment · Point · RJ · TranLogMaker |
| [return_void](./return_void.md) | 一括取消（Void 121）与部分退货重售（ReSales）双模式 | ReSales · Member · Payment · TranLogMaker |
| [payment_change](./payment_change.md) | 多金种复合支付的排序、找零与不可取消闸门 | Payment · CashChanger |
| [point_accrual_offline](./point_accrual_offline.md) | 会员积分累计与网络闪断时的离线降级 | Member · Point |
| [emoney_charge](./emoney_charge.md) | 电子マネー充值（811 charge / 816 void）独立交易 | EMoney · Payment |
| [hold_recall](./hold_recall.md) | 挂单（13 位 MTran ID）与跨机呼出的行级互斥锁 | Sales(MTranObject) · PaymentStation |
| [open_close_daily](./open_close_daily.md) | 开店点检（201）与关店精算（202）的日周期 | OpenCount · CloseCount · CashChanger |
| [price_change](./price_change.md) | 前台手动改价四重防呆与业务层四重闸门 | Sales(LineItem) · Discount |
| [master_sync_tlog](./master_sync_tlog.md) | 主数据下行同步与交易流水（TLog）上行转发 | Background.MasterSync · Background.Transfer |

---

## 通用记号

- **状态**：`SalesTranStates`（28 = 18 TranState + 10 State）等状态空间定义在 `Common/Common.Const/State/*.cs`；迁移边在 `POS4U/Settings/StateWinPOS*.xml` + Command 类（部分 `uncheckable`，见 [verification-status](../90_traceability/verification-status.md)）。
- **交易码**：所有 `TranLogType` 数值码定义在 `Application/Source/Common/Common.Const/TranLogTypes.cs`（101 売上 / 105 返品 / 121 取消 / 201 開設 / 202 精算 / 301 セルフ売上 / 801 プリカチャージ …）。流程篇引用这些码时不再重复定义，回 [40_data/06_enums](../40_data/06_enums_constants.md)。
- **框架引擎**：Event→Command→Observer→State 五要素引擎见 [20_framework](../20_framework/index.md)；基类本体在 `POS4U.Framework.dll`（无源码，`uncheckable`）。

---

## 关联

- 决策取舍（为什么这样设计）→ [80_decisions](../80_decisions/index.md)
- 代码↔文档双向映射 → [90_traceability/matrix](../90_traceability/matrix.md)
- ST-POS 迁移线索 → [90_traceability/stpos-migration-hints](../90_traceability/stpos-migration-hints.md)
