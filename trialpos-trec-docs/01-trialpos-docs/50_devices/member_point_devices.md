---
title: 会员 / 积分 / 预付卡 / 工资扣款设备族
layer: 50_devices
module: Device.PointService / Device.ValueCard / Device.CRM / ...
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Device/Device.DeviceDefine/PointService/IPointService.cs
  - Application/Source/Device/Device.DeviceDefine/ValueCard/IValueCard.cs
  - Application/Source/Device/Device.PointService/PointService.cs
  - Application/Source/Device/Device.PointInfinityService/PointInfinityService.cs
  - Application/Source/Device/Device.ValueCard/ValueCard.cs
  - Application/Source/Device/Device.SalaryDeductionService/SalaryDeductionService.cs
  - Application/Source/Device/Device.CRM/CRM.cs
verification: verified
related:
  devices: [./index.md, ./printer.md, ./others.md]
owner: jinianxiang
updated: 2026-07-14
---

# 会员 / 积分 / 预付卡 / 工资扣款设备族

## 1. 定位与成员（9 模块）

本族是一组**逻辑「设备」**——不驱动物理外设，而是经 HTTP / SOAP 连结会员中心、积分中心、预付卡中心、给与天引き系统等外部服务。全部继承框架的 `DeviceServiceBase`（无源码·`POS4U.Framework.dll`），实现各自契约接口。

| 模块 | 类型 | 主类 / 证据 | 连结 |
|---|---|---|---|
| Device.PointService | 实装 | `PointService : DeviceServiceBase, IPointService`（`PointService.cs:21`「ポイントサービス」） | CRM 积分（SOAP `CRMWebServers`，`:9`） |
| Device.PointInfinityService | 实装 | `PointInfinityService : DeviceServiceBase, IPointInfinityService`（`PointInfinityService.cs:15`） | PointInfinity 积分中心 |
| Device.ValueCard | 实装 | `ValueCard : DeviceServiceBase, IValueCard`（`ValueCard.cs:21`「バリューカードクラス」） | 预付卡中心（TLS1.2 SOAP） |
| Device.SalaryDeductionService | 实装 | `SalaryDeductionService : DeviceServiceBase, ISalaryDeductionService`（`SalaryDeductionService.cs:15`「給料天引き用通信デバイス」） | 给与天引き系统 |
| Device.CRM | 实装 | `CRM : DeviceServiceBase, ICRM`（`CRM.cs:22`「CRMサービス」） | CRM 会员中心 |
| Device.PointServiceSimulator | Simulator | `PointServiceSimulator` + `Form` + `PointServiceTester` | — |
| Device.PointInfinityServiceSimulator | Simulator | `PointInfinityServiceSimulator` + `Form` + `Tester` | — |
| Device.ValueCardSimulator | Simulator | `ValueCardSimulator` + `Form` + `ValueCardTester` | — |
| Device.SalaryDeductionSimulator | Simulator | `SalaryDeductionSimulator` + `Form` | — |

## 2. 积分：PointService 与 CRM 连携

`PointService` 经 SOAP Web 引用 `CRMWebServers`（`PointService.cs:9` `using CRMWebServers`；代理 `Proxy/CRMWebServers.cs`）与 CRM 会员中心交互，提供积分照会/计算/更新（`Param/PointInquiryRequest` / `PointCalculateRequest` / `PointUpdateRequest`，结果 `Result/PointCalculateResult` 等）。报文用 `PointCRMFormat*` / `PointFormat*` 编解码。`Device.CRM`（`CRMServiceConnection.cs`）承担 CRM 侧订单回写（`CRMSaveOrderCallback*`，契约见 `Application/Source/Device/Device.DeviceDefine/CRM/`）。

`PointInfinityService` 是另一套积分中心（PointInfinity）的对接实装，接口 `IPointInfinityService` 与 `IPointService` 并列（`Application/Source/Device/Device.DeviceDefine/PointService/`）。

> 积分小票版面（今回取得/取引前/取引后残高、离线降级文案）→ 详见 [打印机族 §3](./printer.md)。

## 3. 预付卡：ValueCard 走 TLS1.2 SOAP

`ValueCard` 用 `Tls12SoapPost`（`ValueCard.cs:41`）强制 TLS1.2 与预付卡中心通信：`ExecTls12ConnectionWithTimeout(url, timeout, mode, …)`（`ValueCard.cs:506`），照会/充值/支付按 `ValueCardDealTypes`（`GetBalance` 等）分流；`DealServiceWithPoint`（`ValueCard.cs:414`）支持积分连动。底层 TLS1.2 库 → 详见 [others.md · 基盤/共通/库 §1](./others.md)。

## 4. 给与天引き（工资扣款）

`SalaryDeductionService`（「給料天引き用通信デバイス」）用于员工消费从工资扣款：`GetEmployeeCard*` / `GetEmployeeInfo*` 取员工卡/信息，`SavePayInfoParameter` 保存扣款明细（`Application/Source/Device/Device.SalaryDeductionService/`）。

## 5. 可信度与核查

- **verified**：9 模块、主类声明与契约接口、CRM SOAP 连携、ValueCard TLS1.2 调用点、给与天引き请求类，均带 `file:line`。
- **uncheckable**：`DeviceServiceBase` 内部（`POS4U.Framework.dll` 无源码）；CRM / PointInfinity / 预付卡中心 / 给与天引き系统等外部服务的服务端行为与协议内部。

> **ST-POS 迁移提示**（薄）：积分/会员/预付在 ST-POS 后端另有归口（point vendor、e-money 等课题）；本族属 POS4U 设备层逻辑对接，不等同 ST-POS 现状。
