---
title: POS4U 源码分析文档体系 · 架构重构方案（提案 v1）
status: 提案（未执行 · 待 owner 批准）
target_code: ../trialpos-snapshots（POS4U 真实源码，基准 最新发布）
date: 2026-07-14
author: jinianxiang
security: 🟡 敏感（含未公开供应商资料 · 仅本地/私有）
design_inputs:
  - 代码真实结构（本人实测 trialpos-snapshots）
  - 10/11/12 三处线上知识库的真实团队分类法（参考，但均为碎片、无单一真相源、无代码锚定）
  - 行业最佳实践：arc42 · C4 model · Diátaxis · ADR · docs-as-code
  - 90-verification 代码核查基线（2026-07-14）的教训
---

# POS4U 源码分析文档体系 · 架构重构方案（提案 v1）

> **这份文档是什么**：面向 `trialpos-snapshots`（POS4U 真实源码）的**全新文档体系顶层架构设计**。它不是又一份内容文档，而是"该建成什么样、按什么规则建、现有 107 篇如何归位、缺口在哪、分几步落地"的**蓝图**。**本提案不移动/改写任何现有文件**——先定架构，批准后再执行迁移。

---

## 目录

- [1. 为什么要重构（现状诊断）](#1)
- [2. 设计目标与非目标](#2)
- [3. 设计原则（体系的"宪法" · 9 条）](#3)
- [4. 组织轴的抉择（为什么这样分层）](#4)
- [5. 顶层架构（目录骨架）](#5)
- [6. 各层详解（写什么 + 受众 + 体裁 + 来源）](#6)
- [7. 关键规范（frontmatter / 命名 / 链接 / 图示）](#7)
- [8. 领域模块文档模板（30_domain 单篇标准）](#8)
- [9. 现有 107 篇 → 新体系 迁移映射](#9)
- [10. 缺口分析（代码有、文档无）](#10)
- [11. 分阶段落地计划](#11)
- [12. 维护机制（docs-as-code）](#12)
- [13. 受众 × 入口 矩阵](#13)

---

<a id="1"></a>
## 1. 为什么要重构（现状诊断）

现有 `01-trialpos-docs` 是 StackShift 自动分析（2026-04）后部分人工整理的产物。经 [90-verification 代码核查](../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md) 与本轮结构走查，暴露 **5 类结构性病灶**：

| # | 病灶 | 典型表现 |
|---|---|---|
| D1 | **多体裁沿同一轴各铺一遍、彼此不打通** | "退货"散在 6 处（`03_resales` 规格 + `4_trial_specs/return/01-05`）；"折扣"散在 5 处；`open_close` 在卷二卷四同名重复 |
| D2 | **组织轴不一致** | 卷二根=按业务场景、`reports/`=按代码模块、卷四=按专项主题——三种轴混用，无单一真相源 |
| D3 | **无代码锚定 / 版本脆弱** | 全部 `file:///.../Application/Source/...` 链接因目录版本化而断裂；无 frontmatter 关联代码基准 |
| D4 | **成熟度/可信度不分层** | 高质量规格与"定量造假的自动 dump"（行数夸大 16~38 倍）并置，读者无从辨别 |
| D5 | **范围污染** | 卷四混入 ST-POS/KugelPOS 新系统内容（904 分支），与 POS4U 现状混淆 |

> 结论：不是某一卷内部的问题，而是**顶层缺少一套"轴 + 体裁 + 锚定 + 可信度"的统一架构**。这正是本提案要解决的。

---

<a id="2"></a>
## 2. 设计目标与非目标

**目标**
1. **单一真相源**：每个事实只有一个"家"，其余处只链接、不复制。
2. **代码锚定且版本无关**：每篇文档声明代码基准、每条断言带 `file:line`，链接不因版本改名而全断。
3. **可信度可见**：每篇标注"已验证 / 待复核 / 核查不能"，与 `90-verification` 基线联动。
4. **贴合代码真实形状**：文档层级映射到代码的 8 个自然层级，而非臆造分类。
5. **多受众可导航**：BA / 重构开发 / DBA / 设备集成 / 架构师 / 新人各有清晰入口。
6. **可增量、可维护**：docs-as-code，骨架先行、缺口可持续补齐、有回归机制。

**非目标**
- ❌ 不含 ST-POS 前向设计（要件/TO-BE）——那归 ST-POS 仓（`stpos-trec-docs` / `stpos-project-docs`）；本体系只描述 **POS4U 现状（AS-IS）**。
- ❌ 不追求一次填满——本提案给"骨架 + 优先级 + 模板"，内容分阶段补。
- ❌ 不做代码修改建议——那是重构工程的事，本体系只做"高精度 AS-IS 对照"。

---

<a id="3"></a>
## 3. 设计原则（体系的"宪法" · 9 条）

> 这 9 条是所有文档必须遵守的硬约束，等价于本体系的"架构原则"。

1. **单一真相源（Single Source of Truth）**：一个主题一个权威文档；跨主题引用只用相对链接，**绝不复制正文**。（治 D1/D2）
2. **代码锚定（Code-Anchored）**：每篇 frontmatter 声明 `code_baseline` + `code_refs`；每条事实性断言给 `路径:行号`。无代码依据的内容不得写成事实。（治 D3/D4）
3. **版本无关链接（Version-Resilient）**：链接一律用 `Application/Source/...` 前缀，**约定其默认指向最新发布版本**（`trialpos-snapshots` 现为内网 GitLab 真克隆，随最新 release 分支）；不硬编码版本号，避免再次全断。（治 D3）
4. **可信度分级（Verification Status）**：每篇 frontmatter 标 `verification: verified | unverified | uncheckable`，并链接 `90-verification` 证据。（治 D4）
5. **量化诚实（Quantitative Honesty）**：所有计数/规模必须带来源（"实测 最新发布：160 表"）；估算须显式标 `估算/未实测`，绝不把推测写成实测。（治 D4，直接吸取行数造假教训）
6. **体裁分离（Diátaxis 纪律）**：参考型（reference：域/数据/设备/服务）、解释型（explanation：架构/框架/流程）、决策型（ADR：为什么）、教程型（how-to：新建模块）——**四类不混写**。（治 D1）
7. **范围隔离（Scope = POS4U AS-IS）**：只写 POS4U 现状；ST-POS 只允许出现在各篇末尾的"迁移提示"callout 里、且只做**外链**，不含设计正文。（治 D5）
8. **核查不能须显式标注**：`POS4U.Framework.dll`（无源码）、外部系统、运行时绝对路径等无法在源码内验证者，明确标 `uncheckable`，不得静默断言。（治 D4）
9. **docs-as-code**：Markdown + frontmatter + 相对链接 + mermaid；可 lint（frontmatter 必填校验、死链检查）、可回归（版本 bump 时对结构/枚举/计数类跑轻量核查）。（保障可维护）

---

<a id="4"></a>
## 4. 组织轴的抉择（为什么这样分层）

**候选轴对比：**

| 轴 | 优点 | 缺点 | 现状用它的地方 |
|---|---|---|---|
| A. 按业务场景（sales/payment/…） | 贴近功能重构、BA 友好 | 基础模块（框架/输入转换/RJ）无处安放；隐藏代码结构；一笔销售跨多模块导致重叠 | 卷二根 6 篇 |
| B. 按代码模块（Business.*/Device.*/Controller） | 与代码 1:1、读码/维护友好、天然单一真相源 | 丢失端到端流程叙事 | 卷二 `reports/` |
| C. 按架构层（架构/框架/域/数据/设备/服务/流程） | 关注点分离、可扩展、业界主流（arc42/C4） | 需额外的"流程"层补端到端叙事 | 无（现状缺） |

**决策：以 C（架构分层）为骨架，域内用 B（按模块），再用薄薄一层 A（流程）做跨模块叙事，Diátaxis 管体裁。**

这样三种"体裁"各归其位、不再三倍重复：
- 原"规格书（场景）"→ 拆成：业务规则/状态机 归入 `30_domain/<模块>`（reference）；端到端叙事 归入 `70_flows`（explanation，**只链接不复制**）。
- 原"模块分析（模块）"→ 成为 `30_domain/<模块>` 的代码结构/类/接口章节（与规格书**合并为每模块一篇**）。
- 原"专项深评（主题）"→ 折入相关 `30_domain` / `70_flows`；纯研究性的（如小计折扣缺陷调查）留作 `80_decisions` 或 `90/investigations`。

**与业界最佳实践的对应：**

| 本体系 | 借鉴 |
|---|---|
| 分层骨架 + Context/Container/Component 视图 | **C4 model** |
| 架构层的 12 类关注点（上下文/部署/运行时/横切/决策/质量/术语） | **arc42** |
| reference / explanation / how-to / decision 四体裁 | **Diátaxis** |
| `80_decisions` 代码分析 ADR | **ADR（Architecture Decision Records）** |
| frontmatter + lint + 死链 + 版本回归 | **docs-as-code** |
| `10_architecture` 的 業務/運用 视角 · `99` 生命周期 | 参考 **POSSYS（10-）** 的 業務/開発/品質/運用/保守 生命周期分类 |
| `00_portal` 新人上手路径 · `15_howto` 新建教程 | 参考 **GitLab wiki（12-）** 的 概念→架构→教程→框架五要素 上手动线 |

> 即：**骨架取 C4/arc42 的"分层 + 视图"，动线取 GitLab 的"上手路径"，运维视角取 POSSYS 的"生命周期"，体裁取 Diátaxis，决策取 ADR。** 10/11/12 提供的是"真实团队关心哪些主题"的碎片素材，本体系提供的是"把它们钉到代码、去重、分层"的骨架。

---

<a id="5"></a>
## 5. 顶层架构（目录骨架）

> 采用 `00/10/20/…/99` 十进制编号，层间留空位便于插入。★ = 单一真相源层。

```
01-trialpos-docs/
├── 00_portal/                      ← 门户与元信息（先读这里）
│   ├── README.md                     系统一句话 + 卷册地图 + 9 条原则摘要 + 路径/可信度约定
│   ├── glossary.md                   术语表（POS4U/TRI-POS/TRAN4U/MTran/TLog/NodeType/採番…）
│   ├── code-map.md                   ★ trialpos-snapshots 顶层目录 → 文档区 对照（代码地图）
│   ├── reading-paths.md              受众×入口 推荐动线（见 §13）
│   └── conventions.md                frontmatter schema + 命名 + 链接 + 图示规范（见 §7）
│
├── 10_architecture/                ← 系统架构（C4 L1/L2 + 部署 + 运行时 + 横切）【explanation】
│   ├── 01_context.md                 三级"端-边缘-云" + 外部系统（Azure/基幹/CAFIS/Point Infinity/会員）
│   ├── 02_containers.md              8 个进程/部署单元（POS4U/TRAN4U/2Op/WinPOS宿主/LogicService/IIS/Background/Cloud）
│   ├── 03_deployment.md              门店 LAN 拓扑 · IIS · SQL Server Express · 三级降级漏斗
│   ├── 04_runtime_process.md         多进程生命周期 · 启动时序 · UnhandledException
│   ├── 05_ipc.md                     WCF net.tcp(8012) POS4U↔TRAN4U · 边缘 ASP.NET Web API(HTTP)
│   ├── 06_dataflow.md                主数据下发 ⇄ TLog 上传 双向流总图
│   └── 07_crosscutting.md            横切关注点索引：採番/离线降级/事务/日志脱敏/多语言
│
├── 15_howto/                       ← 开发教程（可选层）【how-to / tutorial】
│   ├── new_business_module.md        新建 Business 模块（参考 12- wiki 教程）
│   ├── new_xaml_screen.md            新建 XAML 画面 + 绑定 Event
│   └── add_device_plugin.md          新增设备插件（Factory/Observer 挂载）
│
├── 20_framework/                   ← 应用框架层（WinPOS 引擎，贯穿全业务）【explanation】
│   ├── index.md                      框架五要素总览（38 个 WinPOS 项目地图）
│   ├── 01_event_command_observer.md  Event→Command→Observer 引擎 · EventCodes(2248行)
│   ├── 02_state_machine.md           StateWinPOS.xml 三层(TranType→State→Command) · State/TranState
│   ├── 03_ui_mapping.md              WinPOS/UI · UIMapper(View/Dialog 映射)
│   ├── 04_base_classes.md            TranBase/CommandBase/Observer 基类【⚠️ 定义在 POS4U.Framework.dll · uncheckable】
│   └── 05_conventions.md             MVC · 1 Class 1 File · StyleCop · POS4U.ruleset
│
├── 30_domain/                      ← ★ 业务域层（每个 Business.* 一篇 · 单一真相源）【reference】
│   ├── index.md                      22 模块总表 + 模块依赖图
│   ├── sales.md                      Business.Sales（销售主事务 · 28 状态机 · LineItem 族）
│   ├── payment.md                    Business.Payment（多渠道支付 · SortPaymens · 找零重试）
│   ├── resales.md                    Business.ReSales（退货/整单作废 · Void/ReSales）
│   ├── point.md                      Business.Point（积分策略链 · 离线降级）
│   ├── member.md                     Business.Member（会员 · PointCalcResult · Infinity）
│   ├── discount.md                   Business.Discount（折扣/促销/Mix&Match · 案分）
│   ├── tax.md                        Business.Tax（内外税/軽減税率/合规）
│   ├── emoney.md                     Business.EMoney（电子货币充值/充值取消）
│   ├── inputconverter.md             Business.InputConverter（条码族 · DynamicPricing 26桁）
│   ├── rj.md                         Business.RJ（Receipt/Journal 排版 · Layout 族）
│   ├── open_close.md                 Business.OpenCount + Business.CloseCount（点检/日结）
│   ├── cash_changer.md               Business.CashChanger（找零机业务侧）
│   ├── cash_in_out.md                Business.CashInOut（入出金）
│   ├── operator.md                   Business.Operator（操作员/权限）
│   ├── main_menu.md                  Business.MainMenu（主菜单/EventCode 派发）
│   ├── payment_station.md            Business.PaymentStation（会计机/精算台）
│   ├── entry_non_cash.md             Business.EntryNonCash（非现金录入）
│   ├── retail_media.md               Business.RetailMedia（零售媒体/优惠券）
│   ├── report.md                     Business.Report（报表生成）
│   ├── tran_log_maker.md             Business.TranLogMaker（TLog 生成）
│   └── business_common.md            Business.BusinessCommon（业务公共基座）
│
├── 40_data/                        ← 数据层（SQL Server · Master/Tran 双库）【reference】
│   ├── 01_overview.md                引擎(SQLEXPRESS)/双库/五元组PK/口径(160表·405SP·24视图·27UDT)
│   ├── 02_master_tables.md           主数据表字典（字段/PK/索引，按域分组）
│   ├── 03_tran_tables.md             流水表字典（TransactionLog/Management · [xml] 落盘）
│   ├── 04_views.md                   24 视图（含失效视图标注）
│   ├── 05_stored_procedures.md       405 SP 索引（按域/前缀 usp_/usp_BO_ 分组）
│   ├── 06_enums_constants.md         Common.Const 全枚举（PaymentTypes/TranTypes/NodeTypes/TranLogTypes/SettingMasterKeys…）
│   └── 07_master_sync.md             主数据同步机制（Bulk/Diff/Transfer，链接 65_background）
│
├── 50_devices/                     ← 设备层（Device 78 模块）【reference】
│   ├── index.md                      ★ 设备族 × 型号 × 状态(实装/Simulator) 总表（78 全覆盖）
│   ├── cash_changer.md               Glory RAD/RT-300/ECS7/VT280…（DirectIO/net.tcp 5min）
│   ├── payment_terminal.md           CAFIS 族（Saturn1000L/CT5100/CT6100 · SendSync/ASync）
│   ├── printer.md                    POSPrinter 族（SS900/Posiflex · ESC 能力剔除）
│   ├── scanner.md                    Scanner 族（M11/M8750/Magellan1100i/4DotNet）
│   ├── self_checkout.md              SelfCheckout（TECSS900/TECM8500）+ SecondDisplay
│   ├── member_point_devices.md       PointService/PointInfinity/ValueCard/SalaryDeduction
│   └── others.md                     RetailMedia/SelfFraudDetection/StateManagement/Keyboard/TLS12…
│
├── 60_services/                    ← 服务与集成层（三个子层）【reference】
│   ├── edge-api/                       店内边缘服务
│   │   ├── index.md                    LogicService(6项目) + POS4ULogicService(IIS宿主) 关系
│   │   ├── controllers.md              ★ 11 Controller 全 action 清单
│   │   ├── command_layer.md            LogicService.CommandSales/CommandCommon（边缘命令）
│   │   └── conventions.md              AES-256 脱敏 · AccessCode · ServiceResultBase 7字段
│   ├── background/                     后台/批处理（POS4UBackground 16项目）
│   │   ├── index.md                    Console(MasterSync/VersionUp) + WindowsService(Administrator) + Background.Business.*
│   │   ├── transfer.md                 Transfer（TLog 多通道上传 · FIFO 保序）
│   │   ├── tranlog_service.md          TranLogService
│   │   ├── headquarters_transfer.md    HeadquartersTransfer
│   │   └── schedule_queue.md           Schedule / QueueScheduler / IIS
│   └── cloud/                          云端 BO
│       ├── index.md                    POS4UBO（ASP.NET MVC5）结构（Controllers/Views/Logics/Models）
│       ├── auth_rbac.md                多租户 CompanyCode 鉴权 · RBAC · HTTP 418 超时
│       └── bo_apis.md                  BO 管理 API（后端 SP usp_BO_* 在店端 tran DB）
│
├── 70_flows/                       ← 端到端流程层（跨模块叙事 · ★只链接不复制）【explanation】
│   ├── index.md                      流程清单 + 每流程涉及的模块/表/设备
│   ├── sale_end_to_end.md            一笔销售：Sales→Discount→Tax→Payment→Point→RJ→TLog
│   ├── return_void.md                退货/作废：ReSales/Void→积分逆算→凭证→冲减
│   ├── payment_change.md             支付与找零：混合支付排序→Glory 找零→CAFIS
│   ├── point_accrual_offline.md      积分累计与离线降级
│   ├── emoney_charge.md              电子货币充值/充值取消
│   ├── hold_recall.md                跨机挂账/呼出（MTran · 13位ID）
│   ├── open_close_daily.md           开闭店点检与日结精算
│   ├── price_change.md               手动改价与小计折扣
│   └── master_sync_tlog.md           主数据下发与 TLog 上传（链接 65_background/40_data）
│
├── 80_decisions/                   ← 代码反推架构决策记录（为什么）【ADR】
│   ├── index.md                      ADR 清单
│   ├── adr-001-five-tuple-pk.md       为何用五元组联合主键（分布式防冲突）
│   ├── adr-002-wcf-for-ipc.md         为何 POS4U↔TRAN4U 用 WCF net.tcp
│   ├── adr-003-offline-degradation.md 三级降级漏斗的设计取舍
│   ├── adr-004-tlog-xml-persist.md    TLog 用 [xml] 一体化落盘
│   └── investigations/                研究性调查（含真实缺陷）
│       ├── subtotal_discount_defect.md  小计折扣分摊缺陷（DiscountMaker.cs:34 NRE 等，分析发现）
│       └── ...
│
├── 90_traceability/                ← 追溯 · 覆盖 · 可信度【reference/meta】
│   ├── matrix.md                     ★ 能力/主题 ↔ Business模块 ↔ 代码路径 ↔ 文档 ↔ 表/设备
│   ├── coverage.md                   覆盖率（22模块/78设备/405SP/11Controller 文档化进度）
│   ├── verification-status.md        各文档 verified/unverified/uncheckable（联动 ../../90-verification）
│   └── stpos-migration-hints.md      POS4U→ST-POS 差异与迁移线索（只做外链到 ST-POS 仓）
│
└── 99_archive/                     ← 封存（不作为权威）
    ├── stackshift/                   原 StackShift 自动分析产物（2026-04）
    ├── original_drafts/              原始扁平草稿 · 细粒度模块草稿
    └── migration-log.md              本次重构的迁移留档（谁→谁、去重/剥离记录）
```

---

<a id="6"></a>
## 6. 各层详解（写什么 · 受众 · 体裁 · 来源）

| 层 | 定位（写什么） | 主受众 | 体裁 | 主要来源 |
|---|---|---|---|---|
| **00_portal** | 系统速览、术语、代码地图、动线、规范 | 全体（入口） | 混合 | 新写 + 现 README/SUMMARY 重构 |
| **10_architecture** | C4 上下文/容器、部署、运行时、IPC、数据流、横切 | 架构师/新人/部署 | explanation | 现 `1_architecture/*`（SQLite 已订正）+ 补 crosscutting |
| **15_howto** | 新建模块/画面/设备插件教程 | 新人/框架开发 | how-to | 参考 12- wiki 教程 + 代码 |
| **20_framework** | WinPOS 引擎五要素、状态机、基类、开发规约 | 框架/全业务开发 | explanation | 现 reports/gitlab 碎片 + 代码（基类层标 uncheckable） |
| **30_domain ★** | 22 个 Business.* 模块的**权威单篇**（结构+状态机+BR+接口） | 重构开发/读码/BA | reference | **合并** 卷二规格书 + reports 模块分析（去重造假数字）+ 卷四相关深评 |
| **40_data** | SQL Server 双库表/视图/SP/枚举字典 | DBA/重构开发 | reference | 现 `3_technical_specs/Application/Database/*`（SQLite 已订正）+ 补真实字典 |
| **50_devices** | 78 设备族总表 + 各族驱动规格 | 设备集成 | reference | 现 `3_technical_specs/devices/*` + 补 78 全表 |
| **60_services** | 边缘 API(11 Controller) / 后台(16项目) / 云 BO | 接口/后台/云开发 | reference | 现 apis/* + 补 Controller 全 action + Background 全模块 |
| **70_flows** | 端到端场景叙事（跨模块，**只链接**） | 重构开发/BA/QA | explanation | 卷二场景框架 + 卷四主题（去重后做纯叙事） |
| **80_decisions** | 代码分析 ADR（为什么这样设计）+ 缺陷调查 | 架构师/重构决策 | ADR | 从代码/gap 反推 + 卷四调查报告（如小计折扣缺陷） |
| **90_traceability** | 映射矩阵、覆盖率、可信度、迁移线索 | 全体/PM | meta | 现 `5_traceability/*` + `../../90-verification` 联动 |
| **99_archive** | 封存历史层 | — | — | 现 `6_archive/*` + 迁移留档 |

---

<a id="7"></a>
## 7. 关键规范

### 7.1 frontmatter schema（每篇必带）

```yaml
---
title: <文档标题>
layer: 30_domain            # 所属层
module: Business.Sales      # (域/设备/服务篇) 对应代码模块，可空
audience: [重构开发, 读码]   # 主受众
genre: reference            # reference | explanation | how-to | adr | meta
code_baseline: latest
code_refs:                  # 关联代码路径（用 Application/Source/ 前缀 = 最新版约定，不写版本号）
  - Application/Source/Business/Business.Sales/SalesTran.cs
  - Application/Source/Common/Common.Const/State/SalesTranStates.cs
verification: verified      # verified | unverified | uncheckable
verified_by: ../../90-verification/reverse-docs-vs-code-audit-2026-07-14.md
related:                    # 交叉链接（单一真相源：详见对方，本篇不复制）
  flows: [70_flows/sale_end_to_end.md]
  data:  [40_data/03_tran_tables.md]
  devices: [50_devices/cash_changer.md]
owner: jinianxiang
updated: 2026-07-14
---
```

### 7.2 命名约定
- 目录：`NN_kebab`（十进制层号 + 英文 kebab）。
- 域/设备/服务篇：`<snake_case 模块名>.md`（与代码模块对应，如 `sales.md` ↔ `Business.Sales`）。
- 流程篇：`<scenario>_<qualifier>.md`（如 `sale_end_to_end.md`）。
- ADR：`adr-NNN-<slug>.md`（三位序号）。
- 一律小写 + 下划线/中划线；标题（H1）可用中日英，正文术语保留原文。

### 7.3 交叉链接规则（治重叠的核心）
- **单一真相源**：一个事实只在其"家"层详写；其它层引用只写"→ 详见 [xxx](相对路径)"，**禁止复制正文段落**。
- 例：`70_flows/sale_end_to_end.md` 描述"第 3 步算折扣"时，只写"→ 详见 [30_domain/discount.md](../30_domain/discount.md#案分)"，不重述折扣算法。
- 所有链接用**相对路径**（`docs-as-code` 可做死链检查）；代码链接用 `Application/Source/` 前缀（版本无关约定）。

### 7.4 图示规范
- 统一 **mermaid**（`flowchart`/`sequenceDiagram`/`stateDiagram-v2`/`C4Context`）。
- ⚠️ **mermaid 陷阱（已踩过）**：`subgraph` 标题、节点标签含 `()` `/` 等特殊字符必须加引号或用 `id["标题"]` 形式，否则解析失败。
- 架构层优先用 C4 图（`C4Context`/`C4Container`）；状态机用 `stateDiagram-v2`；流程用 `sequenceDiagram`。

---

<a id="8"></a>
## 8. 领域模块文档模板（`30_domain/<模块>.md` 单篇标准）

> 这是"合并规格书 + 模块分析"后的**每模块权威单篇**统一骨架。目的是让 22 个模块**长得一样、可预期、无重复**。

```markdown
# <模块中文名>（Business.<Module>）

（frontmatter 见 §7.1）

## 1. 模块定位
一句话职责 + 在系统中的角色 + 上下游依赖（← 依赖谁 / → 被谁依赖）。

## 2. 代码结构
子目录与关键类清单（Const/Logic/Model/ExtensionMethods/…），每个关键类给 `路径:行号` + 一句职责。
> 计数须标来源与可信度（"实测：Business.Sales 全 52 文件 / 约 11,318 行"）。

## 3. 状态机（如有）
TranState/State 节点（file:line）+ 迁移边（← 迁移边定义在 StateWinPOS.xml/Framework.dll，标注可核性）。
mermaid stateDiagram-v2。

## 4. 业务规则（BR · 合规）
BR-<MODULE>-NNN 列表，每条：规则描述 + `代码证据 file:line` + 合规背景（如日本零售法令）。

## 5. 关键接口与契约
对外接口（I*.cs）、消费/产出的 EventCode、与框架的挂接点。

## 6. 数据依赖
读写的表/SP → 链接 40_data（不复制字典）。

## 7. 设备依赖（如有）
→ 链接 50_devices。

## 8. 参与的端到端流程
→ 链接 70_flows（不复制流程）。

## 9. 可信度与核查
verified/unverified/uncheckable 说明；核查不能项（如基类在 Framework.dll）。

## 10. ST-POS 迁移提示（薄 · 只外链）
> 差异线索 → 链接 90_traceability/stpos-migration-hints.md 与 ST-POS 仓。
```

---

<a id="9"></a>
## 9. 现有 107 篇 → 新体系 迁移映射

| 现有 | 去向 | 动作 |
|---|---|---|
| `README.md` / `SUMMARY.md` | `00_portal/README.md`（重构）+ 各层 index | 重写为门户 + 卷册地图 + 9 原则 |
| `walkthrough.md` | `99_archive/` | 封存（历史完工报告） |
| `1_architecture/01-04` | `10_architecture/`（拆细为 01-07） | 迁移 + 补 containers/crosscutting（SQLite 已订正） |
| `2_business_specs/01-06`（规格书） | `30_domain/<模块>` 的状态机+BR 章节 + `70_flows/` 叙事 | **拆分**：规则入域、叙事入流程 |
| `2_business_specs/reports/business_*`（7 篇模块分析） | `30_domain/<模块>` 的代码结构+接口章节 | **与规格书合并为每模块一篇**，去重造假数字 |
| `3_technical_specs/Application/Database/*` | `40_data/` | 迁移 + 补真实字典（SQLite 已订正） |
| `3_technical_specs/devices/*` | `50_devices/` | 迁移 + 补 78 全表 |
| `3_technical_specs/apis/*` | `60_services/edge-api/` + `60_services/cloud/` | 拆分（店端 vs 云端）+ 补 11 Controller |
| `4_trial_specs/return/01-05` | `30_domain/resales.md` + `70_flows/return_void.md` | 折入域 + 流程，去重 |
| `4_trial_specs/mixmatch/*` `promotion/*` | `30_domain/discount.md` + `70_flows/` | 折入域 + 流程 |
| `4_trial_specs/price_change/*` | `70_flows/price_change.md` + `80_decisions/investigations/subtotal_discount_defect.md` | 叙事 + 缺陷调查独立留档 |
| `4_trial_specs/open_close/*` | `30_domain/open_close.md` + `70_flows/open_close_daily.md` | 合并（消除与卷二同名重复） |
| `4_trial_specs/receipt/*` | `30_domain/rj.md` + `50_devices/printer.md` | 折入 |
| `4_trial_specs/cancel_specified/*` | `30_domain/resales.md` + `70_flows/return_void.md` | 折入 |
| `4_trial_specs/hold_recall/*business_spec*` `*evaluation_904*` | `70_flows/hold_recall.md` + `30_domain`（MTran） | 折入（**仅 POS4U 部分**） |
| `4_trial_specs/hold_recall/consistency_report_904_spec_vs_code.md` | **移出本仓** → `stpos-trec-docs` | **剥离 ST-POS 内容**（治 D5） |
| `5_traceability/*` | `90_traceability/` | 迁移 + 扩为跨层矩阵 |
| `6_archive/*` | `99_archive/` | 平移 |

> 迁移全程记录到 `99_archive/migration-log.md`（谁→谁、去重、剥离），保证可追溯、可回滚。

---

<a id="10"></a>
## 10. 缺口分析（代码有、文档无 —— 来自 90-verification §6.2）

| 领域 | 代码现状 | 文档缺口 | 补齐去向 |
|---|---|---|---|
| 内部 WebAPI | 11 Controller | 仅 4 个被详述；`Member/ItemDetection/Report/Receipt/Cart*` 等缺 | `60_services/edge-api/controllers.md` 全 action |
| 业务逻辑链 | 22 模块 State/Command/Observer 链 | 现"★ビジネスロジック★"类页多空 | `30_domain/*` 全 22 篇 |
| 设备族 | 78 Device 模块 | 仅少数机型有描述 | `50_devices/index.md` 78 全表 + 分族篇 |
| DB 数据字典 | 160 表/405 SP/24 视图 | 仅外链、计数曾虚高/低估 | `40_data/*` 真实字典 + 正确口径 |
| 框架五要素 | WinPOS 38 项目 + Framework.dll | 三库口径/路径不一、基类层未标不可核 | `20_framework/*` 统一权威说明 |
| 后台/批处理 | POS4UBackground 16 项目 | 薄弱 | `60_services/background/*` |
| 启动/部署链路 | launcher→9 程序 | launcher 前提有误、exe 名不符 | `10_architecture/02-04` |
| 系统边界 | 门店端 ⇄ Azure/基幹 ⇄ ST-POS | 混淆 | `10_architecture/01_context.md` + 每篇 scope 标注 |
| 代码决策/缺陷 | 五元组PK/WCF/降级/小计折扣缺陷 | 无"为什么"层 | `80_decisions/*` |

---

<a id="11"></a>
## 11. 分阶段落地计划

> 骨架先行、单一真相源优先、缺口按"代码密度 × 重构价值"排序。

**阶段 0 · 骨架与宪法（1~2 天，低成本高收益）**
- 建 11 个层目录 + 各层 `index.md` 占位；写 `00_portal`（README/glossary/code-map/reading-paths/conventions）。
- 固化 §3 九原则 + §7 frontmatter schema + §8 模块模板。
- 迁移 `6_archive`→`99_archive`。产出即"可见的骨架 + 规则"。

**阶段 1 · 迁移与去重（3~5 天）**
- 按 §9 迁移现有 107 篇；**每模块合并为一篇** `30_domain/*`（规格书 ⊕ 模块分析），去重造假数字（P0-3 已订正的直接采用）。
- 剥离 ST-POS（904 consistency）到 ST-POS 仓（治 D5）。
- 应用已完成的 P0 修正（SQLite→SQL Server、Application/Source/ 约定）。
- 产出 `90_traceability/matrix.md` v1（跨层映射）。

**阶段 2 · 域层补全（1~2 周）**
- `30_domain` 补齐到全 22 模块（含此前空缺的 BusinessCommon/CashChanger/CashInOut/EntryNonCash/MainMenu/Operator/PaymentStation/Report/RetailMedia/Tax/TranLogMaker），逐篇代码核实、标 `verified`。

**阶段 3 · 数据/接口/设备字典（1~2 周）**
- `40_data` 真实表/SP/视图/枚举字典；`50_devices` 78 全表 + 分族；`60_services` 11 Controller 全 action + Background 16 项目 + 云 BO。

**阶段 4 · 流程与决策（1 周）**
- `70_flows` 端到端叙事（sale/return/payment/point/emoney/hold-recall/open-close/price-change/master-sync）；`80_decisions` 代码分析 ADR + 缺陷调查。

**阶段 5 · 维护机制（持续）**
- 见 §12。

---

<a id="12"></a>
## 12. 维护机制（docs-as-code）

1. **frontmatter lint**：CI/脚本校验必填字段（code_baseline/verification/owner/updated）。
2. **死链检查**：相对链接 + 代码路径（`Application/Source/` 前缀按最新版解析）可自动校验。
3. **版本回归**：`trialpos-snapshots` 新增版本时，对**结构/枚举/计数类**文档跑一次轻量核查（复用 `90-verification` 的 subagent 方法），检测漂移，更新 `verification-status`。
4. **可信度联动**：任何标 `verified` 的文档，其 `verified_by` 必须指向一次真实核查；核查基线以 `90-verification` 为准。
5. **owner 与评审**：每层设 owner；重构里程碑或代码大改时评审"文档 ⇄ 代码"一致性。
6. **单一真相源守卫**：评审时检查是否出现"复制而非链接"的重叠正文（治 D1 复发）。

---

<a id="13"></a>
## 13. 受众 × 入口 矩阵

| 受众 | 目标 | 推荐动线 |
|---|---|---|
| **ST-POS 重构开发（按功能）** | 照功能重建 | `00_portal` → `70_flows`（看端到端）→ `30_domain`（看模块细节）→ `90_traceability`（对照代码/差异） |
| **老代码维护/读码** | 从代码定位文档 | `00_portal/code-map` → `30_domain`/`50_devices`/`60_services`（按模块） |
| **DBA** | 表/SP/字段 | `40_data/*` |
| **设备集成** | 机型/驱动/超时 | `50_devices/index` → 分族篇 |
| **架构师** | 全局与取舍 | `10_architecture` → `80_decisions` |
| **新人 onboarding** | 快速上手 | `00_portal` → `10_architecture` → `20_framework` → `15_howto` |
| **QA/BA** | 业务规则/流程 | `70_flows` → `30_domain`（BR 章节） |
| **PM/管理** | 覆盖与进度 | `90_traceability/coverage` |

---

## 附：本提案与现状的一句话对比

| 维度 | 现状 | 本提案 |
|---|---|---|
| 组织轴 | 场景/模块/主题混用 | C4 分层骨架 + 域内按模块 + 流程薄叙事 |
| 重叠 | 同主题散 3~6 处 | 单一真相源 + 只链接不复制 |
| 代码锚定 | 链接全断、无 frontmatter | frontmatter + file:line + 版本无关约定 |
| 可信度 | 高质量与造假并置 | verified/unverified/uncheckable 分级 |
| 范围 | 混入 ST-POS | 纯 POS4U AS-IS，ST-POS 只外链 |
| 体裁 | 规格/分析/评测混写 | Diátaxis 四体裁分离 |
| 最佳实践 | 无 | arc42 + C4 + Diátaxis + ADR + docs-as-code |

> **下一步**：本提案定架构、不动文件。批准后从**阶段 0（骨架 + 门户 + 宪法）**开始执行；每阶段产出可见、可回归。
