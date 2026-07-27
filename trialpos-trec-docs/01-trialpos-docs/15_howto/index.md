---
title: 开发教程（how-to）· 索引
layer: 15_howto
genre: how-to
audience: [新人, 框架开发, POS4U 维护]
code_baseline: latest
verification: unverified
owner: jinianxiang
updated: 2026-07-14
---

# 开发教程（how-to）

> **定位**：面向"在 POS4U（现行）框架内**新建/扩展**功能"的操作型教程。**优先级说明**：本体系的核心用途是为 **ST-POS 重构**提供 AS-IS 对照，而非维护 POS4U，故本层排在后位。三篇核心教程已从 `12-gitlab-wiki`（AIPOS wiki）**迁移并回代码核实**后落地（2026-07-14）。

> **可信度口径**：教程为 how-to 体裁，整篇标 `verification: unverified`——但**引用的每个类名/命名空间/路径/EventCode/XML 结构均已回 最新发布 逐条核实（锚点 verified）**；仅 Visual Studio 建工程/复制文件等 IDE 操作叙事为 unverified，框架 DLL 内符号标 uncheckable。迁移时已订正 12- wiki 的系统性过时（常量前缀 `Bussiness/`→顶层 `Common/`、`Commom`/`ObServer`/`CreatePlugun`/`PluginWinPPOS` 等拼写、`Event.cs`→`EventCodes.cs`、`Plugin.xml` 实际在 `POS4ULogicService/Settings/`）。

## 已完成的教程

| 文件 | 内容 | 可信度 |
|---|---|---|
| [`new_business_module.md`](./new_business_module.md) | 新建一个 `Business.*` 模块：建工程 → TranType → Tran(`CommonTranBase`) → State → EventCode → Command → Observer → 两个 XML 注册（8 步端到端） | 锚点 verified · 操作叙事 unverified |
| [`new_xaml_screen.md`](./new_xaml_screen.md) | 新建 XAML 画面/对话框并绑定 EventCode → Command（含 UIMapper 登记、按钮绑定、启动加载） | 锚点 verified · 操作叙事 unverified |
| [`add_device_plugin.md`](./add_device_plugin.md) | 新增设备插件：Device 工程（实装 + Simulator 对偶）→ 实现接口 → `Plugin*.xml` 注册 → `DeviceObserver`/Factory 挂载 → TRAN4U 宿主加载 | 锚点 verified · 操作叙事 unverified |

## 相关

- 框架机制：[20_framework](../20_framework/index.md)（Event→Command→Observer 引擎、状态机、UIMapper、基类）
- 设备族：[50_devices](../50_devices/index.md)
- 上手动线：[reading-paths](../00_portal/reading-paths.md)
