# trialpos-trec-docs 学习笔记

> 学习对象：`D:/ai-work/ai-work/trialpos-trec-docs`
> **学习目标（两条主线）**：
> 1. 搞懂**现行 POS 体系**（POS4U / TRI-POS）——架构、业务思想
> 2. 搞懂**文档驱动编程**在这个体系中的应用——怎么用文档驱动理解、怎么用文档驱动开发
> 整理日：2026-07-20

---

## 0. 仓库定位

`trialpos-trec-docs` 不是源码，是描述 **POS4U（现行 TRIAL 自社 POS，别名 TRI-POS）**门店收银系统的文档知识库。TRIAL 正在做 **ST-POS**（新一代完全自研 POS）替换它，这个库是"吃透现行系统"的知识底座。

四个子目录，权威性递减，**只学 `01-trialpos-docs/` 就够了**：

| 目录 | 内容 | 定位 |
|---|---|---|
| `01-trialpos-docs/` ⭐ | 93 篇代码锚定文档，C4/arc42 分层重整 | **权威、当前、单一真相源** |
| `10-confluence-cloud/` | 461 页 Confluence 镜像 | 原始素材，不用逐页啃 |
| `11-confluence-trec/` | 147 页自建 Confluence 镜像 | 原始素材 |
| `12-gitlab-wiki/` | 157 页 GitLab Wiki 镜像 | 原始素材 |

`00-project/` 是另一条线索：项目管理/协作规范，其中 `management/` 下藏着 SDD（spec-kit）流水线的记录——这是主线 2 的关键材料，见下文 Part B。

---

# Part A · 搞懂现行 POS 体系（POS4U）

## A1. 三级架构

```
端 Terminal（收银机）        边缘 Store LAN（门店服务器）      云 Cloud/HQ
POS4U.exe (WPF前台)    ──HTTP──>  POS4ULogicService (IIS)  ──同步──>  POS4UBO (MVC5)
  ↕ WCF net.tcp:8012              POS4UBackground(批处理)             + 基幹主数据
TRAN4U.exe (外设守护)
+ 本地 SQL Server Express 双库
```

关键事实：
- 前台是 **WPF**，外设/流水由独立守护进程 **TRAN4U** 托管，两者通过 **WCF net.tcp（端口 8012）**通信——真正的进程间 IPC，不是进程内直调。
- 端侧数据库是 **SQL Server Express（双库：Master/Tran）**，不是 SQLite（早期文档误写过，已订正）。
- 终端角色靠 `NodeType` 枚举区分 17 种（登録機/自助/会計機/二人制/充值机…），同一套代码承载多种终端形态。
- 8 个部署单元：POS4U.exe（前台）/ TRAN4U.exe（外设守护）/ POS4UTwoOperatorsCH.exe（二人制副屏）/ POS4ULogicService（边缘 API，11 Controller）/ POS4UBackground（后台批处理，16 项目）/ POS4UBO（云端后台，ASP.NET MVC5）等。

对应文档：`10_architecture/01_context.md`（三级+外部系统）、`02_containers.md`（8 个部署单元）、`05_ipc.md`（WCF 细节）。

## A2. 业务引擎：Event → Command → Observer 闭环

前台核心机制，是理解"业务规则改动落到代码哪里"的关键：

- UI/设备操作 → 抽象成 `EventCode`（429 个常量，如 `Sales_Total`）
- `EventManager` 路由到对应 `Command` 执行业务、改写全局状态 `POSData`
- `Observer` 监听状态变化去驱动外设/画面，必要时再投递新 Event，形成闭环

调度核心（`EventManager`/`CommandController`）本身**没有源码**（闭源 `WinPOS.Framework.dll`），文档明确标成 `uncheckable`，只核实"使用层"——这本身也是文档诚实度的示例，见 Part B。

业务含义：**收银的每一步操作都被建模成状态机的状态迁移**，一笔"通常売上"要经过 扫码→小计→折扣计算→税额计算→结算→落盘→打印 这条状态链。任何业务规则改动本质上是"在某个状态节点插入/修改一个 Command"。

对应文档：`20_framework/01_event_command_observer.md`、`02_state_machine.md`；串起来看全流程：`70_flows/sale_end_to_end.md`。

## A3. 业务思想

| 设计取向 | 说明 | 依据 |
|---|---|---|
| **合规优先于效率** | 年龄限制商品（烟酒等）强制进入 `WaitingAgeConfirm` 确认状态；业务规则用 `BR-<MODULE>-NNN` 编号追踪，要求给出合规依据 | `30_domain/sales.md` |
| **离线降级是一等公民** | 会员积分累计"联机优先、离线降级"，门店网络不稳定是常态，业务逻辑必须能在断网时继续跑 | `adr-003-offline-degradation.md` |
| **交易一致性靠五元组主键** | `CompanyCode/StoreCode/TerminalNo/ManagedNo/TransactionNo` 联合主键，解决多终端并发写入不冲突 | `adr-001-five-tuple-pk.md` |
| **TLog 是核心数据契约** | 交易确定后整笔交易序列化成 XML 一次性落盘，再异步上传总部——"端侧优先本地可靠落盘，云端最终一致" | `adr-004-tlog-xml-persist.md` |

## A4. 学习路径（主线 1）

1. 门户：`00_portal/README.md` → `glossary.md`（术语表）
2. 架构：`10_architecture/01_context.md` → `02_containers.md` → `05_ipc.md` → `06_dataflow.md`
3. 框架：`20_framework/01_event_command_observer.md` → `02_state_machine.md`
4. 挑几个业务域精读：`30_domain/sales.md`、`discount.md`、`payment.md`、`point.md`
5. 串成全景：`70_flows/sale_end_to_end.md`
6. 补设计动机：`80_decisions/adr-001~004`

按角色的动线（如果你的视角更具体）：

| 受众 | 推荐动线 |
|---|---|
| 老代码维护/读码 | `code-map.md` → `30_domain`/`50_devices`/`60_services` |
| DBA | `40_data/01_overview.md` |
| 架构师 | `10_architecture` → `80_decisions` |
| QA/BA | `70_flows` → `30_domain`（BR 章节） |

---

# Part B · 文档驱动编程在这个体系中的应用

这个体系里"文档驱动"分**两层**，性质完全不同，必须先分清楚：

| | 第一层：AS-IS 知识库（`01-trialpos-docs`） | 第二层：SDD 开发流水线（`trialpos-snapshots` 仓 `sdd/main` 分支） |
|---|---|---|
| 驱动什么 | **理解**现有系统 | **修改**现有系统（写代码） |
| 本质 | docs-as-code 逆向工程文档 | spec-kit（Spec-Driven Development）实际开发工作流 |
| 产出 | Markdown 说明文档 | 真实代码变更（PR） |
| 关键材料 | `01-trialpos-docs/00_portal/*` | `00-project/management/speckit-upgrade/`、`branch-triage/sdd-suite-comparison-2026-07-19.md` |

第一层是"用文档去镜像代码"；第二层才是**真正意义上的"文档驱动编程"**——先写 spec/plan/tasks，再让人/Agent 照着写代码。两层不是孤立的，B4 会讲它们怎么咬合。

## B1. 第一层：AS-IS 文档体系的方法论

依据：`01-trialpos-docs/00_portal/architecture-redesign-proposal.md`（这套文档系统自己的"设计文档"）。

**起点：5 类结构性病灶诊断**（旧版 StackShift 自动分析产物的问题）

| # | 病灶 | 典型表现 |
|---|---|---|
| D1 | 多体裁沿同一轴各铺一遍、彼此不打通 | "退货"散在 6 处，"折扣"散在 5 处 |
| D2 | 组织轴不一致 | 一会按业务场景、一会按代码模块、一会按专项主题混用 |
| D3 | 无代码锚定 / 版本脆弱 | 链接因目录版本化而全断 |
| D4 | 成熟度/可信度不分层 | 高质量规格与"定量造假的自动 dump"（行数夸大 16~38 倍）并置 |
| D5 | 范围污染 | 混入 ST-POS/KugelPOS 新系统内容，与 POS4U 现状混淆 |

**对策：9 条宪法**（`conventions.md`）——把"文档"当"代码"治理：

1. **单一真相源**：一个事实只有一个家，别处只能链接，不能复制正文
2. **代码锚定**：每条断言必须有 `file:line`，frontmatter 声明 `code_baseline`/`code_refs`
3. **版本无关链接**：用 `Application/Source/...` 约定指向最新版，不写死版本号
4. **可信度分级**：`verified/unverified/uncheckable` 三态，查不清楚的（如闭源 `POS4U.Framework.dll`）必须显式标 `uncheckable`
5. **量化诚实**：数字必须有来源，不能拍脑袋
6. **体裁分离（Diátaxis）**：reference/explanation/how-to/adr/meta 各司其职，不混写
7. **范围 = POS4U AS-IS**：只写现状，ST-POS 只允许出现在末尾"迁移提示"且只外链
8. **核查不能须显式标注**：无法验证的部分不静默断言
9. **docs-as-code**：Markdown + frontmatter + 相对链接 + mermaid，可 lint、可回归

**组织轴的抉择**（三选一）：

| 轴 | 优点 | 缺点 |
|---|---|---|
| A. 按业务场景 | 贴近功能重构、BA 友好 | 基础模块无处安放，跨模块导致重叠 |
| B. 按代码模块 | 与代码 1:1，读码/维护友好 | 丢失端到端流程叙事 |
| C. 按架构层（C4/arc42） | 关注点分离、业界主流 | 需额外"流程"层补叙事 |

**决策：以 C 为骨架，域内用 B，再用薄薄一层 A 做跨模块叙事，Diátaxis 管体裁。**

**维护机制**：frontmatter lint（必填字段校验）→ 死链检查 → 版本回归（新版本发布时对结构/枚举/计数类文档跑轻量核查）→ 可信度联动（`verified` 必须有 `verified_by` 指向真实核查）→ owner 评审 → 单一真相源守卫。

这套东西的价值不是"写得好看"，是**让文档具备可验证性和可维护性**——`90-verification` 报告揪出过真实问题（如早期文档误写"端侧双 SQLite"），9 条宪法就是吸取那次教训后定下的护栏。

## B2. 第二层：spec-kit / SDD 开发流水线

这是真正的"文档驱动编程"，藏在 `00-project/management/` 里，讲的是 `trialpos-snapshots`（POS4U 真实源码仓）`sdd/main` 分支实际跑的开发流程，用 GitHub 的 **spec-kit** 框架（Spec-Driven Development）。本地装置目前 **v0.13.0**（2026-07-19 从 0.8.2 升级完，见 `speckit-upgrade/`）。

> 注：`trialpos-snapshots` 仓库本体不在本工作区，以下依据 `branch-triage/sdd-suite-comparison-2026-07-19.md` 整理。

**装置构成**：

1. **宪章（Constitution）v2.0.0**——日语写的"第一原理 F1~F5 + 8 条原则"，硬约束如"禁止改 .NET 版本""`Framework.dll` 内部标 uncheckable""离线降级行为必须保全"。`plan`/`analyze` 阶段做门禁校验。
2. **知识层 `.claude/knowledge/`**——16 篇：架构原则、ADR 0001~0004、领域知识、测试战略、遗留系统行为规律。
3. **基础技能链（10 本，日语 fork）**：
   `specify → clarify → plan → tasks → analyze → implement → checklist → constitution → converge`
   - **specify**：写 `spec.md`（做什么、为什么，不涉及怎么做）
   - **clarify**：消歧，把模糊点问清楚
   - **plan**：写 `plan.md`（技术方案），做宪章校验（Constitution Check）
   - **tasks**：拆成 `tasks.md`，checkbox 逐条勾选执行
   - **analyze**：跑合规分析，**CRITICAL=0 才能进入下一步**（硬门禁）
   - **implement**：照 tasks 写代码
   - **converge**（v0.13 新增）：对照 spec/plan/tasks 盘一遍代码现状，把残留工作追记回 tasks——拉回"文档"和"代码"的漂移
4. **治理技能（本地独有，7 本）**：`context-preload`（强制把宪章/原则/ADR/领域知识注入上下文）、`test-spec`/`test-results`（NUnit characterization 测试先行、Windows 上跑完回填结果）、`approve-spec`/`approve-adr`（人工审批）、`feedback`。
5. **人手门（5 道）**：spec 生命周期 `Draft → レビュー待ち → 承認済み`，加上 test-spec 评审、test-results 评审、approve-adr、analyze 的 CRITICAL=0 门禁——不是写完就自动合并。
6. **可追溯性**：Conventional Commits + `[spec:NNN-名]` 标签，1 任务 1 提交，`SPECKIT_BASELINE.md` 记录 fork 台账。

## B3. 两层如何咬合：一个完整闭环案例

`70_flows/sale_end_to_end.md`（第一层 AS-IS 文档）记录的真实缺陷——"手动小计折扣会导致 `DiscountMaker.cs:34` 空引用崩溃"——对应的 SDD 案例正是：

- `001-fix-discount-maker-nre`
- `002-fix-linetotal-subtotal-divided`（修另一个相关的金额算错问题）

完整链条：

```
AS-IS 分析文档挖出 Bug（第一层：文档驱动理解）
  → 立项为 SDD 案例（spec.md）
  → plan/tasks 拆解
  → characterization 测试锁定现有行为（test-spec）
  → implement 修复
  → Windows 验证回填（test-results）
  → 宪章合规校验（analyze CRITICAL=0）
  → 人工审批（approve-spec / approve-adr）
  → 合并（第二层：文档驱动开发）
```

**第一层文档负责"发现问题、建立对现状的可信理解"，第二层 SDD 负责"用文档做门禁、把修改过程本身也变成可审计的文档"。**

## B4. 做得好 vs 做得糙：与内网上游团队的对照

内网上游团队（中川氏）也在用 spec-kit，但版本落后（0.7.2 vs 本地 0.13.0）、**无宪章**（plan 里自认"Constitution Gates 不适用"）、无治理层、无知识层、spec 长期停在 Draft。

| 维度 | 上游 | 本地 |
|---|---|---|
| 基座版本 | 0.7.2.dev0（落后约 6 个 minor） | v0.13.0（工具链最新） |
| 宪章 | ❌ 未填充的原始模板 | ✅ v2.0.0 已批准 |
| 知识层 | ❌ 无 | ✅ 16 文件 |
| 测试纪律 | ❌ 无独立测试产物 | ✅ characterization + Windows 验证门 |
| 人手门 | ❌ spec 长期 Draft | ✅ 5 道人工关卡 |
| 实战里程 | ✅ 3 个月高频迭代，已随实装跑通全链 | 里程尚浅，但基座最新 |

一句话总结（原文）：上游是"**工具链原味 + 实战驱动**"（无治理层，但产物随代码高频迭代、已在真实案件全程落地）；本地是"**治理增强 + 流程完备**"（宪章/知识层/人手门/测试门齐备，但实战里程还浅）。

**结论**：文档驱动编程做得好不好，不取决于有没有用 spec-kit 这类工具，而取决于有没有**宪章、门禁、测试纪律、知识层**这些让流程"可复制、可移交"的东西——否则就退化成"个人素养驱动，换个人就没有门禁兜底"。

## B5. 学习路径（主线 2）

1. 精读 `01-trialpos-docs/00_portal/architecture-redesign-proposal.md` + `conventions.md` 原文（第一层方法论全貌，尤其 §3 九原则/§4 组织轴取舍/§12 维护机制）
2. 精读 `80_decisions/investigations/subtotal_discount_defect.md`（那个真实 Bug 的调查报告，第一层的产出样本）
3. 精读 `00-project/management/branch-triage/sdd-suite-comparison-2026-07-19.md` 全文（第二层讲得最透的一篇）
4. 精读 `00-project/management/speckit-upgrade/upgrade-runbook.md`（spec-kit 基座升级的可复用流程，能看到装置具体怎么落地维护）
5. 如果能拿到 `trialpos-snapshots` 仓库本体，去看 `specs/001-fix-discount-maker-nre/` 下的 `spec.md`/`plan.md`/`tasks.md`/`test-spec.md`/`test-results.md` 全套产物，把"文档挖出 Bug → SDD 修复"这条线走完整，是最有体感的学习方式

---

## 附：关键文件速查表

| 主题 | 文件路径（相对 `trialpos-trec-docs/`） | 属于哪条主线 |
|---|---|---|
| 门户/术语 | `01-trialpos-docs/00_portal/README.md`、`glossary.md` | A |
| 系统上下文 | `01-trialpos-docs/10_architecture/01_context.md` | A |
| 8 个部署单元 | `01-trialpos-docs/10_architecture/02_containers.md` | A |
| Event-Command-Observer 引擎 | `01-trialpos-docs/20_framework/01_event_command_observer.md` | A |
| 销售端到端流程 + 已知 Bug | `01-trialpos-docs/70_flows/sale_end_to_end.md` | A + B（闭环起点） |
| 五元组主键 ADR | `01-trialpos-docs/80_decisions/adr-001-five-tuple-pk.md` | A |
| WCF IPC ADR | `01-trialpos-docs/80_decisions/adr-002-wcf-for-ipc.md` | A |
| 离线降级 ADR | `01-trialpos-docs/80_decisions/adr-003-offline-degradation.md` | A |
| TLog XML 落盘 ADR | `01-trialpos-docs/80_decisions/adr-004-tlog-xml-persist.md` | A |
| 缺陷调查（小计折扣） | `01-trialpos-docs/80_decisions/investigations/subtotal_discount_defect.md` | A + B |
| 文档体系方法论（宪法） | `01-trialpos-docs/00_portal/conventions.md` | B（第一层） |
| 文档体系设计提案 | `01-trialpos-docs/00_portal/architecture-redesign-proposal.md` | B（第一层） |
| 代码核查报告 | `90-verification/reverse-docs-vs-code-audit-2026-07-14.md` | B（第一层） |
| SDD 装置对比 | `00-project/management/branch-triage/sdd-suite-comparison-2026-07-19.md` | B（第二层） |
| spec-kit 升级记录 | `00-project/management/speckit-upgrade/` | B（第二层） |
