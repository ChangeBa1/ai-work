---
title: ADR-002（代码反推）WCF net.tcp 仅用于本机进程间通信
layer: 80_decisions
genre: adr
audience: [架构师, 重构开发]
code_baseline: latest
code_refs:
  - Application/Source/WinPOS/Batch/WinPOS.Batch/TranRemoteControllerLibrary.cs
  - Application/Source/POS4ULogicService/Global.asax.cs
verification: verified
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
related:
  arch: [../10_architecture/]
owner: jinianxiang
updated: 2026-07-14
---

# ADR-002（代码反推）WCF net.tcp 仅用于本机进程间通信

## 背景

店端一台机器上有多个进程：`POS4U`（WPF 前台收银）、`TRAN4U`（WinForms 守护/外设与流水宿主）、`POS4UTwoOperatorsCH`（双人副屏）。前台需要驱动守护进程持有的外设与流水控制器——这是**同机跨进程**通信。另有店内**边缘服务** `POS4ULogicService`（IIS 宿主）供跨机调用。两种通信被有意用**不同技术**实现。

## 决策

- **本机进程间（POS4U ↔ TRAN4U）** = **WCF `net.tcp`**，`localhost`，`SecurityMode.None`。
- **边缘服务 API（跨机）** = **ASP.NET Web API（HTTP）**，非 WCF。

## 证据（file:line）

- IPC = WCF net.tcp：`WinPOS/Batch/WinPOS.Batch/TranRemoteControllerLibrary.cs`
  - `:20` `net.tcp://localhost:{0}/TranRemoteControllerService`
  - `:132` `ReceiveTimeout = new TimeSpan(0, 5, 0)`（5 分钟）
  - `:145` `netTcpBinding.Security.Mode = SecurityMode.None`
  - 端口 **8012**（`WinPOSSettingValues.cs:27`）
- 边缘 API = Web API：`POS4ULogicService/Global.asax.cs:31` `GlobalConfiguration.Configure(WebApiConfig.Register)`；`Web.config` 无 `system.serviceModel` 段。

## 取舍

- **本机 IPC 选 net.tcp**：同机二进制 TCP 吞吐/延迟优于 HTTP，`SecurityMode.None` 省握手（信任本机边界），5 分钟超时容忍外设长操作（如找零机出钞）。绑定到 `localhost` → 不对外暴露。
- **跨机 API 选 Web API/HTTP**：跨终端调用要经得起网络与多客户端，HTTP 生态（路由/内容协商/IIS 宿主）更合适。
- **反例订正**：`01-` 旧报告反复把边缘/Logic API 也标成 WCF——错。WCF 在本系统**只**出现在 POS4U↔TRAN4U 本机 IPC（[90-verification P1 #6](../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md)）。

## 现状 / 对新系统含义

- 两条通信技术边界清晰，`verified`。
- ST-POS 的进程/服务拓扑与 IPC 取舍差异 → [migration-hints](../90_traceability/stpos-migration-hints.md)（只外链）。
