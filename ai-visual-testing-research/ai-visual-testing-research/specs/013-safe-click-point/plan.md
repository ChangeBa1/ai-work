# Implementation Plan: 安全点击点计算（safe-click-point）

**Branch**: `013-safe-click-point` | **Date**: 2026-07-26 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/013-safe-click-point/spec.md`

## Summary

把 ActionPolicy 两处机械 bbox 中心点击坐标（`_unique_ocr_or_template` 三处
`(b[0]+b[2])//2`、`_executable_from_candidate` 的 `cand.center()`）替换为独立纯函数
`safe_click_point`：以 bbox 中心为基准，四边内缩 `edge_inset_ratio`（默认 0.15，配置
`click.edge_inset_ratio`）形成安全区，在安全区固定网格上确定性地选择不落入任何 sibling
bbox 的点；无法完全避开时选重叠深度最小的点并以伴随元数据 `residual_overlap=True` 标注；
提供 `screen_resolution` 时 clamp 到屏幕内。`ExecutableAction.target_region` 保持原始
bbox 不变，只有 `coordinates` 改变。「避开 OCR 文字外溢区域」降级为由重叠规避覆盖
（spec C-002/FR-011）。

## Technical Context

**Language/Version**: Python 3.12（uv 管理，项目根 `vnc_agent/`）

**Primary Dependencies**: 标准库即可（`typing.NamedTuple`、纯算术）；pydantic 仅用于
`config.py` 的 `ClickConfig` 配置模型

**Storage**: N/A（纯计算，无持久化）

**Testing**: pytest（`uv run pytest tests/unit tests/fixtures -q`、`uv run pytest tests/e2e -q`）

**Target Platform**: 与现有 agent 一致（Windows 本地单进程）

**Project Type**: 既有单体库内的新纯函数模块 + 两处接线

**Performance Goals**: 单次计算 O(网格点数 × siblings 数)，网格 ≤ 9×9=81 点，微秒级；
每次动作解析至多调用一次，无性能风险

**Constraints**: 纯函数、无 I/O、无随机源、确定性输出（回放一致性）；改动边界受并行
feature 012 约束（见下）

**Scale/Scope**: 新模块约 150 行 + action_policy.py 内约 20 行改动 + 配置 2 处 + 测试

### 并行开发改动边界（硬约束）

- 只允许改：`src/vnc_agent/planning/click_point.py`（新建）、
  `src/vnc_agent/planning/action_policy.py`（仅坐标计算表达式所在行与函数签名透传）、
  `src/vnc_agent/config.py`、`config/agent.yaml`、tests、specs 文档。
- 禁止改：`_unique_ocr_or_template` 的命中判定逻辑（feature 012 领地）；
  `runtime/`、`recovery/`、`perception/`、`verification/`、`execution/`、`models/`。
- `runtime/agent_runtime.py` 中 `ActionPolicy(...)` 的配置透传一行留作集成跟进
  （spec C-004）；构造默认值与 yaml 默认值一致（0.15），运行时行为无偏差。

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **Principle I（确定性运行时控制）**：safe_click_point 为确定性纯函数（固定网格 +
      全序决胜），无模型参与，同输入同输出，回放/审计一致。PASS。
- [x] **Principle II（职责分离）**：只改 Executor 之前的坐标选点（planning 层），不触碰
      Planner/Grounder/Verifier 判定；Grounder 输出的 bbox 与置信度语义不变。PASS。
- [x] **Principle III（键盘优先）**：不改变优先级链，仅影响已经落到 OCR/模板/Grounding
      鼠标路径后的"点哪里"。PASS。
- [x] **Principle IV（独立验证闭环）**：`target_region` 保持原始 bbox，验证证据语义零变化。PASS。
- [x] **Principle V（受控自进化）**：不涉及。PASS。
- [x] **Principle VI（业务无关核心）**：
  - [x] 新增代码全部是通用几何（bbox、内缩比例、重叠深度），无任何业务字段/关键词。
  - [x] 配置项 `click.edge_inset_ratio` 是通用几何参数。
  - [x] 跨场景验证：接线测试用两个互不相关 GUI 场景词汇（表单按钮流 / 图标菜单流）构造
        相同几何关系断言行为一致（spec US2-AS4）。
- [x] **工程约束**：无新依赖、无新进程/模型、无截图存储变化；测试覆盖门禁由"坐标转换/
      边界计算单元测试 + 离线策略接线测试"满足。PASS。

**Post-Phase-1 re-check**: 设计未引入新违规，全部 PASS，Complexity Tracking 为空。

## Project Structure

### Documentation (this feature)

```text
specs/013-safe-click-point/
├── spec.md
├── plan.md              # 本文件
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── checklists/
│   └── requirements.md
└── tasks.md             # /speckit-tasks 输出
```

### Source Code (repository root: `vnc_agent/`)

```text
src/vnc_agent/
├── planning/
│   ├── click_point.py         # 新建：safe_click_point 纯函数 + SafeClickPoint
│   └── action_policy.py       # 改：两处坐标表达式 + __init__/内部签名透传
└── config.py                  # 改：新增 ClickConfig（edge_inset_ratio）

config/
└── agent.yaml                 # 改：新增 click: edge_inset_ratio: 0.15

tests/
├── unit/
│   ├── test_click_point.py            # 新建：纯函数单测
│   └── test_action_policy_click_point.py  # 新建：策略接线测试（跨场景）
└── unit/test_config_click.py          # 新建：配置默认值与校验
```

**Structure Decision**: 沿用现有单体结构；纯函数放 `planning/`（与消费方
`action_policy.py` 同层，见 spec C-001）。无外部接口变化 → 不生成 `contracts/`
（`ExecutableAction` 契约字段不变，仅 `coordinates` 取值变化）。

## 设计要点（Phase 1 摘要）

1. **safe_click_point 算法**（详见 data-model.md）：
   - 安全区：`inset_x = round(w * ratio)`、`inset_y = round(h * ratio)`；某轴内缩后为空
     （`x1+inset_x > x2-inset_x`）则该轴退化为中心坐标。
   - 候选网格：每轴在安全区上取至多 9 个等距整数采样点（含中心与安全区端点，去重排序），
     两轴笛卡尔积。
   - 过滤 siblings：仅保留与 bbox 相交且非退化的 sibling；点含于 sibling 用闭区间。
   - 评分：`overlap_depth(p) = Σ_s min(p.x-s.x1+1, s.x2-p.x+1, p.y-s.y1+1, s.y2-p.y+1)`
     （对包含 p 的 sibling 求逃逸距离并求和）；排序键
     `(overlap_depth, dist²_to_center, y, x)` 取最小。
   - clamp：提供分辨率时把最终点 clamp 到 `[0,w-1]×[0,h-1]`（与 bbox 交集内）。
   - 返回 `SafeClickPoint(x, y, residual_overlap)`（NamedTuple）。
2. **action_policy 接线**：
   - `_unique_ocr_or_template(target, screen)`：三处返回点改为
     `safe_click_point(picked_bbox, siblings=其余命中 bbox, screen_resolution=screen.resolution,
     edge_inset_ratio=self.click_edge_inset_ratio)`；命中判定分支结构逐字不动。
   - `_executable_from_candidate(...)` 增加 `resolution` 参数（由 `_from_grounding` 传
     `screen.resolution`），坐标改为 `safe_click_point(cand.bbox, siblings=其余 in_bounds
     候选 bbox, ...)`。
   - `ActionPolicy.__init__` 新增 `click_edge_inset_ratio: float = 0.15`。
3. **配置**：`ClickConfig(edge_inset_ratio: float = Field(default=0.15, ge=0.0, lt=0.5))`；
   `AgentConfig.click`；`agent.yaml` 新增 `click:` 段。

## Complexity Tracking

无 Constitution 违规，无需记录。
