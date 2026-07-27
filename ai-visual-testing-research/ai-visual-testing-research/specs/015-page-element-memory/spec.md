# Feature Specification: 页面记忆与元素记忆（page-element-memory）

**Feature Branch**: `015-page-element-memory`

**Created**: 2026-07-26

**Status**: Draft

**Input**: User description: "总体设计 §12（页面记忆/元素记忆）+ §13（页面相似度和经验
检索）的最小可用实现。被测系统是日文 POS，页面集合固定、按钮位置稳定，记忆命中率会
很高。当前每次点击都要走 OCR/（可能的）Grounding，页面无任何跨 run 记忆。设计文档
§21.3 明确『历史经验命中时不立即调用 MiMo』——本 feature 把这条通道建起来，并为
Feature 016 Record-Replay 预留检索接口。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 成功点击沉淀为跨 run 记忆 (Priority: P1)

一次鼠标动作经独立验证 `passed` 后，系统用**动作前帧**按解析出的 `target_region`
裁剪元素模板图，连同锚点文本（目标附近的 OCR 文本）、页面指纹一起写入元素记忆；
页面指纹 upsert 进页面记忆。下次（包括下个 run）再遇到同一页面、同一目标时可以检索。

**Why this priority**: 没有写入就没有命中；写入路径是记忆通道的地基。

**Independent Test**: 离线 e2e——第一次运行经 Grounding 成功点击并 `passed`；断言
SQLite 中出现 `page_memories` / `element_memories` 行、模板图物理文件落盘、统计字段
正确。

**Acceptance Scenarios**:

1. **Given** 一次 `needs_grounding` 的鼠标点击经 Grounder 定位、执行并独立验证
   `passed`，**When** 迭代结束，**Then** 系统写入 ElementMemory（模板图路径、历史
   bbox、锚点文本、成功计数=1）并 upsert PageMemory（指纹、分辨率、命中统计、最后
   见到时间）。
2. **Given** 同一（页面, 目标标签）已有记录，**When** 再次成功，**Then** 更新统计
   （成功计数+1、连续成功计数+1、最新 bbox、最后成功时间），并按模板替换策略决定
   是否刷新模板图（见 Clarifications 决策 4）。
3. **Given** 键盘动作（无坐标）验证通过，**When** 迭代结束，**Then** 不产生任何
   元素记忆写入（只记 mouse 路径）。
4. **Given** 记忆写入过程抛出任何异常（DB 不可用、图像解码失败等），**When** 迭代
   结束，**Then** 主流程不受影响（fail-open，仅记日志），步骤结果不变。

---

### User Story 2 - 记忆命中直点，跳过 Grounder (Priority: P1)

第二次遇到同一页面同一目标（`PolicyResult.needs_grounding=True` 时），系统在调用
MiMo 前先查记忆：当前帧指纹与 ElementMemory 所属页面指纹达 high 阈值（≥0.88）且
目标标签匹配 → 在历史 bbox 邻域做模板匹配 → 匹配置信度达标 → 直接产生点击
（坐标经 feature 013 `safe_click_point`），跳过 Grounder 调用。

**Why this priority**: 这是设计 §21.3『历史经验命中时不立即调用 MiMo』的落地，也是
本 feature 的直接价值（省一次模型调用 + 时延）。

**Independent Test**: 离线 e2e——同一页面第一次走 Grounding 成功并写入记忆；第二次
同目标 Grounder 调用计数为 0、点击坐标与模板匹配 bbox 的 safe point 一致、run
`passed`、报告可见 memory_hit。

**Acceptance Scenarios**:

1. **Given** 记忆中存在（页面指纹相似度 ≥ `memory.page_match_high`，目标标签相等）
   的 ElementMemory，且历史 bbox 邻域（外扩比例可配）内模板匹配置信度 ≥
   `memory.template_match_threshold`，**When** 该迭代进入 Grounding 分支，**Then**
   系统不调用 Grounder，直接以模板匹配 bbox 的 safe_click_point 产生点击。
2. **Given** 页面相似度落在 medium 档（[0.72, 0.88)），**When** 该迭代进入 Grounding
   分支，**Then** 系统照常调用 Grounder，但把记忆中的历史 bbox 作为候选提示经既有
   `GroundingRequest` 候选通道（template_candidates）传入——绝不直点。
3. **Given** 任一环节不满足（页面相似度不足 / 标签不匹配 / 模板文件缺失 / 模板匹配
   低于阈值 / 分辨率与记忆不一致），**When** 该迭代进入 Grounding 分支，**Then**
   无损回落到既有 Grounder 路径，行为与无记忆时一致。
4. **Given** 记忆直点已执行，**When** 进入验证，**Then** 独立验证照常执行——记忆命中
   **绝不豁免**后续独立验证（Constitution IV）。
5. **Given** 记忆直点后独立验证 `failed`/`uncertain`，**When** 迭代结束，**Then**
   该 ElementMemory 失败计数+1、连续成功计数清零，且**本步骤内**后续迭代不再使用该
   条记忆（防失效模板反复误导），回落既有路径。
6. **Given** 本迭代存在待消费的 zoom_reground 计划（feature 014），**When** 进入
   Grounding 分支，**Then** 记忆通道让位于 zoom 观察（不做记忆查找），既有 014 行为
   不变。

---

### User Story 3 - 安全红线与配置开关 (Priority: P1)

元素模板截图必须经过与报告截图相同的敏感区遮罩规则；`memory.enabled: false` 时
全链路行为与现状逐字节一致。

**Independent Test**: 单测——`target_region` 与 `security.mask_regions` 任一矩形相交
时元素记忆不写入（页面记忆照常）；e2e——`enabled: false` 时两次运行 Grounder 调用
计数与基线一致、无记忆表写入、无模板目录产生。

**Acceptance Scenarios**:

1. **Given** `security.mask_regions` 配置了敏感区且目标 region 与之相交，**When**
   动作 `passed`，**Then** 不落模板、跳过该元素的记忆写入（日志记录原因）；页面
   指纹 upsert 不受影响（指纹本身来自已遮罩的 safe 帧，见 Clarifications 决策 3）。
2. **Given** `memory.enabled: false`，**When** 运行任意用例，**Then** 系统不读不写
   任何记忆（无查找、无表写入、无模板落盘、无 memory 相关 telemetry），与本 feature
   合入前行为一致。
3. **Given** 模板图落盘，**Then** 裁剪源是已按 `security.mask_regions` 遮罩的
   safe 帧（与报告截图同一遮罩规则），未遮罩像素永不进入记忆存储。

---

### User Story 4 - 可观测性 (Priority: P2)

工程师能从报告/日志看出『这一步是记忆直点』：命中来源（element_memory）、页面
相似度分、模板匹配分；性能摘要含记忆命中计数；Grounder 被跳过有 `model_call_skipped`
审计（reason=element_memory_hit）。

**Independent Test**: e2e 断言 iteration 的 `memory_hit` 字段、
`performance_summary.memory_hits.element_memory` 计数、outcome="skipped" 的 grounder
ModelCallAudit。

**Acceptance Scenarios**:

1. **Given** 一次记忆直点，**Then** 该 iteration 记录 `memory_hit`（element_memory_id、
   page_memory_id、target_label、page_similarity、template_score、matched_bbox），
   JSON 报告透出。
2. **Given** 一次记忆直点，**Then** 追加一条 `element_memory_hit` CounterEvent 与
   一条 `model_call_skipped`（model_role=grounder, reason=element_memory_hit）
   CounterEvent + outcome="skipped" 的 ModelCallAudit；
   `performance_summary.memory_hits.element_memory` 与 `skipped_model_call_count`
   相应递增。
3. **Given** 无任何记忆命中的 run，**Then** `performance_summary.memory_hits`
   仍存在且 `element_memory` 为 0（与 cache_hits 的 setdefault 惯例一致）。

---

### Edge Cases

- 当前帧 safe 图像文件读不出（IO/解码失败）→ 记忆查找返回未命中，写入跳过
  （fail-open）。
- 目标标签为空（SemanticAction 无 target 文本/描述/意图）→ 不查找、不写入。
- 模板图为纯色平坦区域 → `TM_CCOEFF_NORMED` 数值不稳定，匹配分达不到阈值 →
  自然回落 Grounder 路径（无需特判）。
- 分辨率与记忆页面不一致 → 页面匹配档位封顶为 low（bbox/模板都是分辨率相关的），
  永不直点、也不作为候选提示。
- 每页元素数达到 `memory.max_elements_per_page` 上限时新元素写入 → 按确定性规则
  淘汰『最后成功时间最旧』的一条（并删除其模板文件）。
- 同一步骤内记忆直点验证失败后再次进入 Grounding 分支 → 该 element 在本步内被
  排除，其余记忆仍可参与（本步失败清单随步骤重置）。
- 数据库中存在记录但模板物理文件丢失 → 不直点，降级为候选提示（medium 语义）。
- OCR 关闭（`perception.ocr_enabled: false`）→ 指纹的文本/布局分量为空集，相似度
  由 pHash 主导；写入与命中语义不变。
- 动态区域（时钟、日期、金额跳动）→ 指纹构建时过滤『纯数字/日期时间形态』token
  （见 Clarifications 决策 2），不参与文本/布局分量。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001（页面指纹）**: 系统 MUST 提供纯函数式页面指纹构建
  （`memory/fingerprint.py`）：pHash（32x32 灰度 DCT 取 8x8 低频、去 DC 均值化的
  64-bit 感知哈希，自实现，无新依赖）+ OCR 关键词集合（归一化、去动态 token）+
  OCR 文本位置分布（8x8 粗网格占用集合，按分辨率归一化）+ 分辨率。相同输入 MUST
  产生相同指纹（确定性）。
- **FR-002（相似度打分）**: 页面相似度 MUST 按设计 §13 权重计算；MVP 无稳定模板
  集合分量，其 0.20 权重按比例并入前三项：pHash 0.375 + OCR 文本 0.375 + OCR 布局
  0.25（见 Clarifications 决策 1）。三档阈值 MUST 可配：
  `memory.page_match_high: 0.88 / medium: 0.72 / low: 0.55`。分辨率不一致时档位
  MUST 封顶为 low。
- **FR-003（领域模型与存储）**: `domain/memory.py` MUST 定义 PageMemory（指纹、
  页面标识、分辨率、命中统计、最后见到时间）与 ElementMemory（所属页面、归一化
  目标标签、模板图路径、历史 bbox、锚点文本、成功/失败/连续成功计数、最后成功
  时间）。SQLite MUST 新增 `page_memories` / `element_memories` 表（照
  `storage/database.py` + `storage/repositories.py` 既有模式）；模板图片落盘到
  记忆存储目录（`memory.storage_dir`，缺省为 `<artifacts.root_dir>/memory/templates`），
  路径入库。
- **FR-004（记忆写入）**: 一次鼠标动作（method=mouse 且带 target_region）经独立
  验证 `passed` 后，系统 MUST 用动作前帧的 safe 图像按 `target_region` 裁剪模板图，
  连同锚点文本（目标邻近 OCR 文本，至多 5 条、按中心距排序）与页面指纹写入
  ElementMemory，并 upsert PageMemory。keyboard 路径 MUST NOT 写入元素记忆。写入
  失败 MUST NOT 影响主流程（fail-open，log）。
- **FR-005（安全红线）**: 模板裁剪源 MUST 是已按 `security.mask_regions` 遮罩的
  safe 帧（与报告截图同一遮罩规则）；`target_region` 与任一 mask 矩形相交时 MUST
  跳过该元素的记忆写入（不落模板）。
- **FR-006（命中直点）**: `PolicyResult.needs_grounding=True` 且无待消费 zoom 计划
  时，系统 MUST 在调用 Grounder 前查记忆：页面相似度 ≥ `page_match_high` 且目标
  标签相等 → 在历史 bbox 按 `memory.bbox_expand_ratio` 外扩的邻域内做模板匹配 →
  置信度 ≥ `memory.template_match_threshold`（默认 0.85）→ 以匹配 bbox 的
  `safe_click_point`（feature 013）直接产生点击并跳过 Grounder。任一步不满足 MUST
  无损回落原路径。
- **FR-007（medium 档候选提示）**: 页面相似度在 [medium, high) 或高档但模板匹配
  未达标/模板缺失时，系统 MAY 把 ElementMemory 的历史 bbox 作为提示经既有
  `GroundingRequest.template_candidates` 通道传给 Grounder，MUST NOT 直点。
- **FR-008（验证独立性）**: 记忆命中 MUST NOT 豁免后续独立验证。记忆直点后验证
  `failed`/`uncertain` 时 MUST：该 ElementMemory 失败计数+1、连续成功计数清零、
  本步骤内不再使用该条记忆。
- **FR-009（配置）**: `config/agent.yaml` MUST 新增 `memory` 段：`enabled`（默认
  true）、`page_match_high/medium/low`、`template_match_threshold`（默认 0.85）、
  `bbox_expand_ratio`（默认 0.5，每侧按 bbox 宽高比例外扩）、
  `max_elements_per_page`（默认 64）、`template_refresh_min_consecutive_successes`
  （默认 3）、`storage_dir`（默认 null → artifacts 根下）。`enabled: false` 时
  全链路行为 MUST 与现状逐字节一致。
- **FR-010（可观测性）**: 记忆直点 MUST 产生：iteration 级 `memory_hit` 记录
  （additive 字段）、`element_memory_hit` CounterEvent、grounder 的
  `model_call_skipped` CounterEvent + outcome="skipped" ModelCallAudit
  （reason=element_memory_hit）、结构化日志事件。`PerformanceSummary` MUST 新增
  additive 字段 `memory_hits: dict[str,int]`（键 `element_memory`，无命中时为 0），
  JSON/HTML 报告透出。
- **FR-011（接线边界）**: 接入点仅限 runtime 的 Grounding 分支（仿 feature 014
  zoom_reground 的 runtime 内消费模式）。MUST NOT 修改：`planning/action_policy.py`
  的既有逻辑行（其 `resolve` 语义不变）、`verification/`、
  `perception/ocr/engine.py`、`planning/click_point.py`、`execution/`、
  `models/mimo_grounder.py` 坐标链路、feature 008 缓存接线、009 planner-skip、
  014 zoom 分支既有逻辑。`evolution/experience_collector.py` 保持 write-only，
  记忆读取 MUST NOT 进入它。
- **FR-012（业务无关性）**: 指纹、相似度、检索、存储逻辑 MUST 完全基于通用几何/
  文本/像素结构，MUST NOT 引入被测应用专用词汇（Constitution VI）。
- **FR-013（016 扩展点）**: fingerprint 构建/相似度与 ElementMemory 检索 MUST 以
  可独立调用的公开签名暴露（输入 StructuredScreen/帧，输出匹配结果），供将来的
  replay player 使用（见下节『016 扩展点』）。

### Key Entities

- **PageFingerprint**（`domain/memory.py`，纯数据）: `phash`（16 hex）、
  `ocr_tokens`（排序去重）、`layout_cells`（8x8 网格占用，"col,row" 排序）、
  `resolution`、`version="pfp-v1"`。
- **PageMemory**: `page_id`、`fingerprint`、`resolution`、`hit_count`、
  `last_seen_at`、`created_at`。
- **ElementMemory**: `element_id`、`page_id`、`target_label`（归一化）、
  `template_path`、`bbox`（最近一次成功的 target_region）、`anchor_texts`、
  `success_count` / `failure_count` / `consecutive_success_count`、
  `last_success_at`、`created_at`。
- **MemoryLookupResult**: `level`（"high"/"medium"/"none"）、`page` /
  `page_similarity`、`element`、`template_score`、`matched_bbox`——016 replay 的
  检索返回类型。
- **MemoryHitAudit**（iteration additive 字段）: `source="element_memory"`、
  `element_memory_id`、`page_memory_id`、`target_label`、`page_similarity`、
  `template_score`、`matched_bbox`。
- **MemoryConfig**: 见 FR-009。

### 016 扩展点（本 feature 只定义、不实现 replay）

Feature 016 Record-Replay 的 player 可独立调用以下公开接口（不依赖 AgentRuntime）：

- `memory.fingerprint.build_page_fingerprint(image, ocr_items, resolution) -> PageFingerprint`
  —— 纯函数；`image` 为解码后的 BGR 帧（可为 None，则 pHash 分量为空）。
- `memory.fingerprint.page_similarity(a, b) -> float` 与
  `memory.fingerprint.classify_page_match(score, *, same_resolution, high, medium, low)
  -> "high"|"medium"|"low"|"none"` —— 纯函数。
- `memory.retrieval.match_element_template(frame, template, bbox, *, expand_ratio,
  threshold, resolution) -> (bbox, score) | None` —— 纯函数，历史 bbox 邻域模板匹配。
- `memory.service.PageElementMemory.lookup(screen: StructuredScreen, target_label: str,
  *, exclude_element_ids) -> MemoryLookupResult | None` —— 异步检索门面：输入当前
  StructuredScreen 与目标标签，输出匹配结果（含直点判定所需的全部证据）。replay
  player 持有 `MemoryRepository`（同一 SQLite）即可独立构造并调用。
- `memory.service.PageElementMemory.record_success / record_element_failure` ——
  replay 成功/失败的统计回写复用同一入口。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 离线 e2e：run1 经 Grounding 成功 → 记忆写入；run2（同页面同目标）
  Grounder 调用计数 = 0，点击坐标与模板匹配 bbox 的 safe point 逐像素一致，run
  `passed`。
- **SC-002**: 记忆直点但验证失败的场景：ElementMemory 失败计数+1，且该步内后续
  迭代回落 Grounder（调用计数 ≥ 1），run 按既有语义终结。
- **SC-003**: `memory.enabled: false` 时与基线行为一致：Grounder 调用计数不变、
  无记忆表行、无模板文件、无 memory telemetry。
- **SC-004**: 单测覆盖：pHash 确定性与小噪声近似不变性、相似度权重与三档阈值、
  分辨率变化封顶 low、ElementMemory upsert 与统计/模板替换策略、mask 相交拒写、
  邻域模板匹配命中/未中回落——100% 通过。
- **SC-005**: 既有测试套件（unit / fixtures / e2e / integration 离线）全部保持
  通过；golden 快照（legacy JSON projection、zh-CN HTML）因 additive 字段按其
  自带流程再生成，属预期内变更。

## Clarifications（全自动流程，代替 /speckit-clarify）

### 决策 1：MVP 相似度权重——模板分量按比例并入前三项

设计 §13 的 0.20 模板匹配分量依赖『稳定模板集合』（页面级模板库），本 MVP 尚无
该设施（元素模板是点击目标级、非页面级）。将 0.20 按原比例摊入其余三项：
pHash 0.30/0.80=0.375、OCR 文本 0.375、OCR 布局 0.25。阈值语义（0.88/0.72/0.55）
不变。未来引入页面级稳定模板后可恢复四分量原权重，阈值无需迁移。

### 决策 2：动态区域降噪——按 token 形态过滤，而非区域建模

时钟/日期/流水号等动态内容的共同形态是『纯数字与日期时间标点构成的 token』
（如 `12:34`、`2026/07/26`、`No.0012`、`¥1,234`）。指纹构建时将『去掉数字、
时间日期分隔符（`:/-.,`）、货币与序号记号后为空』的 token 从关键词集合与布局
网格中剔除。这是确定性、业务无关的形态规则；页面标题/按钮文字（含日文假名汉字）
不受影响。不建模『常见动态区域』（设计 §12.1 的完整形态）——那需要跨帧统计，留给
后续 feature；本规则已覆盖 POS 页面最主要的动态噪声源。

### 决策 3：指纹与模板一律取自 safe（已遮罩）帧

页面指纹与元素模板都从 `StructuredScreen.image_path`（安全遮罩后的 safe 帧）读取，
与报告截图同一遮罩规则：未遮罩像素永不进入记忆存储（FR-005 红线的实现基础）。
遮罩区域对指纹是恒定黑块，对确定性无损；对模板，因 mask 相交的 region 直接拒写，
落盘模板中不含黑块残缺。代价：mask 配置变更会使旧指纹 pHash 分量失配——POS 部署
mask 稳定，可接受；且失配只导致回落原路径（fail-open），无正确性风险。

### 决策 4：模板替换策略——连续 3 次成功才替换模板图

已有记录再次成功时：统计与 bbox/锚点/最后成功时间总是更新；模板图仅当
`consecutive_success_count >= template_refresh_min_consecutive_successes`（默认 3）
时用最新裁剪替换并将连续计数清零重新累计。理由：单次成功即替换会把偶发的渲染
异常帧（反色高亮、残影）固化进模板；连续成功门槛保证替换源是稳定外观。失败会将
连续计数清零，防止失效外观被采纳。

### 决策 5：命中直点的接线方式——runtime Grounding 分支内消费，不改 ActionPolicy

仿 feature 014 zoom_reground：在 `needs_grounding` 分支内、构造 GroundingRequest
之前查记忆；直点命中时由 runtime 直接构造 ExecutableAction（safe_click_point +
target_region=匹配 bbox），不经过也不修改 `ActionPolicy.resolve`（FR-011）。
medium 提示走既有 `template_candidates` 请求通道（对 Grounder 是 hint 语义，与
既有模板候选完全同构）。zoom 计划待消费时记忆让位（zoom 是失败后的恢复升级，
此时上一轮记忆/常规路径已失败，继续用记忆无意义）。

### 决策 6：本步失败封禁 + 跨步重置

记忆直点验证失败后，该 element_id 进入 runtime 的本步封禁集合（随每个 TestStep
的 recovery 重置一起清空）。持久层同时累计失败计数。不做全局封禁：跨步骤/跨 run
的失效由失败计数与模板替换策略慢性收敛，避免单次瞬态失败永久废弃高价值记忆。

### 决策 7：页面 upsert 的匹配规则与统计口径

写入时以『相似度 ≥ high 且分辨率相等』的最佳既有页面为同一页面：命中则
`hit_count+1`、刷新 `last_seen_at`，**保留原指纹**（指纹稳定性优先，避免漂移）；
否则插入新 PageMemory。`lookup` 是只读操作，不更新统计（统计只在成功写入路径
更新），保证检索可被 016 replay 任意调用而无副作用。

### 决策 8：每页元素上限的淘汰规则

达到 `max_elements_per_page` 时插入新元素前淘汰 `last_success_at` 最旧（空值最先、
并列取 element_id 字典序）的一条并删除其模板文件——确定性规则，无随机性。

### 决策 9：telemetry 形态——复用 model_call_skipped + 新增 element_memory_hit

Grounder 被跳过复用既有 `model_call_skipped` CounterEvent / outcome="skipped"
ModelCallAudit（与 feature 009 planner-skip 完全同构，`skipped_model_call_count`
自然纳入既有守恒口径）；命中明细另加新 CounterEvent 种类 `element_memory_hit`
（payload: element_memory_id / page_similarity / template_score），汇总为
`performance_summary.memory_hits`（dict 形态仿 cache_hits）。golden 快照按自带
流程再生成（SC-005）。

### 决策 10：记忆服务的构造位置

`AgentRuntime.__init__` 内按 `config.agent.memory.enabled && repo is not None`
构造（复用 repo 的 session_factory 与 artifact_store 根目录派生模板目录），CLI /
e2e conftest 零改动。禁用或无 repo（纯内存运行）时 `self.memory = None`，所有
接线点短路——保证 `enabled: false` 逐字节一致性。

## Assumptions

- 被测 POS 页面集合固定、控件位置稳定（用户输入），记忆命中率高是收益前提而非
  正确性前提——低命中率只是回落原路径。
- `StructuredScreen.image_path` 指向的 safe 帧在 lookup/写入时刻仍在磁盘（同一
  迭代内，capture 刚完成）；读不出则 fail-open。
- 模板匹配复用 `perception/template/matcher.py::match_template_array`
  （TM_CCOEFF_NORMED），其阈值语义与既有模板路径一致。
- SQLite 表由既有 `init_db`（`Base.metadata.create_all`）自动建表；旧库升级即
  新表追加，无迁移脚本需求。
- pHash 对 32x32 下采样后的小噪声（±少量像素扰动）稳健；对分辨率缩放不做跨分辨率
  匹配承诺（FR-002 封顶 low 即此含义）。
