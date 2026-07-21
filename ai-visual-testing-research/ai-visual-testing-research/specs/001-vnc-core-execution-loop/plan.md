# Implementation Plan: VNC 黑盒 GUI 自动化测试核心执行闭环

**Branch**: `001-vnc-core-execution-loop` | **Date**: 2026-07-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-vnc-core-execution-loop/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes
the execution workflow. 本次为 2026-07-20 澄清会话（`/speckit-clarify`，5 个问题已解决，
见 spec.md 的 `## Clarifications`）之后的重新规划，以下内容已吸收全部澄清结论。

## Summary

在纯 VNC 黑盒条件下（只获取屏幕像素、只发送键鼠事件，被测机不可安装任何辅助程序）实现并验证
系统的第一个可运行纵向切片：观察屏幕 → 理解当前状态 → 选择动作 → 定位目标 → 执行动作 →
等待界面稳定 → 验证结果 → 保存证据。技术方案为一个自研的单进程 Python Agent Runtime：
显式异步状态机驱动整条闭环，且同一个 `TestStep` MAY 因 Planner 自主插入的前置微动作
（聚焦、滚动、关闭安全弹窗等）而多轮迭代"选择动作 → 定位 → 执行 → 等待 → 验证"，直到某轮
验证通过或用尽该步骤的 `max_retries`（Clarification 2026-07-20）；Planner（可替换的强
视觉/推理模型）只产出单个语义动作，不得自我宣布步骤完成，Action Policy 按"快捷键 → 焦点
导航 → OCR/模板 → MiMo-V2.5 Grounding → 停止并恢复"的优先级解析执行方式，Executor 通过
vncdotool 发送键鼠事件，Wait Engine 基于多帧比对判定页面稳定，Verifier 基于操作后独立
采集的新证据（而非执行/定位模型的自我判断）给出通过/失败/不确定——复合验证条件下
"不确定"具有传染性，不会被静默折叠为通过或失败；Grounding 的"目标未找到""整体置信度偏低"
"Top-1/Top-2 接近"三种情况分别归类但共用恢复引擎；VNC 断线重连成功后被中断的步骤 MUST
重新执行（从重新观察开始）。Recovery Engine 对已识别的失败类型执行有限次数的恢复策略，
所有重试与迭代共享同一个步骤级预算。每一轮迭代的完整决策与证据（截图、OCR、Grounding
候选、执行结果、等待结果、验证结果、恢复记录、模型原始响应、各阶段耗时）写入 SQLite 与
本地制品目录，运行结束后生成 JSON 与 HTML 报告；发往外部 Planner/Grounder 模型 API 的
截图不做敏感区域遮罩（遮罩仅用于本地持久化与报告展示，Clarification 2026-07-20），并为
未来的页面/元素记忆、Record-Replay 和视觉自进化预留数据结构（本功能只采集保存，不做
检索、回放或训练）。

## Technical Context

**Language/Version**: Python 3.12+

**Primary Dependencies**: vncdotool（VNC 键鼠与截图驱动，固定约束）；opencv-python + numpy
（截图差异、ROI 裁剪、稳定性判定、模板匹配的图像处理）；轻量 OCR（ONNX Runtime 推理的
文本检测/识别模型，例如 RapidOCR 一类的 ONNX 发行版，避免引入完整深度学习框架）；httpx
（异步调用 Planner 强模型 API 与 OpenCode Go API 上的 MiMo-V2.5 Grounder）；Pydantic v2
（领域模型与模型结构化输出校验）；PyYAML + pydantic-settings（测试用例与配置加载）；
SQLAlchemy 2.x（SQLite 持久化）；structlog（结构化 JSON Lines 日志）；Typer（CLI 入口）；
pytest（单元/离线截图/集成/端到端测试）

**Storage**: 单个 SQLite 数据库文件（测试运行、步骤、观察、动作、定位、执行、等待、验证、
恢复、视觉经验样本等记录）+ 本地文件系统制品目录（截图、标注图、模型请求/响应存档、
JSON/HTML 报告）。不引入 PostgreSQL、对象存储或分布式存储。

**Testing**: pytest。四类测试各司其职——① 纯函数单元测试（坐标换算、越界校验、多帧稳定性
判定、复合断言求值）；② 基于固定截图/固定响应的离线测试（OCR 解析、模板匹配、Grounding
响应解析、Verifier 各判定分支、Recovery 失败分类），不连接真实 VNC；③ 针对真实（或本地
测试用）VNC 服务的集成测试（连接、截图、键鼠、断线重连）；④ 端到端场景测试，覆盖验收场景
一至九。

**Target Platform**: 控制端——无独立显卡的普通 Windows/Linux 办公电脑，运行本 Agent 的单个
Python 进程；被测端——通过 VNC 暴露、分辨率与 DPI 固定的 Windows 10 桌面，不安装任何辅助
程序。

**Project Type**: 单一项目（single project）——一个可通过 CLI 驱动的 Python Agent Runtime
后端包；本功能不包含 Web 前端或对外 HTTP API（FastAPI 按总体设计推迟到 MVP 后半阶段，
不在本纵向切片范围内）。

**Performance Goals**: 默认单步超时 60s、单动作执行超时 10s、等待引擎默认超时 20s（可配置）；
截图节奏在页面不稳定时约 500ms 一帧、页面稳定后不做高频截图；Grounding 调用默认超时 30s、
Planner 调用默认超时 60s；系统非吞吐导向（不追求高 QPS），核心目标是单会话闭环的时延可控、
可预测、可配置。

**Constraints**: 不依赖独立显卡；不在本地运行大型视觉语言模型（重理解一律走远程模型 API）；
同一时刻仅维持一个 VNC 会话、执行一个测试任务；内存中仅保留最近 3～5 帧截图，原始截图立即
落盘；OCR/模板匹配优先限制在 ROI 内以控制 CPU 占用；VNC 密码与模型 API Key 不得以明文形式
写入配置文件或日志；Planner 组件必须可替换，不与特定模型供应商耦合；Agent Runtime 必须
自研，不借助 OpenCode Agent 或其他现成 Agent 框架作为运行核心。

**Scale/Scope**: 覆盖 spec.md 中的全部 10 个用户故事（P1 的 8 个闭环阶段 + P2 基础恢复 +
P3 面向未来自进化的数据采集），单机单会话单测试任务规模；不含多 VNC 并发、分布式调度、
Record-Replay 执行引擎、自愈补丁自动应用、页面/元素记忆的检索复用、模型训练——这些均已在
spec.md 的"本功能不包含"中明确排除，本计划的模块划分也不预先为其搭建复杂基础设施，仅保证
数据结构可被未来功能复用（对齐宪法 V. 受控自进化）。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution 条款 | 本功能的落实方式 | 结论 |
|---|---|---|
| I. 确定性运行时控制模型 | Agent Runtime 采用自研显式状态机（`CREATED→…→PASSED/FAILED/CANCELLED`）驱动闭环，含步骤内多轮 `ActionIteration` 的显式循环规则（data-model.md §12）；Planner 的 `task_completed_hint` 仅为提示，MUST NOT 决定状态迁移或步骤通过（Clarification 2026-07-20），真正的迁移判定仍由 Verifier 的独立结果驱动 | PASS |
| II. Planner/Grounder/Executor/Verifier 分离 | 模块划分为独立的 `planning/`（Planner + Action Policy）、`models/`（Grounder 客户端）、`execution/`（Executor）、`verification/`（Verifier）四层，Planner 输出语义动作而非坐标，Verifier 不采信 Planner/Grounder 自评（含 `task_completed_hint`） | PASS |
| III. 键盘优先，视觉点击兜底 | Action Policy 按”快捷键 → 焦点导航 → OCR/模板 → MiMo Grounding → 停止恢复”解析候选执行方案（对齐 spec 用户故事三），仅在确定性路径不可用时升级；同一步骤内的每一轮微动作迭代都独立重新走一遍该优先级，不因上一轮已升级到视觉定位而跳过后续轮次的键盘优先判断。宪法条款本身列出的 8 级优先链中”已验证回放动作”与”Win+R + PowerShell 配方”两级本切片不实现——原因见下方”动作安全分级 / PowerShell 黑盒配方”行（该两级功能超出本纵向切片范围，非对本条款的违反），并已在 Complexity Tracking 中登记为已知范围缩减 | PASS（范围内 5 级完整落实；缺失的 2 级见 Complexity Tracking） |
| IV. 观察-执行-验证独立闭环 | Verifier 基于动作执行后由 Perception Pipeline 重新采集的独立证据判定，`uncertain` 不视为通过、也不折叠为失败（复合断言下具有传染性，见 data-model.md §7）；执行结果与验证结果为两个独立数据实体；VNC 重连后 MUST 重新观察再验证，不复用断线前的证据（FR-039） | PASS |
| V. 受控自进化 | 本功能仅通过 `evolution/experience_collector.py` 采集 `VisualExperience` 记录并落库，不做检索、不做训练、不自动修改断言或回放脚本，与 FR-043/044 一致 | PASS |
| 黑盒边界 | 仅通过 `drivers/vncdotool_driver.py` 使用 vncdotool 收发像素与键鼠事件，不引入 UIA/pywinauto/WinRM/SSH/DOM/内部 API/文件系统/注册表访问 | PASS |
| 架构约束（模块化单体） | 单进程 Python 包，单 VNC 会话，单 SQLite 库，单本地制品目录；不引入 MCP、LangGraph、Temporal、Kafka、Kubernetes、分布式数据库或本地大型视觉模型 | PASS |
| 资源约束（弱配置电脑） | 仅保留最近 3～5 帧于内存、截图落盘后释放、OCR/模板匹配限定 ROI、页面稳定时不高频截图、遵循“确定性手段优先、能不升级到模型就不升级”的调用路由 | PASS |
| 动作安全分级 / PowerShell 黑盒配方 | 本纵向切片不包含 PowerShell 配方执行与 high 风险动作（重启/关机/系统配置等），相关分级机制留待后续功能引入时落实；本功能范围内不触碰该类风险动作 | N/A（超出本切片范围，非本功能违反） |
| 凭据与隐私 | 配置项 `FR-045/047` 要求 VNC 密码与模型 API Key 通过环境变量/系统凭据存储管理，测试日志与配置文件不落明文；截图支持敏感区域打码，遮罩仅作用于本地持久化与报告渲染两个出口，MUST NOT 应用于发往外部 Planner/Grounder 模型 API 的截图，团队已知悉并接受该权衡（FR-049，Clarification 2026-07-20） | PASS |
| 验证独立性门禁 | Verifier 的判定输入固定为“操作后新截图 + 独立证据”，代码评审可直接核对该数据流；Planner 的 `task_completed_hint` 不作为判定输入 | PASS |
| 恢复与重试门禁 | 每类 `FailureType` 在 `recovery/strategies.py` 中显式配置最大重试次数与冷却时间，禁止无限循环（FR-038）；步骤内微动作迭代与 VNC 重连后的整步重做（`restart_step`）均计入同一个 `TestStep.max_retries` 共享预算，不额外开辟无上限的迭代通道（Clarification 2026-07-20） | PASS |
| 测试覆盖门禁 | Project Structure 中的 `tests/` 覆盖单元、离线截图、VNC 集成、端到端四类，对应 Constitution 的测试覆盖门禁 | PASS |
| MVP 验收门禁 | spec.md 的 Success Criteria（SC-001~SC-010）与 Constitution 的 MVP 验收标准一一对应 | PASS |
| 制品与可观测性 | `storage/` + `reporting/` 落实完整运行轨迹、JSON/HTML 报告、structlog JSON Lines 日志 | PASS |

**结论**：Phase 0 研究前门禁全部通过；Core Principle III 的范围缩减已登记于 Complexity Tracking，不构成对 Constitution 的违反。

## Project Structure

### Documentation (this feature)

```text
specs/001-vnc-core-execution-loop/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   ├── cli-contract.md
│   ├── test-case-schema.md
│   ├── model-provider-contract.md
│   └── report-schema.md
├── checklists/
│   └── requirements.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

单一项目结构。仅包含支撑本闭环（观察→理解→选择动作→定位→执行→等待→验证→保存证据 +
基础恢复 + 自进化数据采集）所必需的子包；`overall_design.md` 第 6 节工程目录中与
Record-Replay 执行、页面/元素记忆检索、PowerShell 配方、HTTP API、技能库相关的目录本次
不创建，留待后续功能引入。

```text
vnc_agent/
├── pyproject.toml
├── config/
│   ├── agent.yaml            # runtime/vnc/perception 默认配置
│   ├── models.yaml           # Planner/Grounder 提供方与超时配置
│   └── vnc-targets.yaml      # VNC 连接信息（密码通过环境变量引用，不落明文）
│
├── src/vnc_agent/
│   ├── main.py
│   │
│   ├── runtime/               # 状态机、运行上下文、步骤调度、超时/重试/取消
│   │   ├── agent_runtime.py
│   │   ├── state_machine.py
│   │   ├── run_context.py
│   │   ├── step_controller.py
│   │   └── exceptions.py
│   │
│   ├── domain/                 # Pydantic 领域模型（对应 data-model.md）
│   │   ├── testcase.py
│   │   ├── observation.py
│   │   ├── action.py
│   │   ├── grounding.py
│   │   ├── verification.py
│   │   ├── recovery.py
│   │   └── run.py
│   │
│   ├── drivers/                # VNC 黑盒驱动（固定使用 vncdotool）
│   │   ├── base.py             # VNCDriver Protocol，便于未来替换驱动实现
│   │   ├── vncdotool_driver.py
│   │   └── key_mapping.py
│   │
│   ├── perception/              # 观察与结构化理解（用户故事二）
│   │   ├── pipeline.py
│   │   ├── screenshot.py
│   │   ├── screen_diff.py
│   │   ├── stability.py
│   │   ├── ocr/
│   │   ├── template/
│   │   └── structured_screen.py
│   │
│   ├── models/                  # 可替换的模型客户端（Planner/Grounder Protocol）
│   │   ├── provider.py          # ModelProvider 接口，Planner 可插拔的关键落点
│   │   ├── planner_client.py
│   │   ├── mimo_grounder.py      # 通过 OpenCode Go API 调用 MiMo-V2.5
│   │   └── response_parser.py
│   │
│   ├── planning/                 # 动作选择（用户故事三）
│   │   ├── planner.py
│   │   ├── action_policy.py      # 键盘优先/视觉兜底的候选执行方案排序
│   │   └── plan_validator.py
│   │
│   ├── execution/                 # 键鼠执行（用户故事五）
│   │   ├── router.py
│   │   ├── mouse_executor.py
│   │   └── keyboard_executor.py
│   │
│   ├── verification/              # 独立验证（用户故事七）
│   │   ├── engine.py
│   │   ├── ocr_verifier.py
│   │   ├── template_verifier.py
│   │   ├── screen_change_verifier.py
│   │   └── visual_verifier.py
│   │
│   ├── recovery/                   # 基础失败处理（用户故事八）
│   │   ├── classifier.py
│   │   ├── engine.py
│   │   └── strategies.py
│   │
│   ├── evolution/                   # 面向未来自进化的数据采集（用户故事十）
│   │   └── experience_collector.py
│   │
│   ├── storage/                      # SQLite + 制品目录
│   │   ├── database.py
│   │   ├── repositories.py
│   │   └── artifact_store.py
│   │
│   ├── reporting/                     # JSON/HTML 报告（用户故事九）
│   │   ├── report_builder.py
│   │   ├── html_report.py
│   │   └── json_report.py
│   │
│   └── api/
│       └── cli.py                     # Typer CLI 入口（本切片不含 HTTP API）
│
├── testcases/                          # 声明式测试用例样例（用户故事一）
├── templates/                          # 固定图片模板
├── data/                                # SQLite 数据库文件
├── artifacts/                            # 截图、报告、模型请求响应存档
│
└── tests/
    ├── unit/                              # 坐标换算、稳定性判定、复合断言等纯函数测试
    ├── fixtures/                           # 基于固定截图/固定响应的离线感知与解析测试
    ├── integration/                        # 真实/测试用 VNC 服务集成测试
    └── e2e/                                 # 对应验收场景一至九的端到端测试
```

**Structure Decision**：采用单一项目结构（非 Web 前后端分离、非移动端）。整个功能落地为一个
可通过 `vnc_agent.api.cli` 启动的 Python 包，`runtime/` 承载状态机与调度、`domain/` 承载
Pydantic 数据契约、`drivers/` 隔离 vncdotool 依赖以保留未来更换 VNC 驱动的可能、`models/`
以 Protocol 方式隔离 Planner/Grounder，满足 FR-046 的可替换要求；`planning/execution/
verification/recovery` 四个子包直接对应宪法第 II 条的四层职责分离；`evolution/` 仅做数据
采集，不实现检索或训练逻辑；`storage/reporting` 落实证据留存与报告生成。测试目录按宪法
“测试覆盖门禁”的四类测试分层组织。

## Complexity Tracking

> Constitution Check 全部通过；下表记录的是范围缩减而非违反——均在 spec.md Assumptions 中已明确排除，此处按 Governance 要求登记留痕，供后续功能引入 Record-Replay / PowerShell 配方时对照检查。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Core Principle III 的 8 级动作优先链中，"已验证回放动作"（Record-Replay）与"Win+R + PowerShell 配方"两级未在本切片的 Action Policy（FR-012/`planning/action_policy.py`）中实现，仅保留快捷键→焦点导航→OCR/模板→MiMo Grounding→停止恢复 5 级 | Record-Replay 执行引擎与 PowerShell 黑盒配方本身是独立于本次"核心执行闭环"纵向切片的后续功能（spec.md Assumptions 与 Constitution Check"动作安全分级 / PowerShell 黑盒配方"行已判定 N/A、超出本切片范围）；本切片的目标仅是验证"观察→…→保存证据"闭环本身是否可行，不要求一次性交付完整的 8 级优先链 | 若在本切片中一并实现，需要同时引入尚未设计的回放脚本存储格式与 PowerShell 配方白名单/风险策略机制，会显著扩大本次纵向切片的范围并推迟闭环可行性验证；待 Record-Replay 与 PowerShell 配方功能在后续迭代设计完成后，可在不改动本切片已交付接口的前提下，作为 Action Policy 优先级链中更高优先级的新增分支接入 |
