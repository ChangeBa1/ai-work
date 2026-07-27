# Feature Specification: 轨迹录制与回放（record-replay）

**Feature Branch**: `016-record-replay`

**Created**: 2026-07-26

**Status**: Draft

**Input**: User description: "总体设计 §11（ReplayStep/ReplayPatch）+ §10.2（回放模式）
+ §10.1（探索模式产出候选回放轨迹）+ ADR-005（自愈只生成候选补丁）的实现，直接建立在
feature 015（page-element-memory）的公开接口之上。回归测试的最大提速项：探索成功一次
后，后续回归 happy path 零 planner 调用、零 grounder 调用。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 探索成功自动沉淀回放脚本 (Priority: P1)

一次 explicit 探索运行整体 `passed` 后，系统把每个成功步骤的通过迭代转换为
ReplayStep，按 test_case 存为一个新版本 ReplayScript（`replay.auto_generate: true`
默认开）。键盘步骤记录可直接重放的按键序列；鼠标步骤记录动作前帧页面指纹、
target_region 模板裁剪、锚点文本（含位置）、归一化 bbox 与该步验证 spec。

**Why this priority**: 没有脚本就没有回放；录制是整条链路的地基。

**Independent Test**: 离线 e2e——探索 run 成功后断言 SQLite 中出现
`replay_scripts`/`replay_steps` 行、模板图落盘、字段内容正确（指纹/锚点/归一化
bbox/验证 spec）。

**Acceptance Scenarios**:

1. **Given** 一次 explicit 探索 run 整体 `passed` 且每个步骤的通过迭代都带
   executable_action，**When** run 结束，**Then** 生成 version=1 的 ReplayScript，
   步骤数与 TestCase 步骤数一致、顺序一致；鼠标步骤含模板路径/锚点/归一化 bbox/
   页面指纹/验证 spec，键盘步骤含可重放的 ExecutableAction 快照。
2. **Given** 同一 test_case 再次探索成功，**When** run 结束，**Then** 插入
   version=2 的新脚本，version=1 保留不动（不自动删除）。
3. **Given** run 整体 `failed`/`cancelled`，**Then** 不生成任何脚本。
4. **Given** 录制过程中任何异常（存储/图像解码失败），**Then** 主流程与 run 结果
   不受影响（fail-open，仅日志）。
5. **Given** 鼠标步骤的 target_region 与 `security.mask_regions` 任一矩形相交，
   **Then** 该步不落模板、标记为 `direct_fallback_only`（回放时直接走 MiMo 兜底），
   其余步骤照常录制。

---

### User Story 2 - 回放 happy path：零 planner / 零 grounder (Priority: P1)

TestCase `mode: "replay"` 运行时，系统加载该 test_case 最新版本脚本，逐 ReplayStep：
观察 → 页面指纹匹配（≥ high 才可直接定位）→ 目标模板匹配 → OCR 锚点匹配 →
历史归一化 bbox（仅同分辨率）→ 命中即以 `safe_click_point` 执行 → 既有独立验证
（验证 spec 用 ReplayStep 存的）。全程不调用 Planner，不调用 Grounder。

**Why this priority**: 设计 §21.3「回放成功时不调用 Planner」与「历史经验命中时
不立即调用 MiMo」的终态——回归几乎零模型调用。

**Independent Test**: 离线 e2e——探索 run 生成脚本后，replay run：planner 调用
计数 0、grounder 调用计数 0、逐步验证通过、run `passed`、每步定位方式可审计。

**Acceptance Scenarios**:

1. **Given** 页面指纹匹配 high 且模板匹配达 `replay.template_match_threshold`，
   **Then** 直接以匹配 bbox 的 safe_click_point 点击，`locate_method="template"`。
2. **Given** 模板未中但目标标签文本在当前帧 OCR 中唯一命中，**Then** 以该 OCR bbox
   点击，`locate_method="anchor"`；目标标签未中时用记录的锚点位置推算平移量
   （全部匹配锚点位移一致才采纳）。
3. **Given** 模板与锚点都未中且当前分辨率与录制分辨率一致，**Then** 以归一化 bbox
   还原的像素 bbox 点击，`locate_method="bbox"`；分辨率不一致 MUST NOT 直点。
4. **Given** 键盘 ReplayStep，**Then** 直接重放记录的按键序列（不需要视觉定位），
   `locate_method="keyboard"`。
5. **Given** 任何直接定位命中并执行，**Then** 后续独立验证照常执行，绝不因回放
   豁免（Constitution IV）；验证 spec 来自 ReplayStep。
6. **Given** happy path 全部步骤通过，**Then** run `passed` 且 telemetry 中
   planner/grounder 的 `model_call` 计数为 0。

---

### User Story 3 - 回放失败兜底 + 候选补丁（ADR-005） (Priority: P1)

页面指纹低于 high、或定位全部未中、或直接定位后的验证失败 → 该步进入兜底：调用
MiMo 重新 grounding 一次（复用既有 GroundingRequest 通道 + ActionPolicy 共识
门槛）→ 成功则继续执行并生成 ReplayPatch（status=pending，携带 old/new target 与
前后帧证据）→ 兜底也失败则 run 失败，报告指明失败在哪个 ReplayStep。补丁永不
自动应用；正式脚本目标字段在回放过程中只读。

**Why this priority**: ADR-005 红线——自愈只生成候选，人工审核后才能变更基线。

**Independent Test**: 离线 e2e——按钮移位场景：模板/锚点未中 → grounder 兜底成功 →
patch 生成 pending 且原脚本步骤字段不变 → run `passed`；兜底也失败 → run `failed`
且 failure_reason 含 ReplayStep 标识。

**Acceptance Scenarios**:

1. **Given** 按钮移位使模板/锚点/bbox 全部未中，**When** MiMo 兜底 grounding 成功
   且验证 `passed`，**Then** 生成一条 status="pending" 的 ReplayPatch（old_target=
   记录的模板/bbox/锚点，new_target=兜底解析出的 bbox/坐标，before/after 帧证据、
   验证证据引用），该步 `locate_method="fallback_grounding"`，run `passed`。
2. **Given** 兜底成功，**Then** 数据库中原 ReplayStep 的目标字段（模板路径/bbox/
   归一化 bbox/锚点）逐字节不变；只允许成功/失败统计计数更新。
3. **Given** `replay.patch_auto_apply: true`，**Then** 行为与 false 完全一致，仅
   多一条警告日志（MVP 中该开关不生效——留给人工审核流程）。
4. **Given** 兜底 grounding 未找到目标或兜底后验证仍失败，**Then** run `failed`，
   失败步骤的 failure_reason 指明 replay_step_id 与原步骤 id，后续 ReplayStep 不再
   执行。
5. **Given** 兜底 grounding 成功且验证通过，**Then** 照常调用 015 记忆的
   `record_success` 回写（复用既有服务入口，不另建通道）。
6. **Given** 键盘 ReplayStep 验证失败，**Then** 不做 grounding 兜底（视觉定位对
   键盘无意义），run 直接按失败终结并指明该步。

---

### User Story 4 - CLI、配置与可观测性 (Priority: P2)

工程师能：用 CLI 运行 replay 模式（testcase `mode: "replay"` 或 `--mode replay`
覆盖）；查询某 test_case 的脚本版本与 pending patches（JSON 输出）；从报告/
telemetry 看到每步定位方式、脚本版本、patch 生成事件、回放模式的模型调用计数，
性能摘要可对比「回放 vs 探索」的调用数。

**Acceptance Scenarios**:

1. **Given** `vnc-agent replay scripts <test_case_id>`，**Then** 输出该 test_case
   全部脚本版本（script_id/version/source_run_id/created_at/step 数）JSON。
2. **Given** `vnc-agent replay patches <test_case_id>`，**Then** 输出全部
   pending（及其他状态）补丁 JSON。
3. **Given** 一次 replay run，**Then** 每个 ReplayStep 的迭代记录含 `replay_audit`
   （replay_step_id、script_version、locate_method、template_score/page_similarity、
   patch_id），JSON 报告透出；`performance_summary` 新增 additive 字段
   `replay_locate_methods`（各定位方式计数）与 `replay_patch_count`；
   `model_calls` 既有字段即为「回放 vs 探索」调用数对比的依据。
4. **Given** `replay.enabled: false` 或该 test_case 无任何脚本，**When** 以
   mode:"replay" 运行，**Then** 在 VNC 连接之前 fail fast，报出清晰错误（CLI 退出
   码 2 validation），不产生 run 记录。

---

### Edge Cases

- 通过迭代无 executable_action（步骤经 repeat-guard 阻断裁决通过）→ 该步无法录制
  → 整个脚本放弃生成（fail-open，日志说明原因）。
- 脚本步骤数与当前 testcase 声明步骤数不一致（testcase 已被编辑）→ replay 预检
  fail fast，报错提示重新探索。
- 模板物理文件丢失 → 模板定位跳过，落入锚点/bbox/兜底链。
- 当前分辨率 ≠ 录制分辨率 → 指纹档位封顶 low（015 语义）→ 全部直接定位被禁 →
  逐步走兜底 grounding。
- OCR 关闭 → 锚点匹配自然未中（空 OCR 集），模板/bbox 仍可用。
- 锚点文本在当前帧出现多次（不唯一）→ 该锚点不参与位移推算；全部锚点位移不一致
  （超过 `anchor_offset_tolerance_px`）→ 锚点定位未中。
- 回放中 VNC 断线 → 按既有 VNCDisconnectedError 语义终结 run（MVP 不做回放内
  重连重试）。
- patch 存储失败 → fail-open：该步执行结果不受影响，仅日志（补丁是附加产物）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001（领域模型）**: `domain/replay.py` MUST 定义（设计 §11）：`ReplayStep`
  （replay_step_id、step_id、order_index、页面指纹 PageFingerprint（015）、
  semantic_action、preferred_method、recorded_executable（键盘重放快照）、
  target_template_path、direct_fallback_only、anchor_texts、anchors（文本+bbox）、
  bbox、normalized_bbox、expected VerificationSpec、success_count/failure_count、
  version）；`ReplayScript`（script_id、test_case_id、version、source_run_id、
  created_at、有序 steps）；`ReplayPatch`（patch_id、script_id、replay_step_id、
  old_version/proposed_version、old_target/new_target dict、reason、before_image/
  after_image、verification_evidence、status ∈ {pending, approved, rejected}）；
  `ReplayStepAudit`（迭代级审计）。
- **FR-002（存储）**: SQLite MUST 新增 `replay_scripts` / `replay_steps` /
  `replay_patches` 表（照 `storage/database.py` + `repositories.py` payload 模式），
  `ReplayRepository` 提供脚本保存/最新版本查询/版本列举、补丁保存/查询、步骤统计
  计数更新（仅 success_count/failure_count 字段）。模板图落
  `replay.storage_dir`（缺省 `<artifacts.root_dir>/replay/templates`）。
- **FR-003（录制触发）**: explicit 探索 run 整体 `passed` 且
  `replay.enabled && replay.auto_generate && repo 可用` 时，系统 MUST 把每个步骤
  最后一次验证 `passed` 且带 executable_action 的迭代转为 ReplayStep 存为新版本
  脚本（version = 既有最大版本 + 1，旧版本保留）。任一步骤缺少可录制迭代 → 放弃
  本次脚本生成（日志）。录制失败 MUST NOT 影响 run 结果（fail-open）。
- **FR-004（录制内容）**: 键盘步骤 MUST 记录 ExecutableAction 快照（keys/text/
  operation/repeat 参数）供直接重放；鼠标步骤 MUST 记录：动作前帧页面指纹
  （015 `build_page_fingerprint`，safe 帧）、target_region 的模板裁剪（源为 safe
  帧）、锚点文本及其 bbox（目标邻近 OCR，至多 5 条按中心距排序）、原始 bbox 与
  按分辨率归一化的 bbox、该步验证 spec。target_region 与 `security.mask_regions`
  相交时 MUST NOT 落模板且该步标记 `direct_fallback_only=true`。
- **FR-005（回放预检）**: mode:"replay" 运行 MUST 在 VNC 连接前完成预检：
  `replay.enabled` 为 false、无持久化仓库、该 test_case 无脚本、或脚本步骤序列与
  testcase 声明步骤 id 序列不一致时 MUST fail fast（`ReplayUnavailableError`，
  CLI 退出码 2），不产生 run 记录。默认加载最新版本脚本。
- **FR-006（回放定位顺序）**: 每个鼠标 ReplayStep MUST 依序：页面指纹匹配
  （015 `classify_page_match`，档位 ≥ `replay.min_page_match_level`（默认 high）
  才可直接定位）→ 模板匹配（015 `match_element_template`，记录 bbox 邻域
  `replay.bbox_expand_ratio` 外扩、阈值 `replay.template_match_threshold`）→
  OCR 锚点匹配（目标标签唯一 OCR 命中；否则记录锚点位移推算，位移一致性容差
  `replay.anchor_offset_tolerance_px`）→ 历史归一化 bbox（MUST 仅当前分辨率 ==
  录制分辨率）→ 全部未中进入兜底。命中 bbox MUST 经
  `planning/click_point.safe_click_point` 产生点击坐标。
  `direct_fallback_only=true` 的步骤 MUST 跳过全部直接定位。
- **FR-007（零模型调用）**: 回放 happy path MUST NOT 调用 Planner（下一步信息
  全部来自 ReplayStep 序列，设计 §21.3）且 MUST NOT 调用 Grounder；telemetry 的
  `model_calls` 中 planner/grounder 计数 MUST 为 0 可断言。每步独立验证 MUST 照常
  执行（含 verification 角色的模型调用），绝不豁免。
- **FR-008（兜底）**: 指纹低于要求档位 / 定位全部未中 / 直接定位后验证失败时，
  该步 MUST 兜底：用既有 `GroundingRequest` 通道调用 Grounder 一次（记录的
  bbox 作为 template_candidates 提示传入），经既有 `ActionPolicy.resolve` 共识
  门槛产生 executable → 执行 → 独立验证。兜底成功 MUST 生成 status="pending" 的
  ReplayPatch 并继续后续步骤；兜底失败（grounding 未中/policy stop/验证失败）
  MUST 终结 run 为 failed，failure_reason 指明 replay_step_id。每步至多一次兜底。
  键盘步骤验证失败 MUST 直接失败，不做 grounding 兜底。
- **FR-009（ADR-005 红线）**: ReplayPatch MUST NOT 被自动应用；
  `replay.patch_auto_apply` 配置存在但默认 false，且 MVP 中即使 true 也仅记警告
  日志、不产生任何应用行为。回放过程中已存脚本的目标字段（模板/bbox/归一化
  bbox/锚点/动作）MUST 只读；仅 success_count/failure_count 统计允许更新。
- **FR-010（记忆协同）**: 兜底 grounding 成功且验证 `passed` 后 MUST 复用 015
  `PageElementMemory.record_success` 回写记忆（不另建写入通道）。回放模块 MUST
  只消费 `memory/` 公开接口（fingerprint/retrieval 纯函数 + service），MUST NOT
  修改其内部实现；脚本数据与 015 记忆表 MUST 分开存储（不同生命周期）。
- **FR-011（CLI 与配置）**: `api/cli.py` MUST 支持：`run` 命令接受 mode:"replay"
  testcase 及 `--mode replay` 覆盖；新增 `replay scripts <test_case_id>` 与
  `replay patches <test_case_id>` JSON 查询命令。config MUST 新增 `replay` 段：
  `enabled`（默认 true）、`auto_generate`（默认 true）、`patch_auto_apply`
  （默认 false）、`template_match_threshold`（默认 0.85，独立于 memory 段）、
  `bbox_expand_ratio`（默认 0.5）、`min_page_match_level`（默认 "high"）、
  `anchor_offset_tolerance_px`（默认 8）、`storage_dir`（默认 null）。
  `domain/testcase.py` 的 mode MUST 扩展为 Literal["explicit","replay"]（additive）。
- **FR-012（可观测性）**: 每个回放迭代 MUST 记录 `replay_audit`（additive 字段：
  replay_step_id、script_version、locate_method ∈ {template, anchor, bbox,
  fallback_grounding, keyboard}、page_similarity、template_score、patch_id）；
  新增 CounterEvent 种类 `replay_step_replayed`（payload: replay_step_id、method、
  script_version）与 `replay_patch_generated`（payload: patch_id、replay_step_id、
  script_version）；`PerformanceSummary` 新增 additive 字段
  `replay_locate_methods: dict[str,int]` 与 `replay_patch_count: int`；兜底的
  grounder 调用照常记 `model_call` 事件与 audit；JSON/HTML 报告透出。
- **FR-013（探索路径不变性）**: 探索模式（mode:"explicit"）的既有行为 MUST 逐字节
  不变——唯一允许的插入是：迭代通过后的录制草稿采集与 run passed 后的脚本落库
  （两者均 fail-open、无行为副作用）。MUST NOT 修改：`memory/` 内部、
  `planning/action_policy.py`、`planning/click_point.py`、`verification/` 引擎与
  仲裁、`perception/ocr/engine.py`、`models/mimo_grounder.py` 坐标链路、008 缓存、
  009 planner-skip、014 zoom、015 记忆 hot path 既有行为。
- **FR-014（业务无关）**: 录制/回放/补丁逻辑 MUST 完全基于通用几何/文本/像素结构
  （Constitution VI），不引入被测应用专用词汇。

### Key Entities

- **ReplayStep**: 见 FR-001；`anchors` 为 `[{text, bbox}]`（比设计 §11 的纯文本
  锚点 additive 增强，用于位移推算）；`normalized_bbox` 为 [0,1] 比例坐标；
  `direct_fallback_only` 标记 mask 相交步骤。
- **ReplayScript**: test_case_id ↔ 有序 ReplayStep 列表 + version + source_run_id。
- **ReplayPatch**: 见 FR-001/设计 §11；status 生命周期 pending →（人工）approved/
  rejected，MVP 只产生 pending。
- **ReplayStepAudit**: 迭代级 additive 审计（FR-012）。
- **ReplayConfig**: 见 FR-011。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 离线 e2e：探索 run `passed` → 自动生成脚本；断言 replay_steps 行数 ==
  步骤数、鼠标步骤模板文件落盘、指纹/锚点/归一化 bbox/验证 spec 内容正确。
- **SC-002**: replay run happy path：planner `model_call` 计数 0、grounder
  `model_call` 计数 0（stub 调用计数同为 0）、每步验证 `passed`、run `passed`、
  每步 `replay_audit.locate_method` 正确。
- **SC-003**: 按钮移位：直接定位未中 → 兜底成功 → pending patch 落库、原脚本目标
  字段不变、run `passed`；兜底失败 → run `failed` 且 failure_reason 含
  replay_step_id。
- **SC-004**: `replay.enabled:false` 或无脚本时 mode:"replay" fail fast（错误信息
  指明原因），CLI 退出码 2。
- **SC-005**: 单测覆盖：ReplayStep 序列化往返、归一化 bbox 还原与分辨率不一致拒绝、
  mask 相交录制拒绝、patch 生成与 pending 状态、patch_auto_apply=true 仅告警不
  应用、脚本版本递增与旧版本保留——100% 通过。
- **SC-006**: 既有测试套件（unit/fixtures/e2e/integration 离线）全绿；golden 快照
  （legacy JSON projection、zh-CN HTML）因 additive 字段按其自带流程再生成。

## Clarifications（全自动流程，代替 /speckit-clarify）

### 决策 1：录制来源——通过迭代的现场采集 + run passed 后落库

StructuredScreen（OCR 项等）不持久化，因此录制素材在 `run_action_iteration` 中
`vr.status=="passed"` 时现场采集为内存草稿（指纹/锚点/归一化 bbox 即时计算，
保留 safe 帧路径），run 整体 passed 后 finalize 时才裁剪模板并落库——失败 run 零
磁盘写入。同一步骤多次通过迭代（理论不发生）以最后一次为准。经
repeat-guard 阻断裁决通过的步骤（通过迭代无 executable_action）无法录制，整个
脚本放弃生成——半份脚本比没有脚本更危险（回放会在缺失步骤处必然失败）。

### 决策 2：锚点匹配的两级语义

设计 §11 只存锚点文本；仅有文本无法推算位置，故 additive 存 `anchors:[{text,bbox}]`。
回放时：(a) 目标标签归一化文本在当前帧 OCR 唯一命中 → 直接用该 bbox（最强锚点
即目标自身文本）；(b) 否则对每条记录锚点找当前帧唯一同文本 OCR 项，计算中心位移，
全部匹配锚点位移两两一致（≤ anchor_offset_tolerance_px）时取位移中值平移记录
bbox。不唯一的锚点不参与；无一致位移即未中。确定性、无随机。

### 决策 3：归一化 bbox 仅同分辨率直点

归一化 bbox 理论上可跨分辨率还原，但字体/布局缩放非线性，跨分辨率直点风险高于
收益。MVP 规则：当前分辨率 != 录制分辨率 → 指纹档位天然封顶 low（015 语义）→
全部直接定位被禁，逐步兜底。归一化存储保留（未来跨分辨率特性无需迁移 schema）。

### 决策 4：兜底复用 ActionPolicy.resolve 共识门槛

兜底 grounding 的候选筛选不重造：构造与探索路径同构的 GroundingRequest（记录
bbox 作为 template_candidates 提示、confidence=page_similarity），结果交给既有
`ActionPolicy.resolve(sa, screen, grounding_result=...)`——置信度阈值、gap 检查、
safe_click_point 全部继承，行为与探索模式的 grounding 分支一致（只用不改，
FR-013 冻结面不破）。

### 决策 5：脚本只读红线的统计例外

「正式脚本回放中只读」指目标定位字段与动作内容；success_count/failure_count 是
运行统计（同 015 ElementMemory 的计数语义），经 `ReplayRepository.bump_step_stats`
只写这两个字段。补丁生成绝不触碰 replay_steps 行的其余字段（SC-003 断言逐字节
不变）。

### 决策 6：每步预算——一次直接定位 + 至多一次兜底

回放是确定性回归，不引入 Tier-1/Tier-2 重试循环与 RecoveryEngine：直接定位执行
后验证失败 → 一次兜底（重新 grounding + 执行 + 验证）→ 仍失败即终结 run。
探索模式的 recovery 语义（重试/换路/缩放）属于探索，回归失败应当被报告而不是被
掩盖。VNC 断线按既有异常路径终结。

### 决策 7：键盘步骤不做视觉兜底

grounding 只能定位可点击目标；键盘序列失败（焦点漂移等）没有可靠的自动补救且
自动补救有误操作风险 → 直接失败并指明步骤，让人回到探索模式重新沉淀。指纹低于
high 的键盘步骤仍直接重放（记警告日志），由独立验证兜住正确性。

### 决策 8：replay 阈值独立于 memory 段

`replay.template_match_threshold` / `bbox_expand_ratio` 独立配置（默认与 memory
相同：0.85/0.5）：脚本是 per-testcase 正式基线，记忆是全局在线经验，二者调优
节奏不同（回归可能要求更严阈值）。`min_page_match_level` 默认 "high"（设计
§10.2 语义），允许放宽到 "medium"（显式配置，风险自担——medium 仍有独立验证兜底）。

### 决策 9：与 015 的分界

- 存储：`replay_*` 三表与 `page_memories`/`element_memories` 完全分离，不混存。
- 共享：`memory.fingerprint` / `memory.retrieval` 纯函数、遮罩规则
  （`region_intersects_any` + safe 帧裁剪源）。
- 生命周期：脚本按版本显式生成/保留，per-testcase；记忆在线增量 upsert/淘汰，
  全局。回放兜底成功回写记忆（FR-010）；回放直接命中不回写记忆（脚本自身统计
  已覆盖，避免把脚本轨迹重复灌入全局记忆）。
- 015 hot path（探索模式 grounding 分支内的记忆直点）在回放模式不参与——回放
  有自己的定位链。

### 决策 10：失败步骤报告口径

回放失败的 run：失败步骤 StepRecord.failure_reason 格式
`replay step failed: replay_step_id=<id> step_id=<原步骤id> reason=<...>`；
`replay_audit` 保留在迭代记录中——报告读者可直接定位到脚本步骤与版本。

### 决策 11：无脚本/禁用的 fail fast 语义

mode:"replay" 是显式回归意图；静默降级为探索会把「基线丢失」掩盖成「更慢的
通过」。因此预检失败一律 `ReplayUnavailableError` fail fast（CLI 退出码 2
validation，与无效 testcase 同级），错误信息指明补救（先跑探索/启用 replay）。

## Assumptions

- 探索 run 与回放 run 使用同一 SQLite（`artifacts.db_path`）与 artifacts 根——脚本
  模板路径为绝对/相对一致可读。
- ReplayStep 的验证 spec 快照冻结于录制时刻；testcase 后续编辑验证条件不影响已存
  脚本（步骤 id 序列变化才触发预检失败）。
- 兜底 grounding 需要模型 API 可用；离线 e2e 用 Stub 计数验证调用次数。
- 回放模式沿用探索模式的观察/稳定等待/验证基建（pipeline/stability/verifier），
  这些组件的行为对 mode 不敏感。
