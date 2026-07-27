---
title: 跨层追溯矩阵 · 能力 ↔ 模块 ↔ 代码 ↔ 文档 ↔ 表/设备
layer: 90_traceability
genre: meta
audience: [重构开发, 架构师, PM]
code_baseline: latest
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
owner: jinianxiang
updated: 2026-07-14
---

# 跨层追溯矩阵

> 一张"上帝视角"表：把**能力/主题**串到 **Business 模块 → 代码路径(file:line) → 00- 文档 → 表/设备 → 可信度**。每格的代码锚点均以 最新发布 为准。可信度口径见 [verification-status](./verification-status.md)。
>
> **本表只做索引，不复制正文**：规则细节回 [30_domain](../30_domain/index.md)，字典回 [40_data](../40_data/01_overview.md)，叙事回 [70_flows](../70_flows/index.md)。

## A. 核心能力矩阵

| 能力/主题 | Business 模块 | 关键代码（file:line） | 00- 文档 | 表/设备 | 可信度 |
|---|---|---|---|---|---|
| 商品扫描·PLU | Sales | `EventCodes.cs:162`（`Sales_PriceLookup`=101）· `SalesTran.PriceLookup` | [flows/sale](../70_flows/sale_end_to_end.md) · [domain/sales](../30_domain/sales.md) | `ItemMaster`(3元组) / Scanner | verified |
| 明细行金额 | Sales | `LineItemBase.cs:119-123` | [investigations/subtotal](../80_decisions/investigations/subtotal_discount_defect.md) | — | verified（**缺陷**） |
| 年齢/药品/防犯确认 | Sales | `AgeConfirmType` + 5×`AgeConfirmTypes`（非虚构 `IsAgeLimitProhibition`） | [domain/sales](../30_domain/sales.md) | — | unverified |
| 手动改价·四重闸门 | Sales | `LineItemBase.cs:249/254/261/268` | [flows/price_change](../70_flows/price_change.md) | — | verified |
| 指定/直前取消 | Sales | `Sales_CancelSpecifiedLineByItem` · `SalesLayout.cs:146-148` | [flows/return_void](../70_flows/return_void.md) · [domain/rj](../30_domain/rj.md) | Printer(RJ) | verified |
| 自动促销 Mix&Match | Discount | `DiscountMixMatchLogic.cs:98/160/191/210` | [domain/discount](../30_domain/discount.md) | `TranMasterDataSet.DiscountMixMatchMaster`(内存) | verified |
| 手动小计折扣（缺陷） | Discount / TranLogMaker | `DiscountMaker.cs:34` · `SalesTran.DiscountTotal` | [investigations/subtotal](../80_decisions/investigations/subtotal_discount_defect.md) | `SalesDiscount` | verified（**崩溃 Bug**） |
| 税额计算 | Tax | `TaxManager.Calc`（引用 `TotalDiscountSubTotalDivided`） | [domain/tax](../30_domain/tax.md) | — | uncheckable（基类） |
| 复合支付·金种排序 | Payment | `PaymentObject.cs:781-791`（`SortPaymens`） | [flows/payment_change](../70_flows/payment_change.md) · [domain/payment](../30_domain/payment.md) | — | verified |
| 刷卡后不可取消 | Payment | `PaymentCAFISArchLANBase.cs:311`（`CanCancel=false`） | [flows/payment_change](../70_flows/payment_change.md) | CAFIS(Saturn1000L/CT5100) | verified |
| 会员积分·离线降级 | Member / Point | `MemberObject.cs:591/679/947` · `SalesTranStates.cs:119`(`ValueCardOffline`) | [flows/point](../70_flows/point_accrual_offline.md) · [ADR-003](../80_decisions/adr-003-offline-degradation.md) | PointInfinity(外部) | verified（状态位） |
| 退货 Void / ReSales | ReSales | `VoidTran.cs` · `ReSalesTran.cs` · `TranLogTypes.cs:67`(121)/`:47`(105) | [flows/return_void](../70_flows/return_void.md) · [domain/resales](../30_domain/resales.md) | `TransactionLog` | verified |
| 挂单 / 跨机呼出 | Sales(MTranObject) | `MTranObject.cs:23/659-668` · `usp_GetMTransactionManagement`(ROWLOCK/UPDLOCK) | [flows/hold_recall](../70_flows/hold_recall.md) · [ADR-001](../80_decisions/adr-001-five-tuple-pk.md) | `MTransactionManagement` | verified |
| 电子マネー充值 | EMoney | `EMoneyChargeTran.cs` · `TranLogTypes.cs:142`(801)/`:147`(816) | [flows/emoney_charge](../70_flows/emoney_charge.md) · [domain/emoney](../30_domain/emoney.md) | 电子マネー端末(外部) | verified |
| 开店点检 | OpenCount | `OpenCountTran.cs` · `TranLogTypes.cs:97`(**201**) | [flows/open_close](../70_flows/open_close_daily.md) · [domain/opencount](../30_domain/opencount.md) | CashChanger(Glory) | verified |
| 关店精算 | CloseCount | `CloseCountTran.cs` · `TranLogTypes.cs:102`(**202**) | [flows/open_close](../70_flows/open_close_daily.md) · [domain/closecount](../30_domain/closecount.md) | CashChanger · CAFIS | verified |
| 入金 / 出金 | CashInOut | `TranLogTypes.cs:217`(CashIn 813)/`:222`(CashOut 814) | [domain/cashinout](../30_domain/cashinout.md) | CashChanger | verified（码） |
| 交易落盘 XML | TranLogMaker | `TransactionLog.Table.sql:24`(`[xml]`) · `usp_InsertTransactionLog` | [ADR-004](../80_decisions/adr-004-tlog-xml-persist.md) · [flows/master_sync](../70_flows/master_sync_tlog.md) | `TransactionLog` | verified |
| 主数据下行同步 | Background.MasterSyncPos | `Download.cs:54`(POST `GetMasterDownloadFile`) · `ControllerBulk`/`ControllerDiff` | [flows/master_sync](../70_flows/master_sync_tlog.md) | 主档全体 | verified |
| 流水上行转发 | Background.Transfer | `Transfer/Controller.cs` · `usp_InsertTLogQueue` | [flows/master_sync](../70_flows/master_sync_tlog.md) · [ADR-004](../80_decisions/adr-004-tlog-xml-persist.md) | `TransactionLog` | verified |
| 本机 IPC | WinPOS.Batch / TRAN4U | `TranRemoteControllerLibrary.cs:20/132/145`(net.tcp:8012) | [ADR-002](../80_decisions/adr-002-wcf-for-ipc.md) | 全外设(经 TRAN4U) | verified |
| 边缘 API（跨机） | POS4ULogicService | `Global.asax.cs:31`(Web API, 11 Controller) | [ADR-002](../80_decisions/adr-002-wcf-for-ipc.md) · [60_services/edge-api](../60_services/edge-api/index.md) | — | verified |
| 分层联合主键 | （数据层） | `TransactionLog.Table.sql:25-32`(5) · `SettingMaster`(4) · `ItemMaster`(3) | [ADR-001](../80_decisions/adr-001-five-tuple-pk.md) · [40_data/03](../40_data/03_tran_tables.md) | 上述三表 | verified |

## B. 22 个 Business 模块 ↔ 流程覆盖

> 模块清单实测 `Application/Source/Business/Business.*/`（22 个）。

| 模块 | 主要能力 | 参与的 70_flows |
|---|---|---|
| Sales | 销售主事务 | sale_end_to_end · price_change · hold_recall · return_void(指定取消) |
| ReSales | 退货/作废 | return_void |
| Payment | 支付/找零 | payment_change · sale_end_to_end |
| PaymentStation | 付款机（半自助） | hold_recall |
| Discount | 折扣/促销 | sale_end_to_end · price_change |
| Tax | 税额 | sale_end_to_end |
| Member / Point | 会员/积分 | point_accrual_offline · return_void |
| EMoney | 电子マネー充值 | emoney_charge |
| OpenCount / CloseCount | 开闭店 | open_close_daily |
| CashChanger / CashInOut | 找零机/入出金 | payment_change · open_close_daily |
| RJ | 小票/日记账版式 | sale_end_to_end · return_void |
| TranLogMaker | 交易日志构建 | sale_end_to_end · master_sync_tlog |
| BusinessCommon · EntryNonCash · InputConverter · MainMenu · Operator · Report · RetailMedia | 公共/录入转换/主菜单/操作员/报表/零售媒体 | **未单列流程**（→ [domain](../30_domain/index.md) 单篇） |

## C. 外部/不可核依赖（全体共享）

| 依赖 | 性质 | 可信度 |
|---|---|---|
| `POS4U.Framework.dll`（TranBase/State/Observer/EventCode/CheckDigitM10W31） | 无源码 | uncheckable |
| Point Infinity · CAFIS · 电子マネー上游 · Azure/总部 | 外部系统 | uncheckable（只核 POS 侧调用） |
| 状态机迁移边（`StateWinPOS*.xml` + Command） | 节点已核，边逐条另核 | 部分 unverified |

## 关联

- 逐篇 verified/unverified/uncheckable 台账 → [verification-status](./verification-status.md)
- 文档化进度（22模块/78设备/11Controller/405SP） → [coverage](./coverage.md)
- ST-POS 迁移线索（只外链） → [stpos-migration-hints](./stpos-migration-hints.md)
