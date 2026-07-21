# Phase 0 Research: 稳定动作身份与坐标空间定位纠正

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

本阶段的目标是在进入 Phase 1 设计前，把 spec.md 中隐含的实现层决策显式化。本 feature
不引入任何新的第三方依赖——001/002 已交付的 `vnc_agent` 包（Python 3.12、Pydantic v2、
现有 `execution/`、`models/`、`planning/`、`reporting/` 子包）完全够用。每条决策均以
阅读既有源码（`src/vnc_agent/...`）与真实事故报告
（`vnc_agent/artifacts/runs/cefe36a9-f5c3-4622-9998-ef06690a5ab6/report.json`）为依据。

## 1. 定位现有 RepeatGuard 的具体缺陷（对照真实事故报告逐行核实）

- **现状**：`execution/repeat_guard.py::actions_semantically_equivalent()` 当前实现：

  ```python
  def actions_semantically_equivalent(a, b):
      if a.action_type != b.action_type: return False
      if _target_key(a) and _target_key(a) == _target_key(b): return True
      if _normalize(a.intent) and _normalize(a.intent) == _normalize(b.intent): return True
      return False
  ```

  `_target_key()` 是 `role + text + description` 拼接后的规范化字符串**完全相等**比较，
  **完全没有使用 `SemanticAction.action_id`**。对照真实事故报告 `report.json`：三轮迭代
  的 `semantic_action.action_id` 全程为 `"act-1"`（Planner 确实保持了稳定 ID），但
  `target.description`/`intent` 逐轮改写，导致 `_target_key`/`intent` 均不相等 →
  `actions_semantically_equivalent()` 返回 `False` → `RepeatGuard.check()` 归类为
  `"different_action"` → `allowed=True` → 第二、三轮各执行了一次本不该发生的鼠标点击。
  这是本 feature 需要修复的第一个、也是最直接的根因，且证实"Planner 其实提供了可用的
  强信号（`action_id`），只是现有代码没有使用它"。
- **Decision**：不新增 RepeatGuard 的调用位置——`runtime/agent_runtime.py::run_action_iteration()`
  中 `guard = self.repeat_guard.check(sa, previous_iteration)` 已经发生在
  `RESOLVING_ACTION`（ActionPolicy/Grounding）与 `EXECUTING`（Executor）**之前**（紧跟
  PLANNING 阶段之后），这正是 spec 计划要点 #2"RepeatGuard 在 Grounding 和 Executor 之前
  完成判断"的现状——**该约束已经满足，无需改动调用时机**，只需要重写 `RepeatGuard` 内部
  的身份匹配算法本身（见 §2）。
- **Rationale**：把"发现问题"与"给出修复"分开记录，避免 Phase 1 设计误以为需要移动
  `RepeatGuard.check()` 的调用点——真正需要动的只是它如何判断"是否为同一动作"。

## 2. CanonicalActionIdentity 的数据模型与计算位置

- **Decision**：新增 `domain/action_identity.py`：

  ```python
  class CanonicalActionIdentity(BaseModel):
      step_id: str
      action_type: ActionType
      action_id: str | None          # 本轮/上一轮各自携带的 action_id（可为空）
      normalized_target: str          # 优先取 target.text（OCR 容忍归一化），
                                       # 缺失时退化为 normalized(intent)
  ```

  新增 `execution/action_identity.py::compute_identity(step_id, action) ->
  CanonicalActionIdentity` 纯函数；新增
  `execution/action_identity.py::identity_match(prev, curr) -> Literal["action_id_match",
  "normalized_target_match", "no_action_id_ambiguous"]`（`"different_step"` 另计，
  见 §3）——**做三件事**：(a) 当 `prev.action_id` 与 `curr.action_id` 均非空、相等，
  **且 `prev.action_type == curr.action_type`** 时返回 `"action_id_match"`（FR-002/007，
  决定性强证据，不比较 `normalized_target`/自由文本；`action_type` 不同则不命中本分支，
  见下方 FR-007 修正）；(b) `action_type` 相同但 `action_id` 缺失/不相等时，若
  `normalized_target` 经 OCR 容忍比较判定为同一目标，返回 `"normalized_target_match"`
  （FR-005，见下方修正）；(c) 否则返回 `"no_action_id_ambiguous"`，交给 §4 的步骤意图
  一致性检查处理（FR-003/004）。

  **修正（源自 `/speckit-analyze` 发现的 CRITICAL/HIGH 缺口，2026-07-21 补充）**：
  初版设计中 `identity_match()` 只比较 `action_id`，完全没有校验 `action_type`——
  这意味着如果 Planner 出现 bug、把同一个 `action_id` 复用在两个不同 `action_type`
  的动作上（例如先 `click` 后 `type_text`），系统会错误地把它们判定为
  `"action_id_match"` 并按"同一动作"处理，直接违反 FR-007"MUST NOT 过度宽松地将
  两个真正不同的业务动作错误合并"。现已修正为 `action_type` 相等是
  `"action_id_match"` 的必要前提，`action_type` 不同时下沉到
  `evaluate_target_consistency()`（§4），该函数新增一条前置规则：`action_type`
  不同时无条件判定为 `"dangerous_drift"`。
  同时，初版设计从未真正落实 FR-005（OCR 噪声容忍的规范化目标识别，如"レジ袋"被
  识别为"ジ袋"仍应视为同一目标）——`normalized_target` 字段虽然被计算，但没有
  任何函数实际比较过它。现已新增 `"normalized_target_match"` 作为
  `identity_match()` 的第三种返回值，在 `action_id` 缺失/不相等但
  `action_type`/`normalized_target` 均判定一致时命中，证据强度弱于
  `"action_id_match"` 但仍按同一套 no_effect-only 重试许可规则处理（`reason` 加
  `_normalized_target` 后缀以区分审计记录，见 §5 修正）。
- **Rationale**：把"计算身份"（纯数据转换）与"判断是否允许执行"（`RepeatGuard.check()`
  的编排职责）拆成两个文件，`CanonicalActionIdentity` 作为可独立单测、可写入报告
  （FR-025）的值对象；`identity_match()` 只表达 FR-001/002 两条规则本身，不涉及
  fail-safe 或漂移判断，保持每个函数职责单一、可独立测试。
- **Alternatives considered**：
  - 把身份计算内联在 `RepeatGuard.check()` 里，不单独建模——`CanonicalActionIdentity`
    需要出现在报告审计字段（FR-025）里，必须是一个可序列化的独立值对象，不能只是
    `RepeatGuard` 内部的临时变量，拒绝内联。
  - 用一个哈希值代替结构化对象作为"身份"——哈希值无法在报告里展示"到底因为什么匹配/
    不匹配"（FR-025 要求判定理由可审计），拒绝。

## 3. 步骤边界隔离：确认 FR-001 无需新代码即可满足

- **现状核实**：`runtime/agent_runtime.py::run()` 每次 `ctx.advance_step()` 后都会
  开始一个新的 `StepController`/`ctx.current_step_record`；`run_action_iteration()` 中
  `previous_iteration = ctx.current_step_record.iterations[-2]` 永远只从**当前**步骤的
  `StepRecord.iterations` 取值，`RepeatGuard` 本身也是无状态的（不持有跨步骤的成员
  变量）。也就是说，**两个不同测试步骤之间永远不会有一个 `previous_iteration` 跨越
  步骤边界传给 `RepeatGuard.check()`**——spec 计划要点 #4"真正不同步骤的动作不被错误
  阻止"在现有架构下已经成立。
- **Decision**：`CanonicalActionIdentity.step_id` 字段与 §2 `identity_match()` 中的
  步骤边界判断仍然保留（不因"现状已经安全"就省略）——一是作为显式的防御性正确性保证，
  避免未来任何重构（如引入并行步骤调度）意外破坏这一假设；二是 FR-025 要求报告能审计
  "所属测试步骤"，必须有一个显式字段承载这一信息，不能仅依赖调用时机的隐式保证。
- **Rationale**：区分"现状已经正确的部分"和"需要新增代码的部分"，避免过度设计；同时
  不因为"现在恰好安全"就删除本应显式声明的不变量。

## 4. 步骤意图一致性验证与危险目标漂移检测

- **Decision**：新增 `execution/target_consistency.py`：

  ```python
  ConsistencyOutcome = Literal[
      "legitimate_micro_action",   # 独立目的、符合 step intent 的合法新目标（FR-003）
      "dangerous_drift",           # 危险漂移（FR-008，两种方向）
      "ambiguous",                 # 无法可靠判断（触发 FR-004 fail-safe）
  ]

  def evaluate_target_consistency(
      step_intent: str,
      previous_action: SemanticAction | None,
      proposed_action: SemanticAction,
  ) -> ConsistencyOutcome: ...
  ```

  判定规则（仅在 §2 `identity_match()` 返回 `"no_action_id_ambiguous"` 时被调用）：
  1. 若 `previous_action is None` → `"legitimate_micro_action"`（步骤内第一轮，不存在
     "漂移自谁"的问题）。
  2. **若 `previous_action.action_type != proposed_action.action_type` → 无条件
     `"dangerous_drift"`**（FR-007 修正，见 §2 同步说明），优先于以下角色/关键词
     判断——`action_type` 不同本身就是决定性的危险信号，不需要再看角色/关键词。
  3. 判断 `previous_action.target` 的角色类别（可交互控件 vs 非交互结果展示元素，
     依据 `target.role` 字段与 `target.text`/`description` 中的常见结果展示关键词，
     如"行/row/列表/list/已添加/合計"等，作为启发式信号，见 Assumptions）与
     `proposed_action.target` 的角色类别：
     - 若 `previous_action` 指向可交互控件、`proposed_action` 指向非交互结果展示
       元素 → `"dangerous_drift"`（FR-008 第一种方向）。
     - 若两者都指向可交互控件，但 `proposed_action` 的目标文字/描述与 `step_intent`
       的核心关键词重合度明显低于 `previous_action` 与 `step_intent` 的重合度（简单
       关键词重叠度量，非 NLP 模型）→ `"dangerous_drift"`（FR-008 第二种方向：控件→
       另一个不符合 intent 的控件）。
     - 若 `proposed_action` 与 `step_intent` 重合、且与 `previous_action` 指向不同的
       独立交互目的（如"关闭弹窗"类关键词）→ `"legitimate_micro_action"`（FR-003 的
       合法前置微动作分支）。
     - 以上均不满足（信号不足以分类）→ `"ambiguous"`。
- **Rationale**：直接落实 FR-003/FR-008；采用关键词重叠这一确定性、可测试的启发式
  而非引入 NLP/向量相似度模型，符合宪法"确定性手段优先"的资源约束，且 spec Assumptions
  已明确"具体判别规则由实现阶段结合真实场景数据给出，不在规格中固化算法细节"，把关键词
  信号列表设计为可配置项（`config/agent.yaml` 新增
  `planning.result_display_keywords`/`planning.dismissal_keywords`），方便后续依据更多
  真实场景调整，不需要改代码。
- **Alternatives considered**：
  - 调用视觉模型判断"这是不是同一类控件"——违反宪法"确定性手段优先"路由原则，且
    `evaluate_target_consistency()` 处于 RepeatGuard 决策链路中，一旦引入模型调用，
    RepeatGuard 就不再是"是否允许执行"的纯确定性快速判断，拒绝。
  - 把该逻辑放进 `planning/action_classification.py`（002 已有的 `action_kind` 分类
    模块）——`action_classification.py` 职责是"这个动作是否幂等"，与"这个目标是否漂移"
    是两个不同维度的判断，混合会让该模块承担过多职责，拒绝合并。

## 5. RepeatGuard.check() 的组合逻辑重写

- **Decision**：`RepeatGuard.check()` 重写为：

  ```text
  1. curr_id = compute_identity(step_id, proposed_action)
  2. if previous_iteration is None: return allowed=True, reason="first_attempt"
  3. prev_id = compute_identity(step_id, previous_iteration.semantic_action)
  4. kind = classify_action_kind(proposed_action)
  5. if kind == "idempotent": return allowed=True, reason="idempotent_action"
  6. match = identity_match(prev_id, curr_id)
  7. if match == "action_id_match":
       同一逻辑动作 → 走 FR-006 的 no_effect-only 重试许可规则（复用 002 既有分支）
  8. elif match == "normalized_target_match":
       同一逻辑动作（OCR 容忍匹配，FR-005）→ 走同一套 no_effect-only 重试许可规则，
       但 reason 取对应的 "*_normalized_target" 后缀变体，与上一分支的证据来源区分
  9. else (no_action_id_ambiguous):
       outcome = evaluate_target_consistency(step.intent, previous_iteration.semantic_action, proposed_action)
       if outcome == "dangerous_drift": return allowed=False, reason="dangerous_drift"
       if outcome == "legitimate_micro_action": return allowed=True, reason="legitimate_micro_action"
       if outcome == "ambiguous": 走 FR-004 fail-safe（等同于"视为同一逻辑动作"分支）
  ```

  `RepeatGuardDecision.reason` 的取值集合从 002 的
  `["first_attempt","different_action","idempotent_action","no_effect_confirmed",
  "blocked_effect_pending","blocked_uncertain"]` 扩展为新增
  `"dangerous_drift"`、`"legitimate_micro_action"`、`"ambiguous_fail_safe"`，以及
  `"no_effect_confirmed_normalized_target"`、
  `"blocked_effect_pending_normalized_target"`、
  `"blocked_uncertain_normalized_target"` 三个后缀变体（对应第 8 步的
  `"normalized_target_match"` 分支，FR-005 修正），
  **移除** `"different_action"` 这一在 002 中被证明会掩盖真实事故的宽松归类（不再有
  任何路径仅因文本不完全相等就返回该原因）。
- **Rationale**：直接落实 spec 计划要点 #3（相同 action_id 加措辞改写、目标漂移的
  处理规则）；`RepeatGuardDecision.reason` 移除 `"different_action"` 是刻意的——003
  的整个动机就是"文本不同不能再单独作为放行理由"，保留这个取值会让审计报告里出现
  "这次是因为文本不同才放行"这种误导性归因，必须替换为更精确的原因分类。
- **Alternatives considered**：
  - 保留 `"different_action"` 作为 `"ambiguous"` 分支判定后确实合法通过时的取值——
    与 `"legitimate_micro_action"` 语义重复且不如后者精确，拒绝保留旧名。

## 6. GroundingCandidate 的 coordinate_space 数据模型与一次性转换架构

- **现状**：`domain/grounding.py::GroundingCandidate.bbox` 目前是裸
  `tuple[int,int,int,int]`，注释写"in original VNC pixels"但没有任何字段或校验强制
  这一假设；`models/mimo_grounder.py` 的系统提示词硬编码"bbox 为图片内的像素坐标"，
  完全没有给模型声明 `normalized_1000` 的选项；`_apply_crop_and_cap()` 只做
  `crop_offset` 平移，不做任何坐标空间换算。对照真实事故报告，第二轮候选坐标
  `bbox=[251,402,405,459]`（分辨率 1024×1568）与第一轮实际点击位置 `y≈678` 相差
  极大，若将该 bbox 当作 0–1000 归一化坐标换算（`y: 402/1000*1568≈630`~
  `459/1000*1568≈720`），换算后的 y 区间恰好落在第一轮点击的 `y≈678` 附近——这是
  "模型可能返回了归一化坐标、系统却当像素坐标直接使用"这一假说的有力佐证，但由于
  历史响应本身没有留存 `coordinate_space` 字段，无法 100% 确证，故 spec 与本计划均
  将其列为"很可能的根因"而非已证实的唯一原因（见 spec.md User Story 3 "Why this
  priority"）。
- **Decision**：
  1. `domain/grounding.py::GroundingCandidate` 新增两个字段：
     `coordinate_space: Literal["pixel","normalized_1000"] | None = None`（候选声明的
     坐标空间，缺省 `None` 表示历史响应未声明）、
     `raw_bbox: tuple[int,int,int,int] | None = None`（换算前的原始候选坐标，仅用于
     报告审计，FR-026/036；`bbox` 字段本身**换算后**永远是原始 VNC 像素坐标，保持对
     下游 `ActionPolicy`/`Executor` 完全透明——它们不需要知道坐标空间概念）。
  2. 新增 `models/coordinate_space.py::resolve_pixel_bbox(raw_bbox, declared_space,
     resolution, *, siblings=()) -> tuple[int,int,int,int] | None`：纯函数，实现
     FR-013/014/015/017 的换算、边界与推断规则；返回 `None` 表示"拒绝该候选"。
  3. 该函数**只在一个调用点**被调用——`models/mimo_grounder.py::MimoGrounderClient.ground()`
     内，紧跟在 `_apply_crop_and_cap()`（现有的 crop_offset 平移）之后、`GroundingResult`
     返回给调用方之前；`StubGrounder`（离线测试用双）在构造固定 `GroundingResult` 时
     同样通过该函数产出 `bbox`，保证测试路径与生产路径共用同一个换算实现，不是各自
     重新实现一遍换算逻辑。这就是 FR-014"转换有且仅发生一次"的架构落地——不是靠一个
     运行时标志位去"检测是否已经换算过"，而是**从设计上只留一个换算调用点**，下游
     （`ActionPolicy`、`Executor`、`RepeatGuard`）自始至终只看到已经是像素坐标的
     `bbox`，物理上没有第二次换算的机会。
  4. `_GROUNDING_SYSTEM_PROMPT` 更新，要求模型为每个候选显式输出
     `"coordinate_space": "pixel" | "normalized_1000"` 字段，并说明两种坐标空间的
     含义（X/Y 轴独立归一化）。
  5. `models/response_parser.py::parse_grounding_response()` 不需要改动——
     `coordinate_space` 作为 `GroundingCandidate` 的可选字段，Pydantic 校验会自动
     从候选字典中提取该字段（若模型未提供则保持 `None`），现有的 `**c` 透传逻辑已经
     兼容。
- **Rationale**：直接落实 FR-012～017/031；把换算收敛到 Grounder 边界内的单一调用点，
  是让"只换算一次"从"文档承诺"变成"架构上不可能违反"的具体做法，比在多处加运行时
  断言更可靠；`raw_bbox`/`coordinate_space` 保留在 `GroundingCandidate` 上（而不是
  换算后丢弃）是为了满足 FR-026/036 的报告审计要求。
- **Alternatives considered**：
  - 在 `ActionPolicy`/`Executor` 侧做换算，让 `GroundingCandidate.bbox` 保持"原始、
    未换算"状态——意味着每一个消费 `GroundingCandidate` 的下游代码都必须记得先换算，
    任何一处遗漏都会重新引入本次事故的 bug 模式，拒绝——换算必须在生产者（Grounder）
    一侧一次性完成，消费者不应该、也不需要知道坐标空间这个概念。
  - 给 `GroundingCandidate` 加一个 `converted: bool` 运行时标志位，在多处调用换算函数
    前先检查该标志——这是用运行时状态模拟"只换算一次"，比"物理上只有一个调用点"更
    脆弱（标志位本身可能被遗忘设置/重置），拒绝。

## 7. 归一化坐标推断规则的实现（历史响应兼容）

- **Decision**：`resolve_pixel_bbox()` 内部按 spec FR-015 (a)(b) 两个条件实现：

  ```text
  candidates_to_try = [declared_space] if declared_space is not None else ["pixel", "normalized_1000"]
  for space in candidates_to_try:
      pixel_bbox = _convert(raw_bbox, space, resolution)
      valid = _bbox_fully_in_bounds(pixel_bbox, resolution)  # 闭区间 [0,1000] 已在 _convert 内处理
      consistent = _consistent_with_siblings(pixel_bbox, siblings)  # 与同响应内其它已声明候选/已知目标区域不矛盾
      record (space, valid and consistent)
  if declared_space is not None:
      return pixel_bbox if valid_and_consistent else None
  # declared_space is None（历史响应）：要求 pixel/normalized_1000 两种解释中恰好一个 valid_and_consistent
  passing = [r for r in results if r.ok]
  return passing[0].pixel_bbox if len(passing) == 1 else None
  ```

- **Rationale**：直接落实 spec FR-015 的 (a)(b) 两个条件，是一个纯粹、无副作用、
  完全离线可单测的函数，不依赖真实 Grounder 调用即可覆盖全部分支。
- **Alternatives considered**：
  - 用一个数值启发式阈值（如"数值都小于等于 1568 就默认按像素处理"）代替严格的
    双解释验证——会重新引入本次事故的问题模式（一个数值在两种空间下都"看似合理"时
    被随意采信），拒绝。

## 8. 执行前合理性校验（OCR / 分辨率 / 目标区域）

- **Decision**：`resolve_pixel_bbox()` 换算成功后，`ActionPolicy._from_grounding()`
  /`_executable_from_candidate()`（`planning/action_policy.py`）新增一层轻量交叉核对：
  若该轮 `SemanticAction.target.text` 非空且 `StructuredScreen.ocr_items` 中存在与之
  匹配的 OCR 锚点，换算后的候选中心点若与该 OCR 锚点中心相距过远（超出一个可配置的
  像素容差，默认取截图较短边的 10%），则视为"换算结果与已有 OCR 证据不一致"，按
  FR-016 拒绝该候选并转入恢复/重新定位，而不是直接点击一个与已知锚点明显不符的位置；
  该核对仅在存在唯一 OCR 锚点时触发，OCR 证据本身缺失或有歧义时不阻塞（避免过度
  拒绝合法但 OCR 未命中的候选）。
- **Rationale**：落实 spec 计划要点 #7（"使用 OCR、截图分辨率和目标区域进行执行前
  合理性验证；证据不充分时停止，不猜测"）；分辨率与目标区域的合理性校验已经由 §6/§7
  的换算与越界拒绝规则覆盖，本条只补充 OCR 交叉核对这一额外证据来源，且明确"证据
  不充分时不阻塞"（不产生新的误杀），只在"有明确矛盾证据"时才拒绝。
- **Alternatives considered**：
  - 把该核对做成强制项（OCR 锚点缺失也拒绝）——会让大量本来正常的候选（目标本就不是
    文字锚点，如纯图标按钮）被误杀，与 spec"不依赖固定 ROI、适应当前画面实际内容"的
    精神冲突，拒绝。

## 9. pos-buy-bag-checkout.yaml 的业务断言设计（依据真实事故报告的 OCR 证据）

- **现状**：真实事故报告第一轮 `action_effect.evidence.ocr_added` 包含
  `["1", "1点", "5月", "二1-", "内税10%", "单！", "商品登錄行<", "抿取消", "袋"]`——
  可见真实 OCR 引擎对该 POS 应用界面的识别噪声较大（"レジ袋"被识别为"袋"或丢字，
  "5円"很可能被误识别为"5月"，"取消"被识别为"抿取消"/"遥捉取消"）。
- **Decision**：`pos-buy-bag-checkout.yaml` 的"加入购物袋"步骤改为
  `verification_mode: business`，`expected.conditions` 使用 002/001 已支持的确定性
  断言类型组合（`operator: all`）：
  1. `text_appears, value: "1"` —— 件数数字，真实 OCR 已证明能稳定识别出裸数字"1"
     （比"1点"整体匹配更抗 OCR 噪声，`ocr_verifier` 的包含匹配足以覆盖）；
  2. `text_appears, value: "5"` —— 金额数字（同理，不强绑定"円"/"月"这类易被 OCR
     混淆的单位字符）；
  3. `text_appears, value: "袋"` —— レジ袋本身的稳定可识别子串（真实 OCR 输出中"袋"
     独立出现，比要求"レジ袋"整体匹配更鲁棒）；
  4. 保留一条 `screen_changed` 作为动作效果辅助证据（不单独构成通过依据，002
     FR-006 既有规则）。
  "小計"步骤同样升级为 `verification_mode: business`，`expected` 使用
  `text_appears`（依据小計确认画面的稳定文字，如"小計"/"合計"本身或确认按钮文字）
  断言进入了小計确认状态；`visual_question` 类型本次不使用——确定性文本断言已经
  足以覆盖 spec FR-019/020 的要求，符合宪法"语义验证仅作为最后手段"与 spec 计划
  要点 #8"只有确定性断言不足时才使用 visual_question"。
- **Rationale**：直接落实 FR-018～022；断言文本选择依据真实 OCR 输出而非理想化的
  完整日文字符串，是为了让新增的可信业务断言在真实环境下真正稳定可靠，而不是看起来
  严谨、实际因 OCR 噪声而永远无法匹配——这正是 002 事故里"看似合理的断言在真实环境
  下失效"这一类问题的直接前车之鉴。
- **Alternatives considered**：
  - 直接要求完整字符串"1点"/"5円"/"レジ袋"精确匹配——真实 report.json 已经证明这些
    完整字符串在 OCR 输出中并不总是完整出现，拒绝，改用已被真实证据验证过的稳定子串。
  - 使用 `visual_question` 断言"购物车是否显示 1 件商品、5 円"——违反宪法确定性
    手段优先原则，且现有确定性断言已经足够，拒绝在本次默认启用视觉模型验证。

## 10. 报告审计字段扩展的实现位置

- **Decision**：`reporting/json_report.py::build_report_dict()` 的每轮迭代记录新增
  `canonical_action_identity`（`CanonicalActionIdentity.model_dump()`，含
  `step_id`/`action_type`/`action_id`/`normalized_target`）与
  `coordinate_space_audit`（列表，每个被评估过的候选各一条：声明的坐标空间、
  `raw_bbox`、换算后 `bbox`、是否被采纳）两个字段；`RepeatGuardDecision.reason` 的
  新增取值（`dangerous_drift`/`legitimate_micro_action`/`ambiguous_fail_safe`）无需
  额外的报告改动——既有 `repeat_guard_decision` 字段已经会序列化新取值。
  `reporting/html_report.py` 的 Jinja2 模板新增一个可折叠的"Action Identity /
  Coordinate Space"证据区块，复用已有的 `<details>` 折叠展示模式（不新增 CSS 类，
  保持与 002 已交付的 `warn-weak`/`label-effect-only`/`label-trusted` 视觉语言一致）。
- **Rationale**：落实 spec 计划要点 #9 与 FR-025/026/036；沿用 002 已确立的
  "`build_report_dict()` 是 JSON/HTML 唯一数据源"的既有架构（`html_report.py` 复用
  `build_report_dict()` 输出，不重复实现字段提取逻辑）。
- **Alternatives considered**：
  - 只在 HTML 报告里展示、不写入 JSON 报告——JSON 报告是复核与未来自动化审计的
    机器可读来源，FR-025/026 的措辞（"报告记录 MUST 包含"）不区分 JSON/HTML，拒绝
    只做单一格式。

## 11. 离线回归测试的构造方式（延续 002 既有模式）

- **Decision**：延续 002 `research.md §9` 已建立的模式——不提交二进制截图资产，新增
  测试全部通过 `numpy`/`cv2`/直接构造 Pydantic 模型（`SemanticAction`、
  `TargetDescription`、`GroundingCandidate`）程序化构造固定场景；真实事故报告
  `report.json` 中的三轮 `semantic_action`/`grounding_candidates` 原始数据作为其中
  一组回归测试的**输入字面量**直接固化进测试代码（而非引用外部文件路径），使"用
  本次真实事故的原始数据重放，验证不再重复点击/不再误判坐标"这一回归测试不依赖任何
  运行时才能取得的外部产物。
- **Rationale**：与 002 既有测试基础设施保持一致；把真实事故的 `action_id`/目标描述/
  候选坐标字面量直接写进测试断言，使回归测试具备"如果这段特定历史数据重新出现，必须
  产生正确结果"这一最强的可信度，不依赖对该数据的抽象重述。
- **Alternatives considered**：
  - 引用 `report.json` 文件路径，测试运行时读取——引入对仓库外部产物目录
    （`artifacts/runs/...`，通常不提交或会被后续运行覆盖）的运行时依赖，脆弱，拒绝；
    改为把所需的具体字段值复制为测试代码内的字面量。

## 12. FR-036/FR-038/SC-012/SC-013 起始状态门禁与动作审计的实现方式

- **背景（源自 `/speckit-analyze` 发现的 HIGH 缺口，2026-07-21 补充）**：初版
  plan.md/tasks.md 完全没有为 FR-036（真实 VNC 报告 MUST 额外包含人工前置确认记录、
  确认时间戳、前置截图引用、程序实际观察到的起始画面结果、按类别分类的动作执行次数
  统计）与 SC-012（这些统计必须可直接从报告读出）安排任何实现任务——初版报告任务
  只覆盖了 FR-025/026 的 `canonical_action_identity`/`coordinate_space_audit`，
  初版人工真实 VNC 验收任务只是**使用**这些字段做核对，从未有任务
  真正**构建**它们，导致该任务实际执行时会发现报告里根本没有这些字段可核对。
- **Decision**：
  1. `vnc-agent run` 新增 `--confirm-start-state`/`--confirmed-cart-items`/
     `--confirmed-cart-amount`/`--confirmed-screenshot` 四个参数（`api/cli.py`）。CLI
     校验参数组后，将 `HumanStartStateConfirmation` 直接写入
     `RunContext.test_run.human_start_state_confirmation`；不把只存在于 `RunContext`
     的临时属性交给只接收 `TestRun` 的报告构建器，避免数据流断裂。
  2. 新增 `verification/business_resolver.py::extract_cart_state(screen) ->
     ObservedStartState`，复用 FR-019 的确定性 OCR 匹配。真实 VNC 验收运行完成首次
     Observe/Understand 后、进入第一个 PLANNING/RESOLVING_ACTION 前，运行时把结果写入
     `TestRun.observed_start_state`，并与人工确认自动比较。任一值为 `None`、不相等或
     证据冲突均写入 `StartStatePrecondition(status="failed")`，将运行置为 failed 并
     直接进入报告记录；不得生成 `ExecutableAction`。两项完全一致才写入 `passed` 并继续。
  3. 新增 typed `ReportingConfig.category_keywords` 并挂入 `AgentConfig.reporting`；
     `config/agent.yaml` 提供 `add_to_bag`/`subtotal`/`payment`/`clear_or_reset` 四类默认值。
     配置模型与 YAML 必须同时更新，禁止仅写 YAML 后被 Pydantic 忽略。
  4. `build_report_dict()` 从 `TestRun` 直接读取人工确认、观察结果和前置判定；遍历全部
     `ActionIteration` 时，仅将 `execution_result is not None and execution_result.success`
     （001 定义为“输入事件已发送”）的迭代加入 `executed_action_log` 与
     `action_category_counts`。被 RepeatGuard/ActionPolicy 拦截的提案继续保留在逐轮
     `semantic_action`/`repeat_guard_decision` 中，但不得增加任何执行计数。
  5. 新增运行级字段的完整定义与来源见 data-model.md §8b；JSON/HTML 继续共用同一份
     `build_report_dict()` 数据。
- **Rationale**：与 §10 已确立的"`canonical_action_identity`/`coordinate_space_audit`
  是逐轮字段"不同，FR-036 明确要求的是"完整动作执行清单与按类别分类的执行次数
  统计"——这是**跨轮次的运行级聚合**，必须单独设计聚合口径（类别关键词表、优先级
  规则），不能简单复用逐轮字段的序列化方式；人工确认记录必须通过 CLI 参数在运行
  开始前显式传入，不能从截图或运行日志里事后反推，否则"人工确认"这一步就形同虚设；
  `TestRun` 是运行与报告之间的稳定数据边界，人工确认和首帧观察都落在该对象上，避免
  `RunContext` 临时状态无法传入 `build_report_dict(TestRun)`。执行统计必须以
  `ExecutionResult.success` 为门槛，否则被安全组件拦截的危险提案会被误计为真实点击。
- **Alternatives considered**：
  - 让人工在验收记录里手写这些统计数字，不新增代码——违反 SC-012"均可直接从
    报告的分类统计字段读出，无需复核原始日志或重新运行"的明确措辞，拒绝。
  - 复用 `--dry-run`/交互式终端输入采集人工确认，而非显式 CLI 参数——交互式输入
    在自动化/脚本化的验收流程中不可复现、难以留痕，显式参数更符合"该次确认的
    时间戳"必须被记录这一 FR-036 要求（参数传入的时刻即确认发生的时刻，无需额外
    的交互式采集环节），拒绝交互式方案。

## 13. FR-037 恢复策略显式配置与 Constitution 门禁

- **Decision**：扩展 `config.py::RecoveryPolicy`，保留 `max_retries`、`cooldown_ms` 并
  移除其模型默认值，新增四个同样**无默认值**的必填布尔字段：`consumes_global_retry_budget`、
  `allows_action_path_change`、`requires_strong_model`、`requires_human_confirmation`。
  六个字段全部为无默认值的必填项；`config/agent.yaml` 的每个恢复策略必须逐项填写；缺任一字段时配置加载失败，
  不允许 Pydantic 默认值掩盖遗漏。`dangerous_drift`、`ambiguous_fail_safe` 与坐标空间拒绝
  继续映射到既有失败分类，但所选策略必须通过同一 typed contract 和共享预算门禁。
- **Rationale**：Constitution 的恢复与重试门禁要求“每个恢复策略”显式配置这六个维度。
  仅声明“复用既有框架”不足以证明合规，而当前两字段模型无法表达其余四项。把字段设为
  必填可在启动时 fail closed，并通过固定配置测试证明不存在隐式无限重试或预算旁路。
- **Alternatives considered**：
  - 给任一字段提供默认值——这仍不是“显式配置”，且新增策略可能在评审时遗漏关键
    风险选择，拒绝。
  - 只为 003 新失败类型新增旁路配置——会形成脱离共享预算的第二套恢复通道，违反 FR-031，
    拒绝。
