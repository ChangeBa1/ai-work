# Implementation Plan: 通用动作身份、目标一致性与坐标空间安全

**Branch**: `003-action-identity-grounding` | **Date**: 2026-07-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-action-identity-grounding/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition
describes the execution workflow. 本次是**重新基线**，不是对 2026-07-21 版本 plan.md
的增量补丁。触发原因：2026-07-22 spec.md 已按 Constitution v1.1.0 Principle VI
（业务无关核心与声明式场景隔离）重新基线，随后的 `/speckit-clarify`（3 项决议）与
`/speckit-checklist` → `checklists/domain-independence.md`（14 项检查、11 项未通过）
证实旧版本 plan.md/research.md/data-model.md/contracts/*.md 仍然围绕单一 POS 购物袋
场景设计，其中两处（`contracts/action-identity-contract.md` 的 `action_id_match`
跳过一致性检查、`data-model.md` 的 `action_type` 不同即无条件 `dangerous_drift`）与
spec.md 修正后的安全问题 A/B **直接矛盾**。本次规划的架构前提直接取自用户对本次
`/speckit-plan` 调用给出的 10 条要求，逐条落实见下方 Constitution Check 与 Project
Structure。

## Summary

本 feature 是通用的、业务无关的框架能力：①测试步骤范围内的稳定动作身份，用于
非幂等动作重复执行防护，但该身份匹配 MUST NOT 被当作新目标安全的证明（安全问题
A）；②新目标与步骤已声明 intent 的一致性验证，驱动由声明目的、声明风险级别、
一致性检查结果三者 AND 组合决定的危险目标漂移分类，而非由 `action_type` 变化
单独判定（安全问题 B）；③Grounder 显式 `coordinate_space` 声明与一次性坐标
转换，缺失/矛盾/未知/越界时 fail-safe 拒绝；④声明式运行前置条件（复用既有
`VerificationSpec`/`VerificationEngine`）、声明式动作 tag 审计（`ActionMatcher`/
`ActionTagRule`）、通用恢复策略预算与人工确认门禁、通用 JSON/HTML 审计证据。
本次规划相对 2026-07-21 版本的核心变化：**删除**全部围绕 POS 购物袋场景硬编码的
业务字段与关键词表（`HumanStartStateConfirmation.confirmed_cart_items`、
`ObservedStartState.cart_items`、`ReportingConfig.category_keywords` 固定四分类、
`execution/target_consistency.py` 的 `_RESULT_DISPLAY_KEYWORDS`/
`_DISMISSAL_KEYWORDS`、`extract_cart_state()`、`--confirmed-cart-items` 等 CLI
参数），**替换**为业务无关的声明式机制（`DeclaredFact`/`RunPrecondition`/
`ActionTagRule`/`SemanticAction.micro_action_purpose`+`risk_level`）；**修复**
`contracts/action-identity-contract.md`/`data-model.md` 中与 spec.md 安全问题 A/B
直接矛盾的两处设计；**新增**三个业务无关的离线契约测试场景（表单提交、图标菜单、
弹窗/滚动微动作），POS 场景保留为第四个附加回归 fixture；坐标空间协议
（`coordinate_space`/`resolve_pixel_bbox()`）与 `RecoveryPolicy` 六字段契约因
本身已经业务无关，**原样保留**，仅做编辑性修订。全部实现遵循测试先行，新增测试
均离线运行，真实/在线环境验收单独列为人工批准环节。

## Technical Context

**Language/Version**: Python 3.12+（与 001/002/旧 003 完全一致，无变化）

**Primary Dependencies**: 复用 001/002 已引入的全部依赖（vncdotool、
opencv-python + numpy、RapidOCR、httpx、Pydantic v2、PyYAML + pydantic-settings、
SQLAlchemy 2.x + aiosqlite、structlog、Typer、pytest）；**本 feature 不引入任何
新的第三方依赖**——`has_target_evidence_conflict()`、重写后的
`evaluate_target_consistency()`、声明式前置条件/tag 机制均为纯 Python/Pydantic
逻辑，且大量复用既有的 `VerificationSpec`/`VerificationEngine`，比旧版本设计
更少新增代码而非更多。

**Storage**: 沿用 001/002 的单个 SQLite 数据库文件 + 本地制品目录；
`ActionIteration` 表继续使用可空的 `canonical_identity_json` 列（不变）；
`TestRun` 的 `precondition_evaluation`/`human_confirmed_facts` 字段随现有的
运行记录序列化一并落库，不新增数据表（与旧版本"不新增独立表"的既有原则一致，
只是字段内容从业务专用改为通用）。

**Testing**: pytest，沿用 001/002 建立的分层测试；本 feature 新增的全部测试属于
"基于固定截图/固定响应的离线测试"（`tests/fixtures/`）与"端到端场景测试"
（`tests/e2e/`）两类，**不新增真实/在线环境集成测试**。**测试先行**：`tasks.md`
中每个实现任务前必须先有一个失败测试。新增测试集合的关键变化：三个新的通用
场景测试文件（`test_scenario_form_submit.py`、`test_scenario_icon_menu.py`、
`test_scenario_popup_scroll.py`）作为每项通用能力的**主要**验证证据，既有的
`test_scenario_15_pos_bag_business_acceptance.py`（POS）降级为**第四个附加**
回归 fixture（FR-040 要求至少两个互不相关场景，不再以 POS 单场景作为唯一证据）。

**Target Platform**: 与 001/002/旧 003 完全一致——无独立显卡的普通办公电脑运行
控制端 Agent 进程；被测端为固定分辨率/DPI 的桌面环境，本 feature 的坐标空间
测试覆盖非正方形分辨率（示例数值沿用 1024×1568，仅作几何测试参数，不代表任何
业务绑定）。

**Project Type**: 单一项目（single project），延续 001/002/旧 003 的 `vnc_agent`
包结构。

**Performance Goals**: `has_target_evidence_conflict()`、重写后的
`evaluate_target_consistency()`、声明式前置条件/tag 匹配 MUST 是纯本地结构化
字段比较（角色相等性、IoU 数值、枚举比较、`VerificationSpec` 既有评估器），
不新增网络调用；对单次 `RESOLVING_ACTION` 阶段耗时的增量预期在毫秒级，不影响
既有 `Performance Goals`。

**Constraints**: 沿用 001/002/旧 003 的全部资源约束；新增约束——目标一致性/
危险漂移判断 MUST NOT 依赖任何硬编码关键词列表（改为读取 Planner 声明的
`micro_action_purpose`/`risk_level` 结构化字段，research.md §4/§7）；声明式
前置条件与动作 tag 的具体业务内容 MUST 仅来自测试用例/场景 profile，核心
`config.py`/`domain/` 模块 MUST 默认空集合/无固定分类；坐标空间换算 MUST 在
Grounder 边界内的单一调用点完成（不变）；恢复策略六字段 MUST 全部显式配置
（不变）。

**Scale/Scope**: 覆盖 spec.md 的全部 8 个用户故事（P1 的 3 个对应安全问题 A/B
与坐标空间协议 + P2 的 4 个配套声明式能力 + P3 的多场景离线验证）；改动范围
限定在下方 Project Structure 列出的文件，不触碰 001/002 中
`runtime/state_machine.py`、`drivers/`、`perception/action_effect.py`
（ActionEffect 判定本身不变）的既有结构。`planning/action_classification.py`
中已知的业务关键词泄漏（`_DEFAULT_NON_IDEMPOTENT_KEYWORDS` 含
`"レジ袋"`/`"購入"`/`"支払い"`）**明确排除在本 feature 范围之外**——spec.md
Assumptions 已声明"非幂等动作分类沿用既有机制，不在本 feature 中重新定义"，
该项作为已知技术债记录在 research.md §0，交由独立 feature 处理。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution 条款 | 本功能的落实方式 | 结论 |
|---|---|---|
| I. 确定性运行时控制模型 | `has_target_evidence_conflict()`/`evaluate_target_consistency()`/`resolve_pixel_bbox()`/前置条件评估/tag 匹配均为代码状态机内的确定性函数，不引入模型自主决策 | PASS |
| II. Planner/Grounder/Executor/Verifier 分离 | 身份匹配/目标一致性判断归属 Executor（延续既有 `RepeatGuard` 职责归属）；坐标空间换算归属 Grounder 边界；Planner 新增声明 `micro_action_purpose`/`risk_level`，仍是"提出语义动作"这一既有职责的扩展，不越界到判定环节；Planner 与 Verifier 职责/接口不变 | PASS |
| III. 键盘优先，视觉点击兜底 | 本 feature MUST NOT 重排既有候选优先级；不改动本条 | PASS |
| IV. 观察-执行-验证独立闭环 | `RepeatGuard.check()`/`evaluate_precondition()` 的判断依据均为既有独立观测证据（`ActionIteration.action_effect`、`VerificationEngine.verify()` 对首次独立观察的评估），不采信 Planner/Grounder 自我判断 | PASS |
| V. 受控自进化 | 本 feature 不新增经验采集/回放/训练相关行为 | PASS |
| **VI. 业务无关核心与声明式场景隔离**（新增，2026-07-22 引入） | 本次规划的**核心目标**：删除 `HumanStartStateConfirmation`/`ObservedStartState`/`ReportingConfig.category_keywords`/`_RESULT_DISPLAY_KEYWORDS`/`_DISMISSAL_KEYWORDS`/`extract_cart_state()`/`--confirmed-cart-items` 等全部固定业务字段与关键词表，替换为 `DeclaredFact`/`RunPrecondition`/`ActionTagRule`/`micro_action_purpose` 等业务无关声明式机制（research.md §0 完整清单）；POS 内容收敛到唯一位置——`testcases/pos-buy-bag-checkout.yaml` 本身；新增三个互不相关的通用离线场景（research.md §13）证明每项通用能力，POS 场景降级为第四个附加 fixture | **PASS（Phase 1 设计已逐项落实 `checklists/domain-independence.md` 的 11 项未通过发现，见下方"Constitution Check（Phase 1 后复核）"）** |
| 黑盒边界 | 全部新增逻辑仅消费 `SemanticAction`/`StructuredScreen`/`GroundingResult` 既有结构与截图分辨率，不新增任何超出黑盒边界的观测或控制手段 | PASS |
| 架构约束（模块化单体） | 新增/修改模块均落在既有单进程 `vnc_agent` 包内，无新模块跨越现有子包边界 | PASS |
| 资源约束（弱配置电脑） | 身份匹配、目标一致性、坐标换算、前置条件/tag 评估均为本地纯逻辑运算 | PASS |
| 凭据与隐私 | 本 feature 不新增任何截图外发路径或新的模型 API 调用面 | PASS |
| 验证独立性门禁 | `RepeatGuard.check()`/`evaluate_target_consistency()`/`evaluate_precondition()` 的判定输入固定为既有独立观测证据 | PASS |
| 恢复与重试门禁 | `RecoveryPolicy` 六字段契约原样保留；风险级别驱动的额外确认需求通过该契约路由，不新增独立裁决通道 | PASS |
| 测试覆盖门禁 | 新增测试全部落在"离线固定数据测试"与"端到端场景测试"两类；额外要求至少两个互不相关通用场景覆盖每项通用能力（FR-040） | PASS |
| MVP 验收门禁 | spec.md Success Criteria（SC-001~013）覆盖三个通用场景 + POS 附加场景、坐标安全、前置条件 fail-safe、恢复预算门禁 | PASS |
| 制品与可观测性 | `canonical_action_identity`、`coordinate_space_audit`、`precondition_evaluation`、`declared_tag_counts` 随迭代/运行记录 | PASS |

**结论（Phase 0 前）**：研究前门禁全部通过，无需 Complexity Tracking 登记任何
违规。Principle VI 的 PASS 结论以 Phase 1 设计**必须**逐项落实
`checklists/domain-independence.md` 的 11 项未通过发现为前提，见下方 Phase 1
后复核。

**结论（Phase 1 设计后复核）**：完成 research.md 与 data-model.md/contracts/
quickstart.md 设计后逐项核对 `checklists/domain-independence.md`：

| CHK 编号 | 结论 |
|---|---|
| CHK001（`data-model.md` 固定业务字段） | RESOLVED — §8 `DeclaredFact`/`RunPrecondition` 替换 `HumanStartStateConfirmation`/`ObservedStartState` |
| CHK002（tasks.md 缺少多场景任务） | 待 `/speckit-tasks` 落实——research.md §13 已给出三个通用场景的具体文件与断言设计，供任务生成直接消费 |
| CHK003（`action_id_match` 跳过一致性检查，与安全问题 A 矛盾） | RESOLVED — action-identity-contract.md §3.1/§4 新增 `has_target_evidence_conflict()` 前置门 |
| CHK004（`no_effect` 是否豁免漂移检查） | RESOLVED — action-identity-contract.md §4 步骤 3/4 明确 `no_effect` 只影响 `"ambiguous"` fail-safe 分支，不豁免 `conflict` 检查 |
| CHK005（固定四分类 report/config） | RESOLVED — data-model.md §8b `ActionTagRule`/`ReportingConfig.action_tags` 默认空集合 |
| CHK006（`recovery-policy-contract.md` "清空购物车"措辞） | RESOLVED — 已改写为通用措辞 |
| CHK007（多场景可测量性依赖不存在的任务） | 待 `/speckit-tasks` 落实，同 CHK002 |
| CHK008（SC-001～013 业务无关） | 已通过（spec.md 层面），本次规划的 SC 引用（Summary/Technical Context）保持一致 |
| CHK009（`action_id_match` 场景无对应设计流程分支） | RESOLVED — data-model.md §9 状态流程图新增 `has_target_evidence_conflict()` 分支 |
| CHK010（`action_type` 不同无条件 `dangerous_drift`，与安全问题 B 矛盾） | RESOLVED — data-model.md §3、action-identity-contract.md §3.2 改为 AND 语义 |
| CHK011（场景 profile 可选性） | 已通过（spec.md Assumptions），本次规划的 `TestCase.precondition`/`action_tags` 均为 `TestCase`/`AgentConfig` 顶层可选字段，不新增 profile 注册接口，与该决议一致 |
| CHK012（下游产物与 spec.md 依赖未追踪） | RESOLVED — 本次 `/speckit-plan` 即完成重新生成 |
| CHK013（业务无关规则单一来源） | 已通过，未变化 |
| CHK014（矛盾是否记录为阻塞项） | RESOLVED — 本次规划即为该阻塞项的解决方案本身 |

全部条款结论维持 PASS；CHK002/CHK007 的完全解决依赖 `/speckit-tasks` 将
research.md §13 的场景设计转化为具体任务，本 Phase 1 设计已提供任务生成所需的
全部文件路径、函数签名与断言要点，不构成 Complexity Tracking 违规。

## Project Structure

### Documentation (this feature)

```text
specs/003-action-identity-grounding/
├── plan.md                          # This file (/speckit-plan command output)
├── research.md                      # Phase 0 output (/speckit-plan command)
├── data-model.md                    # Phase 1 output (/speckit-plan command)
├── quickstart.md                    # Phase 1 output (/speckit-plan command)
├── contracts/                       # Phase 1 output (/speckit-plan command)
│   ├── action-identity-contract.md      # 重写：安全问题 A/B 修正
│   ├── coordinate-space-contract.md     # 原样保留，示例去业务化
│   ├── real-vnc-audit-contract.md       # 重写：声明式前置条件/tag 审计
│   └── recovery-policy-contract.md      # 原样保留，措辞去业务化
├── checklists/
│   ├── requirements.md
│   ├── requirements-safety.md       # 已标注 STALE（FR/SC 编号对应旧版本 spec.md）
│   └── domain-independence.md       # 本次规划逐项对照解决的 14 项发现
└── tasks.md                         # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

单一项目结构，延续 001/002/旧 003 已交付的 `vnc_agent/` 包。下表只列出本次
重新基线**新增**、**修改**或**删除**的文件；未列出的文件保持既有交付状态不变。

```text
vnc_agent/
├── config/
│   └── agent.yaml                          # [修改] 删除 planning.result_display_keywords/
│                                            #        dismissal_keywords 与 reporting.
│                                            #        category_keywords 四分类默认值；
│                                            #        新增 planning.micro_action_risk_
│                                            #        thresholds（通用 UI 类别→风险阈值）
│                                            #        与 planning.target_region_conflict_
│                                            #        iou_threshold；reporting.action_tags
│                                            #        默认空列表；recovery 六字段不变
│
├── src/vnc_agent/
│   ├── config.py                            # [修改] 删除 PlanningConfig.result_display_
│   │                                        #        keywords/dismissal_keywords；删除
│   │                                        #        ReportingConfig.category_keywords 及
│   │                                        #        其四分类校验器；新增 PlanningConfig.
│   │                                        #        micro_action_risk_thresholds/
│   │                                        #        target_region_conflict_iou_threshold；
│   │                                        #        新增 ReportingConfig.action_tags:
│   │                                        #        list[ActionTagRule]
│   ├── domain/
│   │   ├── action.py                       # [修改] SemanticAction.risk_level 扩展为
│   │   │                                    #        Literal["low","medium","high"]；
│   │   │                                    #        新增 micro_action_purpose 字段
│   │   ├── action_identity.py              # [不变] CanonicalActionIdentity
│   │   ├── grounding.py                    # [不变] coordinate_space/raw_bbox
│   │   ├── reporting_tags.py               # [新增] ActionMatcher / ActionTagRule
│   │   ├── repeat_guard.py                 # [修改] RepeatGuardDecision.reason 组合
│   │   │                                    #        逻辑注释更新（枚举值不变）
│   │   ├── run.py                          # [修改，删除+新增] 删除
│   │   │                                    #        HumanStartStateConfirmation/
│   │   │                                    #        ObservedStartState/
│   │   │                                    #        StartStatePrecondition；新增
│   │   │                                    #        DeclaredFact/RunPrecondition/
│   │   │                                    #        FactEvaluation/
│   │   │                                    #        PreconditionEvaluation/
│   │   │                                    #        HumanConfirmedFact；TestRun 新增
│   │   │                                    #        precondition_evaluation/
│   │   │                                    #        human_confirmed_facts
│   │   └── testcase.py                     # [修改] TestCase 新增
│   │                                        #        precondition: RunPrecondition | None、
│   │                                        #        action_tags: list[ActionTagRule]
│   │
│   ├── execution/
│   │   ├── action_identity.py              # [不变] compute_identity() / identity_match()
│   │   ├── target_consistency.py           # [重写] 删除 _RESULT_DISPLAY_KEYWORDS/
│   │   │                                    #        _DISMISSAL_KEYWORDS 与关键词参数；
│   │   │                                    #        删除 action_type 无条件 dangerous_
│   │   │                                    #        drift 分支；新增
│   │   │                                    #        has_target_evidence_conflict()；
│   │   │                                    #        evaluate_target_consistency() 改为
│   │   │                                    #        AND(purpose, intent一致性, risk阈值)
│   │   └── repeat_guard.py                 # [修改] check() 新增
│   │                                        #        previous_resolved_region/
│   │                                        #        proposed_resolved_region 入参；组合
│   │                                        #        逻辑新增 has_target_evidence_conflict()
│   │                                        #        前置门（见 action-identity-contract.md §4）
│   │
│   ├── models/
│   │   ├── coordinate_space.py             # [不变] resolve_pixel_bbox()（唯一换算点）
│   │   ├── mimo_grounder.py                # [不变]
│   │   └── response_parser.py              # [不变]
│   │
│   ├── planning/
│   │   ├── action_policy.py                # [不变] OCR 合理性核对
│   │   └── action_classification.py        # [不变，已知技术债] `_DEFAULT_NON_IDEMPOTENT_
│   │                                        #        KEYWORDS` 含业务关键词，明确排除在
│   │                                        #        本 feature 范围外（见 Scale/Scope）
│   │
│   ├── verification/
│   │   ├── business_resolver.py            # [修改，删除] 删除 extract_cart_state()、
│   │   │                                    #        evaluate_start_state_precondition()
│   │   └── engine.py                       # [不变] VerificationEngine.verify() 被
│   │                                        #        §12 前置条件评估直接复用
│   │
│   ├── api/
│   │   └── cli.py                          # [修改] 删除 --confirm-start-state/
│   │                                        #        --confirmed-cart-items/
│   │                                        #        --confirmed-cart-amount/
│   │                                        #        --confirmed-screenshot；新增
│   │                                        #        --confirm-precondition key=value
│   │                                        #        （可重复）、--confirm-screenshot
│   │
│   ├── runtime/
│   │   ├── run_context.py                  # [修改] human_confirmed_facts 写入 TestRun
│   │   ├── agent_runtime.py                # [修改] 删除 extract_cart_state() 调用；
│   │   │                                    #        改为在首次观察后调用
│   │   │                                    #        evaluate_precondition()；RepeatGuard
│   │   │                                    #        调用新增已解析区域入参
│   │   └── step_controller.py              # [不变] 共享预算消费逻辑
│   │
│   ├── recovery/
│   │   ├── classifier.py                   # [不变]
│   │   └── engine.py                       # [不变] 消费 RecoveryPolicy 六字段（不变）
│   │
│   ├── storage/
│   │   └── repositories.py                 # [不变] canonical_identity_json 可空列
│   │
│   └── reporting/
│       ├── json_report.py                  # [修改] 删除 _CATEGORY_KEYWORDS 常量与固定
│       │                                    #        四分类聚合逻辑；新增按
│       │                                    #        ReportingConfig.action_tags 匹配
│       │                                    #        的 declared_tag_counts 聚合；新增
│       │                                    #        precondition_evaluation/
│       │                                    #        human_confirmed_facts 字段
│       └── html_report.py                  # [修改] 折叠区块字段名同步更新
│
├── testcases/
│   └── pos-buy-bag-checkout.yaml           # [不变，业务内容] 继续使用
│                                            #        verification_mode: business；新增
│                                            #        顶层 precondition/action_tags 声明
│                                            #        （业务内容完全在本文件内，核心零改动）
│
└── tests/
    ├── fixtures/
    │   ├── test_scenario_form_submit.py     # [新增] 通用场景 1（研究 §13）
    │   ├── test_scenario_icon_menu.py       # [新增] 通用场景 2（研究 §13）
    │   ├── test_scenario_popup_scroll.py    # [新增] 通用场景 3（研究 §13）
    │   ├── test_cross_scenario_coverage.py  # [新增，/speckit-analyze 补充：
    │   │                                    #        tasks.md T045 引入] 断言
    │   │                                    #        每项通用能力与 SC-006/007
    │   │                                    #        在三个通用场景间成立，
    │   │                                    #        独立于 POS 场景是否通过
    │   ├── test_action_identity.py          # [修改] different_step 等既有用例保留，
    │   │                                    #        新增覆盖 conflict 前置门的用例
    │   ├── test_target_consistency.py       # [重写] 删除关键词相关断言；新增
    │   │                                    #        micro_action_purpose/risk_level
    │   │                                    #        AND 语义用例
    │   ├── test_coordinate_space.py         # [不变] 归一化换算等既有用例
    │   ├── test_action_policy_sanity_check.py  # [不变]
    │   ├── test_repeat_guard.py             # [修改] 新增 has_target_evidence_conflict
    │   │                                    #        前置门用例
    │   ├── test_run_precondition.py         # [新增] 声明式前置条件评估
    │   ├── test_declared_action_tags.py     # [新增] 声明式 tag 审计
    │   ├── test_pos_bag_assertions.py       # [不变] POS 业务断言单元测试
    │   ├── test_recovery_no_destructive_actions.py  # [修改] 新增风险级别路由用例
    │   ├── test_report_builder.py           # [修改] 新增 precondition_evaluation/
    │   │                                    #        declared_tag_counts 断言
    │   └── test_testcase_loader.py          # [修改] precondition/action_tags 顶层
    │                                        #        字段加载校验
    │
    ├── unit/
    │   ├── test_no_auto_clear_action.py     # [不变]
    │   └── test_cli_start_state_confirmation.py  # [重写为]
    │       test_cli_precondition_confirmation.py #        --confirm-precondition
    │                                        #        key=value 通用参数校验
    │
    └── e2e/
        ├── test_scenario_15_pos_bag_business_acceptance.py  # [不变，降级为
        │                                      #   第四个附加回归 fixture]
        └── test_start_state_precondition.py  # [重写为]
            test_run_precondition_e2e.py     #   通用前置条件端到端场景
```

**Structure Decision**：延续 001/002/旧 003 的单一项目结构，不新建子包、不新建
对外接口层。两个安全问题的修复（`has_target_evidence_conflict()`、
`evaluate_target_consistency()` AND 语义重写）落在既有的 `execution/` 层
（Executor 归属，与 Constitution Core Principle II 一致）；声明式前置条件/tag
复用既有 `domain/verification.py`/`verification/engine.py`，只新增极少量薄
包装类型（`DeclaredFact`/`RunPrecondition`/`ActionTagRule`），不新增第二套
断言引擎；坐标空间协议维持在 Grounder 边界内不变。`runtime/agent_runtime.py`
只新增 `evaluate_precondition()` 调用与 `RepeatGuard.check()` 的入参扩展，
调用时机与状态机转移表本身不变。

## Complexity Tracking

> Constitution Check 全部通过，无需登记任何违规或范围缩减。CHK002/CHK007 的
> 完全解决转移给 `/speckit-tasks`（生成具体任务），不构成本 Phase 1 设计的
> 违规——research.md §13 已提供其所需的全部具体设计。
