---
title: 扫描 / 键盘族（Scanner + Keyboard）
layer: 50_devices
module: Device.Scanner* / Device.*Keyboard*
audience: [重构开发, 读码]
genre: reference
code_baseline: latest
code_refs:
  - Application/Source/Device/Device.DeviceDefine/Scanner/IPackageScanner.cs
  - Application/Source/Device/Device.ScannerM8750/ScannerM8750.cs
  - Application/Source/Device/Device.Scanner4DotNet/Scanner4DotNet.cs
  - Application/Source/Device/Device.ScannerMagellan1100i/ScannerMagellan1100i.cs
  - Application/Source/Device/Device.KeyboardScanner/FujitsuKeyboardScanner.cs
  - Application/Source/Device/Device.PosKeyboardTECM8000/PosKeyboardTECM8000.cs
verification: verified
related:
  devices: [./index.md, ./self_checkout.md]
owner: jinianxiang
updated: 2026-07-14
---

# 扫描 / 键盘族（Scanner + Keyboard）

## 1. 定位与成员（7 模块）

商品条码/会员码录入。有三条集成路线：**POS for .NET**（`Microsoft.PointOfService.Scanner` 事件）、**OPOS OCX**（`FrmOcx` ActiveX）、**键盘楔入式**（HID 键入拦截）。

| 模块 | 类型 | 主类 / 证据 | 链路 |
|---|---|---|---|
| Device.ScannerM8750 | 实装 | `ScannerM8750 : PosForNetDeviceBase<Scanner>`（`ScannerM8750.cs:15`）；`TECScannerQT100 : ScannerM8750`（`TECScannerQT100.cs:13`）；`TECPackageScanner : ScannerM8750, IPackageScanner`（`TECPackageScanner.cs:19`） | POS for .NET |
| Device.Scanner4DotNet | 实装 | `Scanner4DotNet : PosForNetDeviceBase<Scanner>`（`Scanner4DotNet.cs:15`）；含 `TECScannerIS910` / `TECScannerQT100` | POS for .NET |
| Device.ScannerMagellan1100i | 实装 | `ScannerMagellan1100i : DeviceBase`（`ScannerMagellan1100i.cs:16`）+ `FrmOcx` | OPOS OCX |
| Device.ScannerM11 | 实装 | `ScannerM11 : DeviceBase`（`ScannerM11.cs:17`「スキャナー制御クラス」）+ `FrmOcx` | OPOS OCX |
| Device.KeyboardScanner | 实装 | `FujitsuKeyboardScanner : DeviceBase, IKeyboardDevice`（`FujitsuKeyboardScanner.cs:17`）；变体 `KeyboardScanner`（`:11`）/`DensoKeyboardScanner`（`:11`）/`M9000KeyboardScanner`（`:12`）均继承之 | 键盘楔入(HID) |
| Device.PosKeyboardTECM8000 | 实装 | `PosKeyboardTECM8000 : PosForNetDeviceBase<PosKeyboard>`（`PosKeyboardTECM8000.cs:14`） | POS for .NET |
| Device.ScannerSimulator | Simulator | `ScannerSimulator : DeviceBase, IDisposable`（`ScannerSimulator.cs:11`）+ `TECPackageScannerSimulator` | — |

## 2. 集成方式差异

- **POS for .NET 系**（`ScannerM8750` / `Scanner4DotNet` / `PosKeyboardTECM8000`）：经 `PosForNetDeviceBase<T>`（`Application/Source/Device/Device.PosForNet/PosForNetDeviceBase.cs:12`）用 `PosExplorer` 枚举逻辑设备并订阅 `DataEvent`（如 `Scanner4DotNet.cs:257` 读 `ScanData`）。
- **OPOS OCX 系**（`ScannerMagellan1100i` / `ScannerM11`）：`DeviceBase` 直接持有 `FrmOcx`（内嵌 ActiveX 控件）。
- **键盘楔入系**（`KeyboardScanner`）：`FujitsuKeyboardScanner` 拦截键盘输入，按 `DeviceSettingValues.KeyboardScannerStartKey`/`EndKey`（`FujitsuKeyboardScanner.cs:360/372`）识别一段扫入串；Denso/M9000 为厂商变体。

> 契约：仅 **`IPackageScanner`**（自助结算篮内扫描，`Application/Source/Device/Device.DeviceDefine/Scanner/IPackageScanner.cs`）与 `ITECIS890LCDScannerMode` 抽象；普通扫描枪不经 `IScanner` 契约，直接以 POS for .NET / OCX 事件暴露扫入数据（未发现 `interface IScanner`）。`TECPackageScanner` 供自助机整篮扫描 → 详见 [自助结算族](./self_checkout.md)。

## 3. 可信度与核查

- **verified**：模块清单、主类声明与继承链、三条集成路线的类型证据、键盘楔入起止键设定引用点、`IPackageScanner` 契约存在性，均带 `file:line`。
- **uncheckable**：`DeviceBase` 内部（`POS4U.Framework.dll`）；OPOS OCX 与 POS for .NET 运行期事件行为；厂商扫描枪固件。

> **ST-POS 迁移提示**（薄）：扫描/键盘归 `stpos-device-kugelpos` 设备网关。
