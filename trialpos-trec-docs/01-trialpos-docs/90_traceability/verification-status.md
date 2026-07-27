---
title: 可信度状态 · 各文档 verified / unverified / uncheckable
layer: 90_traceability
genre: meta
audience: [全体, PM]
code_baseline: latest
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
owner: jinianxiang
updated: 2026-07-14
---

# 可信度状态

> 每篇文档 frontmatter 的 `verification` 汇总于此。精度基线 = [`../../90-verification/`](../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md)（2026-07-14 五路代码核查）。

## 分级定义

- **verified**：核心断言已逐条回 `trialpos-snapshots` 代码核实（file:line）。
- **unverified**：内容已迁移/撰写，但尚未完成逐条代码核实（谨慎引用）。
- **uncheckable**：依赖 `POS4U.Framework.dll`（无源码）或外部系统，源码内无法验证——只能核到"使用层/存在性"。

## 已知 uncheckable 项（全体共享）

- 框架基类：`TranBase` / `CommandBase` / `State` / `TranState` / `Observer` / `EventCode` / `CheckDigitM10W31` 的**定义本体**在 `Application/POS4UCloud/ExternalModule/Framework/POS4U.Framework.dll`。
- 状态机**迁移边**：定义在 `Application/Source/POS4U/Settings/StateWinPOS*.xml` + Command 类；本体系核到"状态节点存在"，迁移边逐条另核。
- 外部系统：CAFIS 网络、Point Infinity、Azure/基幹 侧行为。

## 状态台账

> 随各篇完成更新。建成初期，凡引用了 90-verification 已核实事实者标 verified，纯迁移未复核者标 unverified。

> **全库口径（实测 2026-07-14）**：90 篇中 **87 verified / 1 unverified（`15_howto/index.md` 骨架）/ 2 uncheckable（`20_framework/04_base_classes.md` 基类在 Framework.dll、`99_archive/README.md`）**。零死链、frontmatter 全合规。

| 层 | 文档 | verification | 备注 |
|---|---|---|---|
| 00_portal | README / conventions / code-map / glossary / reading-paths / architecture-redesign-proposal | verified | 真值基线来自 90-verification |
| 10_architecture | 01_context~07_crosscutting（7 篇） | verified | IPC/端口 8012/超时 5min 逐条 file:line；MasterSync 机制已回 `Background.Business.MasterSyncPos` 核实 |
| 15_howto | index + new_business_module + new_xaml_screen + add_device_plugin | **unverified**（锚点 verified） | 2026-07-14 从 12-gitlab 迁移+回代码核实落地；how-to 整篇 unverified 但引用的类/EventCode/XML/路径逐条 verified；已订正 12- 系统性过时（`Bussiness/`→`Common/`、多处拼写、`Plugin.xml` 真实位置） |
| 20_framework | index + 01_event_command_observer~05_conventions（6 篇） | verified / **uncheckable** | 使用层 verified；`04_base_classes` 基类定义在 `POS4U.Framework.dll` 无源码=uncheckable |
| 30_domain | **全 22 模块**（sales/payment/resales/point/member/discount/tax/emoney/inputconverter/rj/open_close/cash_changer/cash_in_out/operator/main_menu/payment_station/entry_non_cash/retail_media/report/tran_log_maker/business_common + index） | **全 verified** | 8 篇轻量模块 2026-07-14 深核升级（逐条 file:line；分析发现 `CashInOutTran.cs:861` 恒不可达条件、`MTranDeleteMode` 实为 DTO 等订正） |
| 40_data | 01_overview~07_master_sync（7 篇） | verified | 引擎 SQLEXPRESS/计数 160-405-24/五元组 PK 逐条 |
| 50_devices | index + 7 分族篇 | verified | 78 模块全覆盖/net.tcp 超时/CAFIS Saturn1000L |
| 60_services | edge-api(4)/background(5)/cloud(3) | verified | 11 Controller·70 action/AES-256/HTTP 418 |
| 70_flows | index + 9 场景 | verified | 状态码/交易码/SortPaymens/缺陷点逐条回代码；各篇末列残留项 |
| 80_decisions | index + ADR-001~004 + investigations/subtotal_discount_defect | verified | 4 代码分析 ADR + 缺陷调查（LineItemBase.cs:123 / DiscountMaker.cs:34 亲核） |
| 90_traceability | verification-status（本篇）+ matrix + coverage + stpos-migration-hints | verified | matrix 跨层大表；migration-hints 只外链 ST-POS 仓 |
| 99_archive | README | uncheckable | 封存说明（历史层） |
