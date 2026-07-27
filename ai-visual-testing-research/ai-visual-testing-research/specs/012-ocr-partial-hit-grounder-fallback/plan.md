# Implementation Plan: OCR 可疑命中转 Grounding 兜底

**Branch**: `012-ocr-partial-hit-grounder-fallback` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/012-ocr-partial-hit-grounder-fallback/spec.md`

## Summary

在 `planning/action_policy.py` 第 3 优先级（Unique OCR / template localization）加入可疑命中
检测：唯一 OCR 命中满足 R-A2（非精确包含）/ R-B（confidence < 0.85 可配置）/ R-C（可比长度
≤ 1）任一时不返回坐标，resolve 落入既有 grounding 路径（`needs_grounding=True`），PolicyResult
携带 `OcrSuspicion` 观测数据并打 INFO 日志；无命中但唯一真子串 item 时补充 `truncated_ocr_read`
观测数据（R-A1）。精确高置信命中、keyboard/focus、模板路径、grounding 防线全部零改动。

## Technical Context

**Language/Version**: Python 3.11+（既有项目约束）

**Primary Dependencies**: pydantic（配置模型）、pytest（测试）；不新增依赖

**Storage**: N/A（OcrSuspicion 仅为运行时 dataclass + 日志，不新增持久化实体）

**Testing**: `uv run pytest tests/unit tests/fixtures -q`（基线 762 passed）、
`uv run pytest tests/e2e -q`（基线 40 passed，离线 FakeVNC/Stub）

**Target Platform**: 与主项目一致（Windows/本地单进程 Agent）

**Project Type**: 单体 Python 库/CLI（vnc_agent/）

**Performance Goals**: 精确高置信命中路径新增模型调用 = 0；可疑命中路径复用既有 grounding
调用（不新增额外调用次数）

**Constraints**（改动范围纪律，来自任务书）:

- 核心改动限于 `planning/action_policy.py` 的 `_unique_ocr_or_template` 及其新增辅助函数、
  `resolve` 第 3 步分支（含落入 grounding 时对 suspicion 的携带）、`config.py`、
  `config/agent.yaml`、tests、specs。
- MUST NOT 改动坐标计算表达式（`(b[0]+b[2])//2` 等行，含 `_executable_from_candidate` /
  `_from_grounding` 内）——Feature 013（safe-click-point）并行改动区。
- MUST NOT 改动 `runtime/`、`recovery/`、`perception/`、`verification/`、
  `models/mimo_grounder.py`；`_consistent_with_unique_ocr` 与置信度门限/gap 逻辑零改动。

**Scale/Scope**: 单文件核心逻辑 + 配置字段 + 测试；预计 < 150 行核心 diff

## Constitution Check

| Constitution 条款 | 本功能的落实方式 | 结论 |
|---|---|---|
| I. 确定性运行时控制模型 | 可疑判定是纯函数规则（文本比较 + 阈值 + 长度），确定性可复现；不新增模型自主权，只是把低可信证据从"直点"降级到既有 grounding 状态机路径 | PASS |
| II. 职责分离 | 只影响 Grounder 介入时机（Policy 内部优先级判定）；Planner/Executor/Verifier 无涉；Grounder 请求契约不变 | PASS |
| III. 键盘优先 | resolve 第 1/2 步（keyboard/focus）零改动；第 3 步内部从"不可信直点"降级到第 4 步 grounding，优先级序不变 | PASS |
| IV. 独立闭环 | 不涉及验证语义；点击更准反而减少假失败 | PASS |
| V. 受控自进化 | 不修改基线、不写经验数据 | PASS |
| VI. 业务无关核心 | 判定仅用通用文本/置信度/长度证据；原因码为通用证据语义词；可比文本剥除的是通用装饰标点集而非业务词表；测试用两个互不相关场景词汇参数化 | PASS |
| 恢复与重试门禁 | 不新增重试路径；可疑命中转 grounding 走既有单次 grounding 调用与既有 recovery 预算 | PASS |
| 测试覆盖门禁 | 单元（规则表逐条）+ fixtures（跨场景）+ 既有 e2e 回归门禁 | PASS |

**Domain-Agnostic Core gate (Principle VI)**:

- [x] 核心模块不新增业务专用字段/关键词/流程分支。
- [x] 业务词汇仅出现在测试 fixture 输入中。
- [x] 通用能力以两个互不相关 GUI 场景（日文 POS 按钮流 / 英文表单提交流）参数化验证。

## Phase 0: Research（决策与备选方案）

### R1. 截断证据的可达形态（规则 R-A1/R-A2 拆分）

- **Decision**: 字面需求"OCR 文本 ⊂ target.text"在包含匹配（needle ⊆ OCR 文本）下不可能成为
  唯一命中，只能表现为 miss → 已落 grounding。因此拆为：R-A1（miss + 唯一真子串 item，仅补
  观测数据，行为不变）与 R-A2（唯一命中但非精确相等 → 拦截转 grounding）。
- **Alternatives considered**: 把真子串 item 提升为"命中"再拦截——会扩大命中判定面、
  影响模板分支互斥关系，且行为收益为零（最终同样落 grounding），拒绝。仅实现字面规则——
  规则成为死代码，无法覆盖并读/回显残留形态，拒绝。

### R2. 精确性比较用"可比文本"（首尾装饰标点剥除）

- **Decision**: `strip().lower()` 后再 `strip(装饰标点集)`；集合为通用 ASCII/CJK 引号、
  括号、句读、间隔号等，模块常量。仅影响可疑判定的相等比较，不改包含匹配本身。
- **Alternatives considered**: 直接用 `normalized_text` 相等——「【ログイン】」类纯装饰
  差异会被 R-A2 误伤，凭空增加模型调用，违反"最小扰动"目标；引入编辑距离/相似度——
  超出需求且引入调参面，拒绝。

### R3. 阈值配置与注入

- **Decision**: `config.py::PlanningConfig` 新增 `ocr_direct_click_min_confidence: float =
  Field(default=0.85, ge=0.0, le=1.0)`；`config/agent.yaml` planning 段同步声明 0.85；
  `ActionPolicy.__init__` 新增同名 kwarg（默认 0.85，双端同源）。
- **Deviation**: 运行时装配点 `runtime/agent_runtime.py`（ActionPolicy 构造处）属本 feature
  冻结区；yaml 自定义覆盖值的接线（1 个 kwarg）作为后续一行级任务遗留，默认部署行为双端
  一致——与已合入的 011 R3 同型处理。记入 Complexity Tracking。

### R4. suspicion 的承载与传递

- **Decision**: `action_policy.py` 内新增 `@dataclass OcrSuspicion`；`PolicyResult` 增加
  `ocr_suspicion: OcrSuspicion | None = None` 字段。resolve 第 3 步未命中直点后计算一次
  suspicion：`grounding_result is None` 时随 `needs_grounding=True` 返回并打 INFO 日志
  （只在首轮打，二轮带 grounding_result 时不重复），二轮把 suspicion 附到
  `_from_grounding` 的返回对象上（不进入该函数内部）。grounder 候选提示复用运行时现状
  （全部 `screen.ocr_items` → `ocr_candidates`），零 runtime 改动。
- **Alternatives considered**: 改 runtime 只传可疑命中项——冻结区且缩小 grounder 上下文，
  拒绝；把 reasons 塞进日志字符串不进 PolicyResult——报告/断言不可达，违反 FR-005，拒绝。

### R5. 混合分支（唯一 OCR + 唯一模板）

- **Decision**: OCR 可疑时选模板 bbox（像素证据，仍直点、零模型调用）；OCR 可信时维持
  confidence 择优。
- **Alternatives considered**: 一律转 grounding——把本可零成本的像素级确定性定位降级为
  模型调用，违反 FR-003 精神，拒绝。

## Phase 1: Design

### 数据/契约变更

1. `PlanningConfig.ocr_direct_click_min_confidence`（默认 0.85，[0,1]）；`agent.yaml`
   planning 段同步。
2. `PolicyResult.ocr_suspicion: OcrSuspicion | None = None`（dataclass 默认字段，向后兼容）。
3. `ActionPolicy.__init__(..., ocr_direct_click_min_confidence: float = 0.85)`。

### `action_policy.py` 改动点

1. 模块级：`logger = logging.getLogger(__name__)`、装饰标点常量 `_DECOR_CHARS`、
   `_comparable_text(s)` 纯函数、`OcrSuspicion` dataclass、原因码常量。
2. `_find_unique_hits(target, screen)`：从 `_unique_ocr_or_template` 提取的命中收集辅助
   （needle 计算 + ocr_hits/tmpl_hits 过滤，逻辑逐字保留），供直点判定与 suspicion 计算复用。
3. `_ocr_hit_suspicion_reasons(needle, item) -> list[str]`：R-A2/R-B/R-C 规则表实现。
4. `_unique_ocr_or_template`：唯一 OCR 分支先查 reasons，非空 → return None；混合分支
   reasons 非空 → pick 模板 bbox。**坐标表达式行逐字节不动**。
5. `_ocr_suspicion_for(target, screen) -> OcrSuspicion | None`：唯一命中被拦截 → 携带
   reasons；无命中且唯一真子串 item（可比长度 ≥ 2）→ `truncated_ocr_read`。
6. `resolve` 第 3/4 步衔接：`unique is None` 后计算 suspicion；首轮（无 grounding_result）
   打 INFO 日志并随 needs_grounding 返回；二轮附到 `_from_grounding` 返回对象。

### Project Structure

#### Documentation (this feature)

```text
specs/012-ocr-partial-hit-grounder-fallback/
├── spec.md
├── plan.md              # 本文件（research 并入 Phase 0）
├── tasks.md
├── quickstart.md
└── checklists/requirements.md
```

#### Source Code (repository root: ai-visual-testing-research/ai-visual-testing-research)

```text
vnc_agent/
├── config/agent.yaml                          # [修改] planning 段新增阈值
├── src/vnc_agent/
│   ├── config.py                              # [修改] PlanningConfig 新字段
│   └── planning/action_policy.py              # [修改] 可疑命中检测 + OcrSuspicion
└── tests/
    ├── unit/test_action_policy_ocr_suspicion.py   # [新增] 规则表/豁免/配置单元用例
    ├── unit/test_action_policy_priority.py        # [不改] 既有优先级回归
    ├── fixtures/test_action_policy_sanity_check.py # [不改] grounding 防线回归
    └── e2e/                                       # [不改] 回归门禁
```

**Structure Decision**: 单体项目既有结构，测试新增独立文件避免并行冲突。

## Complexity Tracking

| Violation / Deviation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| yaml 自定义阈值未接线到 runtime 装配点（默认值双端同源 0.85） | `runtime/agent_runtime.py` 属本 feature 冻结区（并行冲突面）；接线是 1 处调用点 1 个 kwarg 的机械后续任务 | 直接改 runtime —— 违反任务书改动范围纪律 |
| resolve 第 4 步入口两行微调（suspicion 附加） | FR-005 要求 PolicyResult 可观测；不进入 `_from_grounding` 内部、不触碰坐标表达式 | 只写日志不进 PolicyResult —— 报告/断言不可达，违反 FR-005 |
