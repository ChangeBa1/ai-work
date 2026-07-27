---
title: 其余设备族（基盤 · MSR · 客显报知 · 外部服务 · セルフ制御）
layer: 50_devices
module: Device.*（其余 35）
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Device/Device.DeviceDefine/
  - Application/Source/Device/Device.DeviceCommon/KeyCreator.cs
  - Application/Source/Device/Device.PosForNet/PosForNetDeviceBase.cs
  - Application/Source/Device/Device.SimulatorCommon/SimulatorLibrary.cs
  - Application/Source/Device/Device.TLS12ConnectLibrary/Tls12Client.cs
  - Application/Source/Device/Device.MSRTECSS900/MSRTECSS900.cs
  - Application/Source/Device/Device.MTranService/MTranServiceListener.cs
verification: verified
related:
  devices: [./index.md, ./scanner.md, ./member_point_devices.md, ./self_checkout.md]
owner: jinianxiang
updated: 2026-07-14
---

# 其余设备族（35 模块）

本文覆盖不属于前六族的全部 `Device/` 模块，分五个子群。合计 **35**（18 实装 + 12 Simulator + 5 基盤/库）。

## 1. 基盤 / 共通 / 库（6）

设备层的地基：契约、常量、基类与通信库。前两者被全族依赖。

| 模块 | 类型 | 主类 / 职责 / 证据 |
|---|---|---|
| Device.DeviceDefine | 基盤/库 | **全设备接口契约**：`IDevice` 派生的 `ICashChanger` / `IPOSPrinter` / `IMSR` / `IPackageScanner` / `IPaymentService` / `IPointService` / `IValueCard` / `ILaneLight` / `IGuidanceLED` / `ILineDisplay` … + 各 `Const/*`（`Application/Source/Device/Device.DeviceDefine/`，实装与 Simulator 共用同契约） |
| Device.DeviceCommon | 基盤/库 | 设备共通：`KeyCreator`（`KeyCreator.cs:12`「キー作成クラス」）、`OposConst`、`DeviceMessageIds`、`DeviceSettingValues`（`Const/`） |
| Device.PosForNet | 基盤/库 | POS for .NET 基类 `PosForNetDeviceBase<T> : DeviceBase`（`PosForNetDeviceBase.cs:12`），封装 `PosExplorer`（`:23`/`:110`）。全 `*4DotNet` 与部分 TEC 设备的父类 |
| Device.SimulatorCommon | 基盤/库 | 仿真器共通 `SimulatorLibrary`（`SimulatorLibrary.cs`）：反射日志、`FlashWindowEx` 窗口闪烁报警等 |
| Device.TLS12ConnectLibrary | 基盤/库 | 强制 TLS1.2 连接：`Tls12Client : DefaultTlsClient`（`Tls12Client.cs:8`）、`Tls12Authentication` / `Tls12Library` / `Tls12Response`。ValueCard 等经此走 TLS1.2 SOAP |
| Device.LogicServiceClient | 实装 | 边缘 LogicService 客户端 `LogicServiceClient : DeviceServiceBase, ILogicServiceClient`（`LogicServiceClient.cs:20`「ロジックサービスクライアント」），设备层访问边缘 API 的入口 |

## 2. MSR 磁条卡读取（6）

信用卡/会员卡/员工卡磁条读取。集成方式分 OPOS OCX、POS for .NET、TEC 专用 DLL。

| 模块 | 类型 | 主类 / 证据 |
|---|---|---|
| Device.MSRTECSS900 | 实装 | `MSRTECSS900 : DeviceBase, IMSR, IMSREx`（`MSRTECSS900.cs:18`）；经 `ICT3K5_6240DLLWrapper`（SS900/SS950 两 Wrapper） |
| Device.MSRTECSS950 | 实装 | TEC SS950 变体——**无自有 `.cs`**（仅 `Properties/AssemblyInfo.cs`），csproj `ProjectReference` 指向 `Device.MSRTECSS900`（复用其 SS950 Wrapper） |
| Device.MSRPosiflex | 实装 | `MSRPosiflex : DeviceBase, IMSR`（`MSRPosiflex.cs:15`）+ `FrmOcx`（OCX） |
| Device.MSR4DotNet | 实装 | `MSR4DotNet : PosForNetDeviceBase<Msr>, IMSR`（`MSR4DotNet.cs:15`） |
| Device.MSRSimulator | Simulator | `MSRSimulator` + `MSRSimulatorForm` |
| Device.MSRTECSS900Simulator | Simulator | `MSRTECSS900Simulator` + `Form` + `MsrSs900Controller` |

> 契约 `IMSR` / `IMSREx` / `Track` 在 `Application/Source/Device/Device.DeviceDefine/MSR/`。

## 3. 客向表示 / 报知（7）

面向顾客的显示与声光提示。

| 模块 | 类型 | 主类 / 证据 |
|---|---|---|
| Device.LineDisplay4DotNet | 实装 | `LineDisplay4DotNet : PosForNetDeviceBase<LineDisplay>, ILineDisplay`（`LineDisplay4DotNet.cs:15`）；客面行显 VFD + `LDSPDisplayBuffer` |
| Device.GuidanceLED | 实装 | `GuidanceLED : DeviceBase, IGuidanceLED`（`GuidanceLED.cs:14`）；引导 LED（提示投币/插卡位） |
| Device.LaneLight | 实装 | `LaneLight : DeviceBase, ILaneLight`（`LaneLight.cs:14`）；通道/报警灯 |
| Device.BeepSound | 实装 | `BeepSoundBase : DeviceBase, IBeepSound`（`BeepSoundBase.cs:15`）；蜂鸣 + `VoiceGuidance` 语音引导 + `WavePlayer` |
| Device.LineDisplaySimulator | Simulator | `LineDisplaySimulator` + `LineDisplayControl`（多种客显仿真） |
| Device.GuidanceLEDSimulator | Simulator | `GuidanceLEDSimulator` + `Form` |
| Device.LaneLightSimulator | Simulator | `LaneLightSimulator` + `Form` |

> 契约 `ILineDisplay` / `IGuidanceLED` / `ILaneLight` / `IBeepSound` / `IVoiceGuidance` 在 `Device.DeviceDefine/`。自助机内建的同名 `GuidanceLED`/`LaneLight` 是另一实装 → 详见 [self_checkout.md](./self_checkout.md)。

## 4. 決済 / コード系服务 · 外部連携（10）

一组 `DeviceServiceBase` 逻辑设备，经 HTTP/API 连结外部支付、优惠券、下单、人脸认证等服务；均配 WinForms Simulator。

| 模块 | 类型 | 主类 / 证据 |
|---|---|---|
| Device.IncommQRApiService | 实装 | `IncommQRApiService : DeviceServiceBase, IQRApiService`（`IncommQRApiService.cs:19`「IncommQR決済サービス」）；InComm QR 決済 |
| Device.ManjyuApiService | 实装 | `ManjyuApiService : DeviceServiceBase, IManjyuApiService`（`ManjyuApiService.cs:7`「ManjyuApiサービス」）；含 Azure 连接 |
| Device.RetailMediaService | 实装 | `RetailMediaService : DeviceServiceBase, IRetailMediaService`（`RetailMediaService.cs:13`）；优惠券/スタンプラリー/トライアルクーポン |
| Device.OrderKitchenApiService | 实装 | `OrderKitchenApiService : DeviceServiceBase, IOrderKitchenApiService`（`OrderKitchenApiService.cs:11`）；厨房下单/菜单/在庫 |
| Device.FaceMeService | 实装 | `FaceMeService : DeviceServiceBase, IFaceMeService`（`FaceMeService.cs:78`「顔認証サービスクラス」）；年龄确认人脸认证 |
| Device.IncommApiServiceSimulator | Simulator | `IncommQRApiServiceSimulator` + `Form`（目录名缺 `QR`，csproj = `Device.IncommQRApiServiceSimulator.csproj`） |
| Device.ManjyuApiServiceSimulator | Simulator | `ManjyuApiServiceSimulator` + `Form` |
| Device.RetailMediaSimulator | Simulator | `RetailMediaSimulator` + `Form` |
| Device.OrderKitchenApiServiceSimulator | Simulator | 与实装同结构 + 仿真 |
| Device.FaceMeSimulator | Simulator | `FaceMeSimulator` + `Form` |

## 5. セルフ制御 / 状态 · POS↔TRAN 中継（6）

自助流程的数据请求、不正检知、状态管理与支付站中継。

| 模块 | 类型 | 主类 / 证据 |
|---|---|---|
| Device.SelfApiConnectionService | 实装 | `SelfApiConnectionService : DeviceServiceBase, ISelfApiConnectionService`（`SelfApiConnectionService.cs:15`「ローカル版セルフAPIよりデータ請求」）；无码商品/防犯品/Manjyu 主档定时取得 |
| Device.SelfFraudDetection | 实装 | `SelfFraudDetection : DeviceServiceBase, ISelfFraudDetection`（`SelfFraudDetection.cs:15`「セルフ不正検知デバイス」）+ Listener |
| Device.StateManagementService | 实装 | `StateManagementService : DeviceServiceBase, IStateManagementService`（`StateManagementService.cs:7`「状態管理サービス」）；含年龄确认状态 `AgeConfirm*` |
| Device.MTranService | 实装 | `MTranServiceCloud : DeviceServiceBase, IMTranService`（`MTranServiceCloud.cs:14`「中間取引サービス(Cloud)」）；`MTranServiceListener` 用 **`HttpListener`**（`MTranServiceListener.cs:117`/`:171`）中継支付站状态/找零机状态；`MTranServiceWinPOS : MTranServiceCloud`（`:26`） |
| Device.SelfFraudDetectionSimulator | Simulator | `SelfFraudDetectionSimulator` + `Form` |
| Device.StateManagementSimulator | Simulator | `StateManagementSimulator` + `Form` |

> ⚠️ `MTranService` 用 **HTTP（`HttpListener`）** 中継，**非** WCF net.tcp——net.tcp 是 `POS4U`↔`TRAN4U` 的 IPC（→ 详见 [cash_changer.md §4 的 5min 超时](./cash_changer.md)），两者勿混。

## 6. 可信度与核查

- **verified**：35 模块全覆盖、各主类声明与契约接口、基类/契约库定位、MSR/客显/服务集成方式、`MTranService` 的 `HttpListener` 中継，均带 `file:line`。
- **uncheckable**：`DeviceBase` / `DeviceServiceBase` 内部（`POS4U.Framework.dll` 无源码）；InComm / Manjyu / RetailMedia / OrderKitchen / FaceMe 等外部服务端行为；OPOS/POS for .NET/TEC DLL 运行期行为。
- `Device.MSRTECSS950` 无自有 `.cs`，仅经 `ProjectReference` 复用 `Device.MSRTECSS900`。

> **ST-POS 迁移提示**（薄）：物理外设（MSR/客显/报知）归 `stpos-device-kugelpos`；决済/优惠券/下单/人脸等外部服务对接在 ST-POS 后端与上游主数据侧另有归口，不等同 POS4U 现状。
