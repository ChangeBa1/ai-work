# Tasks: VNC 黑盒 GUI 自动化测试核心执行闭环

**Input**: Design documents from `/specs/001-vnc-core-execution-loop/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: 本项目 Constitution 的"测试覆盖门禁"要求核心模块至少覆盖单元/离线固定截图/VNC
集成/端到端四类测试之一，plan.md 的 Testing 章节也明确了四类测试的分工，因此本任务列表
**包含**测试任务（非可选）。

**Organization**: 任务按用户故事分组，P1 组的 8 个故事（US1、US2、US3、US4、US5、US6、
US7、US9）共同构成 MVP 闭环——spec.md 明确指出这 8 个故事是"闭环是否可行"这一验证目标的
最小必要集合，缺一不可；US8（P2）在此之上加固鲁棒性；US10（P3）为未来自进化预留数据。

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 可并行执行（不同文件、无依赖）
- **[Story]**: 所属用户故事（US1~US10），Setup/Foundational/Polish 阶段任务无此标签
- 每个任务均给出相对 `vnc_agent/` 项目根目录的具体文件路径

## Path Conventions

单一项目结构（非 Web 前后端分离）。所有源码路径以项目根目录下的 `vnc_agent/src/vnc_agent/`
为前缀，测试路径以 `vnc_agent/tests/` 为前缀，与 plan.md 的 Project Structure 一致。

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: 项目初始化与基础骨架

- [X] T001 按 plan.md Project Structure 创建 `vnc_agent/` 项目骨架：`src/vnc_agent/` 下
      `runtime/ domain/ drivers/ perception/ocr/ perception/template/ models/ planning/
      execution/ verification/ recovery/ evolution/ storage/ reporting/ api/` 各子包及
      `__init__.py`，以及 `config/ testcases/ templates/ data/ artifacts/
      tests/{unit,fixtures,integration,e2e}/` 目录
- [X] T002 在 `vnc_agent/pyproject.toml` 中配置依赖：`vncdotool`、`opencv-python`、
      `numpy`、轻量 OCR（ONNX Runtime，如 `rapidocr-onnxruntime`）、`httpx`、`pydantic>=2`、
      `pydantic-settings`、`PyYAML`、`SQLAlchemy>=2`、`aiosqlite`、`structlog`、`typer`、
      `jinja2`、`pytest`、`pytest-asyncio`
- [X] T003 [P] 在 `vnc_agent/pyproject.toml` 中配置 lint/format 工具（如 `ruff`）与
      `pytest`/`pytest-asyncio` 运行配置（`[tool.pytest.ini_options]`）
- [X] T004 [P] 创建默认配置文件 `vnc_agent/config/agent.yaml`（wait/step/artifacts/
      security 默认值，含 `recovery.<failure_type>.max_retries`/`cooldown_ms` 每种
      `FailureType` 一条）、`vnc_agent/config/models.yaml`（Planner/Grounder provider 与
      超时占位，含 `models.planner.describe_screen_timeout_seconds`）、
      `vnc_agent/config/vnc-targets.yaml`（VNC 连接信息，密码为环境变量引用），字段对齐
      data-model.md §11（含需求质量门禁 2026-07-21 新增的三个字段）

**Checkpoint**: 项目可安装（`pip install -e .`），空骨架可被导入

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: 所有用户故事共用的领域模型、配置、日志、VNC 驱动与运行时骨架

**⚠️ CRITICAL**: 本阶段完成前不得开始任何用户故事的实现

- [X] T005 [P] 实现 `TestCase`/`TestStep` Pydantic 模型（data-model.md §1~2，含
      `mode="explicit"` 约束与 `max_retries≥0` 校验）于
      `vnc_agent/src/vnc_agent/domain/testcase.py`
- [X] T006 [P] 实现 `StructuredScreen`/`ScreenFrame`/`OCRItem`/`TemplateMatch`/`Region`/
      `VisionUnderstanding` 模型（data-model.md §3）于
      `vnc_agent/src/vnc_agent/domain/observation.py`
- [X] T007 [P] 实现 `SemanticAction`/`TargetDescription`/`ExecutableAction` 模型
      （data-model.md §4/§6，`SemanticAction` 类型层面不含 `x`/`y` 字段以落实 FR-013）于
      `vnc_agent/src/vnc_agent/domain/action.py`
- [X] T008 [P] 实现 `GroundingResult`/`GroundingCandidate` 模型（data-model.md §5）于
      `vnc_agent/src/vnc_agent/domain/grounding.py`
- [X] T009 [P] 实现 `WaitResult`/`VerificationSpec`/`VerificationCondition`/
      `VerificationResult` 模型（data-model.md §7）于
      `vnc_agent/src/vnc_agent/domain/verification.py`
- [X] T010 [P] 实现 `FailureType`/`GroundingLowConfidenceReason`/`RecoveryAttempt` 模型
      （data-model.md §8）于 `vnc_agent/src/vnc_agent/domain/recovery.py`
- [X] T011 [P] 实现 `ActionIteration`/`StepRecord`/`TestRun`/`VisualExperience` 模型
      （data-model.md §9~10）于 `vnc_agent/src/vnc_agent/domain/run.py`
- [X] T012 实现配置加载（`pydantic-settings` `BaseSettings`，读取
      `config/agent.yaml`/`config/models.yaml`/`config/vnc-targets.yaml` 并绑定环境变量
      `VNC_AGENT_*_API_KEY`/密码引用，MUST NOT 落明文，对应 FR-045/047）于
      `vnc_agent/src/vnc_agent/config.py`
- [X] T013 [P] 实现结构化日志配置（`structlog` JSON Lines 输出，含 run_id/step_id/
      state/event/耗时字段，敏感字段黑名单过滤处理器）于
      `vnc_agent/src/vnc_agent/logging_setup.py`
- [X] T014 定义 `VNCDriver` Protocol（connect/disconnect/reconnect/capture_screen/
      capture_region/send_key/send_hotkey/send_text/mouse_move/click/double_click/
      right_click/scroll/drag）于 `vnc_agent/src/vnc_agent/drivers/base.py`
- [X] T015 实现 vncdotool 驱动（Twisted 阻塞调用与 asyncio 主循环的桥接，专用后台线程或
      `asyncio.to_thread` + `asyncio.Future` 回传，research.md §1）于
      `vnc_agent/src/vnc_agent/drivers/vncdotool_driver.py`（依赖 T014）
- [X] T016 [P] 实现按键语义名到 vncdotool 键码的映射表于
      `vnc_agent/src/vnc_agent/drivers/key_mapping.py`
- [X] T017 实现 `AgentState` 枚举与状态转移表（data-model.md §12：
      `CREATED→CONNECTING→PREPARING→OBSERVING→…→PASSED/FAILED/CANCELLED`）于
      `vnc_agent/src/vnc_agent/runtime/state_machine.py`
- [X] T018 实现 `RunContext`（承载当前 `TestRun`/`StepRecord`/`ActionIteration` 累积状态）
      于 `vnc_agent/src/vnc_agent/runtime/run_context.py`（依赖 T005-T011）
- [X] T019 实现 `StepController`（为每个 `TestStep` 维护单一剩余预算计数器，验证失败重试/
      步骤内微动作迭代/VNC 重连整步重做三者共用同一计数器，research.md §10）于
      `vnc_agent/src/vnc_agent/runtime/step_controller.py`（依赖 T018）
- [X] T020 [P] 定义运行时异常类型（`VNCConnectionError`、`StepBudgetExhaustedError`、
      `PlanValidationError` 等）于 `vnc_agent/src/vnc_agent/runtime/exceptions.py`

**Checkpoint**: 领域模型、配置、日志、VNC 驱动、状态机骨架就绪，用户故事实现可以开始

---

## Phase 3: User Story 1 - 执行声明式 GUI 测试用例 (Priority: P1) 🎯 MVP 入口

**Goal**: 加载并校验声明式 YAML 测试用例，按已声明步骤顺序调度，不自主插入/省略步骤

**Independent Test**: 提交一份仅含 1~2 个步骤的最小 YAML 用例，验证系统能否正确加载、
校验并按顺序调度，无需后续故事的具体实现

### Tests for User Story 1

- [X] T021 [P] [US1] 单元测试：`TestCase`/`TestStep` 缺失必填字段时被拒绝并返回字段级
      错误、`mode` 非 `explicit` 时被拒绝于
      `vnc_agent/tests/unit/test_testcase_validation.py`
- [X] T022 [P] [US1] 固定用例文件测试：加载合法/非法 YAML 用例，验证解析结果与错误信息于
      `vnc_agent/tests/fixtures/test_testcase_loader.py`

### Implementation for User Story 1

- [X] T023 [US1] 在 `domain/testcase.py` 中扩展 YAML 加载与 JSON Schema 校验函数
      （`load_test_case(path) -> TestCase`，对齐 contracts/test-case-schema.md，逐字段
      报错而非笼统失败，对应 FR-003）于
      `vnc_agent/src/vnc_agent/domain/testcase.py`（依赖 T005）
- [X] T024 [US1] 实现 CLI `vnc-agent run <file> --dry-run` 路径（仅执行用例格式校验，
      不连接 VNC，退出码 2 表示校验失败，对应 contracts/cli-contract.md）于
      `vnc_agent/src/vnc_agent/api/cli.py`（依赖 T023）
- [X] T025 [US1] 准备最小 YAML 用例样例：`vnc_agent/testcases/smoke-connect.yaml`（合法）
      与 `vnc_agent/tests/fixtures/testcases/`（含至少一份缺字段、一份非法 `mode` 的用例）
- [X] T026 [US1] 在 `RunContext` 中实现步骤队列（严格按 `TestCase.steps` 声明顺序调度，
      不额外插入或省略步骤，对应 Acceptance Scenario 3）于
      `vnc_agent/src/vnc_agent/runtime/run_context.py`（依赖 T018、T023）

**Checkpoint**: 测试用例可被独立加载、校验、按序调度

---

## Phase 4: User Story 2 - 观察和理解当前屏幕 (Priority: P1)

**Goal**: 获取完整/区域截图，输出结构化屏幕状态（OCR、模板匹配、变化检测、必要时的视觉
理解），供后续决策与证据留存使用

**Independent Test**: 使用固定截图集合（有变化/无变化/含弹窗/含加载动画），验证观察管线
输出结构化结果，无需连接真实 VNC

### Tests for User Story 2

- [X] T027 [P] [US2] 固定截图测试：完整/区域截图采集与裁剪偏移记录于
      `vnc_agent/tests/fixtures/test_screenshot.py`
- [X] T028 [P] [US2] 固定截图测试：连续两帧无变化 vs 有变化的 `changed_since_last` 判定
      于 `vnc_agent/tests/fixtures/test_screen_diff.py`
- [X] T029 [P] [US2] 固定截图测试：OCR 文字识别与位置返回于
      `vnc_agent/tests/fixtures/test_ocr.py`
- [X] T030 [P] [US2] 固定截图测试：已配置模板的匹配位置识别于
      `vnc_agent/tests/fixtures/test_template_matching.py`
- [X] T031 [P] [US2] 固定场景测试（mock `PlannerProvider`）：图像哈希/OCR/模板均不足以
      理解页面时触发视觉模型补充理解，结果并入结构化屏幕状态而非仅存自然语言描述于
      `vnc_agent/tests/fixtures/test_vision_understanding_fallback.py`

### Implementation for User Story 2

- [X] T032 [P] [US2] 实现完整/区域截图采集（经 `VNCDriver` 获取，记录实际分辨率、时间戳、
      存储路径，区域截图记录相对原图的坐标偏移，对应 FR-005/009；捕获后立即将原始像素数据
      落盘，函数返回值仅含存储路径与元信息、不长期持有原始字节，对应 plan.md Constraints
      "原始截图立即落盘"与 SC-009 的资源约束）于
      `vnc_agent/src/vnc_agent/perception/screenshot.py`（依赖 T014）
- [X] T033 [P] [US2] 实现帧间差异检测（`changed_since_last`/`changed_regions`，对应
      FR-007）于 `vnc_agent/src/vnc_agent/perception/screen_diff.py`
- [X] T034 [P] [US2] 实现轻量 OCR 引擎封装（ONNX Runtime 推理，按需加载，ROI 限定，对应
      FR-006）于 `vnc_agent/src/vnc_agent/perception/ocr/engine.py`
- [X] T035 [P] [US2] 实现固定图片模板匹配引擎（对应 FR-008）于
      `vnc_agent/src/vnc_agent/perception/template/matcher.py`
- [X] T036 [US2] 实现结构化屏幕状态组装（汇总截图/OCR/模板/变化检测，必要时并入视觉理解
      结果，对应 FR-011）于 `vnc_agent/src/vnc_agent/perception/structured_screen.py`
      （依赖 T032-T035、T006）
- [X] T037 [US2] 定义 `PlannerProvider`（`plan`/`describe_screen` 两个方法，均为
      `@runtime_checkable` Protocol 的必需方法）与 `GrounderProvider`（`ground` 方法）
      Protocol，含 `VisionUnderstandingRequest`/`VisionUnderstandingResponse` 的
      Pydantic 模型（`mode="describe"|"answer_question"`，对应
      contracts/model-provider-contract.md 的 `PlannerProvider.describe_screen`
      契约）；同时实现按 `models.yaml` 的 `provider` 字段装配具体实现类的工厂函数，装配后
      MUST 立即执行 `isinstance` 结构化校验，确认实现类具备 Protocol 要求的全部方法，
      校验失败 MUST 在启动阶段直接报错退出（对应 research.md §13）于
      `vnc_agent/src/vnc_agent/models/provider.py`
- [X] T038 [US2] 实现观察管线编排（常规手段均不足以理解页面时调用
      `PlannerProvider.describe_screen(mode="describe")` 补充理解，响应的
      `description`/`confidence`/`model_name` 写入 `StructuredScreen.vision_understanding`
      （data-model.md §3），对应 FR-010）于
      `vnc_agent/src/vnc_agent/perception/pipeline.py`（依赖 T036、T037）

**Checkpoint**: 观察管线可独立输出结构化屏幕状态

---

## Phase 5: User Story 3 - 选择可靠的操作方式 (Priority: P1)

**Goal**: Planner 只输出语义动作，Action Policy 按"快捷键→焦点导航→OCR/模板→MiMo
Grounding→停止恢复"优先级解析执行方式，步骤内可多轮迭代

**Independent Test**: 给定语义动作与模拟页面状态，验证动作选择逻辑按既定优先级选出候选
方式，无需真实执行键鼠动作

### Tests for User Story 3

- [X] T039 [P] [US3] 单元测试：已知快捷键场景优先选快捷键路径不调用视觉定位；OCR 可唯一
      定位场景选 OCR 路径不直接用视觉模型；均无法确定场景进入停止恢复于
      `vnc_agent/tests/unit/test_action_policy_priority.py`
- [X] T040 [P] [US3] 单元测试：`SemanticAction` 模型/校验层拒绝任何裸坐标字段于
      `vnc_agent/tests/unit/test_semantic_action_no_coords.py`

### Implementation for User Story 3

- [X] T041 [US3] 实现 `PlannerProvider` 客户端（`httpx` 异步调用，请求体含
      `step_intent`/`expected`/`structured_screen`/`iteration_index`/
      `remaining_iteration_budget`/`previous_verification_result`，响应经 Pydantic 校验，
      对应 contracts/model-provider-contract.md）于
      `vnc_agent/src/vnc_agent/models/planner_client.py`（依赖 T037）
- [X] T042 [US3] 实现 Planner 编排（调用 `PlannerProvider.plan`，将
      `task_completed_hint` 仅作为参考提示，MUST NOT 用于步骤通过判定，对应宪法 Core
      Principle I/II）于 `vnc_agent/src/vnc_agent/planning/planner.py`（依赖 T041）
- [X] T043 [US3] 实现 Action Policy 优先级解析器（① 已配置快捷键 → ② Tab/Shift+Tab/
      Enter/Space 焦点导航 → ③ OCR/模板唯一定位 → ④ MiMo Grounding → ⑤ 停止并恢复，
      每轮迭代独立走一遍优先级，对应 FR-012）于
      `vnc_agent/src/vnc_agent/planning/action_policy.py`
- [X] T044 [US3] 实现 Planner 响应校验器（JSON 解析 → Pydantic 校验 → 动作白名单校验 →
      风险策略校验四层检查，连续两次非法响应即标记步骤失败进入恢复，对应
      contracts/model-provider-contract.md 契约保证）于
      `vnc_agent/src/vnc_agent/planning/plan_validator.py`

**Checkpoint**: 动作选择逻辑可独立验证优先级顺序

---

## Phase 6: User Story 4 - 通过 MiMo 定位 GUI 目标 (Priority: P1)

**Goal**: 将语义目标转换为实际屏幕区域，返回≤3 个带置信度和理由的候选，坐标还原为原始
VNC 像素坐标，越界候选被拒绝

**Independent Test**: 使用固定截图和语义目标描述，验证 Grounding 调用、坐标系还原与候选
筛选逻辑，无需真实连接 VNC 或执行点击

### Tests for User Story 4

- [X] T045 [P] [US4] 固定截图测试：Grounding 请求/响应解析、裁剪偏移坐标还原、
      `found=false` 时返回空候选列表于
      `vnc_agent/tests/fixtures/test_mimo_grounder.py`
- [X] T046 [P] [US4] 单元测试：越界候选在进入 Action Policy 前被过滤且不计入"已找到"
      （对应 FR-019）于 `vnc_agent/tests/unit/test_grounding_bounds_check.py`

### Implementation for User Story 4

- [X] T047 [US4] 实现 MiMo-V2.5 Grounder 客户端（通过 OpenCode Go API 调用，请求体含
      `image_ref`/`crop_offset`/`target`/`ocr_candidates`/`template_candidates`，响应
      `candidates` 长度 ≤3，不做图像遮罩，对应 FR-015~018/FR-049）于
      `vnc_agent/src/vnc_agent/models/mimo_grounder.py`（依赖 T037）
- [X] T048 [P] [US4] 实现模型响应解析器（JSON → Pydantic `GroundingResult` 校验）于
      `vnc_agent/src/vnc_agent/models/response_parser.py`
- [X] T049 [US4] 在 Action Policy 中扩展 Grounding 触发与候选边界校验（越界 bbox 在执行前
      被拒绝，`found=false`/整体置信度低/Top-1-Top-2 接近三种情况分别归类，对应 FR-016/019
      与 data-model.md §8）于
      `vnc_agent/src/vnc_agent/planning/action_policy.py`（依赖 T043、T047、T048）

**Checkpoint**: 视觉定位可独立完成坐标还原与候选筛选

---

## Phase 7: User Story 5 - 执行键盘和鼠标动作 (Priority: P1)

**Goal**: 通过 VNC 执行文本输入、按键、组合键、焦点导航、鼠标动作，均有独立超时，异常时
释放修饰键，执行结果仅表示"已发送"

**Independent Test**: 针对已建立的 VNC 连接，独立触发单一动作类型，验证正确发送、超时
保护、结果如实记录，无需依赖 Planner/Grounder 完整决策链路

### Tests for User Story 5

- [X] T050 [P] [US5] 集成测试（针对本地测试用 VNC 服务，research.md §9）：文本输入、
      组合键、鼠标点击/双击/右键/滚轮/拖拽的发送与记录、动作超时终止、异常后修饰键释放于
      `vnc_agent/tests/integration/test_execution.py`

### Implementation for User Story 5

- [X] T051 [P] [US5] 实现键盘执行器（文本输入、单键、组合快捷键、Tab/Shift+Tab/Enter/
      Escape/Space，对应 FR-020）于
      `vnc_agent/src/vnc_agent/execution/keyboard_executor.py`（依赖 T014）
- [X] T052 [P] [US5] 实现鼠标执行器（移动、单击、双击、右键、滚轮、简单拖拽；点击前记录
      `target_region` 与 `actual_click_point`，对应 FR-020/023）于
      `vnc_agent/src/vnc_agent/execution/mouse_executor.py`（依赖 T014）
- [X] T053 [US5] 实现执行路由（按 `ExecutableAction.method` 分发到键盘/鼠标执行器，每个
      动作独立超时，异常提前结束时释放 Ctrl/Alt/Shift/Win 修饰键，`ExecutionResult.success`
      仅表示"已发送"不表示步骤通过，对应 FR-021/022/024）于
      `vnc_agent/src/vnc_agent/execution/router.py`（依赖 T051、T052）

**Checkpoint**: 键鼠动作执行可独立触发与验证

---

## Phase 8: User Story 6 - 等待页面稳定 (Priority: P1)

**Goal**: 动作后基于多帧比对判定页面稳定，屏蔽动态区域，支持区域级检查与提前结束条件

**Independent Test**: 使用模拟连续帧序列（持续变化/逐渐收敛/含动态区域），验证稳定性判定
逻辑，无需真实 VNC 连接

### Tests for User Story 6

- [X] T054 [P] [US6] 固定帧序列测试：≥3 帧差异判定稳定/未稳定、动态区域（时钟/指针邻域/
      加载动画）屏蔽后不影响判定、ROI 限定检查、预期文字/模板提前出现时立即结束等待、
      VNC 断开/错误画面时提前终止等待于
      `vnc_agent/tests/fixtures/test_stability.py`

### Implementation for User Story 6

- [X] T055 [US6] 实现等待/稳定性引擎（连续采集≥3 帧、动态区域掩码、ROI 内像素差异比例
      判定、最短/最大等待时间强制、预期条件提前出现或 VNC 异常时提前终止，对应
      FR-025~030；维护一个大小上限为 5 的滑动帧缓冲区，内存中同时只保留判定所需的最近
      3~5 帧，超出上限的旧帧立即从内存中丢弃（原始像素已由 T032 落盘，内存中只需保留判定
      用的引用/数组），对应 plan.md Constraints"内存中仅保留最近 3～5 帧"与 SC-009）于
      `vnc_agent/src/vnc_agent/perception/stability.py`（依赖 T032、T033、T014）

**Checkpoint**: 等待引擎可独立判定稳定性并支持提前结束

---

## Phase 9: User Story 7 - 独立验证操作结果 (Priority: P1)

**Goal**: 基于操作后独立采集的新证据判定通过/失败/不确定，复合断言下"不确定"具有传染性

**Independent Test**: 使用"操作前/操作后"截图对和验证规则，验证判定逻辑给出正确结果，
无需真实执行动作

### Tests for User Story 7

- [X] T056 [P] [US7] 固定截图对测试：文字/模板出现或消失的验证判定于
      `vnc_agent/tests/fixtures/test_ocr_template_verifiers.py`
- [X] T057 [P] [US7] 固定截图对测试：区域变化/整体变化的验证判定于
      `vnc_agent/tests/fixtures/test_screen_change_verifier.py`
- [X] T058 [P] [US7] 单元测试：复合断言 `all`/`any` 聚合算法，`uncertain` 传染性不被
      静默折叠为 `passed`/`failed`（对应 data-model.md §7 算法与 FR-033）于
      `vnc_agent/tests/unit/test_verification_compound.py`

### Implementation for User Story 7

- [X] T059 [P] [US7] 实现文字出现/消失验证器（复用 OCR 结果）于
      `vnc_agent/src/vnc_agent/verification/ocr_verifier.py`
- [X] T060 [P] [US7] 实现模板出现/消失验证器于
      `vnc_agent/src/vnc_agent/verification/template_verifier.py`
- [X] T061 [P] [US7] 实现区域变化/整体变化验证器于
      `vnc_agent/src/vnc_agent/verification/screen_change_verifier.py`
- [X] T062 [US7] 实现视觉问答验证器（仅当确定性方法无法判断时，对
      `type="visual_question"` 条件调用
      `PlannerProvider.describe_screen(mode="answer_question", question=condition.value)`，
      将响应的 `answer` 字段直接作为该子条件的 `passed`/`failed`/`uncertain` 判定，
      `reason` 写入证据，对应 FR-032/data-model.md §7）于
      `vnc_agent/src/vnc_agent/verification/visual_verifier.py`（依赖 T037）
- [X] T063 [US7] 实现验证引擎（分发 `VerificationCondition` 至对应验证器，判定输入固定为
      操作后新采集的 `StructuredScreen`，按 `all`/`any` 聚合并保留 `uncertain` 传染性，
      对应 FR-031~034）于
      `vnc_agent/src/vnc_agent/verification/engine.py`（依赖 T059-T062、T009）

**Checkpoint**: 验证引擎可独立给出通过/失败/不确定三态判定

---

## Phase 10: User Story 9 - 保存完整测试证据 (Priority: P1)

**Goal**: 每个测试步骤的完整决策与证据写入 SQLite 与制品目录，生成 JSON/HTML 报告

**Independent Test**: 针对已执行完毕的一个测试步骤，验证系统能否生成包含操作前后截图、
各阶段决策与耗时的完整证据记录，并汇总为可阅读报告

### Tests for User Story 9

- [X] T064 [P] [US9] 单元测试：报告 `status` 必须等于最后一轮 `verification_result.status`
      （`uncertain` 在预算耗尽时归为 `failed`），不出现"实际失败但报告 passed"（对应
      SC-007）于 `vnc_agent/tests/unit/test_report_status_consistency.py`
- [X] T065 [P] [US9] 固定数据测试：基于已构造的 `StepRecord` 生成 JSON/HTML 报告，二者
      数据源一致于 `vnc_agent/tests/fixtures/test_report_builder.py`

### Implementation for User Story 9

- [X] T066 [US9] 实现 SQLite 数据表结构与异步引擎/会话（SQLAlchemy 2.x + `aiosqlite`，镜像
      `domain/run.py` 实体）于 `vnc_agent/src/vnc_agent/storage/database.py`（依赖 T011）
- [X] T067 [US9] 实现仓储层（`TestRun`/`StepRecord`/`ActionIteration`/`RecoveryAttempt`
      的增删查改）于 `vnc_agent/src/vnc_agent/storage/repositories.py`（依赖 T066）
- [X] T068 [US9] 实现制品存储（截图落盘、落盘前对已配置敏感区域打码，对应 FR-049、
      模型请求/响应存档）于
      `vnc_agent/src/vnc_agent/storage/artifact_store.py`
- [X] T069 [P] [US9] 实现 JSON 报告生成（Pydantic `model_dump_json()`，结构对齐
      contracts/report-schema.md）于 `vnc_agent/src/vnc_agent/reporting/json_report.py`
- [X] T070 [P] [US9] 实现 HTML 报告渲染（Jinja2 单文件模板，内嵌截图缩略图/步骤时间线/
      失败证据折叠区，与 JSON 同一数据源）于
      `vnc_agent/src/vnc_agent/reporting/html_report.py`
- [X] T071 [US9] 实现报告构建编排（从仓储层组装 `TestRun`/`StepRecord`，渲染前应用敏感区域
      遮罩，对应 FR-040~042/049）于
      `vnc_agent/src/vnc_agent/reporting/report_builder.py`（依赖 T067、T069、T070）
- [X] T072 [US9] 实现 CLI `vnc-agent report <run-id> --format json|html|both` 命令（仅从
      已落库数据渲染，不触发新的观察/动作/验证，对应 contracts/cli-contract.md）于
      `vnc_agent/src/vnc_agent/api/cli.py`（依赖 T071）

**Checkpoint**: 完整证据可独立持久化并生成双格式报告

---

## Phase 11: User Story 8 - 处理基础失败 (Priority: P2)

**Goal**: 识别常见失败类型并触发有限恢复策略，每类失败有独立最大重试次数，VNC 断线重连
后整步重做

**Independent Test**: 通过预先构造的异常场景（断开的 VNC 连接、无变化的点击结果、未知
弹窗截图），验证失败类型识别与对应有限恢复策略触发，无需完整跑通整条闭环

### Tests for User Story 8

- [X] T073 [P] [US8] 单元测试：12 种 `FailureType` 的识别，含 `grounding_low_confidence`
      的 `overall_low_confidence`/`top1_top2_close` 子原因路由（对应 FR-036、
      data-model.md §8）于 `vnc_agent/tests/unit/test_failure_classifier.py`
- [X] T074 [P] [US8] 单元测试：每类失败达到其配置的最大重试次数后停止该步骤并标记失败，
      不出现无限重试（对应 FR-038）于 `vnc_agent/tests/unit/test_recovery_budget.py`

### Implementation for User Story 8

- [X] T075 [US8] 实现失败分类器（将检测到的异常情形映射到 12 种 `FailureType`，
      `found=false`→`target_not_found`，置信度低/Top1-Top2 接近→`grounding_low_confidence`
      + 子原因，对应 FR-036）于 `vnc_agent/src/vnc_agent/recovery/classifier.py`
- [X] T076 [P] [US8] 实现恢复策略集（`recapture`/`extra_wait`/`second_candidate`/
      `re_ground`/`switch_to_keyboard`/`release_modifiers`/`press_escape`/`win_d_reset`/
      `restart_step`，每类从 `recovery.<failure_type>.max_retries`/`cooldown_ms`
      读取显式配置的最大重试次数与冷却时间（data-model.md §11），对应 FR-037/038；每个
      策略执行本身 MUST 复用 FR-021 的动作级超时，执行失败/超时 MUST 计入触发它的原
      `FailureType` 的同一个 `attempt_index` 序列，不开辟独立的"恢复的恢复"预算，对应
      data-model.md §8"预算层级"第 4 点）于
      `vnc_agent/src/vnc_agent/recovery/strategies.py`
- [X] T077 [US8] 实现恢复引擎（按 data-model.md §8 完整路由表——12 种 `FailureType` 分别
      对应首选/次选 `strategy`——把 `FailureType` 派发到对应策略；实现"预算层级"规则：
      每个 `FailureType` 的 Tier-2（`RecoveryAttempt.max_retries`）预算在当前
      `ActionIteration` 内独立计数且按迭代重置，Tier-2 耗尽仍未 `resolved` 时，MUST 将
      本轮 `ActionIteration` 判定为 `failed` 并消耗一个 Tier-1（`StepController`/
      `TestStep.max_retries`）单位，不直接调用 Tier-1 的独立计数逻辑——`restart_step`
      例外，直接消耗 Tier-1）于
      `vnc_agent/src/vnc_agent/recovery/engine.py`（依赖 T075、T076、T019）
- [X] T078 [US8] 在 vncdotool 驱动中接入断线检测、有限次数重连、重连成功后触发
      `restart_step`（从重新观察开始整步重做，MUST NOT 从 WAITING/VERIFYING 继续，对应
      FR-039）；触发前 MUST 先检查该 `TestStep` 的 `StepController` 共享预算（Tier-1）是否
      已耗尽为 0——若已耗尽，MUST NOT 尝试重连恢复，直接判定该步骤为 `failed`（Clarification
      2026-07-21，对应 data-model.md §12）于
      `vnc_agent/src/vnc_agent/drivers/vncdotool_driver.py`（依赖 T015、T077、T019）

**Checkpoint**: 常见失败可被独立识别并触发对应有限恢复策略

---

## Phase 12: User Story 10 - 为未来自进化保留数据 (Priority: P3)

**Goal**: 采集足以支撑未来页面/元素记忆、Record-Replay、视觉自进化的数据，本功能只写入
不检索不训练

**Independent Test**: 检查一次已完成测试运行产生的数据，验证其包含必要字段，无需实现任何
检索或训练功能

### Tests for User Story 10

- [X] T079 [P] [US10] 单元测试：经验采集器仅执行写入操作，代码路径中不出现修改模型权重/
      测试断言/回放脚本/自动固化新基线的逻辑（对应 FR-044）于
      `vnc_agent/tests/unit/test_experience_collector_write_only.py`

### Implementation for User Story 10

- [X] T080 [US10] 实现 `VisualExperience` 采集器（记录动作前后观察、语义动作、Grounding
      候选、被选候选、执行/验证结果、`outcome`、`failure_type`，仅写入落库，对应
      FR-043/044）于
      `vnc_agent/src/vnc_agent/evolution/experience_collector.py`（依赖 T011、T067）

**Checkpoint**: 自进化数据采集可独立验证字段完整性与只写不改行为

---

## Phase 13: Polish & Cross-Cutting Concerns（完整闭环集成）

**Purpose**: 将 US1~US10 的独立模块串联为完整的 Agent Runtime 闭环，覆盖 spec.md 验收
场景一至九

- [X] T081a 实现单轮 `ActionIteration` 编排（按 data-model.md §12 状态转移驱动一次
      `OBSERVING→UNDERSTANDING→PLANNING→RESOLVING_ACTION→(GROUNDING)?→EXECUTING→WAITING→
      VERIFYING→RECORDING`，串联感知/规划/定位/执行/等待/验证各模块，返回本轮
      `VerificationResult` 与完整的 `ActionIteration` 证据记录，不自行决定是否开启下一轮或
      推进到下一步骤）于 `vnc_agent/src/vnc_agent/runtime/agent_runtime.py`（依赖 T017、
      T038、T042-T044、T049、T053、T055、T063）
- [X] T081b 实现步骤级预算与流转判定（基于 T081a 每轮返回的 `verification_result.status`
      驱动 `StepController` 消耗共享预算，按 data-model.md §12 的
      `STEP_COMPLETED_PASSED`/`STEP_COMPLETED_FAILED`/`TestRun.status 聚合规则`
      实现：`passed`→该 `TestStep` 标记 `passed`，若有下一 `TestStep` 则调度其进入
      `OBSERVING`（`iteration_index` 重置为 0），否则 `TestRun.status="passed"`；
      `failed`/`uncertain` 且预算未耗尽→回到 `OBSERVING` 开启下一轮 `ActionIteration`
      （`iteration_index+1`）；`failed`/`uncertain` 且预算耗尽→该 `TestStep` 标记
      `failed`，**MUST** 立即终止整条 `TestRun`、将 `TestRun.status` 置为 `failed`，
      **MUST NOT** 调度任何后续 `TestStep`（对应 FR-035、SC-002，与 data-model.md §12
      订正后的状态转移表述一致）；尚未执行的后续步骤保持 `pending`；将最终
      `TestRun`/`StepRecord` 状态写入仓储层）于
      `vnc_agent/src/vnc_agent/runtime/agent_runtime.py`（依赖 T081a、T018、T019、T067）
- [X] T081c 实现 VNC 断线/`restart_step` 集成点（编排循环捕获来自 `VNCDriver` 的断线异常，
      交由恢复引擎路由到 `restart_step` 策略，重连成功后 MUST 从 `OBSERVING` 开启全新一轮
      `ActionIteration`，MUST NOT 从 `WAITING`/`VERIFYING` 等中间阶段继续，本次重做计入
      `TestStep.max_retries` 共享预算，对应 FR-039）于
      `vnc_agent/src/vnc_agent/runtime/agent_runtime.py`（依赖 T081a、T081b、T015、T077）
- [X] T082 实现 CLI `vnc-agent run` 完整执行路径（连接 VNC、驱动 `agent_runtime` 循环、
      生成 JSON/HTML 报告、退出码与 `TestRun.status` 一一对应：0=passed/1=failed/
      2=校验失败/3=cancelled/4=VNC 连接失败，对应 contracts/cli-contract.md）于
      `vnc_agent/src/vnc_agent/api/cli.py`（依赖 T081a-T081c、T071）
- [X] T083 [P] 实现 Typer 应用入口，装配 `run`/`report` 子命令于
      `vnc_agent/src/vnc_agent/main.py`（依赖 T082）
- [X] T084 [P] 端到端测试：验收场景一（建立 VNC 连接，`--dry-run` 不连接、正式运行输出
      分辨率日志与首帧截图）于 `vnc_agent/tests/e2e/test_scenario_01_connect.py`
- [X] T085 [P] 端到端测试：验收场景二（键盘优先执行，`executable_action.method="keyboard"`
      且不出现 Grounder 调用记录）于
      `vnc_agent/tests/e2e/test_scenario_02_keyboard_first.py`
- [X] T086 [P] 端到端测试：验收场景三（视觉定位并点击，候选≤3 且点击点落在候选 bbox 内）
      于 `vnc_agent/tests/e2e/test_scenario_03_grounding_click.py`
- [X] T087 [P] 端到端测试：验收场景四（点击后验证通过才继续下一步骤）于
      `vnc_agent/tests/e2e/test_scenario_04_verify_gate.py`
- [X] T088 [P] 端到端测试：验收场景五（点击无效果触发多轮迭代，预算耗尽后
      `StepRecord.final_status="failed"` 且保留全部轮次证据）于
      `vnc_agent/tests/e2e/test_scenario_05_multi_iteration.py`
- [X] T089 [P] 端到端测试：验收场景六（动态页面等待，`waited_ms` 明显大于
      `min_delay_ms`，不出现等待期间进入 `VERIFYING` 的记录）于
      `vnc_agent/tests/e2e/test_scenario_06_wait_dynamic.py`
- [X] T090 [P] 端到端测试：验收场景七（目标不存在/整体置信度偏低/Top1-Top2 接近三种情况
      分别归类，任何情况均不出现越界或凭空坐标点击）于
      `vnc_agent/tests/e2e/test_scenario_07_grounding_classification.py`
- [X] T091 [P] 端到端测试：验收场景八（VNC 中断与整步重做，重连成功后产生
      `strategy="restart_step"` 的恢复记录并从 `OBSERVING` 重新开始）于
      `vnc_agent/tests/e2e/test_scenario_08_vnc_restart.py`
- [X] T092 [P] 端到端测试：验收场景九（失败报告完整性，`report.json`/`report.html` 含
      `failure_reason`、操作前后截图、Grounding 候选、验证证据、恢复记录）于
      `vnc_agent/tests/e2e/test_scenario_09_failure_report.py`
- [X] T093 端到端测试：复合验证条件"不确定"传染性补充场景（`all` 下 failed 优先于
      uncertain；另一用例 passed+uncertain → 整体 uncertain）于
      `vnc_agent/tests/e2e/test_uncertain_propagation.py`（依赖 T063）
- [X] T094 端到端测试：敏感区域遮罩补充场景（本地持久化截图/报告已打码，发往 Planner/
      Grounder 的存档截图未打码，对应 FR-049）于
      `vnc_agent/tests/e2e/test_sensitive_masking.py`（依赖 T068、T071）
- [X] T095 按 quickstart.md 场景一至九 + 复合验证 + 敏感遮罩 + 十次连续运行（SC-006/
      SC-007）对本地测试用 VNC 环境执行完整验证清单；十次连续运行期间同时观察控制端进程的
      内存/句柄占用趋势，确认不出现因资源耗尽导致的运行中断（对应 SC-009，验证 T032/T055
      的帧内存上限约束在真实运行中生效）（依赖 T081a-T081c、T082-T094）
- [X] T096 [P] 补全 `config/agent.yaml`/`config/models.yaml`/`config/vnc-targets.yaml`
      示例取值与 quickstart.md 前置条件对应的说明文档

**Checkpoint**: 完整闭环可通过 CLI 端到端运行并生成可信报告

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: 无依赖，可立即开始
- **Foundational (Phase 2)**: 依赖 Setup 完成——阻塞所有用户故事
- **User Stories (Phase 3~12)**: 均依赖 Foundational 完成
  - US1（Phase 3）：仅依赖 Foundational
  - US2（Phase 4）：依赖 Foundational（含 T014 VNCDriver）
  - US3（Phase 5）：依赖 Foundational + US2 的 `models/provider.py`（T037）
  - US4（Phase 6）：依赖 Foundational + US2 的 `models/provider.py`（T037）+ US3 的
    `action_policy.py`（T043）
  - US5（Phase 7）：仅依赖 Foundational（T014）
  - US6（Phase 8）：依赖 Foundational + US2 的截图/差异模块（T032、T033）
  - US7（Phase 9）：依赖 Foundational + US2 的 `models/provider.py`（T037，供
    `visual_verifier.py` 使用）
  - US9（Phase 10）：依赖 Foundational（T011 domain/run.py）
  - US8（Phase 11，P2）：依赖 Foundational（T019 StepController）+ US2 的驱动扩展点
    （T015）
  - US10（Phase 12，P3）：依赖 Foundational（T011）+ US9 的仓储层（T067）
- **Polish（Phase 13）**：依赖全部 P1 故事（US1~US7、US9）完成，US8/US10 视验收场景需要
  部分依赖（场景八依赖 US8）

### User Story Dependencies（业务视角）

MVP 闭环由 US1~US7 + US9 共同构成（spec.md 明确 8 个 P1 故事缺一不可）；US8 在闭环之上
加固鲁棒性；US10 为前瞻性数据采集，不影响闭环本身是否成立。各故事的独立测试（Independent
Test）均可在其自身依赖就绪后单独验证，无需等待其他同优先级故事完成。

### Parallel Opportunities

- Phase 1 的 T003、T004 可并行
- Phase 2 中 T005-T011（7 个领域模型文件）可完全并行；T013、T016、T020 可与其他
  Foundational 任务并行
- 每个用户故事内标记 [P] 的测试任务可并行编写
- 每个用户故事内标记 [P] 的不同文件实现任务可并行开发
- US5（Phase 7）与 US6（Phase 8）在 Foundational 完成后可与 US2/US3/US4 并行推进（无直接
  相互依赖）
- Phase 13 的 T084-T092、T096（9 个端到端测试 + 文档）可并行编写

---

## Parallel Example: Foundational Phase

```bash
# 7 个领域模型文件可完全并行创建：
Task: "实现 TestCase/TestStep 模型于 domain/testcase.py"
Task: "实现 StructuredScreen 等观察模型于 domain/observation.py"
Task: "实现 SemanticAction 等动作模型于 domain/action.py"
Task: "实现 GroundingResult 等定位模型于 domain/grounding.py"
Task: "实现 VerificationSpec 等验证模型于 domain/verification.py"
Task: "实现 FailureType/RecoveryAttempt 模型于 domain/recovery.py"
Task: "实现 ActionIteration/StepRecord/TestRun/VisualExperience 模型于 domain/run.py"
```

## Parallel Example: User Story 2

```bash
# 观察相关的固定截图测试可并行编写：
Task: "固定截图测试：截图采集与裁剪偏移于 tests/fixtures/test_screenshot.py"
Task: "固定截图测试：帧间差异检测于 tests/fixtures/test_screen_diff.py"
Task: "固定截图测试：OCR 识别于 tests/fixtures/test_ocr.py"
Task: "固定截图测试：模板匹配于 tests/fixtures/test_template_matching.py"

# 对应实现模块也可并行开发（各自独立文件）：
Task: "实现截图采集于 perception/screenshot.py"
Task: "实现帧间差异检测于 perception/screen_diff.py"
Task: "实现 OCR 引擎封装于 perception/ocr/engine.py"
Task: "实现模板匹配引擎于 perception/template/matcher.py"
```

---

## Implementation Strategy

### MVP First（US1~US7 + US9）

1. 完成 Phase 1: Setup
2. 完成 Phase 2: Foundational（关键阻塞项，尤其 T014/T015 VNCDriver 与 T017-T019 状态机
   骨架）
3. 依次或并行完成 Phase 3~9（US1~US7）与 Phase 10（US9）——8 个 P1 故事共同构成 MVP
4. 完成 Phase 13 的 T081a-T081c/T082（Agent Runtime 完整编排 + CLI `run`）将各模块串联为
   可运行闭环
5. **停止并验证**：运行 quickstart.md 场景一至四、六、七、九，确认闭环可行（SC-001）

### Incremental Delivery

1. Setup + Foundational → 基础就绪
2. US1（测试用例加载调度）→ 独立验证 → 可离线校验用例
3. US2（观察理解）→ 独立验证 → 可对固定截图输出结构化状态
4. US3（动作选择）→ 独立验证 → 可对模拟状态选出候选执行方式
5. US4（视觉定位）→ 独立验证 → 可对固定截图完成坐标还原
6. US5（键鼠执行）→ 独立验证 → 可对本地 VNC 服务发送动作
7. US6（等待稳定）→ 独立验证 → 可对模拟帧序列判定稳定性
8. US7（独立验证）→ 独立验证 → 可对截图对给出三态判定
9. US9（证据与报告）→ 独立验证 → 可对已构造数据生成双格式报告
10. 完成 Phase 13 集成 → 完整闭环可通过 CLI 端到端运行（MVP 完成，对应 SC-001~SC-010）
11. 追加 US8（基础恢复）→ 独立验证 → 闭环具备有限恢复能力
12. 追加 US10（自进化数据采集）→ 独立验证 → 为未来功能留存必要字段

### Parallel Team Strategy

Foundational 完成后：

- 开发者 A：US2（观察）→ US6（等待，依赖 US2 的截图/差异模块）
- 开发者 B：US3（动作选择，依赖 US2 的 `models/provider.py`）→ US4（视觉定位，依赖 US3
  的 action_policy）
- 开发者 C：US5（键鼠执行，仅依赖 Foundational）
- 开发者 D：US7（独立验证，依赖 US2 的 `models/provider.py`）→ US9（证据与报告）
- Foundational 完成、US1~US7+US9 均就绪后，由一人牵头完成 Phase 13 的 Agent Runtime 集成
  （T081a-T081c/T082），随后并行补齐端到端测试（T084-T094）
- US8、US10 可在 MVP 闭环跑通后由任意开发者并行追加

---

## Notes

- [P] 任务 = 不同文件、无依赖
- [Story] 标签用于追溯任务所属用户故事
- 每个用户故事应可独立完成与测试
- 实现前应先确认测试处于失败状态（TDD）
- 建议每完成一个任务或一组逻辑相关任务后提交一次
- 可在任意 Checkpoint 处停下来独立验证对应故事
- 避免：模糊任务描述、同文件冲突、破坏故事独立性的跨故事依赖（本列表中跨故事依赖已在
  "Dependencies & Execution Order" 中显式标注，均为只读式依赖——后置故事复用前置故事已
  定义的接口/模型，不修改其内部实现）

---

## Phase 14: Convergence

**Purpose**: `/speckit-converge`（2026-07-21）对照 spec.md/data-model.md/contracts/ 复核
`/speckit-implement` 产出的代码，发现的偏差在此追加为可执行任务，不修改任何既有任务。

- [X] T097 [CRITICAL] 修复恢复升级状态在多轮 `ActionIteration` 间被过早清空的问题：
      `runtime/agent_runtime.py` 当前在 `while True:` 迭代循环内、每轮开始时调用
      `self.recovery.reset_iteration()`（清空 `candidate_index`/`prefer_keyboard`/
      `need_reground`/`_tier2`），但这些标志是上一轮迭代结束时才由
      `RecoveryEngine._apply_side_effects()` 设置、供**下一轮**使用的，导致第二候选/
      切换键盘路径/重新 Grounding 等"次选"恢复策略从未真正生效——`action_policy.py` 每轮
      都以 `candidate_index=0, prefer_keyboard=False` 重新解析，只会重复尝试第一候选直到
      预算耗尽。MUST 将 `reset_iteration()` 的调用时机从"每轮迭代开始"移到"每个 TestStep
      开始"（`StepController` 创建之后、`while True:` 循环之前），使恢复升级状态在同一步骤
      的多轮迭代间正确保留，仅在推进到下一个 TestStep 时清空 于
      `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` per FR-037, US8/AC2, US8/AC3,
      data-model.md §8"预算层级" (contradicts)
- [X] T098 [P] [CRITICAL] 为 T097 补充回归测试：断言同一 `TestStep` 内第二轮
      `ActionIteration` 相较第一轮，`candidate_index`/`prefer_keyboard`/触发的
      `re_ground` 等确实发生了变化（而不仅断言"最终 failed 且 iterations≥2"），覆盖
      `grounding_low_confidence`→`second_candidate`、`action_no_effect`→
      `switch_to_keyboard` 两条路由 于
      `vnc_agent/tests/e2e/test_scenario_05_multi_iteration.py`（扩展现有测试）per
      quickstart.md 场景五 (missing)
- [X] T099 [HIGH] 修复本地持久化截图未被敏感区域遮罩打码的问题：
      `perception/screenshot.py` 写入 `artifacts/runs/<run_id>/frames/*.png` 的原始像素
      从未经过 `ArtifactStore` 的遮罩逻辑，只有 `reporting/report_builder.py` 为 HTML
      报告另行生成的 `report_frames/` 副本被打码——违反 FR-049"已配置的敏感信息遮罩区域
      MUST 应用于本地持久化的截图"（该要求覆盖持久化制品本身，不仅是报告展示副本）。MUST
      让 `frames/` 目录下的持久化截图本身应用遮罩（写入时或写入后原地遮罩均可），同时
      MUST NOT 影响发往 Planner/Grounder 模型 API 的截图路径（继续使用未遮罩原图，
      FR-049 后半句、contracts/model-provider-contract.md"图像不遮罩"）于
      `vnc_agent/src/vnc_agent/perception/screenshot.py`、
      `vnc_agent/src/vnc_agent/storage/artifact_store.py` per FR-049, Constitution
      凭据与隐私 (partial)
- [X] T100 [MEDIUM] 修复 `--json-only` CLI 参数未生效的问题：`api/cli.py` 接收
      `json_only` 参数后未透传，`runtime/agent_runtime.py` 调用
      `self.report_builder.build(ctx.test_run)` 未传 `formats`，导致默认值
      `("json","html")` 始终生效、HTML 报告总会被生成。MUST 将 `json_only` 从 CLI 一路
      透传到 `ReportBuilder.build(..., formats=...)`，`--json-only` 时传
      `formats=("json",)` 于 `vnc_agent/src/vnc_agent/api/cli.py`、
      `vnc_agent/src/vnc_agent/runtime/agent_runtime.py` per
      contracts/cli-contract.md（`vnc-agent run --json-only`） (partial)

---

## Phase 15: Convergence

**Purpose**: `/speckit-converge`（2026-07-22）对照刚订正的
contracts/model-provider-contract.md"GrounderProvider 默认实现：MiMo-V2.5 / OpenCode Go
真实 Wire 协议"章节复核代码，发现的偏差在此追加为可执行任务，不修改任何既有任务。

- [X] T101 [HIGH] 按 contracts/model-provider-contract.md"GrounderProvider 默认实现"
      章节（2026-07-22 订正）重写 `MimoGrounderClient.ground()`：不再 `POST
      {base_url}/v1/ground` 发送内部 `GroundingRequest` 原始 JSON，改为读取
      `request.image_ref` 指向的本地文件字节、base64 编码后内联进 OpenAI 兼容的多模态
      `messages` 请求体（system 提示词约束模型只输出
      `{"found": bool, "candidates": [{"bbox":[x1,y1,x2,y2],"confidence":0~1,"label":
      string|null,"reason":string}]}` 这一 JSON，不含 markdown 代码块，不得编造坐标），
      `POST {base_url}/chat/completions`；`model` 字段与图片传参格式先按契约文档给出的
      默认值实现，落地前 MUST 用 `GET {base_url}/models` 核对账号下实际可用的模型 ID
      字符串 于 `vnc_agent/src/vnc_agent/models/mimo_grounder.py` per
      contracts/model-provider-contract.md（GrounderProvider 默认实现章节） (contradicts)
- [X] T102 [P] [HIGH] 让 `models/response_parser.py` 的 `parse_grounding_response()`
      支持"先从 chat completion 响应中取出 `choices[0].message.content` 文本、剥离可能的
      ```json 代码块包裹，再解析 JSON"这一步（参照 `parse_planner_response()`/
      `HttpPlannerClient.plan()` 已经正确实现的同类逻辑）；解析失败（非法 JSON、字段缺失）
      MUST 归类为模型响应异常并交由恢复引擎处理，MUST NOT 直接抛出异常终止整个 `TestRun`
      于 `vnc_agent/src/vnc_agent/models/response_parser.py`,
      `vnc_agent/src/vnc_agent/models/mimo_grounder.py` per
      contracts/model-provider-contract.md（GrounderProvider 默认实现章节） (partial)
- [X] T103 [P] [MEDIUM] 为 T101/T102 补充离线测试：mock 一个真实形态的 OpenAI
      `chat.completion` 响应（`choices[0].message.content` 为约定 JSON 字符串，含被
      ```json 代码块包裹的变体），断言 `MimoGrounderClient.ground()` 能正确解析出
      `GroundingResult`；并断言实际发出的 HTTP 请求体符合"OpenAI 兼容 messages + 图片
      base64 内联"的形状（而不是旧的 `/v1/ground` 自定义形状）于
      `vnc_agent/tests/fixtures/test_mimo_grounder.py`（扩展现有测试） per
      contracts/model-provider-contract.md（GrounderProvider 默认实现章节） (missing)

---

## Phase 16: Convergence

**Purpose**: 与 T101-T103 同源发现的第二个 wire-protocol 问题——
`HttpPlannerClient.describe_screen()` 从未真正把截图字节发给模型，已同步订正契约并直接
修复（本阶段任务创建时即完成，未经过额外的 `/speckit-implement` 传递）。

- [X] T104 [HIGH] 修复 `HttpPlannerClient.describe_screen()`（`models/planner_client.py`）
      从未真正发送图片字节的问题：原实现把整个 `VisionUnderstandingRequest`（含
      `image_ref` 本地路径字符串）直接 `json.dumps()` 成文本塞进 `messages[].content`，
      模型永远看不到截图。已改为：读取 `image_ref` 指向的本地文件字节、base64 编码后作为
      `image_url` 内容块内联进多模态 `messages`；新增 `_image_url_content_part()` 辅助
      函数；响应解析增加防御性剥离 ```json 代码块包裹 于
      `vnc_agent/src/vnc_agent/models/planner_client.py` per
      contracts/model-provider-contract.md（PlannerProvider.describe_screen "Wire 协议
      订正 2026-07-22"） (contradicts)
- [X] T105 [P] [MEDIUM] 新增回归测试：mock httpx transport，断言
      `describe_screen()` 实际发出的请求体 `messages[1].content` 是多模态数组、含
      `image_url` 内容块，且解码后的 base64 字节与原始截图文件字节完全一致（而不是像
      修复前那样整个请求被序列化成一段惰性文本）于
      `vnc_agent/tests/fixtures/test_planner_client_describe_screen.py`（新建） per
      contracts/model-provider-contract.md（同上） (missing)

**Checkpoint**: `cd vnc_agent && python -m pytest tests/ -q` → 67 passed, 1 skipped（较
Phase 15 完成前净增 1 个测试，无回归）。

---

## Phase 17: Convergence

**Purpose**: 用户要求"Planner 也应当能支持使用 opencode-go 的订阅"（2026-07-22）。核实后
`HttpPlannerClient`（`models/planner_client.py`）本就是通用 OpenAI 兼容 `/chat/completions`
客户端（FR-046 要求的可替换性已经落实），不需要改代码，只需把 `config/models.yaml` 的
`planner` 一节指向 OpenCode Go；用户选择 Planner 与 Grounder 复用同一个 MiMo-V2.5（已确认
支持视觉，`describe_screen()` 能拿到真实答案而不是靠优雅降级）。本阶段任务创建时即完成。

- [X] T106 [LOW] 将 `config/models.yaml` 的 `planner` 一节改为指向 OpenCode Go
      （`base_url: https://opencode.ai/zen/go/v1`、`provider: opencode-go`、
      `model: mimo-v2.5`，与 `grounder` 一节一致），并注明 `VNC_AGENT_PLANNER_API_KEY`
      可与 `VNC_AGENT_GROUNDER_API_KEY` 共用同一把 OpenCode Go Key 于
      `vnc_agent/config/models.yaml` per FR-046（用户请求：Planner 支持 opencode-go
      订阅） (missing)
- [X] T107 [P] [LOW] 在 README"Configure"章节补充"Using OpenCode Go for both Planner
      and Grounder"小节，说明配置来源、复用 MiMo-V2.5 的理由、`model` 字段仍需通过
      `GET {base_url}/models` 核实 于 `vnc_agent/README.md` per 同上 (missing)

**Checkpoint**: `python -c "from vnc_agent.config import load_config; ..."` 确认
`planner.base_url`/`model`/`provider` 均按预期加载；`cd vnc_agent && python -m pytest
tests/ -q` → 73 passed, 1 skipped，无回归（配置变更不影响任何测试用例，因为测试全部通过
Stub/Mock provider，不实际连接 base_url）。

---

## Phase 18: Convergence

**Purpose**: 首次针对真实 VNC 目标（`192.168.8.122:5900`）+ 真实 OpenCode Go/MiMo-V2.5
执行 `vnc-agent run testcases/smoke-connect.yaml` 端到端验证时，发现并修复了 3 个此前
仅靠 Stub/Mock 测试无法暴露的真实缺陷，另有 1 项配置纠错。本阶段任务创建时即完成。

- [X] T108 [CRITICAL] 修复 `VNCToolDriver._sync_connect()` 中"顺便探测分辨率"的截图调用
      崩溃问题：原代码 `factory.captureScreen(None)` 在真实 vncdotool 版本下会因 PIL 无法
      从 `None` 推断文件后缀而抛出 `ValueError: unknown file extension:`，且被外层
      `except Exception` 误判为"VNC连接失败"（实际 RFB 握手已经成功）。改为复用
      `_sync_capture()` 已验证可用的"写临时 .png 文件→读字节→PIL 探测尺寸"方式，抽成
      `_probe_resolution()`；探测失败时不再让 `connect()` 整体失败（分辨率会在首次真实
      `capture_screen()` 时自我修正）于
      `vnc_agent/src/vnc_agent/drivers/vncdotool_driver.py` per FR-005（真实环境验证发现）
      (contradicts)
- [X] T109 [CRITICAL] 修复 CLI 进程在任意一次 `vnc-agent run` 之后都无法退出、必须被外部
      超时强杀的问题：`vncdotool.api.connect()` 会启动一个非 daemon 的 "Twisted Reactor"
      后台线程（模块级单例），代码里从未调用 `vncdotool.api.shutdown()` 停止它，导致
      Python 解释器在所有异步逻辑跑完后仍挂起等待该线程 join。已在
      `VNCToolDriver._sync_disconnect()` 中补上 `vnc_api.shutdown()` 调用（对应
      plan.md Constraints"同一时刻仅维持一个VNC会话"，全局单例 reactor 在断开时停止是安全的）
      于 `vnc_agent/src/vnc_agent/drivers/vncdotool_driver.py` per Constitution
      "确定性运行时控制模型"（进程必须能确定性地结束，真实环境验证发现） (missing)
- [X] T110 [HIGH] 修复 `HttpPlannerClient.plan()` 的系统提示词过于简略、导致真实
      MiMo-V2.5 返回的 JSON 不满足 `PlannerResponse`/`SemanticAction` schema 的问题
      （实测出现 `task_completed_hint` 返回自然语言字符串而非布尔值、`semantic_action`
      缺 `action_id`/`intent`、`action_type` 用了枚举之外的值、甚至整个
      `semantic_action` 被返回成一个裸字符串）。改为完整的结构化提示词
      `_PLANNER_SYSTEM_PROMPT`，显式列出字段名、类型、`action_type` 允许的枚举值与一个
      完整示例（对齐 `mimo_grounder.py` 的 `_GROUNDING_SYSTEM_PROMPT` 写法）；修复后真实
      调用验证：返回结构完全符合 `PlannerResponse` schema，无需重试 于
      `vnc_agent/src/vnc_agent/models/planner_client.py` per
      contracts/model-provider-contract.md（PlannerProvider.plan 契约，真实环境验证发现）
      (partial)
- [X] T111 [MEDIUM] 订正 `config/models.yaml`/`contracts/model-provider-contract.md` 中
      模型 ID 格式：此前依据用户提供的信息记录为 `"opencode-go/<model-id>"` 前缀形式，
      经对真实端点实测复核（`GET {base_url}/models` 返回裸 ID；`POST /chat/completions`
      传裸名返回 200，传前缀形式返回 401 `{"message":"Model opencode-go/mimo-v2.5 is not
      supported"}`），确认 MUST 使用裸模型名 `"mimo-v2.5"`；`opencode-go/<model-id>`
      前缀是 OpenCode 自身 TUI/内部 provider 配置语法，不是直接调用该 REST API 时
      `model` 字段的取值 于 `vnc_agent/config/models.yaml`,
      contracts/model-provider-contract.md per 真实环境实测复核 (contradicts)

**Checkpoint（真实环境端到端验证，2026-07-21）**：`vnc-agent run
testcases/smoke-connect.yaml --config config` 对真实 VNC 目标
（`192.168.8.122:5900`）+ 真实 OpenCode Go/MiMo-V2.5 执行，`EXIT CODE: 0`（passed）；
`report.json` 显示两轮 `ActionIteration`，均含真实的 Planner 语义动作、真实执行结果、真实
等待耗时（5843ms/5093ms）、真实验证依据，无编造/跳过证据；`cd vnc_agent && python -m
pytest tests/ -q` → 73 passed, 1 skipped，全程无回归。
