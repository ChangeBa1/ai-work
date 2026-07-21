# Implementation Plan: 稳定动作身份与坐标空间定位纠正

**Branch**: `003-action-identity-grounding` | **Date**: 2026-07-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-action-identity-grounding/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition
describes the execution workflow. 本次规划已吸收 2026-07-21 `/speckit-clarify` 会话
（8 项决策）与随后 `/speckit-checklist` 安全需求专项复核（31 项、20 项发现并修复
真实缺口）之后的最终 spec.md，并在动笔前逐行核对了真实事故报告
`vnc_agent/artifacts/runs/cefe36a9-f5c3-4622-9998-ef06690a5ab6/report.json`
与当前 `RepeatGuard`/`AgentRuntime`/`Grounder`/`ActionPolicy`/`VerificationEngine`/
测试用例加载器的实际实现，而非仅凭 spec.md 的描述推断代码现状。

## Summary

002 已实现并离线测试通过（116 passed, 1 skipped），但真实 VNC 验收暴露了两个 002
未覆盖的新缺陷，均已在真实事故报告中逐字段核实：① `execution/repeat_guard.py::
actions_semantically_equivalent()` 完全没有使用 `SemanticAction.action_id`（尽管
Planner 三轮重试中确实保持了稳定的 `action_id="act-1"`），只按 `target`/`intent`
自由文本完全相等判断"是否同一动作"，导致 Planner 的措辞改写让后两轮被误判为
`different_action` 并各执行了一次多余点击，其中一次还把目标从"购物袋按钮"改写成了
"已添加的商品行"这一危险漂移；② `domain/grounding.py::GroundingCandidate.bbox` 与
`models/mimo_grounder.py` 完全没有坐标空间概念（系统提示词硬编码"像素坐标"），在
1024×1568 这类纵向远超 1000 的分辨率下，若模型实际返回 0–1000 归一化坐标，会被
直接误用为像素坐标——真实事故报告中第二轮候选坐标换算后的位置与第一轮真实点击位置
高度吻合，是该假说的有力佐证。本 feature 不改变 001/002 已确立的整体闭环、四层职责
分离、`ActionEffect`/`StepVerificationResult` 分离、`RepeatGuard` 调用时机（已经在
`RESOLVING_ACTION`/Grounding/Executor 之前，无需改动）——只做四处加固：①
新增 `CanonicalActionIdentity`（步骤 ID + 动作类型 + `action_id` 强证据 + 规范化
业务目标），重写 `RepeatGuard` 的身份匹配算法，移除"文本不完全相等即视为不同动作"
这一 002 遗留漏洞；② 新增 `evaluate_target_consistency()`，在 `action_id` 缺失/
歧义时判断新目标是否合法（含危险漂移检测，覆盖"控件→非交互元素"与"控件→另一个
不符合 intent 的控件"两种方向）；③ 为 `GroundingCandidate` 新增显式
`coordinate_space` 字段（`pixel`/`normalized_1000`），在 `MimoGrounderClient.ground()`
内的单一调用点完成一次性换算，越界/矛盾/未知取值一律拒绝，历史无声明响应按"恰好一种
解释同时满足边界与一致性约束"的严格规则推断；④ 把 `pos-buy-bag-checkout.yaml` 从
仅 `screen_changed` 升级为 `verification_mode: business`，业务断言依据真实 OCR
输出（而非理想化完整字符串）设计，确保新断言在真实环境下真正稳定；⑤ 把人工确认、
首次观察与前置条件结果全部落在 `TestRun`，在首个输入事件前自动 fail-closed 比对，报告
仅按 `ExecutionResult.success=True` 的已发送动作聚合分类计数；⑥ 将 `RecoveryPolicy`
扩展为 Constitution 要求的六个显式必填控制项，缺项时配置加载失败。全部实现遵循
测试先行（先写失败测试再改代码），新增测试均离线运行，真实 VNC 验收单独列为人工
批准环节。

## Technical Context

**Language/Version**: Python 3.12+（与 001/002 完全一致，无变化）

**Primary Dependencies**: 复用 001/002 已引入的全部依赖（vncdotool、opencv-python +
numpy、RapidOCR、httpx、Pydantic v2、PyYAML + pydantic-settings、SQLAlchemy 2.x +
aiosqlite、structlog、Typer、pytest）；**本 feature 不引入任何新的第三方依赖**——
`CanonicalActionIdentity` 计算、`evaluate_target_consistency()`、
`resolve_pixel_bbox()` 均为纯 Python/Pydantic 逻辑与算术运算。

**Storage**: 沿用 001/002 的单个 SQLite 数据库文件 + 本地制品目录；`ActionIteration`
表（`storage/repositories.py`）新增一个可空列（`canonical_identity_json`）；
`GroundingCandidate` 的 `coordinate_space`/`raw_bbox` 字段随既有的
`grounding_result_json`/迭代记录序列化一并落库，不新增数据表。`TestRun` 新增 typed
人工确认、首次观察与前置判定字段，供同一运行结束时直接生成报告，不新增独立表。

**Testing**: pytest，沿用 001/002 建立的分层测试；本 feature 新增的全部测试属于
"基于固定截图/固定响应的离线测试"（`tests/fixtures/`）与"端到端场景测试"
（`tests/e2e/`）两类，**不新增真实 VNC 集成测试**——本 feature 修改的是身份判定与
坐标解析这两层纯逻辑，不涉及新的 VNC 协议交互。**测试先行**：`tasks.md` 中每个实现
任务前必须先有一个失败测试（tests written first, confirmed failing, per 用户对
本次规划的明确要求）。

**Target Platform**: 与 001/002 完全一致——无独立显卡的普通办公电脑运行控制端 Agent
进程；被测端为固定分辨率/DPI 的 Windows 10 桌面（本次事故环境为 1024×1568）。

**Project Type**: 单一项目（single project），延续 001/002 的 `vnc_agent` 包结构。

**Performance Goals**: `CanonicalActionIdentity` 计算与 `identity_match()`/
`evaluate_target_consistency()` MUST 是纯本地字符串/枚举比较，不新增网络调用；
`resolve_pixel_bbox()` 是纯算术运算；对单次 `RESOLVING_ACTION` 阶段耗时的增量预期
在毫秒级，不影响既有 `Performance Goals`（`config.agent.action.default_timeout_seconds`
等既有超时配置不变）。

**Constraints**: 沿用 001/002 的全部资源约束；新增约束——身份匹配与目标一致性判断
MUST NOT 默认调用视觉模型（research.md §4，确定性关键词/角色信号优先）；坐标空间
换算 MUST 在 Grounder 边界内的单一调用点完成，不得在多处重复实现（research.md §6，
这是"只换算一次"从文档承诺变为架构强制的具体做法）；真实 VNC 人工确认存在时，首次
观察与确认不一致/不可读/冲突 MUST 在首个输入事件前停止；恢复策略六个 Constitution
控制字段 MUST 全部显式配置且不得用默认值掩盖遗漏。

**Scale/Scope**: 覆盖 spec.md 的全部 7 个用户故事（P1 的 4 个直接对应真实事故的三个
根因修复 + 验收用例本身 + P2 的 2 个配套能力 + P3 的离线回归测试）；改动范围限定在
`config.py`、`domain/{action_identity,grounding,repeat_guard,run}.py`、
`execution/{action_identity,target_consistency,repeat_guard}.py`、
`models/{coordinate_space,mimo_grounder,response_parser}.py`、
`planning/action_policy.py`、`runtime/{run_context,agent_runtime}.py`（新增
`RepeatGuard.check()` 调用参数，并在真实 VNC 验收运行的首次 Observe 后增加前置条件
门禁，不改变既有动作迭代状态迁移规则）、
`reporting/{json_report,html_report}.py`、`testcases/pos-buy-bag-checkout.yaml`、
以及（落实 FR-036/038、SC-012/013）`api/cli.py`（新增
`--confirm-start-state` 等 4 个参数）、`verification/business_resolver.py`（新增
`extract_cart_state()` 与纯函数前置比较，业务结果判定逻辑本身不变）以及
`recovery/{classifier,engine}.py`/`runtime/step_controller.py` 的既有恢复配置消费点之内，不触碰 001/002 中
`runtime/state_machine.py`、`drivers/`、`perception/action_effect.py`
（ActionEffect 判定本身不变）的既有结构。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution 条款 | 本功能的落实方式 | 结论 |
|---|---|---|
| I. 确定性运行时控制模型 | `CanonicalActionIdentity`/`identity_match()`/`evaluate_target_consistency()`/`resolve_pixel_bbox()` 均为代码状态机内的确定性函数（`execution/`、`models/coordinate_space.py`），不引入模型自主决策；FR-007 明确禁止用视觉模型判断目标一致性（research.md §4） | PASS |
| II. Planner/Grounder/Executor/Verifier 分离 | 身份匹配/目标一致性判断归属 Executor（`execution/`，延续 002 `RepeatGuard` 的既有职责归属）；坐标空间换算归属 Grounder 边界（`models/`，Grounder 对外仍只暴露"定位目标具体在哪里"这一职责，只是把"在哪里"的坐标表达从可能歧义的原始数值收敛为无歧义的像素坐标）；Planner 与 Verifier 职责/接口不变 | PASS |
| III. 键盘优先，视觉点击兜底 | 本 feature MUST NOT 重排 001/002 已确立的候选优先级；新增的 OCR 合理性核对（`ActionPolicy._from_grounding()`）是在候选已经过 Grounding 优先级分支之后的**额外拒绝层**，不改变优先级顺序本身 | PASS |
| IV. 观察-执行-验证独立闭环 | `RepeatGuard.check()` 的判断依据是既有 `ActionIteration.action_effect`/`verification_result`（002 已交付的独立观测证据），不采信 Planner/Grounder 自我判断；坐标空间推断规则同样只依据换算数值与已有截图分辨率/证据，不采信模型自称"这就是像素坐标"的单方面说法 | PASS |
| V. 受控自进化 | 本 feature 不新增经验采集/回放/训练相关行为，`canonical_identity`/`coordinate_space_audit` 只是随既有 `ActionIteration` 一并落库供审计与未来分析，不触发任何自动模型更新 | PASS |
| 黑盒边界 | 全部新增逻辑仅消费 `SemanticAction`/`StructuredScreen`/`GroundingResult` 既有结构与截图分辨率，不新增任何超出黑盒边界的观测或控制手段 | PASS |
| 架构约束（模块化单体） | 新增模块（`domain/action_identity.py`、`execution/action_identity.py`、`execution/target_consistency.py`、`models/coordinate_space.py`）均落在既有单进程 `vnc_agent` 包内 | PASS |
| 资源约束（弱配置电脑） | 身份匹配、目标一致性、坐标换算均为本地纯逻辑运算，遵循"确定性手段优先"路由原则，不新增模型调用面 | PASS |
| 凭据与隐私 | 本 feature 不新增任何截图外发路径或新的模型 API 调用面（Grounder 系统提示词的字段增量不涉及新的敏感信息传输） | PASS |
| 验证独立性门禁 | `RepeatGuard.check()`/`evaluate_target_consistency()` 的判定输入固定为既有独立观测证据（`ActionIteration`/`StructuredScreen`），代码评审可直接核对该数据流未变 | PASS |
| 恢复与重试门禁 | `RecoveryPolicy` 扩展为六个无隐式默认值的必填控制项；全部现有策略逐项填写，缺项配置加载失败；坐标拒绝/目标漂移/歧义继续走既有失败分类与共享预算，见 `contracts/recovery-policy-contract.md`（FR-031/037） | PASS（设计已落实，T001/T003/T053/T055 验证） |
| 测试覆盖门禁 | 新增测试全部落在"基于固定截图/固定数据的离线测试"与"端到端场景测试"两类，延续 001/002 四类测试分层；本 feature 额外要求测试先行（用户对本次规划的明确指令），不新增真实 VNC 集成测试 | PASS |
| MVP 验收门禁 | spec.md Success Criteria（SC-001~013）覆盖点击次数精确、0.4669% ActionEffect 回归、起始状态不一致零输入停止、不存在无限重试及不会自动修改正式测试断言 | PASS |
| 制品与可观测性 | `canonical_action_identity`、`coordinate_space_audit` 随迭代记录；运行级报告从 `TestRun` 读取起始状态门禁，并只按已发送动作生成 `executed_action_log`/分类计数（FR-025/026/036/038） | PASS |

**结论（Phase 0 前）**：研究前门禁全部通过，无需 Complexity Tracking 登记任何违规。

**结论（Phase 1 设计后复核）**：完成 research.md 与 data-model.md/contracts/
quickstart.md 设计后重新核对——身份/一致性判断仍归 Executor，坐标换算仍归 Grounder；
新增起始状态门禁位于首次独立观察之后、首个动作规划之前，报告聚合仍只消费运行记录。
contracts 显式约束了单一换算点、六字段恢复策略、共享预算、起始状态 fail-closed 和仅统计
已发送动作等不变量，避免设计阶段引入隐藏重试或审计误计数。全部条款结论维持 PASS，
无需变更 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/003-action-identity-grounding/
├── plan.md                          # This file (/speckit-plan command output)
├── research.md                      # Phase 0 output (/speckit-plan command)
├── data-model.md                    # Phase 1 output (/speckit-plan command)
├── quickstart.md                    # Phase 1 output (/speckit-plan command)
├── contracts/                       # Phase 1 output (/speckit-plan command)
│   ├── action-identity-contract.md
│   ├── coordinate-space-contract.md
│   ├── real-vnc-audit-contract.md   # FR-036/038、SC-012/013
│   └── recovery-policy-contract.md  # FR-031/037 Constitution 门禁
├── checklists/
│   ├── requirements.md
│   └── requirements-safety.md
└── tasks.md                         # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

单一项目结构，延续 001/002 已交付的 `vnc_agent/` 包。下表只列出本 feature **新增**
或**修改**的文件；未列出的文件（`runtime/state_machine.py`、`drivers/`、
`storage/database.py` 表结构等）保持 002 交付状态不变。

```text
vnc_agent/
├── config/
│   └── agent.yaml                          # [修改] 新增 planning.result_display_keywords、
│                                            #        planning.dismissal_keywords、
│                                            #        planning.ocr_sanity_check_ratio、
│                                            #        reporting.category_keywords；
│                                            #        recovery 每项显式六字段
│
├── src/vnc_agent/
│   ├── config.py                            # [修改] PlanningConfig / ReportingConfig；
│   │                                        #        RecoveryPolicy 六字段必填
│   ├── domain/
│   │   ├── action_identity.py              # [新增] CanonicalActionIdentity
│   │   ├── grounding.py                    # [修改] GroundingCandidate 新增
│   │   │                                    #        coordinate_space / raw_bbox
│   │   ├── repeat_guard.py                 # [修改] RepeatGuardDecision.reason 枚举
│   │   │                                    #        移除 different_action，新增三值
│   │   └── run.py                          # [修改] ActionIteration 新增 identity；
│   │                                        #        TestRun 新增起始状态门禁对象
│   │
│   ├── execution/
│   │   ├── action_identity.py              # [新增] compute_identity() / identity_match()
│   │   ├── target_consistency.py           # [新增] evaluate_target_consistency()
│   │   │                                    #        （危险漂移检测两个方向）
│   │   └── repeat_guard.py                 # [修改] check() 签名新增 step_id/
│   │                                        #        step_intent，重写判定组合逻辑
│   │
│   ├── models/
│   │   ├── coordinate_space.py             # [新增] resolve_pixel_bbox()（唯一换算点）
│   │   ├── mimo_grounder.py                # [修改] 系统提示词新增 coordinate_space
│   │   │                                    #        字段要求；ground() 内调用唯一
│   │   │                                    #        换算点；StubGrounder 同步复用
│   │   └── response_parser.py              # [不变] coordinate_space 字段通过既有
│   │                                        #        **c 透传自动兼容，无需代码修改
│   │
│   ├── planning/
│   │   └── action_policy.py                # [修改] _from_grounding() 新增执行前
│   │                                        #        OCR 合理性核对（矛盾即拒绝）
│   │
│   ├── verification/
│   │   └── business_resolver.py            # [修改] 新增 extract_cart_state() /
│   │                                        #        evaluate_start_state_precondition()
│   │
│   ├── api/
│   │   └── cli.py                          # [修改，/speckit-analyze 补充]
│   │                                        #        `vnc-agent run` 新增
│   │                                        #        --confirm-start-state 等 4 个
│   │                                        #        参数（FR-036）
│   │
│   ├── runtime/
│   │   ├── run_context.py                  # [修改] confirmation 写入 TestRun
│   │   ├── agent_runtime.py                # [修改] RepeatGuard 参数；首次观察后
│   │   │                                    #        执行起始状态 fail-closed 门禁
│   │   └── step_controller.py              # [修改] 按策略显式消耗共享预算
│   │
│   ├── recovery/
│   │   ├── classifier.py                   # [核对/必要时修改] 新失败结果继续使用
│   │   │                                    #        既有共享预算路由
│   │   └── engine.py                       # [修改] 消费 RecoveryPolicy 六字段
│   │
│   ├── storage/
│   │   └── repositories.py                 # [修改] 新增 canonical_identity_json
│   │                                        #        可空列
│   │
│   └── reporting/
│       ├── json_report.py                  # [修改] 新增 canonical_action_identity /
│       │                                    #        coordinate_space_audit 字段
│       │                                    #        （逐轮，FR-025/026）；[修改，
│       │                                    #        /speckit-analyze 补充] 新增
│       │                                    #        start-state fields /
│       │                                    #        executed_action_log /
│       │                                    #        action_category_counts（只计已发送）
│       └── html_report.py                  # [修改] 新增对应折叠展示区块
│
├── testcases/
│   └── pos-buy-bag-checkout.yaml           # [修改] 升级为 verification_mode: business，
│                                            #        业务断言依据真实 OCR 证据设计
│                                            #        （research.md §9）
│
└── tests/
    ├── fixtures/                            # [新增测试]
    │   ├── test_feature003_config.py        #   typed reporting/recovery 配置门禁
    │   ├── test_feature003_domain_schema.py #   domain/TestRun/schema/persistence 契约
    │   ├── test_action_identity.py          #   （真实事故重放、跨步骤不误伤、
    │   │                                    #      action_type+action_id 组合、
    │   │                                    #      normalized_target_match OCR 容忍）
    │   ├── test_target_consistency.py       #   （两种漂移方向、合法微动作、
    │   │                                    #      action_type 不同即漂移）
    │   ├── test_coordinate_space.py         #   （归一化换算、越界/矛盾/未知值拒绝、
    │   │                                    #      单次转换、混合坐标空间）
    │   ├── test_action_policy_sanity_check.py  # （OCR 矛盾证据拒绝）
    │   ├── test_repeat_guard.py             # [修改，/speckit-analyze 补充：原大纲
    │   │                                    #      遗漏，tasks.md T008-T011/T014
    │   │                                    #      实际读写此文件] 真实事故重放、
    │   │                                    #      expected_effect+uncertain 零重复、
    │   │                                    #      effect_uncertain 零重复、可靠
    │   │                                    #      no_effect 允许一次重试、歧义 fail-safe
    │   ├── test_pos_bag_assertions.py       # [新增，/speckit-analyze 补充：原大纲
    │   │                                    #      遗漏，tasks.md T036/T037 实际
    │   │                                    #      读写此文件] OCR 噪声容忍的业务
    │   │                                    #      断言单元测试
    │   ├── test_recovery_no_destructive_actions.py  # 新失败模式、六字段策略、
    │   │                                    #      共享预算与无破坏性恢复
    │   ├── test_report_builder.py           # [修改] 新增身份/坐标审计字段断言
    │   │                                    #        （逐轮，FR-025/026）；[修改，
    │   │                                    #        /speckit-analyze 补充] 新增
    │   │                                    #        起始门禁/已发送动作清单/分类统计
    │   └── test_testcase_loader.py          # [修改] pos-buy-bag-checkout business
    │                                        #        模式加载校验
    │
    ├── unit/                                 # [新增测试]
    │   ├── test_no_auto_clear_action.py     #   （静态扫描：代码库无自动"クリア"点击）
    │   └── test_cli_start_state_confirmation.py  # [新增，/speckit-analyze 补充]
    │                                        #      --confirm-start-state 等参数
    │                                        #      正确写入 TestRun（FR-036/038）
    │
    └── e2e/                                  # [新增测试]
        ├── test_scenario_15_pos_bag_business_acceptance.py
        │                                      #   购物袋/小計/支付与 0.4669% effect
        └── test_start_state_precondition.py  #   匹配通过；不匹配/不可读零输入停止
```

**Structure Decision**：延续 001/002 的单一项目结构，不新建子包、不新建对外接口层。
本 feature 的两个核心修复点（动作身份/目标一致性、坐标空间协议）分别落在新增的
`execution/{action_identity,target_consistency}.py`（延续 002 `RepeatGuard` 已确立的
Executor 层归属）与新增的 `models/coordinate_space.py`（落在 Grounder 边界内，与
Grounder 定位职责一致），与宪法 Core Principle II 的四层划分保持一致，不新增第五层
职责。`runtime/agent_runtime.py` 只新增 `RepeatGuard.check()` 的入参，调用时机与
状态机转移表本身不变。

## Complexity Tracking

> Constitution Check 全部通过，无需登记任何违规或范围缩减。
