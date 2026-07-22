---
title: 新建 XAML 画面并绑定事件（how-to）
layer: 15_howto
module: WinPOS.UI
audience: [框架开发, POS4U 维护]
genre: how-to
code_baseline: latest
code_refs:
  - Application/Source/WinPOS/UI/WinPOS.UI.UICommon/Screen/ScreenBase.cs
  - Application/Source/WinPOS/UI/WinPOS.UI.UICommon/Const/ViewIds.cs
  - Application/Source/WinPOS/UI/WinPOS.UI.UICommon/Const/DialogIds.cs
  - Application/Source/WinPOS/UI/WinPOS.UI.UIMapper/UIMapper.cs
  - Application/Source/Common/Common.Const/TranTypes.cs
  - Application/Source/Common/Common.Const/EventCodes.cs
  - Application/Source/POS4U/Settings/MainMenuList.xml
  - Application/Source/POS4U/Settings/PluginWinPOS.xml
verification: unverified
related:
  framework: [../20_framework/03_ui_mapping.md, ../20_framework/01_event_command_observer.md, ../20_framework/index.md]
owner: jinianxiang
updated: 2026-07-14
---

# 新建 XAML 画面并绑定事件

> **目标读者**：需要在 POS4U（WPF 前台，进程 `POS4U`）里**新增一个画面（View）或对话框（Dialog）**、并让按钮把它调出来的开发者。
>
> **本教程只讲"怎么做"**。画面切换与弹窗背后的机制（TranType→View、State→Dialog、Event→Command→Observer）不在此复述，见 → [UI 映射](../20_framework/03_ui_mapping.md) 与 [Event/Command/Observer 引擎](../20_framework/01_event_command_observer.md)。
>
> ⚠️ **可信度**：本页所有**代码锚点（文件路径 / 类名 / 行号）已回 最新发布 核实**；但**操作步骤叙事**（新建工程、拷贝 xaml、加引用等 IDE 动作）为迁移自 wiki 的经验流程，**未逐步实操核实**，故整页标 `unverified`。

---

## 0. 心智模型（先读这个）

在 POS4U 里，画面**不是**业务代码 `new` 出来的，而是一条数据驱动的链路：

```
按钮(MainMenuList.xml) ──EventCode──▶ Command ──改写 POSData.CurrentTran(TranType)──▶ UIMapper ──▶ ViewId ──▶ *View(WPF)
                                                        └── 改写 State ──▶ UIMapper ──▶ DialogId ──▶ Dialog
```

所以"新建一个画面"= 建 XAML 工程 + 在 `UIMapper` 登记映射 + 让某个按钮的 `EventCode` 走到对应 `Command`。下面 5 步照此展开。

> 机制细节（两张映射字典、429 个 EventCode、Command 闸门）→ 详见 [03_ui_mapping §1](../20_framework/03_ui_mapping.md#1-uimapper两张映射字典) 与 [01_event_command_observer §2](../20_framework/01_event_command_observer.md#2-eventcode429-个事件常量)。

---

## 1. 新建 XAML 画面工程（View）

每个主画面对应一个独立的 `WinPOS.UI.*View` 工程（最新发布 实测 `WinPOS/UI/` 下有 20 个 UI 工程，见 [index §2](../20_framework/index.md#2-winpos-38-个-csproj-项目地图)）。新建时以既有 View 工程为模板（如 `WinPOS.UI.SalesView`）。

1. 新建类库工程，命名 `WinPOS.UI.<Name>View`，放在 `Application/Source/WinPOS/UI/` 下。
2. 新建 `<Name>View.xaml` + `<Name>View.xaml.cs`；如需可复用子部品，另建 `<Name>Control.xaml`（部品/共通部品的建法 → 见 wiki「4_1 创建 XAML 画面」，尚未迁移）。
3. 把从模板拷来的 `xmlns`/命名空间改成本工程名，删掉与本画面无关的代码。

**画面基类（锚点已核实）**：View 的 code-behind 继承画面基底 `ScreenBase`：

- `Application/Source/WinPOS/UI/WinPOS.UI.UICommon/Screen/ScreenBase.cs:17` — `public abstract partial class ScreenBase : UserControl, IUpdateDisplay`
- **必须重写的抽象方法**：`NotifyKeyDown(Key, ModifierKeys)`（`:53`）、`UpdateDisplay(POSData)`（`:59`）。
- 可选覆盖的虚方法：`StartView(POSData)`（`:33`，Viewの開始通知）、`NotifyDeviceEvent(...)`（`:43`）。

> `ScreenBase` 与 `POSData`/`IUpdateDisplay` 的绑定基础设施部分位于 `POS4U.Framework.dll`（无源码，`uncheckable`），见 [03_ui_mapping §2](../20_framework/03_ui_mapping.md#2-viewid--view-项目对应)。

---

## 2. 定义 ViewId（和 DialogId）

`UIMapper` 用 `ViewId`/`DialogId` 常量做映射键，不直接引用 View 工程类型。

- **ViewId**：在 `Application/Source/WinPOS/UI/WinPOS.UI.UICommon/Const/ViewIds.cs` 追加一个 `public static ViewId <Name> { get; } = new ViewId(nameof(<Name>));`。实测该文件现有 **24 个** `public static ViewId`。
- **DialogId**（若新建的是对话框而非主画面）：同理在 `Application/Source/WinPOS/UI/WinPOS.UI.UICommon/Const/DialogIds.cs` 追加（实测 34 个 `public static DialogId`）。

---

## 3. 在 UIMapper 注册映射（View 与 Dialog）

映射登记在 `Application/Source/WinPOS/UI/WinPOS.UI.UIMapper/UIMapper.cs`（`public class UIMapper : IUIMapper`，`:20`），有两张只读字典：

**（a）主画面：TranType → ViewId** —— `_tranTypeViewMap`（`:25` 起，实测 26 项）：

```csharp
// UIMapper.cs 内，追加一行：
{ TranTypes.<YourTranType>, ViewIds.<Name> },
```

- 键 `TranTypes.*` 来自 `Application/Source/Common/Common.Const/TranTypes.cs`（新交易种类需先在此定义）。
- 注意映射**可多对一**：实测 `TranTypes.Return`（`:39`）、`TranTypes.ReSales`（`:47`）都映射到 `ViewIds.Sales`——返品/打ち直し复用收银主画面，不另建 View。

**（b）弹窗：State → DialogId** —— `_stateDialogMap`（`:57` 起）：

```csharp
{ <YourTranStates>.<WaitingState>, DialogIds.<Name> },
```

- 实测大量 `Waiting*Confirm` 状态映射到通用 `DialogIds.MessageDialog`；只有特殊交互才映射专用弹窗。

> 两张字典的完整结构与语义 → 详见 [03_ui_mapping §1](../20_framework/03_ui_mapping.md#1-uimapper两张映射字典)，本页不复制。

---

## 4. 绑定按钮 EventCode，并接上 Command

画面要被"调出来"，需要一个按钮把 `EventCode` 投递进引擎，再由对应 `Command` 改写 `POSData` 的 TranType/State，`UIMapper` 随之切换画面。

### 4.1 EventCode（事件常量）

`Application/Source/Common/Common.Const/EventCodes.cs`（`public static class EventCodes`，`:8`）集中定义所有事件，实测 **429 个** `new EventCode(...)`。每个 EventCode 携带一个名字和整数码，例如：

- `Sales_Total`（取引確定）= 码 `32`（`EventCodes.cs:38`）
- `Sales_ChangePrice`（売価変更）= 码 `10`（`:21`）

新事件在此追加：`public static EventCode <Name> { get; } = new EventCode(nameof(<Name>), <码>);`

> ⚠️ **路径订正**：wiki 教程把此文件写成 `Business/Common/Common.Const/EventCodes.cs`，实际**无 `Business/` 前缀**，正确为 `Common/Common.Const/EventCodes.cs`。同理 State 定义在 `Common/Common.Const/State/`（非 `Business/Commom/...`）。

### 4.2 主菜单按钮 → EventCode

主菜单按钮配置在 `Application/Source/POS4U/Settings/MainMenuList.xml`。每个 `<MenuButton>` 用 `<EventCode>` 字段声明按下时投递的整数事件码，例如实测：

```xml
<MenuButton>
  <Description>チャージ機モード</Description>
  <ButtonType>1</ButtonType>
  <EventCode>114</EventCode>          <!-- MainMenuList.xml -->
  <AddInfos>Opened</AddInfos>         <!-- 该按钮生效的状态(如 Opened) -->
</MenuButton>
```

追加一个按钮时，把 `<EventCode>` 设为 4.1 里新事件对应的码；`<AddInfos>` 声明按钮在哪个状态下可见/可用。

> 画面内（非主菜单）的按钮，则在该 View 的 `*Control.xaml` / `*Control.xaml.cs` 里发出 EventCode（wiki「3_10 添加按钮，画面跳转实例」示例在 `WinPOS/UI/WinPOS.UI.EMoneyView/Control/SelectChargeAmountControl.xaml`）。

### 4.3 EventCode → Command 的落地

Command 插件在 `Application/Source/POS4U/Settings/PluginWinPOS.xml` 的 `<Group Id="Command">`（`:300` 起）里逐个注册，`Id` 即 Command 类名、`Class` 为其全限定类型，例如：

```xml
<Group Id="Command">
  <Plugin Id="Common_Total"
    Assembly="WinPOS.CommandCommon, ..."
    Class="ForYouApplications.POS4U.WinPOS.CommandCommon.Common_Total"/>
  <!-- 新 Command 在此追加一行 -->
</Group>
```

引擎的核心插件（`EventManager`、`StateEventConverter`、`UIMapper` 自身）同样在该 XML 注册（`UIMapper` 插件见 `PluginWinPOS.xml:41`）。

> ⚠️ **拼写订正**：wiki 把此文件写成 `PluginWinPPOS.xml`（多一个 `P`），正确为 **`PluginWinPOS.xml`**。
>
> EventCode 如何被路由到具体 Command、Command 基类的闸门与执行 → 详见 [01_event_command_observer §3](../20_framework/01_event_command_observer.md#3-command-基类绑定闸门执行)，本页不复制。

---

## 5. 让新工程被加载 + 启动生效

1. **加引用**：把新 `WinPOS.UI.<Name>View` 工程加进 `POS4U` 前台工程的引用，Command 所在工程同理。
2. **确认注册**：`UIMapper.cs` 的映射（步骤 3）、`PluginWinPOS.xml` 的 Command（步骤 4.3）、`MainMenuList.xml` 的按钮（步骤 4.2）三处齐备。
3. **启动**：POS4U 启动时投递第一个 Event 进入主菜单（机制见 [01 §4 启动即投递第一个 Event](../20_framework/01_event_command_observer.md#4-启动即投递第一个-event)）；按下新按钮 → EventCode → Command 改写 TranType → `UIMapper._tranTypeViewMap` 命中 → 新 View 显示。

> 副屏（CustomerDisplay）会随主 View 同步切换，见 [03_ui_mapping §4 画面切换时序](../20_framework/03_ui_mapping.md#4-画面切换时序示意)。

---

## 6. 对话框（Dialog）的差异

新建的是**弹窗**而非主画面时，与上文的差别：

- 继承基类同为 `ScreenBase`（或其对话框派生），但登记走 **DialogId + `_stateDialogMap`（State→Dialog）**，不是 TranType→View。
- 触发方式通常是 **Command 改写 State**，`UIMapper` 按新 State 命中 `_stateDialogMap` 弹出，而非按钮直呼。
- 消息型弹窗多复用 `DialogIds.MessageDialog`，其内容由 `WinPOS.UI.UIMapper` 内的 `MessageDialogInfoCreator` / `MessageDialogLibrary` 构建（见 [03_ui_mapping §3](../20_framework/03_ui_mapping.md#3-uimapper-项目的其它映射器)）。

---

## 7. 检查清单

| 步骤 | 落点（已核实路径） |
|---|---|
| 建 View 工程、继承 `ScreenBase` | `Application/Source/WinPOS/UI/WinPOS.UI.<Name>View/`；基类 `.../WinPOS.UI.UICommon/Screen/ScreenBase.cs`（重写 `NotifyKeyDown`/`UpdateDisplay`） |
| 定义 ViewId / DialogId | `.../WinPOS.UI.UICommon/Const/ViewIds.cs` / `DialogIds.cs` |
| 定义 TranType | `Application/Source/Common/Common.Const/TranTypes.cs` |
| 登记映射 | `Application/Source/WinPOS/UI/WinPOS.UI.UIMapper/UIMapper.cs`（`_tranTypeViewMap` / `_stateDialogMap`） |
| 定义 EventCode | `Application/Source/Common/Common.Const/EventCodes.cs` |
| 按钮绑 EventCode | `Application/Source/POS4U/Settings/MainMenuList.xml`（`<MenuButton><EventCode>`） |
| 注册 Command | `Application/Source/POS4U/Settings/PluginWinPOS.xml`（`<Group Id="Command">`） |

---

## 8. 可信度与核查

- **verified（锚点）**：全部文件路径、类名（`ScreenBase`/`UIMapper`/`ViewIds`/`DialogIds`/`EventCodes`/`TranTypes`）、计数（EventCode 429、ViewId 24、DialogId 34、`_tranTypeViewMap` 26 项）、示例行号均回 最新发布 核实。
- **unverified（叙事）**：IDE 层面的建工程/拷贝/加引用等操作步骤沿用 wiki 经验流程，未逐步实操验证。
- **对 wiki 的路径订正**：① `EventCodes.cs` 无 `Business/` 前缀；② `PluginWinPOS.xml`（非 `PluginWinPPOS.xml`）；③ EMoney 画面工程实为 `WinPOS.UI.EMoneyView`（非 `WinPos.UI.EMoneyCharge`）；④ State 定义在 `Common/Common.Const/State/`。
- **uncheckable**：`IUIMapper` 契约本体、`POS4U.Framework.dll` 内的画面基础设施。
</content>
</invoke>
