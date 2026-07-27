---
title: 01-trialpos-docs（POS4U 源码分析文档）× 实际代码 精度核查报告
scope: pj-trial-pos / 01-trialpos-docs 5 卷册 + 备份档案箱（107 页 · 1.2M）
truth_baseline: ../trialpos-snapshots（POS4U 真实源码，基准版本 pos-store-ver202606）
date: 2026-07-14
author: jinianxiang
security: 🟡 敏感
method: 5 路并行 subagent 实代码深潜（仅以真实 .cs/.xml/.sql/.config/.csproj/.sln 为证据，file:line 锚定；不采信任何二次文档，含被审文档自身与代码库自带 docs/）
detail: ./slice-reverse-docs-detail.md
---

# 01-trialpos-docs × 实际代码 精度核查报告

> **补齐说明**：主报告 [`kb-vs-code-accuracy-audit-2026-07-14.md`](./kb-vs-code-accuracy-audit-2026-07-14.md) 覆盖 **10/11/12（三处线上知识库镜像）**；本报告补齐最后一块——**`01-trialpos-docs`（从 POS4U 真实源码源码分析直接生成的 5 卷册文档体系，107 页）**。二者构成 `90-verification` 对全库的完整代码对照。逐 file:line 证据见 [`slice-reverse-docs-detail.md`](./slice-reverse-docs-detail.md)。
>
> **⚠️ 命名消歧（2026-07-14 后）**：本报告全文所称 `01-trialpos-docs` 指**被审计的旧 StackShift 代码分析文档**（107 页，已依本报告结论于 2026-07-14 物理删除，备份见 `z-archive/trialpos-trec-docs/01-trialpos-docs.zip`）。基于本核查重构的**新权威文档体系**已改名接替 `01-trialpos-docs` 目录名——如今工作区中的 `01-trialpos-docs/` 是**新体系**，与本报告审计对象（旧文档）不是同一批文件。

---

## 执行摘要

以 **POS4U 真实源码**（`trialpos-snapshots`，基准 `pos-store-ver202606`）为**唯一真值**，对 `01-trialpos-docs` 全 5 卷册 107 页做了 5 路并行、逐 file:line 的代码对照核查。

**总体结论：`01-` 代码分析文档呈现一种与线上镜像（10/11/12）截然不同的画像——「质的分析异常优秀、量的统计系统性造假、门面结论一处颠覆性错误」。**

- **深层技术/业务分析质量出众**：多处达到**行号级、算法级、连 SQL 原文与 CSV 种子数据都逐格命中**的程度（IPC net.tcp 绑定 L126-148、`SortPaymens` 逐字一致、Mix&Match 算法与排他优先级表、退货 reason-08 行号精确……），甚至**分析发现 2 个真实 Bug**（`DiscountMaker.cs:34` NRE、`LineItemBase.LineTotal` 漏减小计折扣分摊）。这是一支有真实代码穿透力的分析工作。
- **但被三类硬伤污染**：①**门面级架构造假**——端侧 DB 引擎被判为「双 SQLite」，实为 **SQL Server（SQLEXPRESS）**；②**定量统计系统性捏造**——尤以卷二报告的行数夸大 16~38 倍、且伴随虚假的「未检出物理拉取」免责；③**全店舗端 `file:///` 链接系统性断裂**——目录版本化后 `pos-store/` 前缀全失效。

**评级（分卷）**：

| 卷册 | 定位 | 精度评级 | 一句话 |
|---|---|---|---|
| **卷一 架构** | 双进程/网络/IPC/数据流 | **C+** | IPC net.tcp 深层记述优秀（行号精确），但 SQLite/WCF 误标、链接全断、L104 指向错、数据流机制失真 |
| **卷二 核心业务**（6 篇） | 销售/支付/退货/积分/折扣/日结 | **B−** | BR 追溯质量意外地高（支付逐字一致），但 17 状态标题错、捏造属性 `IsAgeLimitProhibition`、开店流程功能归属错、路径断裂 |
| **卷二 专项报告**（7 篇） | 模块级技术分析 | **C+** | 质的记述 A 级，定量统计 D 级（行数捏造 + 免责虚假），两极分化 |
| **卷三 技术**（DB/设备/接口） | 数据字典/外设/契约 | **DB C+ ｜设备 B+ ｜接口 B+** | 五元组主键/设备/AES-256/418 teapot 全对，但 SQLite 造假全篇复发、SP 计数失准、`T_BusinessCounter` 表名错 |
| **卷四 Trial 专项**（18 篇） | 改价/MM/退货/暂挂等深评 | **B+ / A−** | 全库最高保真（算法/行号/SQL/CSV 命中 + 挖出真 Bug），扣分在路径断裂、301/302 码错、receipt 符号造假、PauseTypes 漏计 |
| **卷五 追溯** | 双向映射矩阵/gap 分析 | **C** | 追溯文档的生命线——链接（7/7 店舗端断）与数值（SP 428/状态 17/24/30/设备 87）——大面积失真，且 gap 内部自相矛盾 |
| **卷六 档案箱** | 封存历史草稿 + StackShift | **非核查重点** | StackShift 自动分析产物（2026-04-05）+ 被取代草稿；定量造假特征可溯源至此自动层 |

**必须修正的硬偏差（P0）3 类、P1 6 类**（详见 §3）。**权威性定位**：本核查印证了库 README 既定的权威顺序——**真实代码 > 90- 核查结论 > 线上镜像（10/11/12）> `01-` 代码分析文档**。`01-` 的深层内容是 ST-POS 重构的高价值参考，但**须逐条回代码复核后方可引用；其门面架构结论与全部定量统计不可直接采信**。

---

## 0. 核查前提

- **代码 = 唯一真值**。只以真实 `.cs/.xml/.sql/.config/.csproj/.sln` 为证据（file:line）；被审的 `01-` 文档自身、代码库自带 `trialpos-snapshots/docs/`（`01-` 的同源素材）均**未作为正确性依据**。
- **基准版本**：`pos-store-ver202606`（店舗端）。ver202601/202605/202606 顶层目录与 Business 模块一致，卷二核心的状态数已跨三版本复核（27/28/28）。
- **客观不可核层**：框架基类（`TranState`/`State`/`CommandWinPOSBase`/`Observer`/`EventCode`/`CheckDigitM10W31` 等）在编译好的 `pos-cloud/ExternalModule/Framework/POS4U.Framework.dll`（**无源码**）——只能核到"使用层/成员是否存在"，基类语义与状态迁移边（transition）定义（在 `POS4U/Settings/StateWinPOS*.xml` + Command 类）未逐条展开。
- **对象外**：`consistency_report_904_spec_vs_code.md` 通篇讲 **ST-POS kugelpos(Python)** 的 `904-cart-suspend-recall`，与 POS4U 无关（POS4U 全库无 904 交易码），仅指出其前提误置，不做正误判定。

---

## 1. 真值基准（代码事实，已亲自定夺）

| 事实 | 权威值（代码为准） | 证据 |
|---|---|---|
| 店舗端 DB 引擎 | **SQL Server（SQLEXPRESS）**，非 SQLite | `sqlite` 引用=**0**；`SqlClient/SqlConnection` 参照数百处；`Data/Data.Container/app.config:13-16` = `Data Source=(local)\SQLEXPRESS;Initial Catalog=POS4U_Trial_Master/Tran`；`providerName="System.Data.SqlClient"` |
| Master/Tran 双库 | 属实（**两个 SQL Server 库** `POS4U_Trial_Master`/`POS4U_Trial_Tran`，非 .db 文件） | 同上 app.config |
| Business 模块 | **22** | `pos-store-ver202606/Business/*/` |
| Device 模块 | **78** `.csproj` | `find Device -name *.csproj` |
| 内部 WebAPI Controller | **11** | `POS4ULogicService/Controllers/*Controller.cs` |
| C# 项目总数（店舗端） | **168** `.csproj` | `find pos-store-ver202606 -name *.csproj` |
| DB 表 | **160**（`dbo.*.Table.sql`） | `database/01_Tables/` |
| DB 存储过程 | **405**（`dbo.*.StoredProcedure.sql`；+10_BI ~21） | `database/04_StoredProcedures/` |
| DB 视图 | **24** | `database/03_Views/` |
| 销售状态 SalesTranStates | **28**（18 TranState + 10 State） | `Common/Common.Const/State/SalesTranStates.cs:13-149` |
| SelfStates | **39** | `SelfStates.cs` |
| 五元组联合主键 | CompanyCode/StoreCode/TerminalNo/ManagedNo/TransactionNo | `dbo.TransactionLog.Table.sql` PK CLUSTERED |
| POS4ULogicService 协议 | **ASP.NET Web API**（非 WCF） | `Global.asax.cs:31`→`WebApiConfig.Register`；Web.config 无 `system.serviceModel` |
| WCF net.tcp 用途 | **仅** POS4U↔TRAN4U 本地 IPC | `TranRemoteControllerLibrary.cs:20` `net.tcp://localhost:{0}/TranRemoteControllerService`，端口 8012 |
| `pos-store/` 目录 | **不存在**（真实为 `pos-store-ver202601/202605/202606`） | `ls: pos-store: No such file or directory` |

---

## 2. 亮点（与代码高度吻合 / 分析价值突出，可优先信任 — 但仍建议引用前回代码确认行号）

1. **IPC net.tcp 绑定行号级精确**：`TranRemoteControllerLibrary.cs:126-148`（Send/ReceiveTimeout=5 分钟、Max*=int.MaxValue、SecurityMode.None）、端口 8012（`WinPOSSettingValues.cs:27`）、接口 5 方法全中。
2. **支付排序 `SortPaymens` 逐字一致**：`PaymentObject.cs:781-791`（不可溢收→不可找零→面额降序→现金最后）。找零重试 3 次（:560）、刷卡后 `CanCancel=false`（`PaymentCAFISArchLANBase.cs:311`）。
3. **五元组联合主键 CONFIRMED**：`TransactionLog`/`TransactionManagement` PK 恰为五列；SettingMaster 四元组、ItemMaster 三元组均正确。
4. **Trial 专项算法级命中**：改价四重阀门（`LineItemBase.cs:248-270`）、Mix&Match Price/Set 算法与排序（`DiscountMixMatchLogic.cs:98/160/191/210`）、`DiscountTypeMaster.csv` 优先级/排他表**逐格命中**、退货 reason-08/单件例外行号精确、cancel `SalesLayout.cs:314/146`。
5. **分析发现 2 个真实 Bug**：`DiscountMaker.cs:34` `FirstOrDefault()` NRE、`LineItemBase.LineTotal`(:123) 漏减小计折扣分摊——分析不止描述准确，还发现真实缺陷。
6. **技术契约坐实**：AES-256 `ContentEncrypt`（`POS4ULogicServiceLibrary.cs:29-61`）、BO 超时 HTTP 418 teapot（`BOAuthenticationAttribute.cs:53-56`）、CAFIS Saturn1000L、`PrintDataLibrary.ModifyPrintDataByCapabilityESC`、Device=78/Controllers=11。

---

## 3. 偏差清单（按优先级）

### 🔴 P0 · 硬偏差（须尽快修正）

| # | 范围 | 偏差 | 代码真值 | 证据 |
|---|---|---|---|---|
| 1 | 全局（SUMMARY/README/卷一 02·04/卷三 database·devices·apis） | 端侧 DB 判为「**双 SQLite** 离线优先」；index §4 编造 SQLite WAL/PRAGMA 调优整节 | **SQL Server（SQLEXPRESS）**，Master/Tran 两个 SQL Server 库 | `sqlite`=0；`Data.Container/app.config:13-16`（SQLEXPRESS）；index §2 反而粘 SQL Server 专属 DDL（`PRIMARY KEY CLUSTERED`/`[money]`/`[xml]`），自证矛盾 |
| 2 | 全店舗端（卷一/二/三/四/五 + README） | 所有 `file:///.../trialpos-snapshots/pos-store/...` 链接断裂（追溯矩阵店舗端 7/7 断） | 目录版本化为 `pos-store-ver202606/`（`pos-store/` 不存在） | `ls` 报错；17/17 目标文件在 ver202606 下全实在（纯根前缀错） |
| | | **✅ 已按约定解决（owner 决定 2026-07-14）**：不逐处改写链接，确立约定 **`pos-store/` 默认指向最新版本 `pos-store-ver202606/`**。今后新增版本时该约定自动跟随最新版，避免再次因目录版本化而链接全断。 | — | — |
| 3 | 卷二报告（尤 sales/payment）+ 卷五/README 计数 | 定量统计系统性捏造：行数夸大 16~38 倍，且「未检出本地物理拉取」免责为虚假 | 见真值表 | `LineItemPLUBook` 实 371 行 vs 文档 14,083；`Business.Sales` 全 52 文件 11,318 行 vs 文档 ~178,000；`Business.Payment` 8,375 行 vs 文档 ~153,454；「428 SP」实 405 |

### 🟡 P1 · 事实/命名/数值错误（须回写订正）

| # | 卷 | 偏差 | 修正方向 |
|---|---|---|---|
| 4 | 卷一/二/五 | **销售状态数混乱且错**：标题/overview/matrix=17、gap§2.1=24、gap Phase1/§5=30，且 SelfStates 报 32、设备报 87 | 统一为 **SalesTranStates=28 / SelfStates=39 / Device=78 / CloseCountTranStates=28**（`*.cs` 为准） |
| 5 | 卷一/二/四/五 | **捏造符号/属性/编码**：`IsAgeLimitProhibition`（真 `AgeConfirmType`+5 种 `AgeConfirmTypes`）；receipt 符号 ☆/●/軽（真 `ﾋ/★/*`）；open_close 301/302（真 201/202）；return Sign 注释 121/125/122（真 105/816/121，且源码无此注释）；PauseTypes 5（真 9） | 按代码逐条订正 |
| 6 | 卷一/五 | **协议误标 WCF**：POS4ULogicService/边缘 Logic API 反复标 WCF | 改「ASP.NET Web API / HTTP」；WCF 仅限 POS4U↔TRAN4U IPC |
| 7 | 卷一 03/04 | **架构机制失真**：`App.xaml.cs#L104=Process.Start("TRAN4U.exe")`（实为条件启动 TwoOperatorsChecker）；MasterSync「HTTP GET+Gzip+覆盖 SQLite / 5 分钟轮询」；幂等 `TransactionToken`；`sp_InsertTLog` | 按 `Download.cs:52-57`（向边缘 POST `GetMasterDownloadFile`）、`usp_InsertTransactionLog`、无 Token 依据 逐条改写 |
| 8 | 卷三 apis | `T_BusinessCounter` 表名错 | 真实 `BusinessCounter`（表无 `T_` 前缀；`T_D_` 仅视图约定）；`usp_SaveBusinessCounter.sql:25` `MERGE INTO BusinessCounter` |
| 9 | 卷四 | `HeadquartersTransferPriceChangeLogDataFile` 售价变更审计链类名全库不存在 | 疑似虚构，人工复核旧系统是否另有实现，否则删除 |

### 🔵 P2 · 次要 / 结构性说明（信息缺失或表述不准，非致命）

| # | 现象 | 说明 |
|---|---|---|
| 10 | 系统性行号漂移（4~55 行） | 文档基于相近但非同一快照生成；引用符号存在但区间偏移 |
| 11 | 命名/归属偏差 | `CommandBase`（真 `CommandWinPOSBase`，227 类）；Mix&Match「SQL 轮询 `T_MixMatchMaster`」（真内存 `TranMasterDataSet.DiscountMixMatchMaster`）；POS4UBO「Web API 后端」（云端主体是 MVC 前端，BO 业务后端在店端 LogicService） |
| 12 | 局部小误 | index.md:60 `ItemMaster.PointRate` 字段腐化；receipt 返回类型/NoCut 张数/加赠标签/行数 4 处小误；「C# 6.0 / .NET 4.0」未验（.csproj 未逐一确认，且店舗端含 14×v4.6.1） |
| 13 | 安全债未提示 | `ContentEncrypt` 密钥源自硬编码口令+salt，文档未标注 |
| 14 | 卷六档案箱 | StackShift 自动分析产物（2026-04-05）+ 被取代草稿；卷二定量造假特征可溯源至此自动层 |

---

## 4. 改进计划（分阶段）

**阶段 0 · 硬偏差修正（本周，低成本高收益）**
- 修 §3 全部 3 项 P0：
  - ✅ **P0-1（已执行 2026-07-14）**：全局把「双 SQLite」改写为「SQL Server（SQLEXPRESS）· Master/Tran 双库」，删除 index §4 编造的 PRAGMA 整节，保留其真实 SQL Server DDL。
  - ✅ **P0-2（已按约定解决 2026-07-14）**：owner 决定**不逐处改写链接**，确立约定 **`pos-store/` 默认指向最新版本 `pos-store-ver202606/`**（新增版本自动跟随最新版）。链接前缀保持原样。
  - ✅ **P0-3（已执行 2026-07-14）**：卷二报告的捏造行数/文件数按 pos-store-ver202606 实测订正（严重夸大者），移除虚假的「未检出物理拉取」免责，各篇顶部加订正横幅。

**阶段 1 · P1 事实订正（1 周）**
- 统一状态/设备计数（28/39/78/28）；订正捏造符号与属性（`IsAgeLimitProhibition`/receipt 符号/301·302/Sign 注释/PauseTypes）；全局 WCF→Web API；改写 03/04 架构机制（App.xaml.cs L104、MasterSync、幂等、SP 名）；`T_BusinessCounter`→`BusinessCounter`；复核 `HeadquartersTransferPriceChangeLogDataFile` 存废。
- 为每份文档 frontmatter 增加 `code_baseline: pos-store-ver202606` 与 `code_refs:`，把文档锚定到代码，避免再次因目录重构而链接全断。

**阶段 2 · 质量分层与"已验证"标记（2~3 周）**
- 按本报告把 `01-` 内容分层：**已代码复核（可信引用）** / **待复核** / **对象外（ST-POS/框架 DLL）**。卷四高保真专项、卷二 BR 追溯、IPC/五元组/AES 等升级为"已验证"；全部定量统计与门面架构结论标 `unverified` 直至逐条复核。
- `consistency_report_904` 顶部显式声明"对象=ST-POS kugelpos，非 POS4U"，并从 POS4U 专项中剥离。

**阶段 3 · 与 10/11/12 打通、建单一真相源（1 月）**
- 把 `01-`（深度分析链）与 10/11/12（现行知识 + 框架指南）在框架五要素、枚举、DB 字典、内部 API 等**重叠区**做交叉索引，每个能力/主题指向"代码路径 + 唯一真相源"。`01-` 因其行号级深度，适合作为"代码级细节"层，但须以本核查为精度基线。

---

## 5. 覆盖率与局限（诚实说明）

- **深读**：5 卷册 107 页全部按卷归类；**逐 file:line 代码交叉验证的核心页约 45+ 页**（卷一 6 / 卷二 13 / 卷三 16 / 卷四 18 全覆盖 / 卷五 2），交叉核对实代码 60+ 文件。
- **量化确证**：sqlite=0 / SQLEXPRESS 连接串；SP=405 / Table=160 / View=24；SalesTranStates=28（跨 3 版本 27/28/28）/ SelfStates=39；Device=78 / Controllers=11 / csproj=168；net.tcp=8012 / 超时 5 分钟；卷二报告行数逐文件实测（LineItem/QR/payment/rj）。
- **客观不可核**：①`POS4U.Framework.dll` 无源码 → 基类语义、状态迁移边、`CheckDigitM10W31`/`RJDeviceType` 定义本体不可深挖；②BR-xxx 为文档自造编号，代码内无锚点，只能证"被引文件实在"，未逐一追踪调用链证明"该文件确实实现了该 BR"；③各 `.csproj` 的 `TargetFramework/LangVersion` 未逐一确认（"C# 6.0/.NET 4.0"未验）；④SP 内部 SQL、部分离线补录/授权分支列为 ⚠️ 未打开，未凭推测判 ✅。
- 逐 file:line 证据表见 [`slice-reverse-docs-detail.md`](./slice-reverse-docs-detail.md)。
