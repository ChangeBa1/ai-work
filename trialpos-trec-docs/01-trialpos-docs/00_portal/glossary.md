---
title: 术语表
layer: 00_portal
genre: meta
audience: [全体]
code_baseline: latest
verification: verified
owner: jinianxiang
updated: 2026-07-14
---

# 术语表

| 术语 | 含义 |
|---|---|
| **POS4U** | 現行 TRIAL 自社 POS（本体系描述对象）。别称 TRI-POS / 現行POS / 自社POS |
| **ST-POS** | 新規・完全内製 POS，置换 POS4U 的目标系统（本工作区其它子仓库即其实装） |
| **TRAN4U** | 店舗端常驻守护进程（WinForms），托管外设驱动与流水；与 POS4U 经 WCF net.tcp(8012) 通信 |
| **POS4UTwoOperatorsCH** | 二人制（双人操作）副屏进程 |
| **WinPOS** | POS4U 前端应用框架层（38 项目，Event→Command→Observer→State 引擎） |
| **LogicService / POS4ULogicService** | 店内**边缘**服务：前者=业务逻辑/命令层(6 项目)，后者=IIS 宿主 + 11 个 Web API Controller |
| **POS4UBackground** | 后台/批处理（MasterSync/VersionUp 控制台 + Administrator 服务 + Background.Business.* 后台业务） |
| **POS4UBO** | 云端 Backoffice（ASP.NET MVC5 管理前端） |
| **MTran / MTransaction** | 跨机台挂账/暂挂交易（Hold/Recall），13 位 ID 含 M10W31 校验位 |
| **TLog / TransactionLog** | 交易流水日志，`[xml]` 一体化落盘，经 Transfer 异步上传 |
| **採番 / Sequence** | 分布式防冲突的序列号采番；配合五元组联合主键 |
| **五元组联合主键** | CompanyCode/StoreCode/TerminalNo/ManagedNo/TransactionNo |
| **NodeType** | 终端节点类型枚举（登録機/会計機/セルフ/二人制/チャージ機 等） |
| **CAFIS** | 信用卡结算网络；店端经 Device.CAFISArch* 对接（Saturn1000L/CT5100/CT6100） |
| **Glory 找零機** | 自动现金找零机（RAD/RT-300/ECS7 等），经 net.tcp DirectIO 驱动 |
| **Point Infinity** | 外部会员积分平台，经 Device.PointInfinityService 通信 |
| **Mix&Match / MM** | 组合搭售促销（`DiscountMixMatch*`） |
| **DynamicPricing** | 26 桁动态定价条码（消费期限/见切等） |
| **POSSYS** | Confluence Cloud 上的 POS System 空间（`10-` 镜像来源） |
| **AIPOS** | 内网 GitLab 上的 POS 开发项目（`12-` 镜像来源） |
