# Implementation Plan: 自适应动作效果检测与可信业务验证

**Branch**: `002-action-effect-verification` | **Date**: 2026-07-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-action-effect-verification/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes
the execution workflow. 本次规划已吸收 2026-07-21 澄清会话（`/speckit-clarify`，10 项决策
已解决，见 spec.md 的 `## Clarifications`）的全部结论。

## Summary

001 交付的 VNC 黑盒 GUI 自动化测试核心执行闭环存在一个真实生产缺陷：`perception/
screen_diff.py::compute_diff()` 只用单一全屏像素变化比例（默认 2%）判断"动作是否生效"，
导致 pos-buy-bag-checkout.yaml 场景中真实生效的点击（全屏变化仅约 0.424%）被误判为
`ACTION_NO_EFFECT`，触发重复点击造成多个购物袋；恢复策略随后又把点击无依据地退化为 Tab
（`planning/action_policy.py` 的 `prefer_keyboard` 分支无条件发送 `keys=["tab"]`），
触发错误弹窗，而错误弹窗造成的大范围画面变化又让 `screen_changed` 反过来判定"通过"。
本 feature 不改变 001 的整体闭环结构（观察→理解→选择动作→定位→执行→等待→验证→保存
证据、Planner/Grounder/Executor/Verifier 分离均保持不变），只在其"验证"与"动作选择恢复"
两个环节引入四项加固：① 新增独立的 `ActionEffect` 判定（四态：`no_effect` /
`expected_effect` / `unexpected_effect` / `effect_uncertain`），综合局部像素连通域
（不再受全屏阈值门控）、OCR 差集、模板差集、结构化状态差异，与既有的 `screen_changed`
弱证据彻底解耦；② 新增 `RepeatGuard`，在非幂等动作已产生效果但业务结果未定时阻止 Runtime
发起语义等价的重复执行，转而触发"重新观察 + 加强验证（含视觉模型兜底）"；③ 收紧
`ActionPolicy` 的键盘降级路径，要求存在同时包含"记录的焦点导航序列"与"验证该序列当前
仍有效的方法"两部分的 `VerifiedFocusNavigationPath` 证据，否则回退既有失败/恢复框架而不
再无条件发 Tab；④ 新增 `verification/business_resolver.py`，把"业务结果是否通过"
（StepVerificationResult）与"动作是否生效"彻底拆分为两个独立结果，`screen_changed` 类
弱证据只能在测试步骤显式声明 `verification_mode: effect_only` 时单独通过，旧用例（含
pos-buy-bag-checkout.yaml 本身）保持可加载但运行时封顶为 `uncertain` 并附带弱断言警告。
不引入任何新依赖，全部实现在既有 `vnc_agent` 单一 Python 包内完成，新增测试均基于程序化
构造的固定截图离线运行，不连接真实 VNC。

## Technical Context

**Language/Version**: Python 3.12+（与 001 完全一致，无变化）

**Primary Dependencies**: 复用 001 已引入的全部依赖（vncdotool、opencv-python + numpy、
RapidOCR、httpx、Pydantic v2、PyYAML + pydantic-settings、SQLAlchemy 2.x + aiosqlite、
structlog、Typer、pytest）；**本 feature 不引入任何新的第三方依赖**——ActionEffect 判定、
Repeat Guard、焦点路径证据均可用既有 opencv-python/numpy（连通域检测已被
`compute_diff` 使用）、Pydantic v2（新增领域模型）实现。

**Storage**: 沿用 001 的单个 SQLite 数据库文件 + 本地制品目录；`ActionIteration` 表
（`storage/repositories.py`）新增两个可空列（`action_effect_json`、
`repeat_guard_decision_json`），不新增数据表，不引入新的存储引擎。

**Testing**: pytest，沿用 001 建立的四层测试分类；本 feature 新增的全部测试属于"基于
固定截图/固定响应的离线测试"（`tests/fixtures/`）与"端到端场景测试"（`tests/e2e/`）两类，
**不新增真实 VNC 集成测试**——因为本 feature 修改的是感知后处理、验证聚合与动作选择的
纯逻辑层，不涉及新的 VNC 协议交互，复用 001 已有的 `MockVNCDriver`/固定截图基础设施
即可覆盖（research.md §9）。

**Target Platform**: 与 001 完全一致——无独立显卡的普通办公电脑运行控制端 Agent 进程；
被测端为固定分辨率/DPI 的 Windows 10 桌面（本次事故环境为 1024×1568）。

**Project Type**: 单一项目（single project），延续 001 的 `vnc_agent` 包结构，不新增
子项目、不新增对外 HTTP API 或前端。

**Performance Goals**: 新增的 `ActionEffect` 判定 MUST 是纯本地图像/文本比较（复用既有
`compute_diff` 连通域检测 + OCR/模板差集比较），不新增网络调用，对单次验证耗时的增量
预期在毫秒级；`business_resolver` 的加强验证分支 MAY 触发一次额外的 `describe_screen`
调用（沿用 001 已有的 `Planner` 调用超时配置，不新增独立的超时预算）。

**Constraints**: 沿用 001 的全部资源约束（不依赖独立显卡、不在本地运行大型视觉语言模型、
同一时刻仅一个 VNC 会话、内存仅保留最近 3～5 帧）；新增的"确定性手段优先"路由约束——
`ActionEffect` 判定 MUST NOT 默认调用视觉模型（research.md §2），只有 §5 的加强验证分支
在确定性方法不足时才升级。

**Scale/Scope**: 覆盖 spec.md 的全部 8 个用户故事（P1 的 5 个直接对应事故根因修复 + P2
的 2 个配套能力 + P3 的离线回归测试）；改动范围限定在 `perception/`、`verification/`、
`execution/`、`planning/action_policy.py`、`recovery/classifier.py`、
`domain/{action,action_effect,focus_path,run,testcase}.py` 之内，不触碰 001 中
`runtime/state_machine.py`、`drivers/`、`models/`、`storage/database.py`、`reporting/`、
`evolution/` 的既有结构（`runtime/agent_runtime.py` 仅在 `run_action_iteration()` 内部
新增调用点，不改变其状态机迁移规则）。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution 条款 | 本功能的落实方式 | 结论 |
|---|---|---|
| I. 确定性运行时控制模型 | `ActionEffect`/`StepVerificationResult` 判定与 `RepeatGuard` 均为代码状态机内的确定性函数调用（`perception/action_effect.py`、`verification/business_resolver.py`、`execution/repeat_guard.py`），不引入模型自主决策；模型（视觉问答）只在 `business_resolver` 的加强验证分支作为补充证据输入，其结论在与确定性断言冲突时 MUST NOT 覆盖确定性结果（research.md §8，FR-010） | PASS |
| II. Planner/Grounder/Executor/Verifier 分离 | `ActionEffect` 与 `StepVerificationResult` 判定职责归属 Verifier（`perception/`+`verification/`）；`RepeatGuard` 归属 Executor 侧调度（`execution/`），不越权发起新验证或自行判定业务结果；Planner（`planning/planner.py`）与 Grounder（`models/mimo_grounder.py`）职责与接口不变，`action_kind` 分类虽在 `planning/action_classification.py` 落地，但只是对 Planner 已产出的 `SemanticAction` 做附加标注，不改变 Planner 的决策职责（FR-028/029） | PASS |
| III. 键盘优先，视觉点击兜底 | 本 feature MUST NOT 重排 001 已确立的候选优先级（快捷键→焦点导航→OCR/模板→MiMo Grounding→停止恢复，`contracts/action-effect-contract.md` §4 已显式声明这一不变量）；唯一收紧的是"焦点导航"这一级本身的准入条件——从"恢复策略要求就无条件执行"改为"MUST 有可验证证据才可执行"（FR-020~024），这是让该优先级更符合"键盘路径必须足够确定"这一原则本意的修正，而非削弱键盘优先本身 | PASS |
| IV. 观察-执行-验证独立闭环 | `ActionEffect`/`StepVerificationResult` 均基于动作后独立重新采集的 `StructuredScreen` 判定（`perception.action_effect.classify_action_effect` 的输入是 before/after 两帧观察，不是执行/定位模型的自我判断）；`effect_uncertain`/`uncertain` 不会被静默折叠为通过，且新增的弱断言封顶规则（FR-026）进一步强化了本条款——过去可能被误判为可信通过的旧步骤现在会被显式标记为不确定 | PASS |
| V. 受控自进化 | 新增的 `ActionEffect`、`RepeatGuardDecision` 字段并入 `ActionIteration`（`domain/run.py`），继续经由 001 已有的 `evolution/experience_collector.py` 采集保存，不新增检索/训练逻辑，不自动修改测试断言（本 feature 反而是收紧了对"断言是否充分"的静态与运行时校验，方向上进一步强化该条款） | PASS |
| 黑盒边界 | 全部新增逻辑仅消费 `StructuredScreen`（截图 + OCR + 模板 + 结构化状态）与既有 `VNCDriver`/`ExecutionRouter` 接口，不新增任何超出黑盒边界的观测或控制手段 | PASS |
| 架构约束（模块化单体） | 新增模块（`domain/action_effect.py`、`domain/focus_path.py`、`perception/action_effect.py`、`verification/business_resolver.py`、`execution/repeat_guard.py`、`planning/action_classification.py`）均落在既有单进程 `vnc_agent` 包内，不引入新进程、新服务或新的跨进程协议 | PASS |
| 资源约束（弱配置电脑） | `ActionEffect` 判定复用既有 OpenCV/numpy 本地计算，不新增模型加载；加强验证分支遵循"确定性手段优先、能不升级到模型就不升级"路由原则，只在必要时补一次视觉问答调用，不引入常驻推理进程 | PASS |
| 动作安全分级 / PowerShell 黑盒配方 | 本 feature 不涉及 PowerShell 配方或 high 风险动作，维持 001 Complexity Tracking 中已登记的范围缩减，不重新引入 | N/A（超出本 feature 范围，非本功能违反） |
| 凭据与隐私 | 本 feature 不新增任何截图外发路径或新的模型 API 调用面（`describe_screen` 复用既有 `PlannerProvider` 接口与既有遮罩/外发策略），不影响 FR-049 既有权衡 | PASS |
| 验证独立性门禁 | `verification/business_resolver.py` 的判定输入固定为"操作后新截图 + 既有 `VerificationEngine` 逐条件求值结果"，不采信 Executor 或 Planner 的自我判断；代码评审可直接核对该数据流未变 | PASS |
| 恢复与重试门禁 | `RepeatGuard` 明确 MUST NOT 修改 `StepController` 的预算计数（`contracts/action-effect-contract.md` §3），加强验证分支的重试节奏仍完全由既有 `ActionIteration` 循环与 `StepController` 共享预算控制，不开辟脱离预算门禁的隐藏重试通道，直接呼应本次事故"程序随后重复执行添加操作"这一具体违规场景的根治 | PASS |
| 测试覆盖门禁 | 新增测试全部落在"基于固定截图的离线测试"与"端到端场景测试"两类（Project Structure 下文），延续 001 四类测试分层，不新增真实 VNC 集成测试（本 feature 不改变 VNC 协议交互本身） | PASS |
| MVP 验收门禁 | spec.md 的 Success Criteria（SC-001~SC-010）覆盖"不存在无限重试""不会自动修改正式测试断言""每个正式步骤均能独立验证"等既有验收标准在本 feature 场景下的具体化版本 | PASS |
| 制品与可观测性 | `ActionEffect`、`RepeatGuardDecision` 作为 `ActionIteration` 的新增字段随既有运行轨迹一并落库与生成报告，报告层新增弱断言警告的醒目标注（FR-027），不引入独立于既有报告体系之外的新制品格式 | PASS |

**结论（Phase 0 前）**：研究前门禁全部通过，无需 Complexity Tracking 登记任何违规——本
feature 的全部改动都是在 001 已确立的架构与职责边界内做加固，未引入新的架构复杂度。

**结论（Phase 1 设计后复核）**：完成 research.md 与 data-model.md/contracts/quickstart.md
设计后重新核对上表——新增的 5 个模块（`domain/action_effect.py`、`domain/focus_path.py`、
`perception/action_effect.py`、`verification/business_resolver.py`、
`execution/repeat_guard.py`、`planning/action_classification.py`）均已按四层职责归属
明确划入 Verifier（感知/验证两侧）或 Executor（重复防护），未出现职责越界；`RepeatGuard`
与 `business_resolver` 均已在 contracts/action-effect-contract.md 中显式约束"不得自行
修改预算计数、不得自行发起新动作"，避免设计阶段悄悄引入脱离既有恢复与重试门禁的隐藏
循环。全部条款结论维持 PASS，无需变更 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/002-action-effect-verification/
├── plan.md                          # This file (/speckit-plan command output)
├── research.md                      # Phase 0 output (/speckit-plan command)
├── data-model.md                    # Phase 1 output (/speckit-plan command)
├── quickstart.md                    # Phase 1 output (/speckit-plan command)
├── contracts/                       # Phase 1 output (/speckit-plan command)
│   ├── test-case-schema-delta.md
│   └── action-effect-contract.md
├── checklists/
│   └── requirements.md
└── tasks.md                         # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

单一项目结构，延续 001 已交付的 `vnc_agent/` 包。下表只列出本 feature **新增**或
**修改**的文件；未列出的文件（`runtime/state_machine.py`、`drivers/`、`models/`、
`storage/database.py`、`reporting/`、`evolution/` 等）保持 001 交付状态不变。

```text
vnc_agent/
├── config/
│   └── agent.yaml                          # [修改] 新增 perception.error_keywords、
│                                            #        perception.local_blob_min_ratio
│
├── src/vnc_agent/
│   ├── domain/
│   │   ├── action.py                       # [修改] SemanticAction 新增 action_kind 字段
│   │   ├── action_effect.py                # [新增] ActionEffect / ActionEffectEvidence
│   │   ├── focus_path.py                   # [新增] VerifiedFocusNavigationPath
│   │   ├── recovery.py                     # [不变] FailureType/RecoveryStrategy 取值集合不变
│   │   ├── run.py                          # [修改] ActionIteration 新增
│   │   │                                    #        action_effect / repeat_guard_decision
│   │   ├── testcase.py                     # [修改] TestStep 新增 verification_mode 字段 +
│   │   │                                    #        加载时的业务断言校验分支（FR-008）
│   │   └── verification.py                 # [修改] VerificationResult 新增
│   │                                        #        weak_assertion_warning / basis 字段
│   │
│   ├── perception/
│   │   ├── screen_diff.py                  # [修改] 局部连通域检测解除全屏阈值门控
│   │   │                                    #        （research.md §1，本次事故根因修复）
│   │   └── action_effect.py                # [新增] classify_action_effect()（含错误
│   │                                        #        弹窗识别子函数，research.md §2/§6）
│   │
│   ├── planning/
│   │   ├── action_policy.py                # [修改] prefer_keyboard 分支要求
│   │   │                                    #        VerifiedFocusNavigationPath 证据
│   │   │                                    #        （本次事故"无依据退化为 Tab"根因修复）
│   │   └── action_classification.py        # [新增] classify_action_kind()（非幂等动作分类）
│   │
│   ├── execution/
│   │   └── repeat_guard.py                 # [新增] RepeatGuard（防止重复执行非幂等动作，
│   │                                        #        本次事故"重复加购"根因修复）
│   │
│   ├── verification/
│   │   ├── engine.py                       # [不变] 逐条件求值逻辑不变
│   │   ├── screen_change_verifier.py       # [不变] 仍产出弱证据，供 ActionEffect 与
│   │   │                                    #        business_resolver 消费
│   │   └── business_resolver.py            # [新增] resolve_step_result()（StepVerification
│   │                                        #        Result 与 ActionEffect 分离的落地点）
│   │
│   ├── recovery/
│   │   ├── classifier.py                   # [修改] classify_action_no_effect() 改为接收
│   │   │                                    #        ActionEffect，而非裸 screen_changed bool
│   │   └── strategies.py                   # [修改] switch_to_keyboard 副作用需配合构造/
│   │                                        #        校验 VerifiedFocusNavigationPath
│   │
│   ├── runtime/
│   │   └── agent_runtime.py                # [修改] run_action_iteration() 内插入
│   │                                        #        RepeatGuard.check() 与
│   │                                        #        business_resolver.resolve_step_result()
│   │                                        #        调用点；不改变状态机迁移规则本身
│   │
│   └── reporting/
│       ├── html_report.py                  # [修改] 渲染 weak_assertion_warning 醒目标注
│       └── json_report.py                  # [修改] 输出 action_effect / weak_assertion_warning
│
├── testcases/
│   └── pos-buy-bag-checkout.yaml           # [不变] 保持原样作为旧用例回归对象（FR-025），
│                                            #        不因本 feature 而被迁移到新 schema
│
└── tests/
    ├── fixtures/                            # [新增测试] 基于程序化构造截图的离线测试
    │   ├── test_action_effect.py            #   （0.424% 场景、九宫格、四类场景、噪声区域排除，
    │   │                                    #        SC-001/005/006，FR-005）
    │   ├── test_repeat_guard.py             #   （SC-002/003，含 no_effect_confirmed 放行分支）
    │   ├── test_error_popup_classification.py  # （SC-004）
    │   ├── test_business_resolver.py        # [新增] StepVerificationResult 状态/basis 判定表、
    │   │                                    #        确定性断言优先于视觉模型冲突消解（FR-010/
    │   │                                    #        SC-010）、错误弹窗下业务断言仍正常判定
    │   │                                    #        （FR-021）（US2/US3/US4/US6/US7 共用）
    │   ├── test_testcase_loader.py          # [修改] 新增 verification_mode 校验用例（SC-007）
    │   └── test_report_builder.py           # [修改] 新增弱断言警告 / effect-only 通过 / 业务
    │                                        #        断言通过三态在报告中可区分的校验（FR-027）
    │
    ├── unit/                                 # [新增测试]
    │   ├── test_action_kind_classification.py
    │   ├── test_focus_path_gate.py           #   （ActionPolicy 无 focus_path 时不发 Tab）
    │   └── test_no_real_vnc_in_offline_tests.py  # 本 feature 新增测试均未实例化真实 VNCDriver
    │                                        #        （SC-009，归入既有三层测试分类而非独立顶层文件）
    │
    └── e2e/                                  # [新增测试]
        ├── test_scenario_10_no_duplicate_action.py
        ├── test_scenario_11_error_popup_not_passed.py
        ├── test_scenario_12_legacy_weak_assertion.py
        └── test_scenario_13_pos_bag_regression.py   # 本次事故的完整离线回归（FR-031）
```

**Structure Decision**：延续 001 的单一项目结构，不新建子包、不新建对外接口层。本 feature
的四个核心修复点（局部证据解耦、ActionEffect 判定、Repeat Guard、焦点路径校验）分别落在
`perception/`、新增的 `domain/action_effect.py` + `verification/business_resolver.py`、
新增的 `execution/repeat_guard.py`、`planning/action_policy.py` 四处，与宪法 Core
Principle II 的 Planner/Grounder/Executor/Verifier 四层划分一一对应，不新增第五层职责。
`runtime/agent_runtime.py` 只新增两个调用点，其状态机转移表（`runtime/state_machine.py`）
保持 001 交付版本不变。

## Complexity Tracking

> Constitution Check 全部通过，无需登记任何违规或范围缩减。
