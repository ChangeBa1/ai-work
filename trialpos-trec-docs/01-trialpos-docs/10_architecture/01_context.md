---
title: C4 上下文 · 端-边缘-云三级与外部系统
layer: 10_architecture
audience: [架构师, 重构开发, 新人]
genre: explanation
code_baseline: latest
code_refs:
  - Application/Source/Common/Common.Const/NodeTypes.cs
  - Application/Source/Device/Device.PointInfinityService/PointInfinityService.cs
  - Application/Source/POS4ULogicService/Controllers/MemberServiceController.cs
  - Application/Source/Azure/Azure.Logic/AzureStorageInitializer.cs
verification: verified
verified_by: ../90_traceability/verification-status.md
related:
  arch: [./02_containers.md, ./06_dataflow.md, ./07_crosscutting.md]
owner: jinianxiang
updated: 2026-07-14
---

# C4 上下文：端-边缘-云三级与外部系统

> POS4U 是 TRIAL 自社 POS 的**门店收银系统**，采用 **端（Terminal）- 边缘（Store LAN）- 云（Cloud/HQ）** 三级部署，对接 CAFIS、Point Infinity、会員、Azure、基幹（HQ）等外部系统。本篇是最高层的"谁和谁交互"。

## 1. 系统上下文图

```mermaid
C4Context
    title POS4U 系统上下文

    Person(cashier, "収銀员 / 店員", "登録機・会計機・二人制")
    Person(customer, "顾客", "自助収銀 / 会員")

    System_Boundary(store, "门店 (Store)") {
        System(pos4u, "POS4U", "端-边缘 收银系统 (WPF+守护进程+边缘 Web API+后台)")
    }

    System_Ext(cafis, "CAFIS", "信用卡结算网络 (串口/LAN)")
    System_Ext(pointinf, "Point Infinity", "会员积分平台")
    System_Ext(member, "会員系统", "会员信息 (经 Point Infinity)")
    System_Ext(glory, "Glory 找零機", "自动现金找零 (OPOS)")
    System_Ext(azure, "Azure Storage", "TLog/EJournal/小票 云存储")
    System_Ext(hq, "基幹 / HQ (POS4UBO)", "主数据源 + 变价 + 财务审计")

    Rel(cashier, pos4u, "收银操作")
    Rel(customer, pos4u, "自助结算 / 出示会员码")
    Rel(pos4u, cafis, "信用/借记授权", "串口/net.tcp")
    Rel(pos4u, pointinf, "积分加减 / 会员照会", "HTTP")
    Rel(pos4u, glory, "现金收付", "net.tcp DirectIO / OPOS")
    Rel(pos4u, azure, "流水/小票上传", "Blob/Queue/Table")
    Rel(hq, pos4u, "主数据下发 (ZIP over HTTP)")
    Rel(pos4u, hq, "TLog/集計 上传")
```

## 2. 三级层次

| 级 | 是什么 | 关键构成 | 详见 |
|---|---|---|---|
| **端 Terminal** | 收银机本体 | `POS4U.exe`(WPF) + `TRAN4U.exe`(守护) + `POS4UTwoOperatorsCH.exe`(副屏) + 本地 SQL Server Express 双库 | [02_containers](./02_containers.md) · [04_runtime](./04_runtime_process.md) |
| **边缘 Store LAN** | 门店内服务器 | `POS4ULogicService`（IIS · ASP.NET Web API · 11 Controller）+ 边缘 DB（MTran 共享/採番） | [05_ipc](./05_ipc.md) · [60_services/edge](../60_services/edge-api/index.md) |
| **云 Cloud/HQ** | 总部 | `POS4UBO`（ASP.NET MVC5 后台）+ 中央 SQL Server + Azure Storage + 基幹主数据源 | [06_dataflow](./06_dataflow.md) · [60_services/cloud](../60_services/cloud/index.md) |

终端角色由 `NodeType` 区分——`Application/Source/Common/Common.Const/NodeTypes.cs` 定义 **17** 种：`GoCashRegister`(登録機) · `GoSelf`/`GoFullSelf`/`LaneSelf`(自助) · `CashPaymentStation`/`GoSemiSelfPaymentStation`(会計機) · `TwoOperatorsPOS`(二人制) · `EMoneyChargeStation`(充值机) · `OTCDrugPOS`(医薬品) · `OrderKitchen` · `Mobile` · `LocalPOS` 等。

## 3. 外部系统对接点（店端可核）

| 外部系统 | 店端对接类（可核 file:line） | 备注 |
|---|---|---|
| **CAFIS** | 串口 `Device.CAFISArch/CAFISArchJTC31.cs:19`、LAN `Device.CAFISArchLAN/Device/CAFISArchSaturn1000L.cs:10`；支付方 `Business.Payment/Payment/PaymentCreditLAN.cs` | CAFIS 主机内部 = uncheckable |
| **Point Infinity** | `Device.PointInfinityService/PointInfinityService.cs:15` `: DeviceServiceBase, IPointInfinityService` | 平台内部 = uncheckable |
| **会員** | `POS4ULogicService/Controllers/MemberServiceController.cs:21` → `LogicService.ApiLogic/Member/GetMemberInfoLogic.cs:18`（经 Point Infinity） | 无独立 MemberService 客户端类 |
| **Glory 找零機** | `Device.CashChangerGloryRADRT300/CashChanger.cs:25`、`…RT200/CashChanger.cs:24`（OPOS COM 互操作） | OPOS CCO/固件 = uncheckable |
| **Azure Storage** | `Azure.Logic/AzureStorageInitializer.cs:15`（Blob 容器 + Table）；`Accessor/StorageBlobAccessor.cs:9`/`StorageQueueAccessor.cs:16` | Azure SDK 内部 = uncheckable |
| **基幹 / HQ** | 主数据经 `POS4UBackground/.../MasterSync` 转换下发；集計经 `HeadquartersTransfer.cs` 上传 | HQ 侧 = uncheckable |

## 4. 可信度与核查

- **verified**：三级构成、17 NodeType、各外部系统**店端对接类** file:line 均已核实。
- **uncheckable**：所有外部系统的**内部行为**（CAFIS/Point Infinity/会員/Azure/HQ）；上下文图中的协议标注为对接侧观察，非外部系统契约。

## 5. ST-POS 迁移提示

> ST-POS 重构须保留这些**外部集成边界**（CAFIS/Point Infinity/会員/Azure）；三级拓扑向云原生演进的对照 → [90_traceability](../90_traceability/matrix.md)。仅外链。
