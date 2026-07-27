---
title: 代码分析 ADR 与缺陷调查 · 索引
layer: 80_decisions
genre: adr
audience: [架构师, 重构开发]
code_baseline: latest
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
owner: jinianxiang
updated: 2026-07-14
---

# 代码分析 ADR 与缺陷调查（`80_decisions`）

> **体裁 = adr（代码反推）。** POS4U 并无正式 ADR 台账，本层是**代码推断**——从代码里**可被证据支撑**的设计取舍，反推"当初为什么这样决定"。
>
> **红线**：不编造 ADR 内容。每条决策的「证据」必须能回到 `file:line`；无法核实的动机只写"代码呈现的事实 + 合理推断"，并显式标注推断性质。框架 DLL 内部动机为 `uncheckable`。

## 轻量 ADR 格式

每篇：**背景 → 决策 → 证据(file:line) → 取舍 → 现状/对新系统含义**。

## ADR 清单（代码反推）

| # | 决策 | 一句话 | 证据强度 |
|---|---|---|---|
| [ADR-001](./adr-001-five-tuple-pk.md) | 交易表五元组联合主键 | 交易/设定/主档按可变性用 5/4/3 元组分层主键 | verified（DDL 直证） |
| [ADR-002](./adr-002-wcf-for-ipc.md) | WCF net.tcp 仅用于本机 IPC | 进程间用 WCF；边缘 API 用 ASP.NET Web API/HTTP | verified（绑定+配置直证） |
| [ADR-003](./adr-003-offline-degradation.md) | 外部依赖离线降级不阻断收银 | 会员/电子マネー端末抖动时降级记账 | verified（状态位）+ 推断（动机） |
| [ADR-004](./adr-004-tlog-xml-persist.md) | 交易流水 XML 一体化落盘 | `TransactionData [xml]` 整包持久化 + 队列转发 | verified（DDL+SP 直证） |

## 缺陷调查（分析发现的真实 Bug）

| 调查 | 一句话 | 证据强度 |
|---|---|---|
| [subtotal_discount_defect](./investigations/subtotal_discount_defect.md) | 手动小计折扣：合计不减折扣 + 落盘 NRE 崩溃 | verified（两处 file:line 亲核） |

## 与其它层的关系

- 决策**为什么**在这里；**是什么/怎么运作**在 [30_domain](../30_domain/index.md) / [10_architecture](../10_architecture/) / [70_flows](../70_flows/index.md)。
- 精度基线 → [90-verification](../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md)。
