# Tasks: 外部 UI 分析索引消费与通用索引生产规则

**Input**: Design documents from `/specs/007-ui-analysis-index-consumption/`
**Prerequisites**: [plan.md](./plan.md)、[spec.md](./spec.md)、[research.md](./research.md)、[data-model.md](./data-model.md)、[contracts/](./contracts/)、[quickstart.md](./quickstart.md)

**Tests**: 本 feature 显式要求测试先行（spec.md SC-010）；用户本次 `/speckit-tasks` 输出含"含**测试先行**"——每个 Phase 先有测试任务、后有实现任务；测试任务 MUST 先失败（模块尚未实现）。
**Organization**: 按 spec.md 的 4 个 User Story（P1~P4）分阶段；每个阶段可独立交付验证。
**文件命名说明**：`vnc_agent/src/vnc_agent/ui_index/` 下的 `models.py`/`reader.py`/
`validator.py`/`repository.py`/`query.py`/`sanitizer.py`/`audit.py`/`errors.py` 沿用用户
本次输出指定的文件名（`models.py`=data-model.md §1 的 `schema.py`；`reader.py`=合并
data-model.md 的 `manifest.py`+`jsonl_reader.py`；`repository.py`=data-model.md 的 `bundle.py` 中"加载"部分；`query.py`=从同一文件内的查询方法）；`runtime_adapter.py`/
`cli.py` 沿用 plan.md Project Structure 既定路径（用户输出未提及具体文件名，按"由 plan 确认
最终路径为准"）。
**修订说明（2026-07-25 `/speckit-analyze` 整改）**： **`/speckit-analyze` 发现 4 项 CRITICAL/HIGH 缺口并已在本版本修复：① Phase 5 新增 T041（preflight 对无效索引 fail-fast
补全测试，原 T049 实现任务此前没有对应测试）；② T011、T023、T027 扩展覆盖
`flows.jsonl`（此前任何 fixture 都未使用该文件；Flow 引用完整性/判别联合校验此前零覆盖）；③ Phase 5 新增 T042（Verifier 独立性行为测试，取代此前只验签名未做静态检查、且没有前置
测试的旧 T050 实现任务）；④ Phase 5 新增 T044（SC-003 要求的"未配置索引/配置作用未命中"
两种条件下同一批回归 testcase 结果一致性对比测试，此前 SC-003 没有任何任务引用；因插入 3 个测试任务、移除 1 个被测试任务取代的实现任务，Phase 5 起全部任务编号相对上一版本
整体 +2（旧 T051~T069 → 新 T053~T071），本版本 T001~T040 编号不变。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件、无未完成依赖）
- **[Story]**: 所属 User Story（US1/US2/US3/US4）；Setup/Foundational/Polish 阶段任务无此标记
- 每个任务必须含明确文件路径

---

## Phase 1: Setup

**Purpose**: 项目骨架初始化，不涉及任何业务逻辑

- [X] T001 创建 `vnc_agent/src/vnc_agent/ui_index/__init__.py`（空包初始化，表明包存在）
- [X] T002 [P] 创建 `vnc_agent/tests/unit/ui_index/__init__.py` 与
      `vnc_agent/tests/integration/ui_index/__init__.py`（测试包骨架）
- [X] T003 [P] 创建 `vnc_agent/tests/fixtures/ui_index/` 目录（后续任务在此填充 bundle fixture；
      本任务只需放置 `.gitkeep` 或首个子目录以确保目录存在）

**Checkpoint**: 基础测试骨架就绪。

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 全部 4 个 User Story 共同依赖的数据模型、错误模型、配置入口与基础 fixture。**任何 User Story 实现任务都不得在本阶段完成前开始。**

### 测试（先写，MUST 先失败）

- [X] T004 [P] 编写 `vnc_agent/tests/unit/ui_index/test_models.py`：断言
      `Confidence`（`level` 四类枚举、`score`∈[0,1]`）、`NormalizedBounds`（`coordinate_space`
      固定为 `normalized_1000`、`0≤x1<x2≤1000`、`0≤y1<y2≤1000`）、`NeighborRef`（方向枚举）、
      `Screen`/`Element`/`Transition`/`GuardRef`/`Flow`/`FlowStep`/`Diagnostic`（`level ==
      "confirmed"` 时校验失败）、`BundleManifest`（`schema_version` 格式、`extra="allow"`
      未知字段透传、字段级校验）（data-model.md §1）
- [X] T005 [P] 编写 `vnc_agent/tests/unit/ui_index/test_errors.py`：断言 `UiIndexErrorCode`
      全部 17 个稳定字符串值不变、`ValidationIssue`/`ValidationReport` 字段结构（data-model.md §2）
- [X] T006 [P] 编写 `vnc_agent/tests/unit/test_config_ui_index.py`：断言
      `AgentConfig().ui_index.bundle_dir is None`（默认禁用）、`UiIndexConfig` 默认值（
      `screen_match_min_score=0.6`、`screen_inconsistency_max_missing_ratio=0.7`、
      `max_content_file_bytes=50_000_000`、`max_content_file_records=200_000`、
      `max_bundle_total_bytes=200_000_000`）（data-model.md §5）

### 实现

- [X] T007 [P] 在 `vnc_agent/src/vnc_agent/ui_index/models.py` 实现
      `BundleCoordinateSpace`、`Confidence`、`NormalizedBounds`、`NeighborRef`、`Screen`、
      `Element`、`Transition`、`GuardRef`、`Flow`、`FlowStep`、`Diagnostic`、`BundleManifest`
      （`ContentFileEntry`、`Viewport` 等）（全部模型 `model_config = ConfigDict(extra="allow")`
      ）（对应 T004）（data-model.md §1）（contracts/ui-analysis-bundle-v1.md）
- [X] T008 [P] 在 `vnc_agent/src/vnc_agent/ui_index/errors.py` 实现 `UiIndexErrorCode`
      （`StrEnum`、17 个值）、`ValidationIssue`、`ValidationReport`（对应 T005）（data-model.md §2）
- [X] T009 在 `vnc_agent/src/vnc_agent/config.py` 新增 `UiIndexConfig` 类与
      `AgentConfig.ui_index: UiIndexConfig = Field(default_factory=UiIndexConfig)` 字段
      （对应 T006）（data-model.md §5）（不修改任何既有字段的默认值）
- [X] T010 [P] 创建最小有效 bundle fixture：`vnc_agent/tests/fixtures/ui_index/valid_minimal/`
      下的 `manifest.yaml`、`screens.jsonl`（≥1 条）、`elements.jsonl`（≥1 条）、
      `transitions.jsonl`（≥1 条），字段齐全、可通过 T007 校验（
      contracts/ui-analysis-bundle-v1.md §2~5 示例为蓝本）
- [X] T011 [P] 创建跨场景 fixture "表单/文本输入型 GUI"：
      `vnc_agent/tests/fixtures/ui_index/fixture_form_input/` 下的 `manifest.yaml`、
      `screens.jsonl`（≥2 screen）、`elements.jsonl`（含 `role="text_field"`/`"button"`
      等表单控件、至少 1 条含 `normalized_bounds`）、`transitions.jsonl`（≥1 条
      `transition_type="replace"`）、**`flows.jsonl`（≥1 条；`start_screen_id`/
      `completion_screen_id` 引用本 fixture 内已有 screen、`steps` 至少一项引用本 fixture
      内已有 `transition_id`）**——是本 feature 中唯一提交且被测试消费的 `flows.jsonl`
      有效样例，业务场景为通用表单提交场景，不得使用 POS 词汇
- [X] T012 [P] 创建跨场景 fixture "图标/弹层型 GUI"：
      `vnc_agent/tests/fixtures/ui_index/fixture_icon_overlay/` 下的 `manifest.yaml`、
      `screens.jsonl`（≥2 screen、含一个 `screen_type="modal"`）、`elements.jsonl`（含
      `role="icon_button"` 等无文本图标控件、`neighbors`/`anchors` 至少各用到一次）、
      `transitions.jsonl`（≥1 条、`transition_type="overlay"`），业务场景与 T011 明显不同
      （不得使用表单/POS 词汇），两个 fixture 共同满足 spec.md SC-011"至少两个互不相关"要求

**Checkpoint**: 数据模型、错误模型、配置入口与 3 个基础 fixture 全部就绪，US1~US4 可开始。

---

## Phase 3: User Story 1 - 读取并校验外部 UI 分析索引 (Priority: P1) 🎯 MVP

**Goal**: 从用户指定目录加载 bundle，完成 schema/文件/字段/ID/引用/坐标/可信度/路径穿越/
校验和等校验，有效则可用、无效则在执行前返回可诊断错误。
**Independent Test**: 对 T010~T012 的有效 fixture 与本阶段新建的 9 类无效 fixture 逐一调用
`UiIndexBundle.load()`/CLI `validate`，断言有效 bundle 被接受、每种无效 bundle 产出
`contracts/ui-analysis-bundle-v1.md §9` 表中对应的 `error_code` + `file`/`line`/`field_path`。

### 无效 fixture（新建，供下方测试使用）

- [X] T013 [P] [US1] 创建 `vnc_agent/tests/fixtures/ui_index/invalid/unsupported_version/`
      （复制 T010 内容，将 `manifest.yaml.schema_version` 改为 `"2.0"`）
- [X] T014 [P] [US1] 创建 `vnc_agent/tests/fixtures/ui_index/invalid/missing_file/`
      （复制 T010 内容，删除 `elements.jsonl`，`manifest.content_files` 中该项仍标记
      `required: true`）
- [X] T015 [P] [US1] 创建 `vnc_agent/tests/fixtures/ui_index/invalid/jsonl_syntax_error/`
      （复制 T010 内容，向 `screens.jsonl` 追加一行非法 JSON 文本）
- [X] T016 [P] [US1] 创建 `vnc_agent/tests/fixtures/ui_index/invalid/duplicate_id/`
      （复制 T010 内容，向 `elements.jsonl` 追加一条 `element_id` 与已有记录相同的行）
- [X] T017 [P] [US1] 创建 `vnc_agent/tests/fixtures/ui_index/invalid/missing_reference/`
      （复制 T010 内容，将 `transitions.jsonl` 一条记录的 `to_screen_id` 指向不存在的 screen）
- [X] T018 [P] [US1] 创建 `vnc_agent/tests/fixtures/ui_index/invalid/invalid_coordinates/`
      （复制 T010 内容，将 `elements.jsonl` 一条记录的 `normalized_bounds` 缺失
      `coordinate_space`，另建一条 `x1 >= x2` 的具体行）
- [X] T019 [P] [US1] 创建 `vnc_agent/tests/fixtures/ui_index/invalid/invalid_confidence/`
      （复制 T010 内容，一条记录 `confidence.level` 为非法字符串，另建一条 `score=1.5` 的具体行）
- [X] T020 [P] [US1] 创建 `vnc_agent/tests/fixtures/ui_index/invalid/checksum_mismatch/`
      （复制 T010 内容，将 `manifest.content_files.screens\.jsonl.sha256` 填入错误哈希）
- [X] T021 [P] [US1] 创建 `vnc_agent/tests/fixtures/ui_index/invalid/path_traversal/`
      （复制 T010 内容，在 `manifest.content_files` 新增一条 key 为 `"../outside.jsonl"` 的
      `required: false` 条目并在 bundle 外层放置对应文件）

### 测试（先写，MUST 先失败）

- [X] T022 [P] [US1] 编写 `vnc_agent/tests/unit/ui_index/test_reader.py`：
      `read_manifest()` 对 T010（成功）、目录不存在（`bundle_dir_not_found`）、
      T014 场景变体（`manifest_missing`、单独缺 manifest.yaml 的记录）三种输出行为；
      `iter_jsonl()` 对 T015 场景产出 `(line_no, ValidationIssue)`、对构造
      `max_bytes`/`max_records` 的输入产出 `resource_limit_exceeded` 后停止迭代
- [X] T023 [P] [US1] 编写 `vnc_agent/tests/unit/ui_index/test_validator.py`：对 T010~T012、
      T013~T021 全部 fixture 逐一调用 `validate_bundle()`，断言 T010~T012 的 `report.ok is
      True`（含 T011 的 `flows.jsonl` 被正确解析且不产生任何 issue），T013~T021 各产出
      contracts §9 对应的 `error_code`；另用程序化临时目录（非提交 fixture）断言 §9
      表中 T013~T021 未直接覆盖的其余错误码（`field_type_error`、`parent_cycle`（*element
      与 screen 的 `parent`/`parent_screen_id` 自引用、环吸收等情形的四种子用例*）、
      `dangling_guard_reference`、`invalid_diagnostic_confidence`（`diagnostics.jsonl` 一条
      记录 `confidence.level="confirmed"`）等**以及 Flow 相关的悬空引用**（`steps` 中的
      `transition_id`/`element_id` 不存在、`start_screen_id`/`completion_screen_id` 不存在、
      `FlowStep` 判别联合违规、同时提供/都不提供 `transition_id` 与
      `element_id`+`action`）*；断言校验顺序遵循 contracts/ui-index-consumer-interfaces.md
      §3 六步顺序；**其中 `dangling_reference` 这一类程序化用例 MUST 以 T011（而非 T010
      为基底构造（复制 T011 内容后引用一个空 `to_screen_id`），使两个跨场景 fixture
      （T011/T012）中至少一个的错误覆盖路径经过测试，而不只是 T010 派生的 9 个无效
      fixture）（spec.md SC-011"其中至少一个 fixture 的验证过程需覆盖至少一类 FR-002 校验
      失败场景"）**
- [X] T024 [P] [US1] 编写 `vnc_agent/tests/unit/ui_index/test_repository_load.py`：
      `UiIndexBundle.load()` 对有效 fixture 返回可用实例（`manifest.bundle_id` 可读、按
      `screen_id`/`element_id`/`transition_id` 建立的索引条数与 fixture 记录数一致，含 T011
      的 `flows` 索引）；对任一无效 fixture 抛出 `UiIndexValidationError`，且 `.report` 与
      `validate_bundle()` 直接调用结果一致
- [X] T025 [P] [US1] 编写 `vnc_agent/tests/unit/ui_index/test_cli_validate.py`：
      `vnc-agent ui-index validate <T010 路径>` 退出码 `0`；对 T013~T021 任一路径退出码
      `1` 且 `--json` 输出可解析为 `ValidationReport`

### 实现

- [X] T026 [US1] 在 `vnc_agent/src/vnc_agent/ui_index/reader.py` 实现 `read_manifest()`
      与 `iter_jsonl()`（对应 T022）（contracts/ui-index-consumer-interfaces.md §1~2）（依赖
      T007 `models.py`、T008 `errors.py`）
- [X] T027 [US1] 在 `vnc_agent/src/vnc_agent/ui_index/validator.py` 实现
      `validate_bundle()`（manifest+schema 版本 → 必需文件+路径 → 逐文件 JSONL 语法 →
      字段类型/重复 ID 登记 → 跨记录引用完整性（含 parent 环检测、**Screen 与 Element 均
      适用**）、guards/anchors/neighbors、**Flow 的 `steps`/`start_screen_id`/
      `completion_screen_id`/`preconditions`** → 坐标空间/坐标范围 → 可信度取值 → 校验和
      比对）（对应 T023）（contracts/ui-index-consumer-interfaces.md §3）（依赖 T026）
- [X] T028 [US1] 在 `vnc_agent/src/vnc_agent/ui_index/repository.py` 实现 `UiIndexBundle`
      类（`load()` 类方法 + 内部 `screens`/`elements`/`transitions`/`flows`/`diagnostics`
      字典索引 + 按 role/transition 维度倒排索引，供 Phase 5 的 `query.py` 使用）与
      `UiIndexValidationError`（对应 T024）（依赖 T027）
- [X] T029 [US1] 在 `vnc_agent/src/vnc_agent/ui_index/cli.py` 实现 Typer 子应用
      `ui_index_app` 与 `validate` 子命令（对应 T025）（contracts/ui-index-consumer-interfaces.md
      §8）（依赖 T028）
- [X] T030 [US1] 在 `vnc_agent/src/vnc_agent/api/cli.py` 挂载
      `app.add_typer(ui_index_app, name="ui-index")`（依赖 T029）

**Checkpoint**: User Story 1 可独立交付——`vnc-agent ui-index validate <dir>` 对任一 bundle
产出正确结论，US2/US3/US4 可在此基础上开始。

---

## Phase 4: User Story 2 - 基于索引查询控件与流程知识辅助 testcase 编写 (Priority: P2)

**Goal**: 对已校验通过的 bundle 提供 screen/文本/role/transition 维度的结构化查询。
**Independent Test**: 对 T011/T012 两个 fixture 分别执行全部查询维度，断言返回结构化结果与
fixture 源数据一致，未命中返回空结果而非报错（依赖 Phase 3 已交付的加载能力）。

### 测试（先写，MUST 先失败）

- [X] T031 [P] [US2] 编写 `vnc_agent/tests/unit/ui_index/test_query.py`：对 T011、T012 两个
      fixture 分别执行 `query_screen`/`query_by_text`/`query_by_alias`/`query_by_role`/
      `query_transitions`（按 `from_screen_id`/`trigger_element_id`/`to_screen_id` 三个
      参数），断言返回值保留 `confidence`/`source_evidence`、命中多个候选时按 ID 字典序
      排序，未命中返回 `[]`/`None`（data-model.md §3.1）（FR-004/005）
- [X] T032 [P] [US2] 编写 `vnc_agent/tests/unit/ui_index/test_cli_query.py`：
      `vnc-agent ui-index query --bundle-dir <T011> --screen <id>` 等各查询维度的 CLI 参数
      组合与 `--json` 输出可解析，未提供任何查询维度参数时报参数错误退出

### 实现

- [X] T033 [US2] 在 `vnc_agent/src/vnc_agent/ui_index/query.py` 实现
      `query_screen(bundle, screen_id)`、`query_by_text(bundle, text)`、
      `query_by_alias(bundle, alias)`、`query_by_role(bundle, role)`、
      `query_transitions(bundle, *, from_screen_id=None, trigger_element_id=None,
      to_screen_id=None)`（对应 T031）（操作 T028 `UiIndexBundle` 的倒排索引，纯函数、无副作用）
- [X] T034 [US2] 在 `vnc_agent/src/vnc_agent/ui_index/cli.py` 新增 `query` 子命令，调用
      T033 各函数（对应 T032）
- [X] T035 [US2] 更新 `.claude/skills/vnc-agent-testcase-authoring/SKILL.md`：新增一节
      "UI 索引查询（如已配置）"，说明存在 `ui_index` 配置时按需运行
      `vnc-agent ui-index query --bundle-dir <dir> --screen <id>`（按文本/role 查询
      获取结构化控件知识用于编写 testcase 步骤），MUST NOT 建议把整份 bundle 内容贴入上下文
      ——只查询当前要编写的页面/元素相关的部分，附 2~3 个具体查询命令示例（对应 T034、
      spec.md FR-006）

**Checkpoint**: User Story 1+2 可独立交付——testcase 编写者可用 CLI 查询结构化控件知识。

---

## Phase 5: User Story 3 - Planner/Grounder 运行时获取可见语义提示但不绕过截图定位与独立验证 (Priority: P3)

**Goal**: 运行时为当前画面提供可见语义提示喂给 Planner/Grounder，索引坐标不直接进入
`SemanticAction`/最终点击坐标，Verifier 判定不受索引影响，未命中/不一致/未配置均正确回退
并产生审计记录；显式配置的无效索引必须在 run 启动前失败（fail-fast），不得静默继续。
**Independent Test**: 按 quickstart.md §四/§五，分别在无索引、命中、未命中、不一致、**显式配置但索引无效**五种条件下运行既有回归 testcase，断言点击坐标来源与 Verifier 判定依据不变、无效索引在第一步执行前即中止运行、审计记录字段完整。

### 测试（先写，MUST 先失败）

- [X] T036 [P] [US3] 编写 `vnc_agent/tests/unit/ui_index/test_sanitizer.py`：
      `to_visible_hint()` 返回对象的字段集合严格等于 `VisibleElementHint` 全部字段（
      `element_id`/`visible_texts`/`aliases`/`role`/`region`/`anchor_texts`/
      `neighbor_texts`——四类可见语义信息 + `element_id` 用于审计关联）；构造
      `source_evidence` 含明显源码路径字符串的 Element，断言该字符串不出现在返回对象任何
      字段值中（FR-015）（data-model.md §4.1）
- [X] T037 [P] [US3] 编写 `vnc_agent/tests/unit/ui_index/test_audit.py`：
      `record_index_usage()` 同时写入 `ActionIteration.ui_index_audit` 与结构化日志（
      `event_name="ui_index_usage"`），两路字段一致；`IndexUsageAuditRecord` 全部字段（
      `bundle_id`/`schema_version`/`outcome`/`matched_screen_id`/`hint_element_ids`/
      `candidate_transition_ids`/`no_match_reason`/`grounder_outcome`）可独立读出（
      data-model.md §4.2）（FR-013）
- [X] T038 [P] [US3] 编写 `vnc_agent/tests/integration/ui_index/test_runtime_adapter_outcomes.py`：
      使用 T011 fixture 构造与某 `Screen.visible_titles` 高度重叠的
      `StructuredScreen.ocr_items`，断言 `build_hints()` 返回 `outcome="hit"` 且
      `hints`/`candidates` 非空；构造与任一 screen 无重叠的 OCR 结果，断言
      `outcome="no_match"`、`no_match_reason="no_screen_matched"`、`hints==[]`；构造匹配但
      `confirmed`/`visually_confirmed` element 断言大量缺失的 OCR 结果，断言
      `outcome="inconsistent"`、`no_match_reason="screen_content_inconsistent"`
      （research.md §9 阈值默认值）（FR-014）
- [X] T039 [P] [US3] 编写 `vnc_agent/tests/unit/ui_index/test_no_index_passthrough.py`：
      `UiIndexConfig.bundle_dir is None` 时 `build_hints()` 返回
      `([], [], IndexUsageAuditRecord(outcome="not_configured", ...))`（FR-011）
- [X] T040 [P] [US3] 编写 `vnc_agent/tests/unit/ui_index/test_no_coordinate_bypass.py`：
      构造 `Element.normalized_bounds` 进入 `GroundingRequest.ui_index_candidates`，断言
      `SemanticAction` 序列化结果中不存在任何坐标字段（复用既有
      `tests/unit/test_semantic_action_no_coords.py` 的断言方式）；断言
      `GroundingResult.candidates[].bbox` 的值来自 `resolve_pixel_bbox()` 换算路径而非
      `normalized_bounds` 原始整数直接透传（FR-009）（contracts/
      ui-index-consumer-interfaces.md §9）；断言源自 `ui_index_candidates` 的候选在
      `GroundingResult.candidates[].reason` 中带有可识别前缀（如 `"ui_index:"`），使
      SC-004 的事后审计可直接从 `GroundingResult` 读出而不需人工猜测（对应 T051）
- [X] T041 [P] [US3] 编写 `vnc_agent/tests/integration/ui_index/test_preflight_invalid_index.py`：
      将 `UiIndexConfig.bundle_dir` 指向 T013~T021 中任一无效 fixture，触发既有 run 启动
      流程，断言 run 在执行第一个测试步骤**之前**即中止、抛出/返回可诊断错误（内容与
      `ValidationReport` 一致），**没有任何测试步骤被执行**（既有 Planner/Grounder/Executor
      均未被调用）；另断言 `UiIndexConfig.bundle_dir` 为 `None` 或指向 T010~T012 任一有效
      fixture 时 run 正常进入第一个测试步骤（FR-012、spec.md Independent Test 中"不会静默
      使用损坏或不完整的数据"——本任务是此前只有实现、没有测试的 preflight 接线补齐的测试）
- [X] T042 [P] [US3] 编写 `vnc_agent/tests/integration/ui_index/test_verifier_independence.py`：
      使用 T011 fixture 构造一次命中场景（`outcome="hit"`），令对应 `Transition` 声明非空
      的 `expected_visible`/`expected_hidden`/`expected_state_changes`，对同一次动作执行
      分别构造"操作后截图证据支持"与"操作后截图证据不支持"两种独立证据，断言
      `VerificationEngine.verify()` 的判定结果只随截图证据变化，与 `Transition.expected_*`
      的声明内容无关；并断言 `VerificationEngine.verify()` 的调用参数/签名中不包含任何
      `ui_index`/`IndexUsageAuditRecord`/`VisibleElementHint` 类型的输出（FR-008/010/019、
      SC-005、quickstart.md §五、Constitution Principle IV"验证独立闭环"）
- [X] T043 [P] [US3] 编写 `vnc_agent/tests/integration/ui_index/test_existing_testcase_regression.py`：
      对 `vnc_agent/testcases/` 下既有 3 个 POS testcase（`pos-buy-bag-checkout.yaml`、
      `pos-click-icon.yaml`、`pos-hover-probe.yaml`）在 `UiIndexConfig.bundle_dir=None` 下
      执行 `--dry-run`，断言与本 feature 实现前的既有基线（运行产出与校验结果）一致（
      spec.md FR-011）（用户输出"六、文档与验证"）
- [X] T044 [P] [US3] 编写
      `vnc_agent/tests/integration/ui_index/test_no_index_vs_no_match_equivalence.py`：
      使用同一批既有回归 testcase，分别在（a）`UiIndexConfig.bundle_dir=None` 与（b）
      `UiIndexConfig.bundle_dir` 指向一个有效但覆盖当前画面外的 bundle（如取自 T012 中一个
      与既有回归 testcase 画面不重叠的 screen 子集）两种条件下各运行一遍，断言两次运行的
      点击坐标来源、Verifier 判定依据、测试通过/失败结论逐步骤一致（排除审计字段 diff 为
      空），仅审计记录中索引命中信息不同（spec.md SC-003——此前没有任何任务引用 SC-003）

### 实现

- [X] T045 [P] [US3] 在 `vnc_agent/src/vnc_agent/ui_index/sanitizer.py` 实现
      `to_visible_hint(element, bundle)`（对应 T036）（依赖 T028 `repository.py` 解析
      `anchors`/`neighbors` 引用）
- [X] T046 [P] [US3] 在 `vnc_agent/src/vnc_agent/ui_index/audit.py` 实现
      `record_index_usage(iteration, audit)`，调用既有
      `runtime/telemetry.py::log_event()`（对应 T037）
- [X] T047 [US3] 在 `vnc_agent/src/vnc_agent/ui_index/runtime_adapter.py` 实现画面匹配算法（
      `match_score`/`missing_ratio` 阈值判定，research.md §9）与 `build_hints()`（对应
      T038/T039）（调用 T033 查询、T045 `sanitizer`、T046 `audit`）
- [X] T048 [US3] 在 `vnc_agent/src/vnc_agent/models/provider.py` 新增
      `PlannerRequest.ui_index_hints: list[VisibleElementHint] = Field(default_factory=list)`
      与 `GroundingRequest.ui_index_candidates: list[dict[str, Any]] =
      Field(default_factory=list)`（data-model.md §5）
- [X] T049 [US3] 在 `vnc_agent/src/vnc_agent/domain/run.py` 的 `ActionIteration` 新增
      `ui_index_audit: IndexUsageAuditRecord | None = None` 字段（data-model.md §5）
- [X] T050 [US3] 修改 `vnc_agent/src/vnc_agent/planning/planner.py::PlannerOrchestrator.plan()`
      接受可选的已加载 `UiIndexBundle`/`UiIndexConfig` 参数，调用 T047 `build_hints()` 填充
      `PlannerRequest.ui_index_hints` 并写入 T049 审计字段（对应 T040）（不修改既有必需参数
      顺序，新参数默认 `None`）
- [X] T051 [US3] 修改 `vnc_agent/src/vnc_agent/models/mimo_grounder.py`：候选融合逻辑将
      `GroundingRequest.ui_index_candidates` 与既有 `ocr_candidates`/`template_candidates`
      一并纳入、复用既有 `models/coordinate_space.py::resolve_pixel_bbox()` 换算/拒绝路径
      （对应 T040）（不新增独立索引直输通道）；源自 `ui_index_candidates` 的
      `GroundingCandidate` MUST 在其 `reason` 字段写入可识别前缀（如 `"ui_index:"` +
      原有 `label`），使最终 `GroundingResult.candidates` 中每条记录的来源（ocr/template/
      ui_index）可从既有字段直接读出——满足 SC-004 事后审计坐标来源不需新增字段（
      contracts/ui-index-consumer-interfaces.md §9"坐标多源事后可追溯性"）
- [X] T052 [US3] 修改 `vnc_agent/src/vnc_agent/runtime/agent_runtime.py`：在既有 run 启动
      preflight 入口（在文件中：`AgentConfig.ui_index.bundle_dir` 非空时，run 启动阶段调用
      `UiIndexBundle.load()`，失败时抛出错误并阻止执行第一个测试步骤）（FR-012）（对应 T041）
      具体文件以现状 run 启动流程实现为准；实现时用 `grep -rn "def run"
      vnc_agent/src/vnc_agent/runtime/` 确认入口函数

**Checkpoint**: User Story 1+2+3 可独立交付——运行时具备完整的索引提示能力，且回归/审计/
坐标不绕过/无效索引 fail-fast/Verifier 独立性全部有测试覆盖。

---

## Phase 6: User Story 4 - 使用通用生产者 skill 生成可被校验的索引 bundle (Priority: P4)

**Goal**: 产出语言/框架无关的 `generate-ui-analysis-index` skill，指导外部项目生成符合
`ui-analysis-bundle-v1` 契约的 bundle，且不附带任何具体语言解析器。
**Independent Test**: `quick_validate.py` 通过 `assets/bundle-template/` 下的最小有效示例；
通过 `ui-index validate`；T011/T012 两个互不相关 fixture 均用 `ui-index validate` 通过——
作为"两个技术栈不同的外部项目均依据本 skill 生成同构 bundle"的依据。

### 测试（先写，MUST 先失败——以脚本断言形式，非 pytest，因为 skill 本身是文档产物）

- [X] T053 [P] [US4] 编写 `vnc_agent/tests/unit/ui_index/test_skill_bundle_contract_sync.py`：
      解析 `contracts/ui-analysis-bundle-v1.md`（本 spec 目录）与
      `.agents/skills/generate-ui-analysis-index/references/bundle-contract.md` 中的
      字段清单（文件名 + 字段名列表，用简单的表格行提取，不要求语义级解析），断言两份文档
      枚举的必需/可选文件集合与顶层字段名集合一致（防止 §12 提到的漂移）（FR-023）
- [X] T054 [P] [US4] 编写 `vnc_agent/tests/unit/ui_index/test_skill_no_forbidden_content.py`：
      对 `.agents/skills/generate-ui-analysis-index/` 全部文件做关键词扫描，断言不出现
      `Roslyn`/`MSBuildWorkspace`/`JavaParser`/`TypeScript Compiler`/`XAML`（作为解析器
      依赖名而非"举例提及某框架"的上下文需人工复核关键词表：Figma API 端点/POS 专用词等）
      （复用 `tests/unit/test_no_business_keywords_in_core.py` 的关键词表），且不存在
      `README.md`/`CHANGELOG.md` 文件（FR-029）（用户本次输出"五、通用 Skill"）

### 实现

- [X] T055 [P] [US4] 创建 `.agents/skills/generate-ui-analysis-index/SKILL.md`
      （frontmatter `name: generate-ui-analysis-index` + `description`；正文只含
      概述、6 个核心分析目标（画面/元素/文本角色/相对位置/邻接关系/动作状态跳转/业务
      流程）、交付前必须运行 `vnc-agent ui-index validate` 的指引、指向 `references/` 与
      `assets/` 的链接；不重复 references 中的字段级细节）（对应 FR-020/021/028）
- [X] T056 [P] [US4] 创建 `.agents/skills/generate-ui-analysis-index/agents/openai.yaml`
      （skill-creator 规范要求的 agent 元数据文件，声明本 skill 面向分析并生成 UI bundle"
      任务，不绑定任何具体语言工具链）
- [X] T057 [US4] 创建 `.agents/skills/generate-ui-analysis-index/references/bundle-contract.md`
      （contracts/ui-analysis-bundle-v1.md 的生产方导向精简版：文件清单、每文件字段表、
      稳定 ID/schema 版本/producer/source_revision 表达方式，内容 MUST 与
      contracts/ui-analysis-bundle-v1.md 逐项一致，供 T053 校验；依赖 T007/plan.md 契约
      已定稿）
- [X] T058 [P] [US4] 创建 `.agents/skills/generate-ui-analysis-index/references/confidence-rules.md`
      （FR-025/026 的生产方指导：四类可信度定义、`level`+`score` 复合结构、禁止将
      statically_inferred/visually_confirmed/requires_runtime_verification 标注为
      confirmed 的具体反例）
- [X] T059 [P] [US4] 创建 `.agents/skills/generate-ui-analysis-index/references/framework-examples.md`
      （两份，为"概念映射"分别用中性通用描述举例说明："XAML 风格框架的
      Window/Control/Click 事件" "Web 框架的 Component/onClick" 应如何分别映射到
      `Screen`/`Element`/`transition trigger_action` 概念；MUST 是纯断点概念映射说明，
      MUST NOT 包含任何可执行的解析代码或对具体解析库的调用示例，对应 FR-021/029；
      用户本次输出"五、Skill 中不得包含...解析器"）
- [X] T060 [US4] 创建 `.agents/skills/generate-ui-analysis-index/assets/bundle-template/blank/`
      下的空白模板骨架（`manifest.yaml`、`screens.jsonl`、`elements.jsonl`、
      `transitions.jsonl`；字段占位、类型合法仅为示意最小内容，供生产方复制填写）（
      FR-027）
- [X] T061 [US4] 创建
      `.agents/skills/generate-ui-analysis-index/assets/bundle-template/minimal-valid-example/`
      下的最小有效示例（`manifest.yaml`、`screens.jsonl`（≥1 条）、`elements.jsonl`（≥1 条）、
      `transitions.jsonl`（≥1 条），可直接复用/裁剪自 T010 内容）（FR-027）（quickstart.md §一）
- [X] T062 [US4] 运行 skill-creator 校验：执行
      `python "$HOME/.claude/skills/skill-creator/scripts/quick_validate.py"
      .agents/skills/generate-ui-analysis-index"`，确认输出 `Skill is valid!` 且退出码 `0`
      （research.md §12）（依赖 T055）
- [X] T063 [US4] 运行 `vnc-agent ui-index validate
      .agents/skills/generate-ui-analysis-index/assets/bundle-template/minimal-valid-example`
      确认退出码 `0`（对应 quickstart.md §一）（依赖 T029/T061）
- [X] T064 [US4] 运行 `vnc-agent ui-index validate vnc_agent/tests/fixtures/ui_index/fixture_form_input`
      与 `vnc-agent ui-index validate vnc_agent/tests/fixtures/ui_index/fixture_icon_overlay`
      确认退出码 `0`（作为"两个互不相关 GUI 均通过本 skill 描述的契约校验"的依据
      （spec.md SC-008/SC-011）（quickstart.md §五））

**Checkpoint**: 全部 4 个 User Story 均可独立交付；通用 producer skill 就绪且通过 skill-creator 校验。

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: 跨 Story 的一致性检查、既有测试回归、静态检查、Constitution 合规复核。

- [X] T065 [P] 运行 `cd vnc_agent && uv run pytest tests/unit/ui_index/ tests/integration/ui_index/ -v`
      （目标测试集，quickstart.md §九）
- [X] T066 运行 `cd vnc_agent && uv run pytest` 全量套件，确认本 feature 未破坏任何既有
      测试（spec.md FR-011）
- [X] T067 [P] 运行 `cd vnc_agent && uv run ruff check src/vnc_agent/ui_index/
      src/vnc_agent/config.py src/vnc_agent/models/provider.py src/vnc_agent/domain/run.py
      src/vnc_agent/planning/planner.py src/vnc_agent/models/mimo_grounder.py`
- [X] T068 对 `vnc_agent/testcases/pos-buy-bag-checkout.yaml`、
      `vnc_agent/testcases/pos-click-icon.yaml`、`vnc_agent/testcases/pos-hover-probe.yaml`
      执行 `uv run vnc-agent run testcases/<file>.yaml --dry-run --config config`（未配置
      `ui_index.bundle_dir`），确认三行为与本 feature 实现前一致（用户本次输出"六、
      文档与验证"——T043 的手工复核版本）
- [X] T069 [P] 扩展 `vnc_agent/tests/unit/test_no_business_keywords_in_core.py` 的扫描
      范围至 `src/vnc_agent/ui_index/**`、`src/vnc_agent/config.py` 新增段落、
      `src/vnc_agent/models/provider.py` 新增字段、`src/vnc_agent/domain/run.py` 新增字段
      （断言不出现 POS/Barcode/预/现计/购物车等固定业务关键词）（spec.md SC-009）
- [X] T070 对 `vnc_agent/src/vnc_agent/ui_index/**` 与
      `.agents/skills/generate-ui-analysis-index/**` 做一次显式关键词 grep 复核（
      `Roslyn`、`MSBuildWorkspace`、`JavaParser`、`TypeScript Compiler`、
      `System.Windows.Markup`（XAML 解析库特征）、`figma.com/api`、POS 专用词表等），确认
      核心代码与 skill 均不包含任何具体语言/框架的源码解析实现（spec.md FR-017、用户本次
      输出"六、文档与验证"最后一条）
- [X] T071 更新 [quickstart.md](./quickstart.md)（如实现路径与既有入口与此任务同步文档
      不引入新行为）

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**：无依赖，立即开始
- **Foundational (Phase 2)**：依赖 Setup，**阻塞全部 4 个 User Story**
- **US1 (Phase 3)**：依赖 Foundational
- **US2 (Phase 4)**：依赖 Phase 3（`repository.py` 的加载与索引能力）
- **US3 (Phase 5)**：依赖 Phase 3（`repository.py`）与 Phase 4（`query.py`、`runtime_adapter`
  内部调用查询能力组装 hints）
- **US4 (Phase 6)**：依赖 Phase 3（`ui-index validate` CLI 必须先可用才能验证 skill 产出物）；
  与 US2/US3 实现无代码依赖，可在 Foundational 完成后与 US2/US3 并行推进，但验收任务
  T063/T064 需等 T029 完成
- **Polish (Phase 7)**：依赖全部 US1~US4 完成

### Within Each Story

- 无效/跨场景 fixture → 该 Story 的测试 → 该 Story 的实现（严格先测试后实现）
- `models.py`/`errors.py`（Foundational）先于各 Story 专用的实现
- T041（preflight fail-fast 测试）先于 T052（preflight 接线实现）
- T042（Verifier 独立性测试）不依赖任何本 feature 实现任务——官方一条纯回归契约断言，
  验证 Verifier 代码路径确实未被本 feature 触碰，可与 T036~T041 并行编写

### Parallel Opportunities

- Phase 2 的 T004/T005/T006（测试）可并行；T007/T008（实现）可并行；T010/T011/T012（fixture）
  可并行
- Phase 3 的 T013~T021（9 个无效 fixture）全部可并行；T022~T025（测试）内部可并行
- Phase 5 的 T036/T037/T038/T039/T040/T041/T042（测试）内部可并行；T045/T046（实现）可并行
- Phase 6 的 T055/T056/T058/T059（skill 文档）可并行；T053/T054（测试）可并行
- US2（Phase 4）与 US4（Phase 6）在 Phase 3 完成后可由不同开发者并行推进

---

## Parallel Example: Phase 2 (Foundational)

```bash
# 并行编写测试：
Task: "编写 vnc_agent/tests/unit/ui_index/test_models.py"
Task: "编写 vnc_agent/tests/unit/ui_index/test_errors.py"
Task: "编写 vnc_agent/tests/unit/test_config_ui_index.py"

# 测试确认失败后，并行实现：
Task: "实现 vnc_agent/src/vnc_agent/ui_index/models.py"
Task: "实现 vnc_agent/src/vnc_agent/ui_index/errors.py"

# 并行创建 fixture：
Task: "创建 vnc_agent/tests/fixtures/ui_index/valid_minimal/"
Task: "创建 vnc_agent/tests/fixtures/ui_index/fixture_form_input/"
Task: "创建 vnc_agent/tests/fixtures/ui_index/fixture_icon_overlay/"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. 完成 Phase 1 Setup
2. 完成 Phase 2 Foundational（阻塞项）
3. 完成 Phase 3 US1（读取校验 CLI validate）
4. **停下验证**：`vnc-agent ui-index validate` 对全部 fixture 产出正确结论
5. 此时已可作为独立能力交付——外部项目可以先用这个 MVP 自检 bundle，不必等 US2~US4

### Incremental Delivery

1. Setup + Foundational → 基础就绪
2. + US1 → 独立验证 → 可交付（bundle 校验能力，MVP）
3. + US2 → 独立验证 → 可交付（testcase 编写查询能力）
4. + US3 → 独立验证 → 可交付（运行时提示能力 + preflight fail-fast + Verifier 独立性）
   （风险最高，放在查询能力之后）
5. + US4 → 独立验证 → 可交付（外部生产方生成就绪）
6. Polish → 全量回归 + 静态检查 + Constitution 合规复核

---

## Notes

- `[P]` 任务 = 不同文件、无未完成依赖
- `[Story]` 标记用于按 User Story 追溯任务
- 每个测试任务 MUST 在对应实现任务完成前处于失败状态（先写测试、确认失败、再实现）
- T052（preflight 接线）在实现前先用 `grep -rn "def run"
  vnc_agent/src/vnc_agent/runtime/` 确认现状入口函数签名，避免猜测既有代码结构；T041 应
  在 T052 之前编写并确认失败
- 每完成一个 Phase 建议提交一次，便于按 Story 回归审查

---

## Phase 8: Convergence

**Purpose**: `/speckit-converge` 对照实际代码（而非 tasks.md 的勾选状态）复核 spec.md/
plan.md/tasks.md 的意图是否已全部落实。全部 71 个既有任务复核结果：声明的产出物均真实存在
且测试通过（`uv run pytest` 全量 763 passed / 1 skipped / 1 deselected，`ruff check` 全部
touched 文件 clean，`pyproject.toml`/`uv.lock` 未新增依赖）。发现 1 处 `partial` 缺口：

- [X] T072 编写 `vnc_agent/tests/unit/ui_index/test_report_includes_audit.py`：构造一个含
      非空 `ActionIteration.ui_index_audit`（`IndexUsageAuditRecord(outcome="hit", ...)`）的
      `TestRun`，调用 `reporting/json_report.py::build_report_dict()`，断言返回字典中对应
      iteration 条目包含 `ui_index_audit` 键且内容与源记录一致；同时断言
      `outcome="not_configured"`（即索引未启用）时该键仍存在但为 `None`（而不是被静默省略，
      保持与其它可选字段一致的显式空值约定） per FR-013, SC-006 (partial)
- [X] T073 在 `vnc_agent/src/vnc_agent/reporting/json_report.py::build_report_dict()` 的
      per-iteration 字典中新增一项：`"ui_index_audit": (it.ui_index_audit.model_dump(mode="json")
      if it.ui_index_audit else None)`（与既有 `verification_result`/`action_effect` 等字段
      同一模式）。当前该函数手工枚举每个 `ActionIteration` 字段（不是泛化 `model_dump()`），
      遗漏了 feature 007 新增的 `ui_index_audit`——数据已正确写入 `ActionIteration` 与结构化
      JSON Lines 日志（`ui_index/audit.py::record_index_usage()`），但从未到达
      `build_report_dict()` 产出的 JSON 报告，`html_report.py::render_html_report()` 直接
      复用同一函数产出，因此 HTML 报告同样缺失；补齐后两者自动一并覆盖，使 SC-006"事后均可
      从审计输出中查到"对 HTML/JSON 报告这一路径同样成立，不再只依赖结构化日志文件 per
      FR-013, SC-006, Constitution"制品与可观测性" (partial)

---

## Phase 9: Convergence

**Purpose**: `/speckit-converge` 在 T072/T073 完成后再次对照实际代码复核。发现 T073 引入了
一处对既有（feature 001-004）JSON 报告向后兼容契约的回归。

- [X] T074 修复 T073 引入的兼容性回归：在
      `vnc_agent/tests/fixtures/test_json_report_compatibility.py` 中把 `"ui_index_audit"`
      加入 `_LEGACY_ITERATION_KEYS`（该集合是逐条精确匹配、不是 additive-only 白名单——
      feature 003 新增 `coordinate_space_audit` 时走的就是这条路径，为本次新增字段延续
      同一惯例）；随后删除并重新生成
      `vnc_agent/tests/snapshots/report_legacy_projection.json` 黄金快照（运行
      `test_legacy_non_path_projection_golden_snapshot` 一次让其自动重建文件，测试会
      `pytest.skip` 提示"created it for review"），人工检查新快照中新增的
      `"ui_index_audit"` 字段值（`_bare_run()` 场景下应为 `null`，因为该基线 fixture 未配置
      索引）后提交；完成后重新运行
      `uv run pytest tests/fixtures/test_json_report_compatibility.py -v` 确认全部 8 项
      通过，且重新运行 `uv run pytest`（全量）确认不再有回归 per plan.md"新增可选字段…
      不修改任何既有字段语义"、既有 report-contract.md"Backward compatibility rule"
      (contradicts)
