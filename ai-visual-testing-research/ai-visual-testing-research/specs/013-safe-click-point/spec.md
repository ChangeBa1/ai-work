# Feature Specification: 安全点击点计算（safe-click-point）

**Feature Branch**: `013-safe-click-point`

**Created**: 2026-07-26

**Status**: Draft

**Input**: User description: "替换 ActionPolicy 中机械 bbox 中心点击坐标：按 overall_design.md §9.6
的安全点击点规则（优先点击 bbox 中心附近 / 避开边缘 15% / 避开 OCR 文字外溢区域 / 避开与其他
候选重叠区域），提供纯函数 safe_click_point(bbox, siblings, screen_resolution)，边缘内缩比例
可配置（默认 0.15），必要时做屏幕边界 clamp，确定性输出以保证回放一致性。"

## 背景与动因

总体设计 `overall_design.md` §9.6 明确要求："点击点默认使用 bbox 内部安全点，而不是机械
中心点"。当前实现（feature 001~011 合入后）在两处仍然是机械 bbox 中心：

1. `planning/action_policy.py::_unique_ocr_or_template` — 三处 `(b[0]+b[2])//2` 形式的
   OCR/模板命中中心点；
2. `planning/action_policy.py::_executable_from_candidate` — `cand.center()` 的
   Grounding 候选中心点。

对 POS 类密集键盘区的小按钮、以及相邻 grounding 候选 / OCR 命中紧贴的场景，机械中心容易
落在控件边缘像素（渲染抗锯齿、bbox 估计偏差下点击失效）或误触相邻控件。本 feature 把
"点哪里"收敛为一个独立、可测、确定性的纯函数，并在上述两处接线。

## Clarifications

全自动运行下的决策记录（2026-07-26）：

- **C-001 模块位置**：新模块放在 `src/vnc_agent/planning/click_point.py` 而非 `domain/`。
  理由：`domain/` 惯例上只放数据模型与其内聚方法（`grounding.py`、`observation.py`），
  点击点选择是 planning 阶段的策略计算，与 `action_policy.py` 同层内聚；且避免 `domain`
  反向依赖策略语义。
- **C-002 「避开 OCR 文字外溢区域」降级**：设计文档的第三条规则降级为"由候选重叠规避规则
  覆盖"。理由：估计文字外溢区域需要 OCR 字形渲染度量（字号、基线、溢出方向），当前
  `OCRItem` 只有 bbox/text/confidence，无法在不引入新感知数据的情况下确定性地计算外溢区；
  而外溢文字在感知层表现为"相邻的其他 OCR 命中 bbox"，把这些 bbox 作为 siblings 传入
  重叠规避规则即可获得等价的规避效果。此决策记入 FR-011。
- **C-003 配置位置**：新增 `click` 配置段（`click.edge_inset_ratio`，默认 0.15，
  取值范围 [0, 0.5)），而非塞进 `grounding` 段。理由：该比例同时作用于 OCR/模板路径与
  Grounding 路径，语义是"点击点计算"而非"grounding 置信度"。
- **C-004 运行时接线边界**：本 feature 的改动边界（与并行 feature 012 划定）禁止修改
  `runtime/`。`ActionPolicy.__init__` 新增 `click_edge_inset_ratio` 参数，默认值与
  `agent.yaml` 默认值一致（0.15），因此在 `runtime/agent_runtime.py` 未透传前运行时行为
  与配置默认完全一致；`config.agent.click.edge_inset_ratio → ActionPolicy(...)` 的一行
  透传作为后续跟进项记录（见 Assumptions）。
- **C-005 残余重叠标注**：无法完全避开 sibling 时的"标注"采用返回值伴随元数据实现：
  纯函数返回 NamedTuple `(x, y, residual_overlap)`，`residual_overlap=True` 表示返回点
  仍落在至少一个 sibling bbox 内（选择的是重叠深度最小的点）。调用方只消费 `(x, y)`，
  元数据供测试与将来审计使用，不改变 `ExecutableAction` 契约。
- **C-006 确定性算法**：安全区内候选点取固定的等距网格（安全区中心 + 每轴至多 9 个等分
  采样点的笛卡尔积），按 (重叠深度, 距中心距离, y, x) 全序排序取最小者。纯整数/浮点
  算术、无随机源、无 I/O，同输入必然同输出（Constitution I 回放一致性）。
- **C-007 sibling 语义（调用点）**：`_unique_ocr_or_template` 传该函数内已计算出的
  其他 OCR/模板命中 bbox（即除被选中 bbox 外的全部 needle 命中）；
  `_executable_from_candidate` 传 in_bounds 列表中未被选中的其他 grounding 候选 bbox。
  不改变任何"命中是否唯一 / 是否可信"的判定逻辑（那是并行 feature 012 的领地）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 密集小按钮不再点到边缘像素 (Priority: P1)

测试工程师的用例点击 POS 密集键盘区的一个小按钮。OCR/模板/Grounding 给出的 bbox 与真实
控件存在 1~3 像素的估计偏差时，机械中心贴近控件边缘会导致点击落在边框或相邻控件上。
接入安全点击点后，返回点必须落在 bbox 四边各内缩 15%（可配置）的内部安全区内，天然远离
边缘像素。

**Why this priority**: 这是设计文档 §9.6 的直接要求，也是密集 UI 场景点击失效的主因。

**Independent Test**: 对纯函数给定普通 bbox，断言返回点在内缩安全区内；对策略层给定唯一
OCR 命中，断言 `ExecutableAction.coordinates` 在安全区内。

**Acceptance Scenarios**:

1. **Given** 一个 100×40 的 bbox 且无 siblings，**When** 计算安全点击点，
   **Then** 返回点即 bbox 几何中心（中心本就在安全区内，优先中心附近）。
2. **Given** 任意合法 bbox，**When** 计算安全点击点，**Then** 返回点满足
   `x1+w*ratio ≤ x ≤ x2-w*ratio` 且 `y1+h*ratio ≤ y ≤ y2-h*ratio`（ratio 默认 0.15）。
3. **Given** 极小 bbox（内缩后安全区为空，如 2×2），**When** 计算，**Then** 退化为
   几何中心，不报错。

---

### User Story 2 - 相邻候选紧贴时点击点被推出重叠区 (Priority: P1)

相邻 grounding 候选或相邻 OCR 命中与目标 bbox 相交时（紧贴/半重叠的按钮），点击机械中心
可能落入重叠区、被相邻控件接收。安全点击点必须在安全区内选一个不落入任何 sibling bbox 的
点；确实无法完全避开时（sibling 完全覆盖安全区），选重叠深度最小的点并在伴随元数据中标注。

**Why this priority**: 与 US1 并列的设计文档核心规则（避开与其他候选重叠区域），直接
决定相邻控件误触率。

**Independent Test**: 纯函数级构造 bbox 与相交 sibling，断言返回点不在 sibling 内；构造
sibling 完全覆盖安全区的输入，断言返回重叠深度最小的点且 `residual_overlap=True`。

**Acceptance Scenarios**:

1. **Given** bbox 与一个 sibling 右半相交，**When** 计算，**Then** 返回点在安全区内且
   不在 sibling bbox 内，`residual_overlap=False`。
2. **Given** siblings 完全覆盖安全区，**When** 计算，**Then** 返回安全区内重叠深度最小的
   点，`residual_overlap=True`。
3. **Given** sibling 与 bbox 不相交（相距很远），**When** 计算，**Then** 行为与无
   siblings 完全一致（返回中心）。
4. **Given** 两个互不相关 GUI 场景词汇的策略层输入（表单按钮流 / 图标菜单流）构造相同
   几何关系，**When** 解析，**Then** 坐标行为一致（Constitution VI 跨场景验证）。

---

### User Story 3 - 屏幕边界与回放一致性 (Priority: P2)

bbox 贴近屏幕边缘（甚至部分越界的 OCR bbox）时，返回点必须 clamp 在屏幕分辨率内；同一
输入无论重复计算多少次都返回同一点，保证回放与审计一致。

**Why this priority**: clamp 是执行安全底线；确定性是 Constitution I（可复现、可审计）
的硬约束。

**Independent Test**: 构造贴边 bbox + 分辨率，断言返回点在 `[0, w-1]×[0, h-1]` 内；同一
输入调用两次断言逐字段相等。

**Acceptance Scenarios**:

1. **Given** bbox 部分超出 800×600 分辨率，**When** 以 `screen_resolution=(800, 600)`
   计算，**Then** 返回点 `0 ≤ x ≤ 799` 且 `0 ≤ y ≤ 599`。
2. **Given** 同一 (bbox, siblings, resolution) 输入，**When** 连续计算两次，
   **Then** 两次返回值完全相等。
3. **Given** 未提供 `screen_resolution`，**When** 计算，**Then** 不做 clamp，其余规则
   不变（纯函数不猜测分辨率）。

---

### Edge Cases

- bbox 内缩后安全区在单轴上为空（细长条控件）：仅该轴退化为中心线，另一轴仍内缩。
- bbox 宽或高为 0（退化 bbox）：直接返回几何中心（再 clamp）。
- sibling bbox 与目标 bbox 完全相同（OCR 与模板命中同一控件）：安全区被完全覆盖，
  返回中心附近重叠深度最小的点并标注 `residual_overlap=True`——不会因此抛错或返回
  bbox 外的点。
- siblings 为空元组 / 含退化 bbox：退化 sibling 忽略，行为与无 siblings 一致。
- `edge_inset_ratio=0`：安全区即整个 bbox；配置校验拒绝 ≥ 0.5 的值（安全区必然为空）。
- 返回点必须始终在原 bbox 内（clamp 到屏幕后仍不允许跳出 bbox 与屏幕的交集之外）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 提供纯函数 `safe_click_point(bbox, *, siblings=(), screen_resolution=None,
  edge_inset_ratio=0.15)`，无 I/O、无随机性、无全局状态；同一输入 MUST 产生完全相同的输出
  （回放一致性，Constitution I）。
- **FR-002**: 基准点 MUST 为 bbox 几何中心；无 siblings 干扰时 MUST 返回中心（或安全区内
  离中心最近的点）。
- **FR-003**: 返回点 MUST 落在 bbox 四边各内缩 `edge_inset_ratio`（默认 0.15，可配置）后的
  内部安全区内；某轴内缩后为空时该轴 MUST 退化为几何中心坐标；两轴均为空时 MUST 退化为
  几何中心。
- **FR-004**: bbox 与任一 sibling bbox 相交时，系统 MUST 在安全区内优先选择不落入任何
  sibling bbox 的点（多个可行点时选离中心最近者，距离并列时按确定性全序决胜）。
- **FR-005**: 安全区被 siblings 完全覆盖、无法完全避开时，系统 MUST 返回安全区内重叠深度
  最小的点，并 MUST 通过返回值伴随元数据 `residual_overlap=True` 标注；重叠深度定义为该点
  对所有包含它的 sibling 的最小逃逸距离之和（确定性度量）。
- **FR-006**: 提供 `screen_resolution=(w, h)` 时，返回点 MUST clamp 在 `[0, w-1]×[0, h-1]`
  内；未提供时 MUST NOT 做任何 clamp。
- **FR-007**: `_unique_ocr_or_template` 的三处返回坐标 MUST 改用 `safe_click_point`，
  siblings 为该函数内已计算出的其他 OCR/模板命中 bbox（被选中者除外）；该函数的命中判定
  逻辑（哪些 hit 算唯一命中、何时返回 None）MUST NOT 改变（并行 feature 012 边界）。
- **FR-008**: `_executable_from_candidate` MUST 改用 `safe_click_point`，siblings 为
  in_bounds 列表中未被选中的其他 grounding 候选 bbox；候选选择与置信度分类逻辑 MUST NOT
  改变。
- **FR-009**: `ExecutableAction.target_region` MUST 保持原始 bbox 值不变（验证与审计依赖
  它），只有 `coordinates` 改为安全点击点。
- **FR-010**: 内缩比例 MUST 进入配置：`config/agent.yaml` 新增 `click.edge_inset_ratio`
  （默认 0.15），`config.py` 新增对应模型（取值校验 `0 ≤ ratio < 0.5`），
  `ActionPolicy.__init__` 新增 `click_edge_inset_ratio` 参数并透传到两处调用点。
- **FR-011**: 设计文档「避开 OCR 文字外溢区域」在本 feature 中 MUST 降级为由 FR-004/005
  的候选重叠规避规则覆盖（理由见 Clarifications C-002）；外溢文字对应的相邻 OCR 命中
  bbox 通过 siblings 参与规避。
- **FR-012**: 返回点 MUST 始终位于原 bbox 与屏幕范围（若提供）的交集内——安全点击点
  永远不会点到 bbox 之外。

### Key Entities

- **SafeClickPoint**: 纯函数返回值。属性：`x`、`y`（整数像素坐标）、`residual_overlap`
  （bool，True 表示返回点仍落在至少一个 sibling bbox 内）。前两个字段供
  `ExecutableAction.coordinates` 消费，第三个字段为伴随元数据。
- **安全区 (safe zone)**: bbox 四边各内缩 `edge_inset_ratio` 后的矩形；点击点的可行域。
- **sibling bbox**: 与目标竞争空间的其他候选矩形（其他 OCR/模板命中、其他 grounding
  候选）；仅几何语义，不携带业务含义（Constitution VI）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 任意合法 bbox 输入下，返回点 100% 落在内缩安全区（或退化中心）内，且 100%
  落在原 bbox 内。
- **SC-002**: 存在可行避让点时，返回点落入 sibling bbox 的比例为 0%；无可行点时 100%
  返回重叠深度最小的点并携带 `residual_overlap=True` 标注。
- **SC-003**: 同一输入重复计算，输出逐字段一致率 100%（含 siblings 顺序不变时的稳定性）。
- **SC-004**: 现有离线测试套件（unit/fixtures/e2e）在新语义下全绿；
  `ExecutableAction.target_region` 语义零变化。

## Assumptions

- `runtime/agent_runtime.py` 属于并行开发禁改区：`config.agent.click.edge_inset_ratio →
  ActionPolicy(click_edge_inset_ratio=...)` 的一行透传由后续集成提交完成。在此之前
  `ActionPolicy` 构造默认值（0.15）与 `agent.yaml` 默认值一致，运行时行为无偏差。
- bbox 坐标语义沿用现状：`(x1, y1, x2, y2)` 原图像素坐标，`x1 < x2`、`y1 < y2`（OCR bbox
  可能轻微越界，由 clamp 兜底）。
- 点落在 sibling bbox 内的判定采用闭区间（`x1 ≤ x ≤ x2`），保守规避。
- 本 feature 不改变命中判定、置信度分类、恢复升级等任何"是否点/信不信"逻辑，只改变
  "点哪里"。
