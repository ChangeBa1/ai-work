---

description: "Task list for 024-app-perception-plugins"
---

# Tasks: 应用感知增强插件框架（Grounding 前置子窗口裁剪放大）

**Input**: Design documents from `/specs/024-app-perception-plugins/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/app-perception-plugin-contract.md, quickstart.md

**Tests**: **包含**。Constitution 的「测试覆盖门禁」要求核心模块变更必须覆盖坐标转换/边界计算单元测试与
基于固定截图的离线感知测试；spec 的每个 User Story 也都给出了 Independent Test。因此测试任务是强制的。

**Organization**: 按 User Story 分组，每组可独立实现与验证。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行（不同文件、无未完成依赖）
- **[Story]**: 所属 User Story（US1–US4）
- 每条任务都给出确切文件路径

## Path Conventions

Python 工程根为 `vnc_agent/`；源码 `vnc_agent/src/vnc_agent/`，测试 `vnc_agent/tests/`，
配置 `vnc_agent/config/`，插件档案数据 `vnc_agent/profiles/app_perception/`。

**贯穿全局的红线**（每条任务都必须遵守）:
- 核心代码中 MUST NOT 出现任何被测应用/窗口/业务控件词汇（Constitution VI）。
- 激活的唯一来源是 `TestStep.perception_scope` 显式声明；MUST NOT 引入任何隐式/推断激活。
- 坐标还原复用既有 `restore_original_bbox`，越界/退化拒绝，**不 clamp、不猜**。
- 所有失败路径 fail-open 回全帧；MUST NOT 新增 FailureType / 重试路径 / 恢复预算消耗。

---

## Phase 1: Setup（共享基础设施）

**Purpose**: 建立包骨架、数据目录与配置段，后续任务才有落点。

- [ ] T001 [P] 创建插件框架包骨架（空实现 + `__all__`）：`vnc_agent/src/vnc_agent/perception/app_plugins/__init__.py`
- [ ] T002 [P] 创建插件档案数据目录与作者指南：`vnc_agent/profiles/app_perception/README.md`（内容按 contracts §B「锚点选择指南」：优先 ASCII/数字/汉字锚点、锚点分布于窗口上/中/下部、避开窗口外也会出现的文本与会变化的文本）
- [ ] T003 在 `vnc_agent/config/agent.yaml` 末尾新增 `app_perception:` 段，含 data-model.md §4 的全部键与默认值，并按 018/020/022/023 的注释风格写明：本 feature 的作用、`enabled: false` 是一行字节级回滚、激活只来自用例 `perception_scope` 声明
- [ ] T004 在 `vnc_agent/src/vnc_agent/config.py` 新增 `AppPerceptionConfig`（data-model.md §4 全部字段与约束：区间校验、`min_scale < max_scale`、`roi_area_ratio_min < max`、枚举 `on_declared_window_missing` / `anchor_constraint_mode`），并挂到 `AgentConfig.app_perception`（`default_factory`，缺省不破坏既有配置文件）

**Checkpoint**: 配置可加载，包可导入，尚无行为变化。

---

## Phase 2: Foundational（阻塞性前置）

**Purpose**: 全部 User Story 共同依赖的数据结构、注册表与声明通道。

**⚠️ CRITICAL**: 本阶段完成前，任何 User Story 都不能开工。

- [ ] T005 [P] 新建通用领域模型 `vnc_agent/src/vnc_agent/domain/app_perception.py`：`AnchorHit` / `SubWindowDetection` / `ActivationReason`（data-model.md §1.4 的 13 个字面量）/ `ScopeHintMismatch` / `ActivationDecision` / `AnchorConstraint` / `ConstraintViolation` / `PerceptionEnhancementAudit`。字段名与语义严格按 data-model.md §1，**不得出现任何业务词汇**
- [ ] T006 [P] 新建声明式档案 schema `vnc_agent/src/vnc_agent/perception/app_plugins/profile.py`：`PluginProfile` + `ZoomOverride`（contracts §B 的全部字段），含加载期校验（`required_anchors` ≥ 2、`name` 形如 `[a-z0-9-]+`、区间合法、`between` 关系恰好 2 个锚点），错误信息必须含**档案文件路径 + 字段路径**
- [ ] T007 新建扩展点协议 `vnc_agent/src/vnc_agent/perception/app_plugins/base.py`：`AppPerceptionPlugin` Protocol（`name` / `detect` / `activation_vote`）、`ActivationVote` 字面量、`ActivationContext`。在 docstring 中明确写死：`REQUIRE` **不能**把未声明的步骤变成激活，当前框架把它等同 `ABSTAIN`（依赖 T005）
- [ ] T008 新建注册表 `vnc_agent/src/vnc_agent/perception/app_plugins/registry.py`：`register` / `get` / `names`（字典序稳定）/ `from_profiles_dir`；重名抛错；目录不存在返回空注册表（非错误）；任一档案非法则抛含路径的加载错误（依赖 T006、T007）
- [ ] T009 [P] 在 `vnc_agent/src/vnc_agent/domain/testcase.py` 为 `TestStep` 增加可选字段 `perception_scope: str | None = None`，为 `TestCase` 增加 `perception_plugins: list[str] = []`；两者均为通用字段，注释说明「省略 ≡ `"none"` ≡ 不激活」
- [ ] T010 在 `vnc_agent/src/vnc_agent/domain/testcase.py::load_test_case` 增加声明校验：`perception_scope` 非空且非 `"none"` 时必须属于用例级白名单（若声明）或已注册插件集合；失败时经 `FieldValidationError` 报出 `steps[i].perception_scope` 字段路径与可选值列表（依赖 T008、T009）
- [ ] T011 [P] 在 `vnc_agent/src/vnc_agent/domain/run.py` 为 `ActionIteration` 增加可选字段 `perception_enhancement: PerceptionEnhancementAudit | None = None`（追加式，注释说明非 Grounding 迭代恒为 None，依赖 T005）
- [ ] T012 [P] 在 `vnc_agent/src/vnc_agent/perception/pipeline.py` 为 `ZoomObservation` **追加** `ocr_items_zoom_space: list[OCRItem]`，并在 `observe_zoom` 中把还原前的放大图坐标系 OCR 项填入该字段；**既有 `ocr_items` 语义与 feature 014 调用点一行不改**（plan.md Complexity Tracking 第 2 条）
- [ ] T012a [P] 新建源码派生相对几何 `vnc_agent/src/vnc_agent/perception/app_plugins/source_geometry.py`：`SourceGeometry` / `ControlGeometry`（data-model.md §2.1）+ 纯函数 `map_control_rect(control, design_size, actual_region)`——统一缩放 `s=min(AW/W,AH/H)` 吸收 DPI、残差 `dx/dy` 吸收拉伸，按 `top/bottom/left/right` 停靠语义逐轴换算；退化/越界返回 None（不 clamp）
- [ ] T012b [P] 单测 anchor 映射 `vnc_agent/tests/unit/test_app_perception_source_geometry.py`：等比缩放（DPI）与非等比拉伸两类 × `Top|Left` / `Bottom|Right` / 双向 / 无停靠四种语义（SC-010）；等比时四种规则结果一致；`Bottom|Right` 控件拉伸后仍贴右下角；越界返回 None
- [ ] T012c [P] 新建离线生成脚本 `vnc_agent/scripts/gen_app_profile_from_designer.py`：解析界面定义源文件（`*.Designer.cs`）导出 `name/title/client_size/controls[]` 草稿 YAML；**只读**被测应用源码树（MUST NOT 写入），输出到 stdout 或指定路径；带 `--help` 用法与"人工需核对项"清单
- [ ] T012d [P] 单测生成脚本 `vnc_agent/tests/unit/test_gen_app_profile_script.py`：用**合成的** Designer 样本（测试内联，不依赖外部源码树）断言 client_size/title/控件矩形/anchor 解析正确，且产物能被 `PluginProfile` 校验通过
- [ ] T013 [P] 新建几何工具 `vnc_agent/src/vnc_agent/perception/app_plugins/geometry.py`：`project_to_zoom_space(bbox, crop_offset, scale_factor)`（原帧→放大图，越界返回 None）、`is_inside(region, bbox)`（按 bbox 中心判定）、`in_edge_band(region, bbox, ratio)`、`evaluate_constraints(constraints, candidate_bbox, anchor_hits, mode)` 实现 `same_row/same_column/right_of/left_of/above/below/between` 七种通用关系 + 容差
- [ ] T014 [P] 新建倍率计算 `vnc_agent/src/vnc_agent/perception/app_plugins/scaling.py`（或并入 geometry）：`compute_scale(roi, config, profile_override)` = `clamp(target_long_edge / roi_long_edge, [min_scale, max_scale])`，再按 `max_upscaled_megapixels` 二次夹紧；结果 ≤ 1.0 返回 None
- [ ] T015 [P] 单测档案与注册表 `vnc_agent/tests/unit/test_app_perception_profile.py`：合法档案加载、`required_anchors` 不足报错、区间矛盾报错、`between` 锚点数报错、重名注册报错、目录缺失返回空注册表、`names()` 顺序稳定（SC-008，依赖 T006、T008）
- [ ] T016 [P] 单测几何与倍率 `vnc_agent/tests/unit/test_app_perception_geometry.py`：七种关系 + 容差边界、`project_to_zoom_space` 往返与越界拒绝、边缘带识别、`compute_scale` 的两级夹紧与 ≤1.0 拒绝（依赖 T013、T014）

**Checkpoint**: 数据结构、档案、注册表、声明通道、几何原语全部就绪且有单测；运行时行为仍与现状一致。

---

## Phase 3: User Story 1 — 子窗口内的小控件被前置放大后一次点中 (P1) 🎯 MVP

**Goal**: 声明了 `perception_scope` 的步骤，在调用 Grounder 之前用子窗口裁剪放大图替换观察输入，
坐标严格还原后走完全未改动的既有闭环，第一次就点在正确像素上。

**Independent Test**: 离线 e2e——脚本化 Grounder 对全帧返回未找到、对放大图返回高置信候选；
断言最终点击坐标逐像素等于手算的 `round(bbox/scale)+crop_offset`，审计 `activated=true`，
且 Grounder 调用次数与未增强路径相同。

### Tests for User Story 1 ⚠️（先写、先失败）

- [ ] T017 [P] [US1] 检测单测 `vnc_agent/tests/unit/test_app_perception_detection.py`：锚点并集→矩形、多命中取最高置信、`padding_ratio` 外扩、viewing-window 入界、面积比/宽高比/最小边拒绝、置信度合成公式、同输入同输出（确定性）、内部异常被吸收为 None（依赖 T005、T006）
- [ ] T018 [P] [US1] 坐标还原组合单测追加到 `vnc_agent/tests/unit/test_coordinate_space.py`：增强路径的 `resolve_pixel_bbox`（放大图分辨率）+ `restore_original_bbox` 组合，覆盖 pixel/normalized_1000、越界拒绝、退化拒绝、`scale=1/offset=0` 恒等（SC-003）
- [ ] T019 [US1] e2e 场景骨架 `vnc_agent/tests/e2e/test_scenario_23_app_perception_enhancement.py`：构造启用了 `app_perception` 的配置、一份测试档案、脚本化 Grounder 与 FakeVNC；先只写 US1 的两个「声明并激活」场景（SC-001、SC-004），此刻应失败

### Implementation for User Story 1

- [ ] T020 [P] [US1] 新建通用声明式检测器 `vnc_agent/src/vnc_agent/perception/app_plugins/detector.py`：`DeclarativeSubWindowPlugin`——归一化匹配（小写 + 去空白 + 容忍 `…`/`...` 截断）在 `screen.ocr_items` 上定位必需锚点、并集 + `padding_ratio` 外扩、复用 `recovery/zoom.expand_region` 的 viewing-window 入界、合理性校验、置信度合成；**只读 `screen`，不触发任何抓屏/OCR/IO**，全部异常吸收为 None（依赖 T006、T007、T013）
- [ ] T021 [US1] 新建激活判定 `vnc_agent/src/vnc_agent/perception/app_plugins/activation.py`：`decide(...)` 的**正向骨架**——未声明立即返回 `not_declared`；声明且检测成功 ⇒ `activated`。负向分支在 US2 补齐（依赖 T005）
- [ ] T022 [US1] 新建编排器 `vnc_agent/src/vnc_agent/perception/app_plugins/coordinator.py`：`AppPerceptionCoordinator.enhance(screen, step, semantic_action, *, pipeline)` 按 plan.md「编排」伪码执行——零开销早退 → 检测 → 判定 → `compute_scale` → `await pipeline.observe_zoom(roi, scale, step_id, capture_source="app_perception")` → 返回 `(ZoomObservation | None, PerceptionEnhancementAudit)`；`reset_step(step_id)` 清零每步计数（依赖 T014、T020、T021）
- [ ] T023 [US1] 在 `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` 构造 `AppPerceptionCoordinator`（按 `config.agent.app_perception` + 注册表；`enabled=false` 时置 None 以保证零开销），并在步骤切换处调用 `reset_step`（与既有 per-step 状态复位同处）
- [ ] T024 [US1] 在 `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` 的 `needs_grounding` 分支**最内层 `else:` 开头**接线：调用 `coordinator.enhance(...)`，把审计写入 `iteration.perception_enhancement`；返回非 None 时按 contracts §C.2 构造增强版 `GroundingRequest`（`image_ref`=放大图、`crop_offset`、`scale_factor`、`resolution`=放大图尺寸、`original_resolution`=原帧、`ocr_candidates`=`ocr_items_zoom_space`、`template_candidates`=投影入 ROI 的 memory 提示否则空、`ui_index_candidates`=空）；返回 None 时**既有全帧请求一行不改**（依赖 T012、T022）
- [ ] T025 [US1] 在同一分支中，把 015 memory 的中置信提示按 `project_to_zoom_space` 投影进 ROI；投影失败（落在 ROI 外）则丢弃并在审计中留痕（plan.md Risks R3）
- [ ] T026 [US1] 校验模型调用审计：确认 `grounder_identity` 的 `coordinate_transform_identity` 在增强路径上携带正确的 `crop_offset` / `scale_factor` / `original_resolution`（既有字段，只需验证不需改代码；若发现缺失则补齐），文件 `vnc_agent/src/vnc_agent/runtime/agent_runtime.py`
- [ ] T027 [US1] 编写第一份声明式档案 `vnc_agent/profiles/app_perception/<scenario-a>.yaml`（对应真实证据形态的工具子窗口：锚点取该窗口内稳定的 ASCII/数字锚点，分布于上/中/下部；含 `padding_ratio`、`area_ratio_range`、`aspect_ratio_range`）——**业务词汇只允许出现在这里**
- [ ] T028 [US1] 制备离线 fixture 截图（子窗口叠在主画面之上）至 `vnc_agent/tests/fixtures/images/`，或在测试中程序化生成等价图像；同时准备其 OCR 项夹具，使检测可在 CI 上无 OCR 引擎依赖地复现
- [ ] T029 [US1] 补全 T019 的 US1 断言：点击坐标逐像素等于手算还原值（SC-001）、`activated=true` 且 `zoom_image_ref` 文件存在、Grounder 调用总次数与关闭本 feature 时相同（SC-004）

**Checkpoint**: 声明了范围的步骤能被正确增强并精确落点；US1 可独立演示。

---

## Phase 4: User Story 2 — 画面里有子窗口但本步不操作它时必须不激活 (P1)

**Goal**: 未声明的步骤 100% 不激活、零检测开销、请求与基线逐字节相同；声明了但窗口不在画面上时
按 `fallback`（默认）回退并强制留痕。

**Independent Test**: 同一张 fixture 上，未声明的主画面步骤断言 `reason_code="not_declared"`、
`detect()` 调用数为 0、Grounding 请求与关闭本 feature 时逐字节相同。

> **依赖说明**: US2 复用 US1 建立的接线与编排（同一批文件），因此在 US1 之后实现；
> 但其验收标准完全独立，可单独运行验证。

### Tests for User Story 2 ⚠️

- [ ] T030 [P] [US2] 激活判定单测 `vnc_agent/tests/unit/test_app_perception_activation.py`：data-model.md §1.4 的 **13 个原因码各至少一例**；核心断言——`perception_scope` 未声明时 `detect()` 的 mock **调用计数为 0**（SC-002 的判定层保证）；`"none"` 与省略等价；`declared_but_undetected` 在两种 `on_declared_window_missing` 模式下的行为；`scope_hint_mismatch` 只记录不改结论
- [ ] T031 [P] [US2] 用例声明单测 `vnc_agent/tests/unit/test_app_perception_declaration.py`：未注册插件名报错（含字段路径与可选值列表）、用例级白名单越界报错、合法声明加载通过、省略/`"none"` 等价（依赖 T009、T010）

### Implementation for User Story 2

- [ ] T032 [US2] 在 `vnc_agent/src/vnc_agent/perception/app_plugins/activation.py` 补齐 FR-011 的**全部 9 级阶梯与 13 个原因码**：`not_declared` / `declared_off` / `disabled` / `plugin_not_registered` / `plugin_not_allowed` / `budget_exhausted` / `non_positional_action` / `not_detected` / `low_detection_confidence` / `roi_not_subwindow` / `scale_not_beneficial` / `observation_failed` / `activated`（依赖 T021）
- [ ] T033 [US2] 在 `coordinator.py` 强制「未声明 ⇒ 零开销」：`perception_scope` 为 None/`"none"` 时在**任何检测运算之前**返回，且 `enabled=false` 时协调器根本不被调用（`vnc_agent/src/vnc_agent/perception/app_plugins/coordinator.py`）
- [ ] T034 [US2] 在 `coordinator.py` 实现 FR-013a：检测失败时置 `declared_but_undetected=true`；按 `on_declared_window_missing` 分支——`fallback`（默认）返回 None 回退全帧；`fail` 抛出可诊断的声明失配异常
- [ ] T035 [US2] 在 `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` 处理 `fail` 模式的异常：转为本轮明确失败并给出可诊断原因；**MUST NOT 新增 FailureType**（复用既有失败语义），且 `fallback` 模式下永不抛出
- [ ] T036 [US2] 在 `coordinator.py` 计算只读警示 `scope_hint_mismatch`：线索集合 = `target.text` ∪ `target.nearby_texts`（**不含 `step.intent` 全文**，research.md R-8），命中项落在检测矩形外或跨内外时填充；**永不改变 `activated`**
- [ ] T037 [US2] 编写「有子窗口但目标在主画面」的用例夹具（未声明 `perception_scope`）供 e2e 使用，位于 `vnc_agent/tests/e2e/test_scenario_23_app_perception_enhancement.py` 内联或 `vnc_agent/tests/fixtures/`
- [ ] T038 [US2] 在 `vnc_agent/tests/e2e/test_scenario_23_app_perception_enhancement.py` 补两个 US2 场景：未声明步骤 ⇒ `not_declared` + 零检测调用 + Grounding 请求与基线**逐字节相同**（SC-002）；声明了但窗口不在画面上 ⇒ `fallback` 回退 + `declared_but_undetected=true`

**Checkpoint**: 假阳性率结构性为 0，缺省路径零开销且字节级等价于现状。

---

## Phase 5: User Story 3 — 能力完全可插拔，核心无业务语义 (P1)

**Goal**: 新增被测应用只需新增一份档案数据；核心目录对业务词汇零命中；两个互不相关场景通过同一套核心。

**Independent Test**: (a) 禁词扫描零命中；(b) 两个无关场景档案各自正确工作且互不干扰；
(c) 删除某档案后对应场景自动退回全帧路径，其它场景不受影响。

### Tests for User Story 3 ⚠️

- [ ] T039 [P] [US3] 业务无关性扫描单测 `vnc_agent/tests/unit/test_domain_agnostic_core.py`（新建或追加）：对 `vnc_agent/src/vnc_agent/` 递归扫描本 feature 引入的被测应用/窗口/业务控件词汇，断言**零命中**（SC-005 前半）；扫描词表放在测试文件内，不进生产代码
- [ ] T040 [P] [US3] 在 `vnc_agent/tests/fixtures/test_cross_scenario_coverage.py` 登记跨场景契约测试：同一套核心（注册表 + 检测器 + 判定 + 几何）在**两个互不相关**的档案与 fixture 上均通过检测/激活/坐标还原契约（SC-005 后半）

### Implementation for User Story 3

- [ ] T041 [P] [US3] 编写第二份**互不相关**的声明式档案 `vnc_agent/profiles/app_perception/<scenario-b>.yaml`：窗口结构、锚点词汇与场景 A 完全无关（Constitution VI 要求的第二个 GUI 场景）
- [ ] T042 [P] [US3] 制备场景 B 的离线 fixture（程序化生成的合成截图 + OCR 项夹具）至 `vnc_agent/tests/fixtures/`，与场景 A 完全独立
- [ ] T043 [US3] 在 `registry.py` 实现并验证多插件确定性选择：同一帧上多个插件都可检测成功时，按 `(检测置信度降序, 插件名升序)` 唯一选中一个；**一个步骤内绝不同时激活多个插件**（`vnc_agent/src/vnc_agent/perception/app_plugins/registry.py`）
  > 注：由于激活由 `perception_scope` 指名单个插件，该规则仅在未来放开"未指名"路径时生效；此处实现并单测该确定性规则以固化契约。
- [ ] T044 [US3] 在 `registry.py` 与 `coordinator.py` 验证「档案缺失即退回」：删掉档案文件后，引用它的用例在加载期报错（T010）而非运行期静默；档案目录整体缺失时注册表为空、全链路退回全帧
- [ ] T045 [US3] 在 `vnc_agent/profiles/app_perception/README.md` 补「新增一个被测应用的完整步骤」（写档案 → 配置允许列表 → 用例加声明 → 验证），明确声明「新增应用不需要改动任何核心代码」

**Checkpoint**: 可插拔性与业务无关性均有自动化证据。

---

## Phase 6: User Story 4 — 全链路可观测与一键回滚 (P2)

**Goal**: 每个 Grounding 迭代 100% 有审计（含否决原因），产物进报告；`enabled=false` 与现状逐字节一致。

**Independent Test**: 断言审计对象全部字段进入 JSON/HTML 报告；关闭开关后既有全量测试套件通过且产物集合与基线一致。

### Tests for User Story 4 ⚠️

- [ ] T046 [P] [US4] 在 `vnc_agent/tests/fixtures/test_json_report_compatibility.py` 的 `_LEGACY_ITERATION_KEYS` 增加 `perception_enhancement`，并断言缺省投影为 `null`
- [ ] T047 [P] [US4] 在 `vnc_agent/tests/e2e/test_scenario_23_app_perception_enhancement.py` 追加审计不变量断言（contracts §C.3 的 5 条）：每个 Grounding 迭代恰有一条记录；`activated=true ⟺ reason_code=="activated" ⟺ zoom_image_ref!=null`；`not_declared ⇒ 几何字段全 null 且零 detect 调用`；`declared_but_undetected ⇒ declared_scope!=null 且 activated=false`；`enabled=false ⇒ 无记录`（SC-006）

### Implementation for User Story 4

- [ ] T048 [US4] 在 `vnc_agent/src/vnc_agent/reporting/json_report.py` 增加可空迭代键 `perception_enhancement`（缺省 `null`，追加式，不改变既有键顺序语义）
- [ ] T049 [US4] 在 HTML 报告渲染中展示增强块（插件名 / ROI / 检测置信度 / 原因码 / 倍率 / 放大图链接）；若 golden 快照因追加字段变化，按其自带流程重新生成（`vnc_agent/src/vnc_agent/reporting/`、`vnc_agent/tests/snapshots/`）
- [ ] T050 [US4] 在 `vnc_agent/tests/e2e/conftest.py` 为 legacy 场景显式钉 `app_perception.enabled=false` 并写明理由注释（022/023 先例），防止将来默认翻转时静默影响既有场景
- [ ] T051 [US4] 回滚验证：新增断言确认 `enabled=false` 时不产生任何增强审计、不产生新产物、Grounding 请求负载与基线**逐字节相同**（FR-026 / SC-007），位于 `vnc_agent/tests/e2e/test_scenario_23_app_perception_enhancement.py`
- [ ] T052 [US4] 确认放大图产物落盘复用 `observe_zoom` 既有的遮罩/私有持久化语义，不新增例外；补一条断言覆盖「遮罩区域与 ROI 相交」的边界（`vnc_agent/tests/unit/` 或既有遮罩测试文件）

**Checkpoint**: 可复盘、可回滚，报告链路完整。

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T053 [P] 实现 `AnchorConstraint` 的运行期接线（**已裁决 Q3：逐条 `enforce`**）：在 `agent_runtime.py` 中于 `grounder.ground(...)` 返回后、`policy.resolve(...)` 之前，对**已还原到原帧坐标**的候选调用 `geometry.evaluate_constraints(...)`——`enforce=true` 的约束违反者**从候选列表中剔除**（剔空则按既有 `target_not_found` 语义继续既有恢复链，**不新增 FailureType**），`enforce=false` 的仅写入 `constraint_violations`；配置 `anchor_constraint_mode="record_only"` 时全部降级为只记录
- [ ] T052a [P] [US1] 相对几何接入提示通道：增强激活且档案有 `source_geometry` 时，把映射后的控件矩形投影进放大图坐标系并作为提示候选下发（`vnc_agent/src/vnc_agent/perception/app_plugins/coordinator.py`）
- [ ] T052b [P] 由 `source_geometry` 自动导出 `AnchorConstraint`（如"某控件与某锚点同一水平带且在其右侧"），减少档案作者手写约束（`vnc_agent/src/vnc_agent/perception/app_plugins/source_geometry.py`）
- [ ] T052c [P] **红线测试** `vnc_agent/tests/unit/test_app_perception_source_geometry.py`：断言源码派生几何只出现在提示通道与约束求值中，最终点击坐标 100% 来自 Grounding 结果的严格还原值（SC-011）
- [ ] T052d [P] 形状无关性参数化测试 `vnc_agent/tests/unit/test_app_perception_detection.py`：以实测极端形态（宽高比 0.73 / 1.42 / 2.16 / 5.34，屏占比 3.3%–77.1%）参数化，断言检测与倍率计算均不因形状被拒绝（SC-009）
- [ ] T053b [P] 单测逐条 `enforce` 语义 `vnc_agent/tests/unit/test_app_perception_geometry.py`：(a) 强约束（`enforce=true`）违反者被剔除、合规者保留；(b) 弱约束（`enforce=false`）违反者**不被剔除**、只进 `constraint_violations`（不误杀）；(c) 强约束把候选剔空时返回空列表且不抛异常；(d) `anchor_constraint_mode="record_only"` 时强约束也只记录
- [ ] T054 [P] 在 `vnc_agent/src/vnc_agent/perception/app_plugins/geometry.py` 补 ROI 边缘带记录：还原后的候选落在 ROI 边缘带内时写入审计（spec Edge Cases），默认不拒绝候选
- [ ] T055 [P] 补充 `vnc_agent/tests/unit/test_app_perception_detection.py` 的边界用例：子窗口部分越屏（viewing-window 平移/收缩）、锚点跨窗口重名、检测退化成近似全屏（`roi_not_subwindow`）
- [ ] T056 性能与预算验证：新增断言确认一次 run 中每 TestStep 的激活次数 ≤ `max_activations_per_step`、Grounder 调用总次数不变、无新增 FailureType 与重试循环（SC-004），位于 `vnc_agent/tests/e2e/test_scenario_23_app_perception_enhancement.py`
- [ ] T057 [P] 更新 `vnc_agent/README.md` 或 `docs/` 中的能力清单，加入应用感知增强插件（一段话 + 指向 `profiles/app_perception/README.md`）
- [ ] T058 按 [quickstart.md](./quickstart.md) 逐节执行验证（§1 离线单测、§2 e2e、§3 跨场景、§4 回滚），记录结果
- [ ] T059 全量回归：`cd vnc_agent && uv run pytest -q`，确认既有 unit / fixtures / e2e 全部通过、产物集合与基线一致（SC-007）
- [ ] T060 Constitution 合规复核（提交前）：核心目录业务禁词零命中（Principle VI）；验证独立性未被绕过（Principle IV）；无新增无限重试路径（恢复与重试门禁）；截图存储的逻辑记录/遮罩语义未被改动（制品与可观测性 + 凭据与隐私）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，可立即开始
- **Foundational (Phase 2)**: 依赖 Phase 1；**阻塞全部 User Story**
- **US1 (Phase 3)**: 依赖 Phase 2
- **US2 (Phase 4)**: 依赖 Phase 2 与 **US1**（复用同一批接线与编排文件；验收标准独立）
- **US3 (Phase 5)**: 依赖 Phase 2；与 US1/US2 可并行（不同文件：档案数据 + 扫描/跨场景测试）
- **US4 (Phase 6)**: 依赖 Phase 2 与 US1（需要有审计对象可观测）
- **Polish (Phase 7)**: 依赖上述期望完成的 Story

### Within Each User Story

- 测试先写并先失败 → 数据结构 → 纯函数 → 编排 → runtime 接线 → 断言补全
- 同一文件的任务串行；不同文件标 [P]

### Parallel Opportunities

- Phase 1：T001、T002 并行（T003/T004 同为配置改动，串行）
- Phase 2：T005、T006、T009、T011、T012、T013、T014 并行；T007→T008→T010 串行；T015、T016 并行
- Phase 3：T017、T018 并行；T020 与 T027、T028 并行（代码 vs 数据）
- Phase 5：T039、T040、T041、T042 全部并行（互不相同的文件）
- Phase 6：T046、T047 并行
- Phase 7：T053、T054、T055、T057 并行

---

## Parallel Example: Foundational (Phase 2)

```bash
# 并行启动（不同文件、无相互依赖）：
Task: "T005 新建 domain/app_perception.py 通用领域模型"
Task: "T006 新建 perception/app_plugins/profile.py 档案 schema"
Task: "T009 domain/testcase.py 增加 perception_scope / perception_plugins 字段"
Task: "T011 domain/run.py 增加 ActionIteration.perception_enhancement"
Task: "T012 pipeline.py 为 ZoomObservation 追加 ocr_items_zoom_space"
Task: "T013 新建 perception/app_plugins/geometry.py"
Task: "T014 新建 perception/app_plugins/scaling.py"
```

---

## Implementation Strategy

### MVP First（US1 Only）

1. Phase 1 Setup → 2. Phase 2 Foundational（关键，阻塞一切）→ 3. Phase 3 US1
4. **停下来验证**：`uv run pytest tests/e2e/test_scenario_23_app_perception_enhancement.py -q`
   确认声明步骤的点击坐标逐像素正确、Grounder 调用次数不变
5. 此时已可演示"声明即精确落点"的核心价值

### Incremental Delivery

1. Setup + Foundational → 基础就绪（行为无变化）
2. + US1 → 增强生效（**MVP**）
3. + US2 → 缺省安全性与 `declared_but_undetected` 语义完备（**上线前必须**）
4. + US3 → 可插拔性与业务无关性有自动化证据（**Constitution VI 合规必须**）
5. + US4 → 可复盘、可回滚（**上线前必须**）
6. + Polish → 相对位置约束、边界、全量回归

> **上线门槛**：US1–US4 全部完成 + T059 全量回归通过 + T060 合规复核通过。
> 仅完成 US1 可用于内部演示，**不可**在真实被测环境上开启 `enabled: true`。

---

## Notes

- **三条问题已于 2026-07-28 全部裁决**（见 spec.md「已由用户确认的决策」），无未决项：
  - **Q1** → `on_declared_window_missing` 默认 `fallback`，`fail` 作为配置分支一并实现（T034、T035）。
  - **Q2** → `select-scanner-simulator` **不声明**；不追加"任务视图网格"档案（属 Future Work）。
  - **Q3** → `AnchorConstraint` 逐条 `enforce`：强约束拒绝候选、弱约束仅记录；
    `anchor_constraint_mode` 默认 `respect_profile`（T053、T053b）。
- **不在本 feature 范围**：feature 014 的 `ocr_candidates` 坐标空间不一致（plan.md Risks R5），
  建议单独立项修正；本 feature 通过 T012 的追加字段绕开该问题且不改动 014 行为。
- **本 feature 不修改任何既有测试用例 YAML**（含 `vnc_agent/testcases/pos-scan-magazine-checkout.yaml`）；
  spec 附录的标注表仅作为 e2e 场景素材与作者指南。
- [P] = 不同文件、无未完成依赖；同一文件的任务必须串行
- 每完成一个任务或一组逻辑相关任务即提交


---

## Phase 8: 真机验证后的设计变更（2026-07-28）

**Purpose**: 真机 5 轮验证发现增强从未激活——步骤被 feature 012 的 OCR 直接点击路径提前
解析，grounding 分支从未进入，且 `perception_enhancement` 为 `null` 无法诊断。
用户裁决：把增强前移到 **OCR/观察阶段**。

- [x] T061 把增强从 grounding 分支移到观察阶段：新增 `AgentRuntime._observe_enhanced()`，
      替换全部 5 处 `pipeline.observe()` 调用（动作前、动作后验证、retry、recovery、
      verification 再观察），`vnc_agent/src/vnc_agent/runtime/agent_runtime.py`
- [x] T062 `AppPerceptionCoordinator.enhance()` → `enhance_screen()`：产出精炼后的
      `StructuredScreen`（替换窗口内 OCR、保留窗口外）而非替换送模型的图像，
      `perception/app_plugins/coordinator.py`
- [x] T063 坐标还原保障：只接受还原后**落在检测矩形内**的项（`_within`，严格拒绝不 clamp）；
      复用 `observe_zoom` 已完成的 `round(v/scale)+crop_offset`
- [x] T064 信息不丢失保障：放大 OCR 在窗口内一无所获时保留原始全帧读数（FR-020f）
- [x] T065 记忆化：按帧内容哈希在步骤内缓存精炼结果，未变化的画面复用（`activated_cached`），
      不消耗预算；`max_activations_per_step` 默认 1 → 6
- [x] T066 移除动作类型门槛（FR-020c）：键盘步骤的断言同样受益
- [x] T067 审计缺口修复（FR-024）：审计在观察阶段写入，声明了 scope 的迭代永不为 null；
      新增 `grounding_reached` / `ocr_items_replaced` / `ocr_items_added` 字段与
      `activated_cached` 原因码
- [x] T068 grounding 请求恢复为全帧 + 源码几何提示改用原帧坐标（014 成为唯一图像裁剪路径）
- [x] T069 e2e 场景 23 重写：以真机失败形态为模型（全帧读花 / 放大读对），覆盖
      "未走 grounding 也有审计"、"记忆化零重复"、"窗口外文本保留"、"grounding 请求仍是全帧"


---

## Phase 9: 源码几何直接点击（2026-07-28 真机实测后新增能力）

**Purpose**: 实测证明可用**运行期 OCR 锚点**反解 design→screen 仿射变换（残差 ≤1.5px），
从而定位 OCR 永远读不到的无 Text 控件（如条码输入框）——这正是本用例反复点错的那个控件。

- [x] T070 `source_geometry.py` 新增 `DesignTransform` / `solve_transform()` / `predict_control_rect()`：每轴最小二乘 + 五道安全闸
- [x] T071 生成脚本导出**无 Text 控件**（以 Name 标识），并更新人工核对清单为五项
- [x] T072 `scanner-sim.yaml` 补 `txbScanData`（`Location(11,25) Size(356,19)`）
- [x] T073 `TestStep.perception_target` 字段（指名控件）
- [x] T074 `AppPerceptionCoordinator.predict_target()`：拟合锚点用**帧内 OCR** 而非 detection 锚点；采用**标点不敏感的精确匹配**（避免短标签匹配到长标签子串导致整个拟合被带偏）
- [x] T075 runtime 接线：几何推算作为确定性点击来源，插入 `postmortem > zoom_reground > 几何 > memory > grounder`；经 `safe_click_point`，验证闭环完全不变
- [x] T076 几何点击失败后本步骤禁用几何（`_geometric_blocked_steps`），避免确定性错误答案循环
- [x] T077 配置项：`geometric_click_enabled` / `min_anchors_for_transform` / `max_transform_residual_ratio` / `transform_min_scale` / `transform_max_scale` / `min_anchor_span_ratio`
- [x] T078 审计 `GeometricPrediction`（变换参数、逐锚点残差、applied、reject_reason）
- [x] T079 单测 15 例：真机数据复现、无 Text 控件预测、五道闸各一例、窗口平移/DPI 跟随
