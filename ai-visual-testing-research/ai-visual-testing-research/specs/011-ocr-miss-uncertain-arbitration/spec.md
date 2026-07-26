# Feature Specification: OCR 漏读弱否定证据仲裁（FR-010 语义修订）

**Feature Branch**: `011-ocr-miss-uncertain-arbitration`

**Created**: 2026-07-26

**Status**: Draft

**Input**: User description: "真实运行 bb9f039e / 25980277 中，点击实际成功、action_effect=expected_effect、
VLM visual_question 高置信回答 passed，但 OCR 把 `10,000` 读成 `10.000`、`単価` 漏识别导致
`text_appears` 确定性断言 failed，Feature 002 的 FR-010（deterministic-over-visual）把正确的视觉
passed 否决成步骤失败，引发无意义重试和假失败。需要按证据强弱重新定义确定性/视觉冲突仲裁规则。"

## 与 Feature 002 FR-010 的关系（语义修订声明）

本 feature 是对 `specs/002-action-effect-verification/spec.md` **FR-010** 的语义修订，不是推翻：

- **旧规则（002 FR-010）**：确定性业务断言与视觉模型结论冲突时，MUST 以确定性断言为准；
  视觉结论 MUST NOT 推翻已有明确结论的确定性断言。该规则把"`text_appears` 未命中"与
  "`text_disappears` 读到了不该存在的文本"同等对待，都视为"明确的确定性 failed"。
- **修订后规则（011 FR-010'）**：确定性证据按强弱分级。**强否定证据**（读到了坏东西型）
  维持旧规则的无条件覆盖权；**弱否定证据**（OCR 没读到型）单独构成的确定性 failed，在
  三条强肯定证据同时在场时（见 FR-002），MUST NOT 否决视觉结论，最终态为 `passed` 并带
  可审计标记。
- **修订理由**：`text_appears` 失败在语义上只证明"OCR 没有读到该文本"，不证明"画面上
  没有该文本"。真实运行中 OCR 对金额分隔符（`10,000`→`10.000`）和 CJK 字形（`単価` 漏识别）
  的漏读是高频、可复现的：此时"确定性"断言其实并不确定，它是一条**弱否定**证据。让弱否定
  无条件压过"像素级动作效果符合预期 + 高置信视觉确认"两条独立强肯定证据，会把真实成功
  判为失败，引发无意义重试、假失败与重试预算浪费——这与 002 引入 FR-010 的初衷（防止
  模型自证掩盖真实失败）无关，反而破坏了测试结果的可信度。
- **不变部分**：视觉结论仍然永远不能推翻强否定确定性证据；视觉低置信、动作效果不符合
  预期时，旧规则原样生效；`uncertain` 仍不得直接作为通过（overall_design.md §9.9）。

## 证据强弱分类（规范性定义）

| 证据 | 类别 | 强度 | 语义 |
|---|---|---|---|
| `text_appears` 未命中（failed） | 确定性·否定 | **弱否定** | 只证明 OCR 没读到，不证明画面上没有（OCR 漏读/误读可能性大） |
| `text_disappears` 失败 | 确定性·否定 | **强否定** | OCR 明确读到了不该存在的文本（读到了坏东西） |
| `template_appears` / `template_disappears` 失败 | 确定性·否定 | **强否定** | 模板匹配为像素级确定性手段，漏配概率远低于 OCR 文本重建 |
| 错误弹窗检测命中（`action_effect=unexpected_effect`） | 确定性·否定 | **强否定** | 明确检测到错误画面特征 |
| `action_effect=no_effect`（画面无变化门禁） | 确定性·否定 | **强否定** | 像素级证明动作没有产生任何效果 |
| `action_effect=expected_effect` | 确定性·肯定 | 强肯定 | 像素级证明画面按预期方向发生了变化 |
| `text_appears` 命中、`text_disappears` 通过、模板断言通过 | 确定性·肯定 | 强肯定 | OCR/模板正向读到了期望内容 |
| `visual_question` 回答 `passed` 且 confidence ≥ 阈值（默认 0.8） | 模型·肯定 | 高置信肯定 | 仅在与其他强肯定证据合取时获得仲裁参与权，单独仍不能定通过 |
| `visual_question` 回答（confidence < 阈值，或 failed/uncertain） | 模型 | 弱 | 维持 002 规则，不参与本仲裁 |
| `screen_changed` / `region_changed` | 弱证据 | 弱 | 沿用 002 弱断言语义，与本仲裁无关（不属于"确定性业务断言"桶） |

> 注：分类按**断言类型**静态判定，不逐次猜测 OCR 是否真的漏读——这保证了仲裁规则本身
> 仍是确定性的、可复现的（Constitution I）。

## User Scenarios & Testing *(mandatory)*

### User Story 1 - OCR 漏读不再制造假失败 (Priority: P1)

测试工程师声明了一个步骤：点击后期望画面出现 `10,000`（`text_appears`）并且视觉问题
"合计金额是否为 10,000？"回答通过。真实运行中点击成功、画面按预期变化
（`action_effect=expected_effect`）、视觉模型以 0.9 置信度回答 passed，但 OCR 把
`10,000` 读成 `10.000` 导致 `text_appears` failed。工程师期望该步骤判 `passed`，
且报告里仍能看到 OCR 未命中的记录以便排查。

**Why this priority**: 这是本 feature 的直接动因（真实运行 bb9f039e / 25980277 的假失败
与无意义重试），不解决则含金额/CJK 文本断言的用例持续产生假失败。

**Independent Test**: 离线构造"text_appears 未命中 + visual_question 高置信 passed +
expected_effect"的解析输入，断言最终态为 `passed` 且 reason 含
`weak_ocr_miss_overridden_by_visual`、`failed_conditions` 保留 OCR 未命中记录。

**Acceptance Scenarios**:

1. **Given** 步骤断言含 `text_appears`（未命中）与 `visual_question`（passed，confidence ≥ 0.8），
   **When** `action_effect=expected_effect` 时解析步骤结果，
   **Then** 最终 `status=passed`，reason 含 `weak_ocr_miss_overridden_by_visual` 标记，
   `failed_conditions` 中保留该 `text_appears` 条目供报告展示。
2. **Given** 同上但 OCR 未命中的文本有多条（全部为 `text_appears`），
   **When** 解析，**Then** 同样判 `passed` 并保留全部未命中记录。
3. **Given** 同一规则输入但来自两个互不相关的 GUI 场景词汇（表单保存流 / 图标菜单流），
   **When** 解析，**Then** 行为一致（Constitution VI 跨场景验证）。

---

### User Story 2 - 强否定证据维持覆盖权 (Priority: P1)

测试工程师声明了"错误提示消失"（`text_disappears`）或模板类断言。OCR 明确读到了不该
存在的文本、或模板断言失败时，即使视觉模型高置信回答 passed，步骤仍必须失败——
"读到了坏东西"是强否定证据，视觉结论永远不能推翻它。

**Why this priority**: 这是修订的安全底线；没有它，修订会把 002 FR-010 防止的
"模型自证掩盖真实失败"重新引入。

**Independent Test**: 离线构造"text_disappears failed（或 template 断言 failed）+
visual_question 高置信 passed + expected_effect"，断言最终态仍为 `failed`。

**Acceptance Scenarios**:

1. **Given** `text_disappears` failed + `visual_question` passed（confidence ≥ 0.8）+
   `expected_effect`，**When** 解析，**Then** `status=failed`（旧规则维持）。
2. **Given** `template_appears` failed + `visual_question` passed（confidence ≥ 0.8）+
   `expected_effect`，**When** 解析，**Then** `status=failed`。
3. **Given** 失败集合中同时含弱否定（`text_appears` 未命中）与强否定（`text_disappears`
   failed），**When** 解析，**Then** `status=failed`——只要存在任何强否定，仲裁不启动。

---

### User Story 3 - 低置信视觉与非预期动作效果维持旧规则 (Priority: P2)

视觉模型回答 passed 但置信度低于阈值，或动作效果不是 `expected_effect`
（`no_effect` / `unexpected_effect` / `effect_uncertain`）时，弱否定仲裁不得启动，
维持 002 的 deterministic-over-visual 行为。

**Why this priority**: 三条件合取是本修订可被接受的前提；任何一条缺失都会退化成
"模型说了算"，违反 Constitution I/IV。

**Independent Test**: 分别构造 confidence=0.5、`action_effect=no_effect`、
`action_effect=unexpected_effect` 的输入，断言均维持 `failed`。

**Acceptance Scenarios**:

1. **Given** `text_appears` 未命中 + `visual_question` passed（confidence < 0.8）+
   `expected_effect`，**When** 解析，**Then** `status=failed`。
2. **Given** `text_appears` 未命中 + `visual_question` passed（confidence ≥ 0.8）+
   `action_effect=no_effect`，**When** 解析，**Then** `status=failed`（并保留 no_effect
   门禁语义，e2e scenario 13 行为不回退）。
3. **Given** `action_effect=unexpected_effect`（错误弹窗命中），**When** 解析，
   **Then** 步骤不得判 `passed`（e2e scenario 11 语义不回退）。
4. **Given** 阈值在配置中被调整（如 0.9），**When** confidence=0.85 的视觉 passed 参与仲裁，
   **Then** 仲裁不启动，维持旧规则。

---

### Edge Cases

- 断言集中没有 `visual_question` 条件（纯 `text_appears` failed）：无视觉肯定证据，
  仲裁不启动，维持 `failed`（可被既有 escalation 路径处理）。
- `visual_question` 的 value 为空：无法复核确认，仲裁不启动。
- 多个 `visual_question` 条件：全部为 passed 才视为"视觉侧 passed"；置信复核使用第一个
  非空问题（一次复核调用上限，见 FR-006）。
- 复核确认调用失败（模型异常/超时）：fail-safe，仲裁不启动，维持旧规则 `failed`。
- 复核确认回答与初次 `visual_question` 不一致（failed/uncertain 或低置信）：仲裁不启动。
- `operator: any` 且视觉 passed：聚合本就为 passed；旧 FR-010 会将其强制覆盖为 failed，
  修订后满足三条件时保留 passed，不满足时维持旧覆盖行为。
- 弱断言-only 步骤（仅 `screen_changed`）：不属于本仲裁范围，`uncertain` +
  `weak_assertion_warning` 语义不变（e2e scenario 12 不回退）。
- `uncertain` 最终态仍不得作为通过（overall_design.md §9.9）；本仲裁只在
  "确定性 failed vs 视觉 passed"冲突时介入，从不把 `uncertain` 改写为 `passed`。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001（证据分级）**: 系统 MUST 按上文"证据强弱分类"表对确定性否定证据分级：
  `text_appears` 未命中为弱否定；`text_disappears` 失败、模板类断言失败、错误弹窗检测
  命中（`unexpected_effect`）、画面无变化门禁（`no_effect`）为强否定。分级按断言类型
  静态判定，MUST NOT 依赖运行时对"OCR 是否真的漏读"的猜测。
- **FR-002（仲裁规则，修订 002 FR-010）**: 当且仅当以下三条同时成立时，确定性侧的
  failed MUST NOT 使步骤最终判 `failed`，最终态 MUST 为 `passed`：
  1. 确定性业务断言侧的全部失败条目均为弱否定（`text_appears` 未命中），且不存在
     任何强否定失败条目；
  2. 步骤声明的 `visual_question` 断言回答 `passed`，且经置信复核 confidence ≥ 可配置
     阈值（默认 0.8）；
  3. `action_effect.status == expected_effect`。
- **FR-003（可审计标记）**: 按 FR-002 判 `passed` 的结果 MUST 在 reason 中携带
  `weak_ocr_miss_overridden_by_visual` 标记（含复核置信度与阈值），并 MUST 在
  `failed_conditions` 中保留被覆盖的弱否定条目原文，供报告展示与事后排查。
- **FR-004（强否定覆盖权保底）**: 失败条目中存在任何强否定时，视觉结论 MUST NOT 推翻
  确定性 failed（002 FR-010 原语义原样生效）。
- **FR-005（旧规则回退条件）**: 视觉回答非 `passed`、置信度低于阈值、复核调用失败、
  断言集中无可复核的 `visual_question`、或 `action_effect.status != expected_effect`
  时，系统 MUST 维持 002 FR-010 行为。
- **FR-006（复核确认与调用预算）**: 启动仲裁前系统 MUST 以步骤声明的 `visual_question`
  原问题做一次带置信度的视觉复核确认；每次步骤结果解析 MUST 至多新增一次视觉复核调用，
  且该调用只发生在"弱否定-only failed + 视觉侧 passed + expected_effect"的候选场景。
- **FR-007（阈值配置化）**: 置信阈值 MUST 在 agent 配置的 `verification` 段以
  `visual_override_confidence_threshold`（默认 0.8，取值 [0,1]）声明，并有对应的
  配置模型校验。
- **FR-008（不回退保底）**: 本修订 MUST NOT 改变以下既有语义：`uncertain` 不得直接作为
  通过（overall_design.md §9.9）；错误弹窗步骤不得判 `passed`（e2e scenario 11）；
  弱断言-only 步骤维持 `uncertain` + 警告（e2e scenario 12）；`no_effect` 时业务断言
  匹配不被信任（e2e scenario 13 / feature 004 回归门禁）。
- **FR-009（业务无关性）**: 分级与仲裁逻辑 MUST 完全基于通用断言类型与通用证据状态，
  MUST NOT 引入任何被测应用/行业专用字段或关键词（Constitution VI），并 MUST 以至少
  两个互不相关的 GUI 场景词汇验证。

### Key Entities

- **证据强弱分级（EvidenceStrength）**: 断言类型 → {弱否定, 强否定} 的静态映射；
  仅覆盖确定性否定证据。
- **仲裁结果标记**: `weak_ocr_miss_overridden_by_visual` reason 标记 + 保留的
  `failed_conditions` 条目；不新增持久化实体。
- **VerificationConfig（配置）**: `verification.visual_override_confidence_threshold`
  （float，默认 0.8，[0,1]）。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 复现 bb9f039e / 25980277 形态的离线输入（OCR 漏读 + 高置信视觉 passed +
  expected_effect）时，步骤判定为 `passed`，不再触发该形态下的重试与假失败。
- **SC-002**: 全部强否定组合用例（text_disappears/模板失败/错误弹窗/no_effect）100%
  维持 `failed`/非 `passed`，与 002 行为逐例一致。
- **SC-003**: 低置信视觉、非 expected_effect、无 visual_question、复核失败四类回退场景
  100% 维持 002 行为。
- **SC-004**: 按 FR-002 判 `passed` 的结果 100% 携带可审计标记且保留被覆盖的失败条目。
- **SC-005**: 每次步骤结果解析新增的模型调用 ≤ 1 次，且仅发生在仲裁候选场景。
- **SC-006**: 既有测试套件（unit/fixtures/e2e，含 scenario 11/12/13）全部保持通过。

## 关键决策记录（全自动流程，代替 /speckit-clarify）

### 决策 1：最终态选 `passed`（带标记），不选 `uncertain`（走 escalation）

**选择**：三条件成立时最终态为 `passed`，reason 携带 `weak_ocr_miss_overridden_by_visual`
标记并保留 `failed_conditions`。

**理由**：

1. **选 `uncertain` 无法解决本 feature 要解决的问题**。按 overall_design.md §9.9 与
   Constitution IV，`uncertain` 不得作为通过，必须触发更强验证/复检/恢复流程——而 OCR
   对 `10,000`→`10.000`、`単価` 的漏读是确定性可复现的，重观察后再次 OCR 仍会漏读，
   escalation 的确定性复检注定再次 failed/uncertain，步骤最终仍以失败收场：假失败与
   无意义重试原样保留，只是多烧了模型与重试预算。
2. **`passed` 判定仍由代码状态机做出，不违反 Constitution I/IV**。视觉模型没有"自证
   通过"：它只是回答测试用例里声明的业务问题（`visual_question` 本身就是 002 认可的
   一等业务断言，FR-009/002 兼容），最终判定由确定性规则对三条独立的、操作后重新采集的
   证据（像素级 action_effect、高置信视觉复核、失败证据全部属于已知高漏读类别）做合取
   得出。这与 002 FR-010 防止的"模型结论单方面推翻确定性结论"不同——这里被推翻的
   不是"确定性事实"，而是一条已被分类为弱否定的证据。
3. **可审计性不受损**。标记 + 保留 failed_conditions 让报告能明确展示"OCR 未命中但被
   视觉覆盖"，人工复核入口仍在。
4. **风险受控**。强否定在场、低置信、非 expected_effect 时全部回退旧规则；阈值可配置，
   保守部署可调高阈值收紧仲裁。

### 决策 2：置信度通过一次复核确认调用获取

002 的既有实现中 `visual_question` 的逐条置信度未随验证结果结构化透出，而透出链路
（验证引擎的 visual_question 调用链）被并行 feature 冻结。仲裁改为在候选场景下用原
`visual_question` 问题做一次带置信度的复核确认调用：既拿到权威置信度，又相当于在推翻
确定性 failed 前做了第二次独立视觉确认，且调用次数有硬上限（FR-006，与 002 契约
"每次解析至多一次可选视觉调用"同型）。复核与初判不一致时 fail-safe 维持旧规则。

### 决策 3：`template_*` 失败归为强否定

模板匹配是像素级确定性手段：`template_appears` 失败意味着在阈值内找不到基线像素块，
其假阴率远低于 OCR 文本重建（后者要经历检测/识别/后处理三层漏读面）。为保持仲裁规则
简单、保守，模板类失败一律按强否定处理（用户需求亦如此指定）。

### 决策 4：阈值放在 `verification` 配置段（新建）

该阈值属于验证仲裁语义，与 `grounding`（定位置信）无关；新建 `verification` 段避免
语义混淆，后续验证类阈值可归并于此。

## Assumptions

- OCR 漏读（假阴）在金额分隔符与 CJK 字形上高频出现，而 OCR"读到不存在的目标文本"
  （在 `text_disappears` 场景下的假阳）概率显著更低——这是弱/强否定分类的经验前提，
  与 002 引入的 OCR confusable/金额位数容错实现互补。
- `visual_question` 是测试用例中声明的一等业务断言；其回答 passed 表示被声明的业务
  结果在画面上成立。
- 阈值默认 0.8 覆盖真实运行观察到的高置信正确回答（0.85~0.95 区间），同时排除模型
  低把握的敷衍回答。
- 运行时对阈值配置的注入点（runtime 装配层）被并行 feature 冻结，本 feature 内配置
  模型与解析器默认值保持同源一致（均为 0.8）；自定义 yaml 覆盖值的运行时接线作为
  后续一行级接线任务记录（见 plan.md Complexity Tracking）。
