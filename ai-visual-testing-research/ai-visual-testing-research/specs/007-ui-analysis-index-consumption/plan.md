# Implementation Plan: 外部 UI 分析索引消费与通用索引生产规则

**Branch**: `007-ui-analysis-index-consumption` | **Date**: 2026-07-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/007-ui-analysis-index-consumption/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

本 feature 把"索引生产方"（外部 C#/Java/XAML/Web/Figma 等项目）与"索引消费方"（当前
vnc-agent）严格分离：vnc-agent 新增一个 `ui_index/` 模块，只负责读取、校验、查询外部项目
已生成的版本化 `ui-analysis-bundle-v1` 目录（`manifest.yaml` + `screens/elements/
transitions.jsonl` 必填、`flows/diagnostics.jsonl` 可选），把校验通过后的结构化控件知识
暴露给 testcase 编写（CLI 查询）与运行时 Planner/Grounder（可见语义提示，经既有
`ocr_candidates`/`template_candidates` 同构的候选通道注入 Grounder，绝不直接提供点击坐标）。
Verifier 与最终点击坐标计算完全不变——索引只新增一路"提示候选"，不新开任何绕过既有
Observe→Plan→Ground→Act→Verify 闭环的路径。技术方案不引入任何源码分析依赖，只新增纯数据
读取/校验代码；同时产出一个语言无关的通用 producer skill（`.agents/skills/
generate-ui-analysis-index/`），用规范性文档 + 空白模板/最小示例指导外部项目生成同构 bundle，
不附带任何具体语言的分析器实现。

## Technical Context

**Language/Version**: Python 3.12（复用 `vnc_agent/pyproject.toml` 现状 `requires-python = ">=3.12"`，不引入新语言/运行时）

**Primary Dependencies**: 复用现状依赖——`pydantic>=2`（bundle 记录模型 + 校验）、`PyYAML`
（`manifest.yaml`）、`typer`（CLI 子命令）、`structlog`（审计结构化日志，经既有
`runtime/telemetry.py::log_event()`）。**不新增任何第三方依赖**——JSONL 流式读取用标准库
`json`/文件迭代实现，sha256 用标准库 `hashlib`，不引入 jsonschema/Roslyn/MSBuildWorkspace/
JavaParser/TypeScript Compiler 等（Constitution 边界 + spec.md FR-017）。

**Storage**: 文件（生产方交付的只读 bundle 目录，vnc-agent 不写回）+ 复用既有 SQLite/JSON
Lines 审计路径（`domain/run.py::ActionIteration` 新增可选字段 + `runtime/telemetry.py`
结构化日志），不新增数据库表/schema 迁移。

**Testing**: `pytest` + `pytest-asyncio`（复用现状 `vnc_agent/tests/` 目录组织——扁平
`tests/unit/*.py`、`tests/integration/*.py`，新测试放入 `tests/unit/ui_index/`、
`tests/integration/ui_index/` 子目录，命名延续既有 `test_*.py` 惯例）。

**Target Platform**: 与现状一致——vnc-agent 运行的同一台弱配置 Windows/Linux 主机；本
feature 全部离线可测，不要求真实 VNC 会话（除既有集成/e2e 套件本身的要求外）。

**Project Type**: 单进程模块化单体（Constitution"架构约束"）内新增一个能力模块，不是
独立服务/独立部署单元。

**Performance Goals**: 校验/查询单个 bundle（数千条记录量级）在开发机上完成时间以秒计
（无硬性 SLA，spec.md 未要求实时性）；运行时 `build_hints()` 单次调用 MUST 快于既有 500ms
截图轮询间隔量级，不得成为步骤执行的显著瓶颈（定性目标，无 spec.md 强制数值）。

**Constraints**: 遵循 research.md §3 的资源上限默认值（单文件 ≤50MB/200,000 行，bundle 总量
≤200MB）；同时只处理一个已加载 bundle（与 Constitution"同时只处理一个 VNC 会话"的单一职责
原则一致，不支持多 bundle 并发查询场景）；不得引入本地大型视觉/语言模型做画面匹配（research.md
§9 选择纯文本重叠算法）。

**Scale/Scope**: 单个 bundle 典型规模——数十个 screen、数百个 element、数十个 transition；
两个跨场景验证 fixture（Web 表单 + 桌面多画面）规模远小于真实生产项目，仅需结构上代表不同
技术栈。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**I. 确定性运行时控制模型**：索引消费全过程（读取/校验/查询/画面匹配）是确定性代码路径，
不引入模型自主决策；唯一涉及"语义理解"的环节（Planner/Grounder 消费 hints）复用既有模型
调用路径，本 feature 不新增模型自主重试/自主判定通过的逻辑。✅ 通过。

**II. Planner/Grounder/Executor/Verifier 职责分离**：`ui_index_hints`/`ui_index_candidates`
分别只进入 Planner 输入与 Grounder 候选通道，不touch Executor/Verifier 的判定输入
（contracts/ui-index-consumer-interfaces.md §9）；Grounder 仍是唯一产出最终 bbox 的角色。
✅ 通过。

**III. 键盘优先，视觉点击兜底**：本 feature 不改变既有动作解析优先级顺序；`normalized_bounds`
只是 Grounder 候选融合中的一路新证据，不提升到比已验证回放动作/快捷键更高的优先级。✅ 通过。

**IV. 观察-执行-验证独立闭环**：FR-008/010/019 + contracts §9 明确 Verifier 输入不变；
`Transition.expected_*` 字段严格限定为"参考线索"，实现层面通过 §5 数据模型的字段集合与
Verifier 现状签名不变来保证（Verifier 函数签名本身不新增任何 `ui_index` 相关参数，天然
不可能被误用为判定依据）。✅ 通过。

**V. 受控自进化**：本 feature 不涉及回放自愈/模型训练/断言自动修改；bundle 是生产方交付的
静态制品，vnc-agent 只读，不产生"待审核补丁"类产出。✅ N/A（不适用，不违反）。

**VI. 业务无关核心与声明式场景隔离**：见下方 Domain-Agnostic Core gate。

**Domain-Agnostic Core gate（Principle VI）**：

- [x] 核心模块（新增 `ui_index/`，以及对 `domain/run.py`、`models/provider.py`、
      `config.py` 的增量修改）不包含任何业务专用字段/关键词/分支——`role`/
      `supported_actions`/`trigger_action` 均为开放 snake_case 字符串而非封闭业务枚举
      （research.md §8）；唯一的封闭枚举 `transition_type` 是纯 UI 结构概念
      （modal/replace/overlay/state_change），与任何具体行业无关。
- [x] 业务/场景语义（POS、Web 表单、桌面多画面等具体示例）只出现在
      `tests/fixtures/ui_index/`、`.agents/skills/generate-ui-analysis-index/assets/
      bundle-template/` 示例、quickstart.md 场景描述中，不出现在 `ui_index/` 源码或
      `data-model.md`/`contracts/*.md` 的字段定义里。
- [x] 通用能力（bundle 读取/校验/查询/运行时提示/审计）已规划至少两个互不相关 GUI fixture
      的跨场景契约测试（quickstart.md §五/§七/§十，spec.md SC-008/SC-011），非单一场景
      回归。

**结论**：Constitution Check 全部通过，无需 Complexity Tracking 例外记录。

## Project Structure

### Documentation (this feature)

```text
specs/007-ui-analysis-index-consumption/
├── plan.md                                  # 本文件
├── research.md                              # Phase 0 输出
├── data-model.md                            # Phase 1 输出
├── quickstart.md                            # Phase 1 输出
├── contracts/
│   ├── ui-analysis-bundle-v1.md             # 外部 bundle wire-format 契约（producer 权威依据）
│   └── ui-index-consumer-interfaces.md      # 消费方内部 Python 接口契约
├── checklists/
│   ├── requirements.md                      # /speckit-specify 产出
│   └── arch-pr-review.md                    # /speckit-checklist 产出
└── tasks.md                                 # Phase 2 输出（/speckit-tasks，不由本命令创建）
```

### Source Code (repository root)

本项目是单一 Python 包（`vnc_agent/`），不是 web/mobile 多项目结构，采用现状既有的
"Option 1: Single project" 布局的实际路径（不是模板占位符）：

```text
vnc_agent/
├── src/vnc_agent/
│   ├── ui_index/                     # 本 feature 新增模块
│   │   ├── __init__.py
│   │   ├── schema.py                 # data-model.md §1：Screen/Element/Transition/Flow/
│   │   │                             #   Diagnostic/Confidence/NormalizedBounds/NeighborRef/
│   │   │                             #   BundleManifest 等 Pydantic 模型
│   │   ├── errors.py                 # data-model.md §2：UiIndexErrorCode/ValidationIssue/
│   │   │                             #   ValidationReport
│   │   ├── manifest.py               # contracts/ui-index-consumer-interfaces.md §1
│   │   ├── jsonl_reader.py           # 同上 §2：流式 JSONL 读取
│   │   ├── validator.py              # 同上 §3：两遍遍历校验编排
│   │   ├── bundle.py                 # 同上 §4：UiIndexBundle 加载 + 查询服务
│   │   ├── sanitizer.py              # 同上 §5：VisibleElementHint allow-list 拷贝
│   │   ├── runtime_adapter.py        # 同上 §6：画面匹配 + hints/candidates/audit 组装
│   │   ├── audit.py                  # 同上 §7：审计记录写入（ActionIteration + 结构化日志）
│   │   └── cli.py                    # 同上 §8：Typer 子命令组，供 api/cli.py 挂载
│   ├── domain/run.py                 # 增量修改：ActionIteration.ui_index_audit
│   ├── models/provider.py            # 增量修改：PlannerRequest.ui_index_hints、
│   │                                 #   GroundingRequest.ui_index_candidates
│   ├── config.py                     # 增量修改：AgentConfig.ui_index / UiIndexConfig
│   ├── api/cli.py                    # 增量修改：挂载 ui_index/cli.py 的 Typer 子应用
│   ├── planning/planner.py           # 增量修改：PlannerOrchestrator.plan() 组装
│   │                                 #   ui_index_hints 进入 PlannerRequest（preflight
│   │                                 #   加载好的 bundle 由调用方注入，不在此处加载 I/O）
│   └── models/mimo_grounder.py       # 增量修改：候选融合纳入 ui_index_candidates
│                                     #   （复用既有 resolve_pixel_bbox() 换算路径）
└── tests/
    ├── unit/ui_index/                # schema 校验、query、sanitizer、错误矩阵单元测试
    ├── integration/ui_index/         # runtime_adapter 命中/未命中/不一致场景、审计集成
    └── fixtures/ui_index/            # 固定 bundle fixture（有效 + 逐类无效 + 两个跨场景 fixture）

.agents/skills/generate-ui-analysis-index/    # 本 feature 新增通用 producer skill
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── bundle-contract.md            # MUST 与 contracts/ui-analysis-bundle-v1.md 保持一致
│   ├── confidence-rules.md           # research.md §5/§8 的生产方指导版本
│   └── framework-examples.md         # 不同框架概念→通用 Screen/Element/Transition 映射示例
└── assets/
    └── bundle-template/
        ├── blank/                    # 空白模板骨架
        └── minimal-valid-example/    # 最小有效示例（quickstart.md §一 的验证对象）
```

**Structure Decision**: 新能力作为 `vnc_agent/src/vnc_agent/ui_index/` 独立模块加入现状
单体（与 `perception/`/`evolution/`/`models/` 等既有非核心枚举模块同级），不新建独立仓库/
独立部署单元；对既有核心模块（`domain`/`models`/`config`/`api`/`planning`）的改动均为
"新增可选字段/新增可选参数"，不修改任何既有字段语义或既有函数签名的必填参数列表，从类型
系统层面保证 FR-011（未配置索引时行为完全一致）。Producer skill 位于仓库既有
`.agents/skills/` 目录下，与 `vnc-agent-testcase-authoring`、`speckit-*` 等既有 skill 同级。

## Complexity Tracking

> Constitution Check 全部通过，无违规需要论证，本节为空。
