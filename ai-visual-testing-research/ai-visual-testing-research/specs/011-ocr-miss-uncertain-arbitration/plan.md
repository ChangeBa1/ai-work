# Implementation Plan: OCR 漏读弱否定证据仲裁（FR-010 语义修订）

**Branch**: `011-ocr-miss-uncertain-arbitration` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/011-ocr-miss-uncertain-arbitration/spec.md`

## Summary

修订 `verification/business_resolver.py` 中 002 FR-010 的 deterministic-over-visual 仲裁：
把确定性否定证据分为弱否定（`text_appears` 未命中）与强否定（`text_disappears`/模板失败/
错误弹窗/no_effect），当确定性 failed 全部由弱否定构成、且视觉复核确认 `visual_question`
回答 passed 且 confidence ≥ 可配置阈值（默认 0.8）、且 `action_effect=expected_effect`
三条同时成立时，最终态判 `passed` 并携带 `weak_ocr_miss_overridden_by_visual` 可审计标记、
保留 `failed_conditions`。其余场景全部维持 002 行为。

## Technical Context

**Language/Version**: Python 3.11+（既有项目约束）

**Primary Dependencies**: pydantic（配置/领域模型）、pytest + pytest-asyncio（测试）；不新增依赖

**Storage**: N/A（不新增持久化实体；reason/failed_conditions 沿既有 VerificationResult 走既有轨迹/报告）

**Testing**: `uv run pytest tests/unit tests/fixtures -q`、`uv run pytest tests/e2e -q`（离线，FakeVNC/Stub 模型）

**Target Platform**: 与主项目一致（Windows/本地单进程 Agent）

**Project Type**: 单体 Python 库/CLI（vnc_agent/）

**Performance Goals**: 每次步骤结果解析新增模型调用 ≤ 1 次，且仅在仲裁候选场景发生（SC-005）

**Constraints**（改动范围纪律，来自任务书）:

- 核心改动限于 `verification/business_resolver.py`（`_deterministic_wins` / `_partition_statuses` /
  FR-010 应用段）、`domain/verification.py`（如需字段）、`config.py` + `config/agent.yaml`、tests、specs。
- MUST NOT 改动 `verification/engine.py` 的 visual_question 调用链路、`verification/visual_verifier.py`、
  `perception/cache.py`（并行 feature 正在给 describe_screen 加缓存）、`runtime/`、`perception/ocr/`。
- `business_resolver.py` 无关区域保持零 diff（不重排/不重格式化）。

**Scale/Scope**: 单文件核心逻辑修订 + 配置模型 + 测试；预计 < 200 行核心 diff

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution 条款 | 本功能的落实方式 | 结论 |
|---|---|---|
| I. 确定性运行时控制模型 | 仲裁是 `business_resolver` 内代码状态机的确定性规则（类型级证据分级 + 三条件合取）；模型只回答用例声明的 `visual_question`，不决定最终判定，判 `passed` 由代码规则做出且可复现 | PASS |
| II. 职责分离 | 仅 Verifier 侧解析逻辑变化；Planner/Grounder/Executor 无涉；Verifier 仍不凭 Planner/Grounder 自评放行——采信的是独立视觉复核 + 像素级 action_effect | PASS |
| III. 键盘优先 | 不涉及动作解析路径 | PASS |
| IV. 独立闭环 | 覆盖判定的三条证据全部来自操作后独立采集的截图（action_effect 像素对比、visual_question 对 after 画面的问答、复核确认调用同画面）；`uncertain` 不得作为通过的语义不变（spec FR-008），本仲裁只处理 failed-vs-passed 冲突 | PASS |
| V. 受控自进化 | 不修改断言、不生成补丁、不写经验数据 | PASS |
| VI. 业务无关核心 | 分级仅基于通用断言类型（`text_appears` 等）与通用效果状态；标记词 `weak_ocr_miss_overridden_by_visual` 为通用证据语义；新增配置为通用阈值；测试含两个互不相关场景词汇（表单保存流/图标菜单流）参数化 | PASS |
| 恢复与重试门禁 | 复核调用有硬上限（每次解析 ≤1 次，仅候选场景）；无新增重试路径；反而消除一类无意义重试源 | PASS |
| 验证独立性门禁 | 见 IV；复核调用的 question 是用例声明的业务问题原文，非模型自评 | PASS |
| 测试覆盖门禁 | 单元（分级/聚合不变式）+ 基于固定输入的离线解析测试（fixtures）+ 既有 e2e 11/12/13 回归 | PASS |

**Domain-Agnostic Core gate (Principle VI)**:

- [x] 核心模块不新增业务专用字段/关键词/流程分支（仅通用断言类型集合与通用阈值配置）。
- [x] 业务词汇仅出现在测试 fixture 输入中。
- [x] 通用能力以两个互不相关 GUI 场景（表单保存流 / 图标菜单流）参数化验证（tests/fixtures/test_business_resolver.py 跨场景参数化用例）。

## Phase 0: Research（决策与备选方案）

### R1. 最终态 `passed` vs `uncertain`

- **Decision**: `passed`（带 `weak_ocr_miss_overridden_by_visual` 标记 + 保留 failed_conditions）。
- **Rationale / Alternatives considered**: 见 spec.md「关键决策记录·决策 1」。`uncertain` 备选被否决：
  §9.9 下 uncertain 必然触发更强验证/恢复，而 OCR 漏读可复现，escalation 的确定性复检注定再次
  失败，假失败与无意义重试原样保留，feature 目标（消除该形态假失败）不成立。
- **Note**: e2e `test_uncertain_propagation.py` 与 scenario 12 的 uncertain 语义不受影响——本仲裁
  从不产生也不消费 `uncertain`。

### R2. 置信度获取：复核确认调用（不动 engine 链路）

- **Decision**: `visual_question` 逐条置信度未随 `VerificationResult` 结构化透出，而透出需要改
  `verification/engine.py`/`visual_verifier.py`（被并行 feature 冻结）。仲裁候选场景下由
  `business_resolver` 直接用原 `visual_question` 问题发一次 `describe_screen(answer_question)`
  复核，取 `VisionUnderstandingResponse.confidence` 做阈值判定。
- **Alternatives considered**:
  - 在 engine/visual_verifier 透传 confidence —— 违反改动范围纪律（并行 feature 冲突面）。
  - 从 reason 字符串反解析 confidence —— engine 未写入，且字符串反解析脆弱。
  - 复核调用的额外收益：推翻确定性 failed 前的第二次独立视觉确认；两次回答不一致时 fail-safe
    维持旧规则。调用预算与 002 契约同型（每次解析至多一次可选视觉调用；候选场景 status=failed
    与既有 escalation 的 uncertain 入口互斥，总量不叠加）。
- **Planner 来源**: `resolve_step_result` 的 `planner` 形参，缺省回退 `engine.planner`（运行时两者同一实例）。

### R3. 阈值配置与注入

- **Decision**: `config/agent.yaml` 新建 `verification:` 段 + `config.py::VerificationConfig`
  （`visual_override_confidence_threshold: float = 0.8`，[0,1] 校验），并入 `AgentConfig.verification`。
  `resolve_step_result` 新增可选形参 `visual_override_confidence_threshold: float | None = None`，
  None 时取 `VerificationConfig()` 默认值（单一事实来源）。
- **Deviation**: 运行时调用点在 `runtime/agent_runtime.py`（本 feature 冻结区），yaml 自定义覆盖值
  的接线（两处调用点各加一个 kwarg）作为后续一行级任务遗留；默认值双端同源（0.8），默认部署行为
  一致。记入 Complexity Tracking。

### R4. 分级集合的实现形态

- **Decision**: `business_resolver` 内新增 `WEAK_NEGATIVE_TYPES = frozenset({"text_appears"})`
  模块常量 + 纯函数判定"失败条目是否全部为弱否定"；不改 `aggregate_conditions()`（001/002 语义、
  `tests/unit/test_verification_compound.py` 既有覆盖不动），仲裁仍是聚合之上的策略层（与 002
  research §8 的分层决策一致）。`domain/verification.py` 不需要新字段（标记走 reason +
  failed_conditions 保留，避免扩散 schema 变更面）。

## Phase 1: Design

### 数据/契约变更（data-model 级）

1. `AgentConfig` 新增 `verification: VerificationConfig`；`VerificationConfig.visual_override_confidence_threshold`
   默认 0.8，Field(ge=0.0, le=1.0)。`config/agent.yaml` 增加对应段与注释。
2. `VerificationResult` schema 不变。新增语义约定：`status="passed"` 且 reason 含
   `weak_ocr_miss_overridden_by_visual` 时，`failed_conditions` 保留被覆盖的弱否定条目
   （既有报告渲染按原字段展示，无渲染变更）。

### `business_resolver.py` 改动点（仅 FR-010 应用段及其辅助函数区）

1. 常量区：`WEAK_NEGATIVE_TYPES`；阈值缺省解析辅助。
2. 新增私有辅助（放在 `_deterministic_wins` 附近）：
   - `_failed_deterministic_all_weak_negative(spec, engine_result) -> bool`：复用
     `_partition_statuses` 的 label 规则，检查确定性桶中全部 failed 条目类型 ∈ WEAK_NEGATIVE_TYPES
     且至少一条。
   - `async _weak_miss_visual_override(spec, engine_result, det, vis, action_effect, screen, planner, threshold) -> VerificationResult | None`：
     三条件门 + 复核调用 + fail-safe；命中返回 `passed` 副本（标记 reason、保留 failed_conditions）。
3. 主流程 FR-010 应用段（原 229–241 行）：`conflict == "failed"` 时先尝试
   `_weak_miss_visual_override`，命中则采用覆盖结果；未命中走原 `deterministic_overrides_visual`
   分支（reason 文本不变）。escalation 内部与 conflict2 处不改（该两处按状态机不可能出现
   "确定性弱否定 failed + 声明视觉 passed"组合，research R2 与 spec Edge Cases 已论证）。
4. 其余区域零 diff。

### Project Structure

#### Documentation (this feature)

```text
specs/011-ocr-miss-uncertain-arbitration/
├── spec.md
├── plan.md              # 本文件（research 已并入 Phase 0 节）
├── tasks.md
├── quickstart.md
└── checklists/requirements.md
```

#### Source Code (repository root: ai-visual-testing-research/ai-visual-testing-research)

```text
vnc_agent/
├── config/agent.yaml                          # [修改] 新增 verification 段
├── src/vnc_agent/
│   ├── config.py                              # [修改] VerificationConfig + AgentConfig.verification
│   └── verification/business_resolver.py      # [修改] FR-010 应用段 + 弱否定仲裁辅助函数
└── tests/
    ├── unit/test_verification_compound.py     # [修改] 聚合不变式保持 + 弱否定分级/阈值配置单元用例
    ├── fixtures/test_business_resolver.py     # [修改] 仲裁判定表用例（新行为/强否定/低置信/no_effect/跨场景）
    └── e2e/                                   # [不改] scenario 11/12/13 作为回归门禁
```

**Structure Decision**: 单体项目既有结构，无新目录。

## Complexity Tracking

| Violation / Deviation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| yaml 自定义阈值未接线到 runtime 调用点（默认值双端同源 0.8） | `runtime/agent_runtime.py` 属本 feature 冻结区（并行 feature 冲突面）；接线是 2 处调用点各 1 个 kwarg 的机械后续任务 | 直接改 runtime —— 违反任务书改动范围纪律 |
| 仲裁候选场景新增 1 次 describe_screen 复核调用 | engine 置信度透出链路被冻结；复核同时充当推翻前的二次独立确认 | 改 engine/visual_verifier 透传 confidence —— 同上冻结区 |
