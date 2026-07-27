---
title: ADR-003（代码反推）外部依赖离线降级 · 不阻断收银
layer: 80_decisions
genre: adr
audience: [架构师, 重构开发]
code_baseline: latest
code_refs:
  - Application/Source/Business/Business.Member/MemberObject.cs
  - Application/Source/Common/Common.Const/State/SalesTranStates.cs
  - Application/Source/WinPOS/Command/WinPOS.CommandEMoney/EMoneyCharge_VDOfflineCancel.cs
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
related:
  flows: [../70_flows/point_accrual_offline.md, ../70_flows/emoney_charge.md]
owner: jinianxiang
updated: 2026-07-14
---

# ADR-003（代码反推）外部依赖离线降级 · 不阻断收银

## 背景

收银主链路依赖若干**外部系统**：会员积分平台（Point Infinity）、电子マネー端末/上游、CAFIS 网络。这些依赖会抖动。零售 POS 的铁律是**顾客不能因为后台系统抖动而结不了账**。

## 决策

**外部依赖不可用时降级为"离线记账"，交易照常确定（`FixTran`），一致性事后补偿**，而非阻断。代码里为此内建了显式的离线状态位与离线取消分支。

## 证据（file:line）

- 会员离线判定：`Business/Business.Member/MemberObject.cs:591`、`:679` `if (valueResult.Value.IsOffline)`。
- 离线积分标志落库：`MemberObject.cs:947`、`:1104` `IsOffline = memberRow.IsPointRefOffline`；`:983` `salesHeader.IsOfflinePointCardNo`。
- 销售状态机离线节点：`Common/Common.Const/State/SalesTranStates.cs:119` `ValueCardOffline`。
- 电子マネー端末离线取消分支：`WinPOS/Command/WinPOS.CommandEMoney/EMoneyCharge_VDOfflineCancel.cs`。

## 取舍

- **得**：可用性优先——网络/中台/端末抖动不打断收银；离线数据随 TLog 上行补传对账（→ [master_sync_tlog](../70_flows/master_sync_tlog.md)）。
- **付**：短时**弱一致**（离线期间积分/余额以本地记账为准，可能与中台短暂不一致，需事后对账）；离线分支增加状态与代码路径的复杂度。
- ⚠️ **动机的核实边界**："不阻断收银"这一**意图**是从"存在离线状态位 + 离线不 return-false 阻断"这一代码事实**推断**的合理设计取舍；`MemberObject.Inquiry`/`Update` 及框架 `FixTran` 的确切失败处理语义部分在 `POS4U.Framework.dll`（无源码），属 `uncheckable`，不作绝对断言。

## 现状 / 对新系统含义

- 离线状态位与离线取消分支 `verified`；降级"意图"为**代码支撑的推断**。
- ST-POS 的离线/容灾策略差异 → [migration-hints](../90_traceability/stpos-migration-hints.md)（只外链）。
