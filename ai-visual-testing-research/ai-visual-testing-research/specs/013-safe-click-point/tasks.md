# Tasks: 安全点击点计算（safe-click-point）

**Input**: Design documents from `specs/013-safe-click-point/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: 本 feature 明确要求测试（纯函数单测 + 配置测试 + 策略接线测试 + 既有套件回归），
测试任务为必选项。

**Organization**: 按 user story 分阶段；US1（内缩安全区）与 US2（重叠规避）共享同一个
纯函数实现，故纯函数骨架放 Foundational，两个故事分别完成其规则与断言。

**改动边界（并行 feature 012，硬约束）**：只允许改 `planning/click_point.py`（新建）、
`planning/action_policy.py`（坐标表达式行 + 签名透传）、`config.py`、`config/agent.yaml`、
tests、specs。禁改 `_unique_ocr_or_template` 命中判定逻辑与 `runtime/` 等目录。

## Phase 1: Setup

- [X] T001 确认环境：`cd vnc_agent && uv sync`，并运行基线
      `uv run pytest tests/unit tests/fixtures -q` 记录全绿基线（vnc_agent/）

## Phase 2: Foundational（阻塞所有 user story）

- [X] T002 新建 `vnc_agent/src/vnc_agent/planning/click_point.py`：`SafeClickPoint`
      NamedTuple（x, y, residual_overlap）+ `safe_click_point()` 骨架（签名、docstring、
      安全区计算与几何中心退化，siblings/clamp 逻辑占位返回中心），纯函数、无 I/O
- [X] T003 [P] `vnc_agent/src/vnc_agent/config.py`：新增 `ClickConfig`
      （`edge_inset_ratio: float = Field(default=0.15, ge=0.0, lt=0.5)`），挂载
      `AgentConfig.click: ClickConfig`
- [X] T004 [P] `vnc_agent/config/agent.yaml`：新增 `click:` 段
      （`edge_inset_ratio: 0.15`，含注释说明 feature 013 与取值范围）
- [X] T005 [P] 新建 `vnc_agent/tests/unit/test_config_click.py`：默认值 0.15、yaml 覆盖、
      `>= 0.5` 与 `< 0` 被拒绝

**Checkpoint**: 配置可加载，`safe_click_point` 可导入（行为为中心退化）

## Phase 3: User Story 1 - 密集小按钮不再点到边缘像素 (P1) — MVP

**Goal**: 返回点落在四边内缩 `edge_inset_ratio` 的安全区内；极小 bbox 退化为中心。

**Independent Test**: `uv run pytest tests/unit/test_click_point.py -q` 中内缩/退化用例；
策略层唯一 OCR 命中 coordinates 落于安全区。

- [X] T006 [US1] 在 `vnc_agent/src/vnc_agent/planning/click_point.py` 实现安全区网格采样
      （每轴 ≤ 9 等距整数点，显式并入中心点）与 `(overlap, dist², y, x)` 全序选点、
      `screen_resolution` clamp（data-model.md 算法步骤 1/2/4/6/7/8；重叠计入 T009）
- [X] T007 [P] [US1] 新建 `vnc_agent/tests/unit/test_click_point.py`：无 siblings 返回
      几何中心、任意 bbox 返回点在内缩安全区内（含 ratio 参数化 0.0/0.15/0.3）、
      细长条单轴退化、2×2 极小 bbox 退化为中心、返回点永在 bbox 内（FR-012）、
      同输入两次调用逐字段相等（确定性）、clamp 用例（贴屏边 bbox + 无 resolution 不 clamp）
- [X] T008 [US1] `vnc_agent/src/vnc_agent/planning/action_policy.py`：
      `ActionPolicy.__init__` 新增 `click_edge_inset_ratio: float = 0.15`；
      `_unique_ocr_or_template` 三处返回坐标改用 `safe_click_point`（siblings=其余命中
      bbox、`screen_resolution=screen.resolution`），region 返回值保持原始 bbox；
      命中判定分支逐字不动

**Checkpoint**: US1 独立可验收（内缩 + 退化 + OCR/模板路径接线）

## Phase 4: User Story 2 - 相邻候选紧贴时点击点被推出重叠区 (P1)

**Goal**: 安全区内优先选零重叠点；无法避开时选重叠深度最小点并标注
`residual_overlap=True`。

**Independent Test**: 纯函数 sibling 推开/最小重叠用例；grounding 双候选紧贴场景
coordinates 不落入邻近候选 bbox。

- [X] T009 [US2] 在 `vnc_agent/src/vnc_agent/planning/click_point.py` 完成 sibling 过滤
      （非退化且与 bbox 相交，闭区间包含判定）与逃逸距离重叠深度
      `esc = min(dx1+1, dx2+1, dy1+1, dy2+1)` 求和评分（data-model.md 步骤 3/5）
- [X] T010 [P] [US2] `vnc_agent/tests/unit/test_click_point.py` 追加：右半相交 sibling
      被推开且 `residual_overlap=False`、siblings 覆盖整个安全区时返回最小重叠深度点且
      `residual_overlap=True`、远处不相交 sibling 行为与无 siblings 一致、退化 sibling
      被忽略、sibling 与 bbox 完全相同时不抛错且标注 True
- [X] T011 [US2] `vnc_agent/src/vnc_agent/planning/action_policy.py`：
      `_executable_from_candidate` 增加 `resolution: tuple[int, int]` 形参
      （`_from_grounding` 传 `screen.resolution`），坐标改用 `safe_click_point`
      （siblings=in_bounds 中未被选中候选的 bbox）；`target_region` 保持 `cand.bbox`；
      候选选择与置信度分类逻辑逐字不动
- [X] T012 [P] [US2] 新建 `vnc_agent/tests/unit/test_action_policy_click_point.py`：
      1) 唯一 OCR 命中 → coordinates 在内缩安全区内且 `target_region` 等于原始 bbox；
      2) OCR+模板同时唯一命中 → 被选 bbox 的 coordinates 在安全区内、target_region 不变；
      3) grounding 双候选紧贴（candidate_index=0/1）→ coordinates 不落入另一候选 bbox；
      4) 跨场景一致性（Constitution VI）：表单按钮流 / 图标菜单流两组业务词汇、相同几何
      → 相同坐标输出；5) 同一输入 resolve 两次 coordinates 一致

**Checkpoint**: US2 独立可验收（重叠规避 + grounding 路径接线 + 跨场景契约）

## Phase 5: User Story 3 - 屏幕边界与回放一致性 (P2)

**Goal**: 贴边/越界 bbox 的返回点 clamp 在分辨率内；策略两条路径输出确定性。

**Independent Test**: 纯函数 clamp 用例 + 策略层越界 OCR bbox 用例。

- [X] T013 [P] [US3] `vnc_agent/tests/unit/test_click_point.py` 追加：部分越界 bbox +
      `screen_resolution=(800,600)` → 返回点在 `[0,799]×[0,599]`；`residual_overlap`
      以 clamp 前网格点判定的语义用例；`screen_resolution=None` 不 clamp
- [X] T014 [P] [US3] `vnc_agent/tests/unit/test_action_policy_click_point.py` 追加：
      轻微越界 OCR bbox（如 y2 超出分辨率）经 resolve 后 coordinates 在分辨率内

## Phase 6: Polish & 回归

- [X] T015 全量回归 `cd vnc_agent && uv run pytest tests/unit tests/fixtures -q` 与
      `uv run pytest tests/e2e -q`；对断言机械中心坐标的既有测试逐一评估：语义仍成立的
      保持不动，被新语义改变的按 spec FR 更新断言并逐处记录理由（当前排查已知
      `tests/e2e/test_scenario_05_multi_iteration.py:122/125` 的 `c1.center()` 断言在
      新语义下值不变——候选互不相交时安全点即中心；如实测有差异再更新）
- [X] T016 [P] 运行 quickstart.md 的 REPL 手工验证段并核对预期输出；确认
      `git diff --stat` 未触碰禁改目录（runtime/recovery/perception/verification/
      execution/models 与 `_unique_ocr_or_template` 判定行）

## Dependencies & Execution Order

- Phase 1 → Phase 2 → Phase 3 (US1) → Phase 4 (US2) → Phase 5 (US3) → Phase 6
- US2 依赖 US1 的 T006（网格与排序骨架先于重叠评分接入）；US3 只追加测试，依赖 T006/T011
- 并行机会：T003/T004/T005 互相并行;T007 与 T008、T010 与 T011/T012、T013 与 T014 可并行

## Implementation Strategy

MVP = Phase 1~3（US1）：纯函数内缩 + OCR/模板路径接线即可交付"不点边缘"价值；
US2 补齐重叠规避与 grounding 路径；US3 为边界与一致性加固。每个 checkpoint 后可独立
运行对应测试验证。
