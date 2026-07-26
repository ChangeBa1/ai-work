# Feature Specification: OCR 可疑命中转 Grounding 兜底（partial-hit grounder fallback）

**Feature Branch**: `012-ocr-partial-hit-grounder-fallback`

**Created**: 2026-07-26

**Status**: Draft

**Input**: User description: "真实运行 bb9f039e：屏幕按钮实际是「レジ袋」，OCR（当时的中文模型）截断
读成「ジ袋」，Planner 回显了这个截断文本作为 target.text，ActionPolicy._unique_ocr_or_template
判定为唯一命中，直接取残缺 bbox 中心点击 → 点击偏移。Feature 010 已换日文 OCR 模型大幅减少截断，
但系统需要一条通用防线：OCR 命中证据可疑时，不直接点，转 MiMo Grounding 兜底，并把该 OCR 命中
作为候选提示传给 grounder（现有 GroundingRequest.ocr_candidates 通道）。"

## 背景与防线定位

Action Policy 第 3 优先级（Unique OCR / template localization）在"归一化目标文本被唯一一条
OCR 结果包含"时直接取该 OCR bbox 中心点击，完全信任 OCR 的文本重建与 bbox 完整性。
bb9f039e 事故链条是：OCR 截断（漏读首字符）→ Planner 回显截断文本 → 截断文本与截断 OCR
结果"完美"唯一匹配 → 点击残缺 bbox 中心 → 偏移。本 feature 在"唯一命中 → 直接点击"之间
加入**可疑命中检测**：命中证据可疑时不返回坐标，让 resolve 落入既有 Grounding 路径
（`needs_grounding=True`），由 MiMo Grounding 以视觉方式重新定位；既有 grounder 请求通道
（`GroundingRequest.ocr_candidates`，运行时已把全部 `screen.ocr_items` 作为候选提示传入）与
既有 grounding 防线（`_consistent_with_unique_ocr` 距离一致性、置信度门限、Top1/Top2 gap）
自动生效，均不做任何修改。

## 可疑命中判定规则（规范性定义）

判定对象：第 3 优先级中按既有包含匹配（归一化目标文本 needle ⊆ OCR 文本）得到的**唯一 OCR
命中**。判定使用"可比文本"：`strip + lower` 后再剥除首尾空白与常见 ASCII/CJK 装饰标点
（引号、括号、冒号、句读、间隔号等），不改动匹配规则本身。

| 规则 ID | 名称 | 触发条件 | 效果 | 理由 |
|---|---|---|---|---|
| R-A1 | 截断部分读取（truncated_ocr_read） | 无任何包含匹配命中，且**恰有一条** OCR item 的可比文本是目标可比文本的真子串（长度 ≥ 2） | 本就不直接点击（现状即落 grounding）；补充记录 suspicion 观测数据，供报告/日志与 grounder 候选提示排查 | 需求 1a 的字面形态（「ジ袋」⊂「レジ袋」）：包含匹配下 OCR 文本 ⊇ needle 恒成立，"OCR 读得比目标短"结构上不可能成为唯一命中，只能表现为 miss。行为已安全，缺的是可观测性 |
| R-A2 | 部分文本重叠（partial_text_overlap） | 唯一命中的 OCR 可比文本 ≠ 目标可比文本（包含但不相等，即 OCR 文本真包含目标文本） | **不直接点击**，转 grounding | 需求 1a 的工程化推广：非精确包含命中意味着要么 OCR 把相邻字形并入同一条结果（bbox 中心偏离目标）、要么 Planner 声明的 target.text 是截断回显的碎片（bb9f039e 回显模式在 010 换模型后的残留形态）。两者都不可区分地指向"bbox 中心 ≠ 目标中心"的风险 |
| R-B | 低置信命中（low_confidence） | 唯一命中的 OCR confidence < 可配置阈值 `planning.ocr_direct_click_min_confidence`（默认 0.85） | 不直接点击，转 grounding | 直接点击等于把定位决策 100% 交给单条 OCR 结果，其证据强度必须显著高于"参与 grounding 提示"的普通 OCR 候选。bb9f039e 中中文模型读日文按钮即属低把握重建。0.85 高于 grounding 链路自身的 0.55 门限——单证据直点应比多证据合议更严 |
| R-C | 超短文本命中（short_text） | 唯一命中的 OCR 可比文本长度 ≤ 1 | 不直接点击，转 grounding；**优先级高于精确匹配豁免** | 单字符在 CJK/符号场景高频混淆（`+`/`十`/`†`、`一`/`-`），且单字符包含匹配的误命中面最大；即使精确且高置信也不足以支撑直点 |

**精确匹配豁免（不可回归约束）**：唯一命中的 OCR 可比文本 == 目标可比文本、且 confidence ≥
阈值、且长度 ≥ 2 时，判定为可信命中，行为与现状逐字节一致（直接 mouse 点击，不新增任何模型
调用）。

**规则边界（决策记录，代替 /speckit-clarify）**：

1. **R-A2 采用"非精确即可疑"而非字面真子串方向**：包含匹配下唯一命中恒满足 OCR ⊇ needle，
   字面方向（OCR ⊂ target.text）在唯一命中集合内不可达（见 R-A1）；把"包含但不相等"整体
   视为截断/并读证据是覆盖需求意图的唯一可达形态。代价是"目标文本是长标签的规范子串"
   （如 target=`保存`，OCR=`保存して閉じる`）也转 grounding——该形态 bbox 中心本就偏离
   `保存` 字面位置，转 grounding 恰好是更安全的行为。
2. **可比文本剥除首尾装饰标点**：避免「【ログイン】」vs「ログイン」这类纯装饰差异被 R-A2
   误伤而增加模型调用；剥除仅限首尾装饰字符，不剥除内部字符，不引入任何业务词表
   （Constitution VI）。
3. **阈值 0.85 的选择**：介于 grounding 整体门限（0.55）与既有离线 fixture 惯用高置信样本
   （0.9~0.99）之间；对既有测试与真实高质量命中零扰动，同时能拦截 0.5~0.8 区间的低把握
   重建。可配置（`planning.ocr_direct_click_min_confidence`），保守部署可调高。
4. **R-C 长度阈值取 ≤ 1（常量，不配置）**：需求 1c 原文即"归一化后长度 ≤ 1"；2 字符 CJK
   词（如「保存」「登录」）是最常见的合法按钮文案，不应纳入。该规则与精确匹配豁免冲突时
   R-C 胜出（需求 1c 显式列为可疑）。
5. **"唯一 OCR + 唯一模板"混合分支**：OCR 命中可疑时改选模板 bbox（像素级匹配无截断问题，
   仍是直接点击、零新增模型调用），OCR 可信时维持既有 confidence 择优。模板唯一命中分支
   本身零改动。
6. **可疑命中的候选提示传递复用现状**：运行时在 `needs_grounding=True` 时已把全部
   `screen.ocr_items`（含可疑命中项）作为 `GroundingRequest.ocr_candidates` 传给 grounder
   （`_candidates_summary` 注入 prompt），无需新增通道；本 feature 不改 runtime/ 与
   models/。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 截断/部分重叠命中不再直接点击 (Priority: P1)

测试工程师的用例要点击画面按钮「レジ袋」。OCR 把按钮附近文本并读成一条更长的结果（或
Planner 回显了截断碎片作为 target.text），包含匹配得到唯一命中但文本与目标声明不相等。
系统不得直接点击该 bbox 中心，必须转 MiMo Grounding 以视觉方式定位，并让 grounder 通过
既有 ocr_candidates 提示看到该 OCR 命中；报告/日志中能看出这次为什么没有直接点击。

**Why this priority**: bb9f039e 点击偏移的直接动因；不解决则任何 OCR 截断/并读残留形态都
会以"唯一命中"的姿态直接错点，且事后无法从轨迹中看出原因。

**Independent Test**: 离线构造"唯一非精确包含命中"的 StructuredScreen，断言
`resolve` 返回 `needs_grounding=True`、`PolicyResult.ocr_suspicion` 含
`partial_text_overlap` 与命中原文/置信度；构造"无命中但恰有一条真子串 item"，断言
suspicion 为 `truncated_ocr_read`。

**Acceptance Scenarios**:

1. **Given** target.text=`レジ袋`，OCR 唯一命中 `レジ袋合計`（confidence 0.95），
   **When** resolve（无 grounding_result），**Then** `needs_grounding=True`、无 executable、
   `ocr_suspicion.reasons` 含 `partial_text_overlap`，且该命中项存在于 `screen.ocr_items`
   （即运行时既有通道会将其作为 ocr_candidates 提示传给 grounder）。
2. **Given** target.text=`レジ袋`，OCR 只有 `ジ袋`（真子串，无包含命中），
   **When** resolve，**Then** `needs_grounding=True` 且 `ocr_suspicion.reasons` 含
   `truncated_ocr_read`（现状行为不变，新增可观测性）。
3. **Given** 同规则输入但换成另一 GUI 场景词汇（表单流 `Submit Order` vs OCR
   `Submit Orders`），**When** resolve，**Then** 行为一致（Constitution VI）。

---

### User Story 2 - 低置信/超短命中转 grounding (Priority: P1)

OCR 唯一命中文本与目标精确相等但 confidence 低于阈值（默认 0.85），或归一化后长度 ≤ 1：
系统不得直接点击，转 grounding；阈值可在 agent 配置中调整。

**Why this priority**: 截断回显形态（bb9f039e：target.text 与截断 OCR 完全相等）唯一的
运行时可检测信号就是低置信与超短文本；这是防线对"精确匹配的假象"的兜底。

**Independent Test**: 离线构造精确命中 confidence=0.5 → `needs_grounding=True` 且 reasons 含
`low_confidence`；单字符精确命中 confidence=0.99 → reasons 含 `short_text`；
`ActionPolicy(ocr_direct_click_min_confidence=0.3)` 下 0.5 精确命中 → 直接点击。

**Acceptance Scenarios**:

1. **Given** target.text=`レジ袋`，OCR 唯一精确命中 confidence=0.5，**When** resolve，
   **Then** `needs_grounding=True`，reasons 含 `low_confidence`。
2. **Given** target.text=`+`，OCR 唯一精确命中 `+`（confidence 0.99），**When** resolve，
   **Then** `needs_grounding=True`，reasons 含 `short_text`。
3. **Given** 阈值调低为 0.3（构造参数/配置），同场景 1 输入，**When** resolve，
   **Then** 直接点击（`outcome=ocr_template`）。

---

### User Story 3 - 可信命中与既有路径零回归 (Priority: P1)

精确匹配（可比文本相等、长度 ≥ 2）且 confidence ≥ 阈值的唯一 OCR 命中必须保持现状：直接
mouse 点击、坐标与现状完全一致、不新增模型调用。keyboard/focus 优先级（resolve 第 1/2 步）、
模板唯一命中路径、转 grounding 后的既有防线（距离一致性、置信度门限、Top1/Top2 gap）全部
零改动。

**Why this priority**: 不可回归约束是本 feature 可被接受的前提；直点路径是最高频路径，
任何扰动都会放大延迟与模型成本。

**Independent Test**: 精确高置信命中 → PolicyResult 与现状逐字段一致（outcome/method/
operation/coordinates/target_region）；既有 unit/fixtures/e2e 全绿。

**Acceptance Scenarios**:

1. **Given** target.text=`登录`，OCR 唯一精确命中（confidence 0.9），**When** resolve，
   **Then** `outcome=ocr_template`、`method=mouse`、坐标 = bbox 中心（与改动前一致）、
   `needs_grounding=False`、`ocr_suspicion is None`。
2. **Given** 唯一模板命中（无 OCR 命中），**When** resolve，**Then** 模板直点，行为不变。
3. **Given** 唯一 OCR 可疑命中 + 唯一模板命中，**When** resolve，**Then** 选模板 bbox 直点
   （零新增模型调用）；OCR 可信时维持既有 confidence 择优。
4. **Given** 可疑命中转 grounding 后 caller 带 grounding_result 二次 resolve，
   **When** resolve，**Then** 走既有 `_from_grounding` 防线（不变），最终 PolicyResult 附带
   suspicion 观测数据。

---

### Edge Cases

- target 为 None 或归一化后 needle 为空：现状直接落 grounding，无 suspicion（不变）。
- OCR 命中 ≥ 2 条或 0 条（且无唯一真子串 item）：现状落 grounding，无 suspicion（不变）。
- 无命中且有 ≥ 2 条真子串 item：歧义，不产生 `truncated_ocr_read` 观测数据（grounding 照走）。
- 真子串 item 可比长度 < 2：不计入 R-A1（单字符子串噪声面过大）。
- 目标文本仅由装饰标点构成（可比文本为空）：R-A2 不评估；R-C 按长度 ≤ 1 触发。
- 命中文本仅装饰差异（`【ログイン】` vs `ログイン`）：剥除后相等 → 精确豁免，直点不变。
- needle 来自 target.description（text 为空）：规则以实际参与匹配的 needle 为基准评估。
- 多可疑原因叠加（如低置信 + 非精确）：reasons 全部记录。
- resolve 第 1/2 步命中（keyboard/focus）：永不进入本判定（路径完全不动）。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001（可疑命中检测）**: Action Policy 第 3 优先级在返回 OCR 唯一命中坐标前 MUST 按
  "可疑命中判定规则"表评估该命中；任一规则（R-A2/R-B/R-C）触发时 MUST NOT 返回坐标，
  使 resolve 落入既有 grounding 路径（`needs_grounding=True`，caller 逻辑不变）。
- **FR-002（候选提示传递）**: 可疑命中转 grounding 时，该 OCR 命中 MUST 经由既有
  `GroundingRequest.ocr_candidates` 通道对 grounder 可见。本 feature MUST NOT 修改
  runtime/ 与 models/（运行时现状已传全部 `screen.ocr_items`，结构上必然包含该命中）。
- **FR-003（精确匹配豁免，不可回归）**: 可比文本相等（长度 ≥ 2）且 confidence ≥ 阈值的
  唯一 OCR 命中 MUST 保持与现状逐字节一致的直接点击行为，MUST NOT 新增模型调用；
  resolve 第 1/2 步（keyboard/focus）与模板唯一命中路径 MUST 零改动。
- **FR-004（阈值配置化）**: R-B 阈值 MUST 在 agent 配置 `planning` 段以
  `ocr_direct_click_min_confidence`（float，默认 0.85，[0,1] 校验）声明，配置模型
  （`PlanningConfig`）含对应字段；`ActionPolicy` 构造参数默认值与配置默认值同源一致（0.85）。
- **FR-005（可观测性）**: 可疑命中转 grounding 的 PolicyResult MUST 携带结构化 suspicion
  数据（触发规则原因码列表 + 命中原文 + confidence + bbox），并 MUST 输出一条 INFO 日志
  说明"为什么本次未直接点击"；原因码 MUST 为通用证据语义词
  （`partial_text_overlap`/`low_confidence`/`short_text`/`truncated_ocr_read`），
  MUST NOT 含业务词汇。
- **FR-006（既有 grounding 防线不动）**: `_consistent_with_unique_ocr` 距离一致性校验、
  `overall_confidence_threshold`、`top1_top2_min_gap` 及 `_from_grounding`/
  `_executable_from_candidate` 的坐标计算 MUST 零改动。
- **FR-007（混合分支降级）**: 唯一 OCR 命中可疑且同屏存在唯一模板命中时，系统 MUST 选用
  模板 bbox 直接点击（不转 grounding、零新增模型调用）；OCR 可信时维持既有 confidence
  择优逻辑。
- **FR-008（业务无关性）**: 判定规则、可比文本归一化、原因码 MUST 完全基于通用文本/置信度/
  长度证据，MUST NOT 引入被测应用专用词汇（Constitution VI），并以至少两个互不相关 GUI
  场景词汇验证。

### Key Entities

- **OcrSuspicion（观测数据）**: `reasons: list[str]`（原因码）、`ocr_text`、
  `ocr_confidence`、`bbox`；仅存在于 PolicyResult 运行时对象与日志，不新增持久化实体。
- **PlanningConfig（配置）**: 新增 `planning.ocr_direct_click_min_confidence`
  （float，默认 0.85，[0,1]）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 复现 bb9f039e 形态的离线输入（非精确包含命中/低置信精确命中/单字符命中）
  100% 转 grounding（`needs_grounding=True`），不再直接点击残缺 bbox。
- **SC-002**: 精确高置信命中（长度 ≥ 2）的 PolicyResult 与改动前逐字段一致，新增模型调用
  数为 0。
- **SC-003**: 全部可疑转 grounding 的结果 100% 携带原因码与命中原文，可从 PolicyResult/
  日志直接回答"为什么没直接点"。
- **SC-004**: 既有测试套件（unit/fixtures/e2e）全部保持通过；keyboard/focus/模板路径与
  grounding 防线相关用例零修改仍绿。
- **SC-005**: 阈值经构造参数/配置调整后行为随之变化（可配置性验证）。

## Assumptions

- 运行时在 `needs_grounding=True` 时把全部 `screen.ocr_items` 传入
  `GroundingRequest.ocr_candidates` 的既有行为保持不变（本 feature 的 FR-002 依赖此现状；
  runtime/ 属并行冻结区，不在本 feature 内改动）。
- `ActionPolicy` 的运行时装配点（`runtime/agent_runtime.py` 构造处）被并行 feature 冻结：
  yaml 自定义阈值的调用点接线（1 个 kwarg）作为后续一行级任务遗留，配置模型与
  `ActionPolicy` 构造参数默认值双端同源（0.85），默认部署行为一致（与 011 R3 同型处理，
  见 plan.md Complexity Tracking）。
- Feature 013（safe-click-point）正在并行修改坐标计算表达式；本 feature 只决定"命中是否
  可信"，不触碰任何"点哪里"的表达式。
