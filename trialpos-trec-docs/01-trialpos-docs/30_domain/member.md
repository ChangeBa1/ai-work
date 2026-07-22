---
title: 会员域（Business.Member）· Member & Value Card
layer: 30_domain
module: Business.Member
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Business/Business.Member/MemberObject.cs
  - Application/Source/Business/Business.Member/PointCalcResult.cs
  - Application/Source/Business/Business.Member/IMemberTran.cs
verification: verified
verified_by: ../../01-trialpos-docs/2_business_specs/reports/business_member_analysis.md
related:
  data:  [../40_data/06_enums_constants.md]
  devices: [../50_devices/index.md]
  domain: [../30_domain/point.md, ../30_domain/emoney.md, ../30_domain/retail_media.md]
  flows: [../70_flows/sale_end_to_end.md]
owner: jinianxiang
updated: 2026-07-14
---

# 会员域（Business.Member）

## 1. 模块定位

会员管理核心。以**大对象** `MemberObject` 为中心，承载会员问合せ / 更新、Value 卡（プリカ）入金 / 取消、以及积分计算结果容器 `PointCalcResult`。它是收银端与外部会员系统（Point Infinity 等，通信在 Device 层）之间的业务侧门面。

- 命名空间：`ForYouApplications.POS4U.Business.Member`
- 被依赖：`Business.Sales`、`Business.Payment`、`Business.EMoney`、`Business.Point`、`Business.RetailMedia` 等。
- 交易类通过实现 `IMemberTran` 接入会员能力（`Business.Point` / `Business.EMoney` 均实现之）。

## 2. 代码结构

实测 `Application/Source/Business/Business.Member/`：**10 个 `.cs`**（不含 `Properties/AssemblyInfo.cs`；含则 11）。

> ⚠️ 订正基线：`business_member_analysis.md` 正文称「12 个文件」、附录表又称「9 个文件」，**两者均误**。实测 10（不含 AssemblyInfo）。

### 2.1 核心大对象 `MemberObject`

[`MemberObject.cs:21`](Application/Source/Business/Business.Member/MemberObject.cs) `public class MemberObject`（**2174 行**，实测 `wc -l`，与基线一致；约 45 个方法，`grep` 概算）。关键方法行号（实测，纠正基线的近似值）：

| 方法 | file:line | 职责 |
|---|---|---|
| `Inquiry(...)` | `MemberObject.cs:251`（另一重载 `:338`） | 排他なし問合せ（无锁） |
| `MemberStateNoneInquiry(...)` | `MemberObject.cs:427` | 状態初期化後問合せ |
| `LockInquiry(...)` | `MemberObject.cs:442` | 排他あり問合せ（积分支付前加锁） |
| `Update(...)` | `MemberObject.cs:531` | 会员信息 / 积分更新 |
| `ValueDeposit(...)` | `MemberObject.cs:566` | Value 卡入金 |
| `ValueDepositCancel(...)` | `MemberObject.cs:653` | Value 卡入金取消 |
| `SetMemberObject(MemberRow)` | `MemberObject.cs:843` | 会员信息复元（普通） |
| `SetReSalesMemberObject(TranDataSet)` | `MemberObject.cs:972` | 部分取消用复元 |
| `PointInfinityServiceCalculate(...)` | `MemberObject.cs:1184` | 积分服务计算（经 Device 层） |

### 2.2 积分结果 `PointCalcResult` 与其它类

`PointCalcResult.cs`（193 行）、`MemberLibrary.cs`（197 行）、`ExtensionMethods/MemberObjectExtensionMethods.cs`（134 行）、`IMemberTran.cs`（25 行）、`AsyncMemberInquiry.cs`、`ECouponPointResult.cs`、`MemberParameter.cs`、`PointPaymentTarget.cs`、`PointServiceCalcResult.cs`。

> 注：`PointCalcResult` 位于模块根目录 `Business.Member/PointCalcResult.cs`（**非** `Model/` 子目录）。

## 3. 状态机

无独立 TranState。`MemberObject` 内部持有会员 / 积分服务状态（`MemberStates` / `PointServiceState`，常量定义在 `Common` / 框架侧），由问合せ结果驱动，不构成本模块的迁移图。

## 4. 业务规则（BR）

- **BR-MEMBER-001（三种問合せ模式）**：`Inquiry`（无锁，浏览 / 余额，`:251`）、`LockInquiry`（排他，积分支付前锁定，`:442`）、`MemberStateNoneInquiry`（状态初期化后，`:427`）。
- **BR-MEMBER-002（`PointCalcResult` 付与ポイント合計＝10 种之和）**：`GrantPointTotal`（[`PointCalcResult.cs:45-62`](Application/Source/Business/Business.Member/PointCalcResult.cs)）恰好求和 **10** 项：`NormalPoint`(`:131`)、`SpecificPoint`(`:136`)、`RankPoint`(`:141`)、`MediaPoint`(`:151`)、`ECouponPoint`(`:156`)、`MemberECouponPoint`(`:161`)、`RMCouponPoint`(`:166`)、`RMLoginPoint`(`:181`)、`EMoneyChargePoint`(`:186`)、`RMStamprallyPoint`(`:171`)。
  - 另有两个不计入 `GrantPointTotal` 的积分字段：`RankPointAllRank`（`decimal[10]`，全ランク補助，`:146`）与 `ReturnPoint`（返品時お買い上ポイント，`:191`）。
  - ⚠️ **订正基线**：`business_member_analysis.md` 代码块列「11 种」（把 `RankPointAllRank` 数组算作一种、且遗漏 `ReturnPoint`），其正文表又列另一组 10 种（含 `ReturnPoint`、缺 `RMStamprallyPoint` / `RankPointAllRank`），前后不一致。**精确口径**：进入付与合計的是 10 项（如上），加全ランク補助 + 返品用共 12 个积分字段。
- **BR-MEMBER-003（Value 卡入金 / 取消成对）**：`ValueDeposit`（`:566`）与 `ValueDepositCancel`（`:653`）配对；取消需原交易号，另有 `CheckFinishedValueDepositCancel` 校验取消完了。入金 / 充值上层编排见 [电子货币域](../30_domain/emoney.md)。
- **BR-MEMBER-004（会员复元两路）**：`SetMemberObject`（普通复元，`:843`）与 `SetReSalesMemberObject`（部分取消 / 返品复元，`:972`）。

## 5. 关键接口与契约

- [`IMemberTran.cs:11`](Application/Source/Business/Business.Member/IMemberTran.cs)（25 行，仅 **2** 成员）：`MemberObject MemberObject { get; }`（`:16`）与 `bool ChangeMember(Func<MemberObject,bool>)`（`:23`）。交易类经此接口读写会员对象。
- `PointCalcResult`（`[Serializable]`，`:12`）：积分计算结果 DTO，被 `Business.Point`、`Business.RetailMedia` 写入。

## 6. 数据依赖

经外部会员 / Value / Point 服务与本地缓存读写会员信息；结果落 `MemberObject`。字段字典与枚举 → 详见 [40_data/枚举与常量](../40_data/06_enums_constants.md)（不复制）。

## 7. 设备依赖

- **Point Infinity（积分中心）通信在 Device 层**：接口 [`Device.DeviceDefine/PointService/IPointInfinityService.cs`](Application/Source/Device/Device.DeviceDefine/PointService/IPointInfinityService.cs)，实现 [`Device.PointInfinityService/PointInfinityService.cs`](Application/Source/Device/Device.PointInfinityService/PointInfinityService.cs)（+ `PointInfinityServiceConnection.cs`、`Device.PointInfinityServiceSimulator`）。`MemberObject.PointInfinityServiceCalculate`（`:1184`）经插件间接调用。
- 会员卡读取（MSR）亦经 Device 层 → 详见 [50_devices](../50_devices/index.md)。

## 8. 参与的端到端流程

会员刷卡问合せ、积分付与 / 使用、返品积分复元 → 详见 [销售端到端流程](../70_flows/sale_end_to_end.md)、[返品·取消流程](../70_flows/return_void.md)（不复制）。与 [积分域](../30_domain/point.md)、[零售媒体域](../30_domain/retail_media.md) 协同。

## 9. 可信度与核查

- **verified**（最新发布 实测）：文件数 10（不含 AssemblyInfo）、`MemberObject.cs` 2174 行、上表方法行号、`PointCalcResult` 10 项付与 + 2 附加字段、`IMemberTran` 2 成员、Point Infinity 在 Device 层。
- **uncheckable**：`MemberObject` 依赖的 `POS4U.Framework` 基类、外部会员 / 积分服务协议内部实现不断言。
- 核查基线报告：`business_member_analysis.md`。本篇订正其**文件数**（非 12 / 9，实为 10）与**积分种类口径**（付与合計为 10 项）。

## 10. ST-POS 迁移提示

> ST-POS（KugelPOS）会员 / 积分为独立 service 实现，`MemberObject` 大对象不移植。对照仅供参考，详见 → ST-POS member / point 相关文档（外链，不在本体系展开）。
