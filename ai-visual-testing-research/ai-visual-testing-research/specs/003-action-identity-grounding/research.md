# Phase 0 Research: 通用动作身份、目标一致性与坐标空间安全

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

**重新基线说明**：本文件替换 2026-07-21 版本，不是增量补丁。旧版本围绕单一 POS
购物袋事故设计（`extract_cart_state()`、`ReportingConfig.category_keywords` 固定
四分类、`result_display_keywords`/`dismissal_keywords` 硬编码日文/中文业务关键词、
`--confirmed-cart-items` 等 CLI 参数），已被 2026-07-22 的
`checklists/domain-independence.md` 判定为直接违反 Constitution v1.1.0 Principle VI，
且其中两处（`action_id_match` 跳过目标安全检查、`action_type` 不同即无条件
`dangerous_drift`）与 spec.md 修正后的 Safety Issue A/B 直接矛盾。本文件的全部决策
均以现状代码（`src/vnc_agent/...`，2026-07-22 读取）为依据，明确标注每一条"移除"或
"替换为通用机制"，不再以单一事故复现作为设计的首要目标。

## 0. 业务泄漏清单与泛化替换计划（对应 FR-040 之前的架构前提、Constitution Principle VI）

下表是 `checklists/domain-independence.md` 与本次代码复核确认的**当前代码中**全部
业务专用符号，逐项给出替换方案。这是 Phase 1 设计必须实现的清单，`/speckit-tasks`
生成任务时 MUST 逐行转换为任务，不得遗漏。

| 位置 | 现状（业务泄漏） | 替换为（通用机制） |
|---|---|---|
| `domain/run.py` | `HumanStartStateConfirmation.confirmed_cart_items/confirmed_cart_amount`、`ObservedStartState.cart_items/cart_amount` | `DeclaredFact`/`RunPrecondition`/`ObservedFactEvaluation`（§12，复用既有 `VerificationSpec`） |
| `verification/business_resolver.py` | `extract_cart_state()`、`evaluate_start_state_precondition()` 硬编码购物车字段比较 | 删除 `extract_cart_state()`；前置条件评估改为直接调用既有 `VerificationEngine.verify()`（§12），不再有任何业务专用提取函数 |
| `config.py::ReportingConfig` | `category_keywords: dict[str, list[str]]` 校验器强制要求恰好 `{add_to_bag, subtotal, payment, clear_or_reset}` 四键 | 删除该字段与校验器；由测试用例/场景 profile 声明 `action_tags: list[ActionTagRule]`，核心 `ReportingConfig` 不再持有任何分类默认值（§10/§12b） |
| `config.py::AgentConfig.reporting` 默认工厂 | `{"add_to_bag": ["レジ袋","购物袋","袋","add bag"], "subtotal": ["小計","subtotal"], "payment": [...], "clear_or_reset": [...]}` | 删除；`ReportingConfig` 默认 `action_tags=[]`（核心零默认业务词表） |
| `config.py::PlanningConfig` | `result_display_keywords`/`dismissal_keywords: list[str]` 字段及默认工厂中的 `["已添加","商品行","合計","小計"]`/`["关闭","閉じる","キャンセル"]` | 删除两个字段；改为新增 `micro_action_risk_thresholds: dict[str, Literal["low","medium","high"]]`（UI 交互类别→风险阈值，通用、非业务，§7） |
| `execution/target_consistency.py` | 模块级常量 `_RESULT_DISPLAY_KEYWORDS`（含"合計"/"小計"/"已添加"/"商品行"）、`_DISMISSAL_KEYWORDS`（含"关闭"/"閉じる"/"キャンセル"）；`evaluate_target_consistency()` 用文本关键词匹配推断"是否为合法微动作"；`if previous_action.action_type != proposed_action.action_type: return "dangerous_drift"` 无条件分支 | 整个关键词匹配启发式删除；改为读取 `SemanticAction.micro_action_purpose`（Planner 声明的结构化枚举）与 `SemanticAction.risk_level`，按 FR-013 的 AND 语义判定（§7）；`action_type` 差异不再单独决定结果 |
| `api/cli.py` | `--confirm-start-state`/`--confirmed-cart-items`/`--confirmed-cart-amount`/`--confirmed-screenshot` 四个固定业务参数 | 替换为通用 `--confirm-precondition key=value`（可重复）+ `--confirm-screenshot <path>`（§12b） |
| `contracts/real-vnc-audit-contract.md`（文档） | 固定 `add_to_bag/subtotal/payment/clear_or_reset` 四分类要求 | 全文重写为声明式前置条件 + 声明式 tag 审计契约（本次 `/speckit-plan` 输出） |
| `contracts/action-identity-contract.md`（文档） | `"action_id_match"` 时"MUST NOT 再比较"目标一致性——与 Safety Issue A 直接矛盾 | 全文重写：新增 `has_target_evidence_conflict()` 前置门（§6） |
| `data-model.md` §2/§9（文档） | `action_type` 不同→无条件 `"dangerous_drift"` | 全文重写为 AND 语义（§7） |
| `planning/action_classification.py` | `_DEFAULT_NON_IDEMPOTENT_KEYWORDS` 含 `"レジ袋"`/`"購入"`/`"支払い"` | **不在 003 范围内**——spec.md Assumptions 明确"非幂等动作分类沿用既有机制，不在本 feature 中重新定义"；本表仅记录为已知技术债，交由后续独立 feature 处理，不在本次 tasks.md 中安排修复任务 |

**架构前提（对应用户本次 10 条要求）**：

1. 公共模型只包含通用 `named facts`（`DeclaredFact`/`VerificationSpec`，复用既有类型）、
   `assertions`（同一 `VerificationSpec`/`VerificationCondition`）、`tags`
   （`ActionTagRule`）、`matchers`（`ActionTagRule.matcher`/`micro_action_purpose` 枚举）、
   `policies`（`RecoveryPolicy` 六字段，保留）、`action records`
   （`ActionIteration`/`ExecutableAction`/`ExecutionResult`，保留）、`evidence`
   （`coordinate_space_audit`/`fact_evaluations`/`declared_tag_counts`）。
2. 核心模型（`domain/`、`config.py`、`reporting/`）不再出现 `cart`/`bag`/`subtotal`/
   `payment`/`clear_or_reset` 等固定业务字段——见上表逐项删除。
3. 报告 `declared_tag_counts` 完全由测试用例/场景 profile 声明的 `action_tags`
   驱动，核心不再硬编码四分类（§10）。
4. `target_consistency` 不再依赖任何关键词列表——改为读取 Planner 声明的
   `micro_action_purpose` 结构化字段（§7）。
5. `action_id_match` 新增 `has_target_evidence_conflict()` 前置门，不能绕过目标
   安全验证（§6，Safety Issue A）。
6. 坐标空间（`GroundingCandidate.coordinate_space`/`raw_bbox`/
   `resolve_pixel_bbox()`）与 `RecoveryPolicy` 六字段契约已经是通用设计，本次
   **原样保留**，仅做编辑性调整（示例标签去业务化，§8/§9）。
7. POS 提取与断言（`pos-buy-bag-checkout.yaml` 的具体业务断言文本）只存在于该
   testcase 文件本身，不再有任何核心函数（如 `extract_cart_state()`）专门为它
   服务。
8. 见上表。
9. 见 §13（三个通用离线场景 + POS 作为第四个回归 fixture 的契约测试设计）。
10. 真实/在线环境验证继续不进入自动化测试（§14，延续 001/002/旧 003 已确立的
    约束，未发现需要修改之处）。

## 1. 定位现有 RepeatGuard 与 target_consistency 的具体缺陷（业务泄漏 + 安全问题 A/B）

- **现状（已核实源码）**：`execution/target_consistency.py::evaluate_target_consistency()`
  第 85-86 行：`if previous_action.action_type != proposed_action.action_type: return
  "dangerous_drift"`——无条件分支，直接违反 spec.md 安全问题 B 的修正（FR-012/013：
  `action_type` 变化只能是风险信号，不能无条件等于 `dangerous_drift`）。同一文件
  第 17-27 行的 `_DISMISSAL_KEYWORDS`/`_RESULT_DISPLAY_KEYWORDS` 模块级常量包含
  `"合計"`/`"小計"`/`"已添加"`/`"商品行"`/`"閉じる"`/`"キャンセル"` 等业务/语言专用
  词汇，作为默认参数值硬编码在核心 `execution/` 模块中，直接违反 Constitution
  Principle VI。`contracts/action-identity-contract.md` 现有文本明确写"`action_id`
  相同...MUST NOT 再比较"，即 `identity_match()` 返回 `"action_id_match"` 时目标
  一致性检查被完全跳过——直接违反 spec.md 安全问题 A 的修正（FR-003/004）。
- **Decision**：三处修复合并为一次重写（不再分阶段打补丁）：
  1. `evaluate_target_consistency()` 删除关键词匹配与 `action_type` 无条件分支，
     改为读取 `SemanticAction.micro_action_purpose`/`risk_level` 的 AND 语义
     判定（§7）。
  2. `RepeatGuard.check()`/`identity_match()` 组合逻辑新增
     `has_target_evidence_conflict()` 前置门（§6）。
  3. `action-identity-contract.md`、`data-model.md`、`real-vnc-audit-contract.md`
     三份设计文档全文替换，不保留任何仍然描述旧行为的段落作为"权威设计"。
- **Rationale**：`checklists/domain-independence.md` 已经证明"分阶段增量修补"会
  让契约文档长期与 spec.md 矛盾（CHK003/CHK010 的两处直接冲突正是历史增量修补的
  产物）；本次要求"重新基线，不是增量补丁"，因此三处一次性替换。

## 2. CanonicalActionIdentity 的数据模型与计算位置（保留，无变化）

- **Decision**：`domain/action_identity.py::CanonicalActionIdentity`
  （`step_id`/`action_type`/`action_id`/`normalized_target`）与
  `execution/action_identity.py::compute_identity()`/`identity_match()` 的现有实现
  已经是业务无关的通用设计（不含任何固定业务字段），**保留不变**。
  `identity_match()` 返回值集合（`"different_step"`/`"action_id_match"`/
  `"normalized_target_match"`/`"no_action_id_ambiguous"`）与判定规则不变。
- **Rationale**：该模块的现状已经满足 Constitution Principle VI 与 FR-001/002/005/
  007/009/011，`checklists/domain-independence.md` 未在此模块发现业务泄漏，唯一
  需要修正的是"`identity_match()` 的结果如何被 `RepeatGuard.check()` 消费"（见
  §6），而不是 `identity_match()` 本身。

## 3. 步骤边界隔离（保留，无变化）

- **Decision**：`CanonicalActionIdentity.step_id` 与既有的"不同 `StepRecord` 之间
  `previous_iteration` 永不跨越步骤边界"这一运行时不变量**保留不变**——现状已经
  正确实现 FR-001，且不含任何业务专用逻辑。
- **Rationale**：同 002/旧 003 research.md 的既有结论，本次复核未发现需要改动之处。

## 4. `SemanticAction` 新增结构化字段：`micro_action_purpose` 与 `risk_level` 扩展

- **Decision**：
  1. `domain/action.py::SemanticAction.risk_level` 从当前的 `Literal["low"] = "low"`
     扩展为 `Literal["low", "medium", "high"] = "low"`——直接复用 Constitution
     "动作安全分级 low/medium/high 三级"这一既有的、业务无关的通用概念，不新增
     概念。
  2. 新增 `micro_action_purpose: Literal["dismiss_overlay", "scroll_reveal",
     "refocus", "wait", "re_observe"] | None = None` 字段——这是一个**封闭的、
     UI 交互通用枚举**（关闭遮挡元素/滚动显现/重新聚焦/等待/重新观察），描述的是
     GUI 交互的结构性类别，不是任何具体业务的词汇表；Planner 在提出一个非主要
     非幂等动作的新目标时，MAY 显式声明该字段以表明其独立的交互目的。
- **Rationale**：这是本次重新基线相对旧版本**最关键的架构决策**——旧代码用
  "文本关键词匹配"（`dismissal_keywords`/`result_display_keywords`）去**推断**
  Planner 的意图，这既是业务语言泄漏的直接来源，也不符合 spec.md FR-006/012/013
  反复使用的"**声明的**交互目的"（声明式，而非推断式）这一措辞。让 Planner 直接
  **声明**一个封闭枚举值，而不是让核心代码去猜测自由文本里有没有出现某个业务
  关键词，从根本上消除了关键词列表这一泄漏面，同时比文本匹配更确定性（枚举比较
  vs 子串匹配），更符合 Constitution"确定性手段优先"原则。
- **Alternatives considered**：
  - 保留关键词匹配，但把关键词列表从"硬编码默认值"改为"测试用例/场景 profile
    可选声明，核心默认空列表"——这确实能满足"核心不含固定业务字段"的字面要求，
    但仍然是"用词表猜测意图"这一本质上脆弱且与"声明的"措辞不符的设计，拒绝；
    结构化枚举声明是更彻底、更简单的修复。
  - 用自由文本字段承载"purpose"（如 `purpose: str | None`）而非封闭枚举——自由
    文本仍然需要某种匹配/解析逻辑才能被 FR-013 的 AND 语义消费，重新引入"要不要
    关键词匹配"的问题，拒绝；封闭枚举可以直接做等值比较。

## 5. 目标证据冲突检测：`has_target_evidence_conflict()`（新增，落实安全问题 A）

- **Decision**：新增 `execution/target_consistency.py::has_target_evidence_conflict(
  previous_action: SemanticAction, proposed_action: SemanticAction, *,
  previous_resolved_region: Region | None = None, proposed_resolved_region: Region
  | None = None) -> bool`：
  1. **角色冲突**：`previous_action.target.role` 与 `proposed_action.target.role`
     经归一化（大小写/首尾空白）后不相等时视为角色冲突。
  2. **交互性质冲突**：两者的角色分别映射到"可交互"/"非交互"两类（复用 §7 中
     `evaluate_target_consistency()` 已有的角色分类判断，不重复实现）时，若分类
     结果不同视为交互性质冲突。
  3. **空间证据冲突**：若两者均提供了已解析的目标区域（`previous_resolved_region`/
     `proposed_resolved_region`，来自各自轮次 Grounding 结果的 §8 换算后
     `bbox`），且两个区域交并比（IoU）低于一个可配置阈值
     （`config.agent.planning.target_region_conflict_iou_threshold`，默认
     `0.10`）视为空间证据冲突；任一区域缺失时空间证据项不参与判断（不产生误判）。
  4. 以上三项**任一为真**即返回 `True`（存在冲突）。
  该函数 MUST NOT 依赖任何关键词列表或业务词汇，只依赖结构化字段（`role`、
  分类结果、`Region` 数值）比较。
- **Rationale**：直接落实 spec.md 安全问题 A（"如果 role、target、交互性质或
  空间证据与前一轮发生实质冲突，仍必须运行目标一致性检查"）；三个信号维度逐字
  对应 spec.md 的措辞（"角色"、"交互性质"、"空间证据"），确保契约与规格可逐条
  对照，不遗漏。
- **Alternatives considered**：
  - 只比较角色，不比较空间证据——真实场景中角色标签本身可能不可靠（spec.md
    Assumptions 已经指出这一风险），只用角色一个信号会让"角色标签错误"的场景
    完全绕过冲突检测；加入空间证据作为独立、不依赖角色标签正确性的第二信号，
    降低单一信号失效的风险，拒绝只用角色。
  - 把这个函数做成 `evaluate_target_consistency()` 的内部私有逻辑，不对外暴露——
    FR-003/004 要求"无论 `action_id` 是否匹配都要能触发"，必须是一个可以在
    `RepeatGuard.check()` 组合逻辑中独立调用、独立单测的函数，拒绝内联。

## 6. `RepeatGuard.check()` 的组合逻辑重写（落实安全问题 A）

- **Decision**：`execution/repeat_guard.py::RepeatGuard.check()` 重写为：

  ```text
  1. if previous_iteration is None: return allowed=True, reason="first_attempt"
  2. if classify_action_kind(proposed_action) == "idempotent":
       return allowed=True, reason="idempotent_action"
  3. prev_id = compute_identity(step_id, previous_iteration.semantic_action)
     curr_id  = compute_identity(step_id, proposed_action)
     match = identity_match(prev_id, curr_id)
  4. if match == "different_step":  # 结构上不会发生，见 §3
       return allowed=True, reason="first_attempt"
  5. conflict = has_target_evidence_conflict(
       previous_iteration.semantic_action, proposed_action,
       previous_resolved_region=..., proposed_resolved_region=...)
  6. if match in ("action_id_match", "normalized_target_match") and not conflict:
       # 安全问题 A 的核心分支：仅当无冲突时，identity 匹配才单独决定"是否为
       # 同一逻辑动作"，走既有 no_effect-only 重试许可规则（reason 视 match 取
       # 对应的 "*_normalized_target" 后缀变体）
       走既有 FR-006/010 规则（002 既有分支，此处不再重复展开）
  7. else:
       # match == "no_action_id_ambiguous"，或者 match 已匹配但 conflict=True
       # ——无论哪种情形，安全问题 A 都要求必须运行一致性检查，不能因为
       # identity 匹配或前一轮 no_effect 就跳过
       outcome = evaluate_target_consistency(step.intent, previous_iteration.semantic_action, proposed_action)
       if outcome == "dangerous_drift":
           return allowed=False, reason="dangerous_drift"
       if outcome == "legitimate_micro_action":
           return allowed=True, reason="legitimate_micro_action"
       # outcome == "ambiguous"
       if 前一轮 ActionEffect 已被可靠判定为 no_effect 且步骤预算仍有剩余:
           return allowed=True, reason="no_effect_confirmed"
       return allowed=False, reason="ambiguous_fail_safe"
  ```

  关键变化（相对旧版本）：第 5-7 步是全新增加的"无论 identity 是否匹配、无论
  前一轮是否 `no_effect`，只要存在目标证据冲突就必须运行一致性检查"这一门禁；
  旧版本第 6 步（原 `action_id_match` 分支）直接跳到 no_effect-only 规则，不检查
  冲突，这正是安全问题 A 描述的缺陷。
- **Rationale**：直接落实 spec.md FR-003/004 与 2026-07-22 `/speckit-clarify`
  会话中安全问题 A 的最终决议；`conflict` 检测独立于 `match` 结果计算，保证"即使
  `action_id` 相同、即使前一轮是 `no_effect`，只要证据冲突就必须检查"这一不变量
  无法被绕过。
- **Alternatives considered**：
  - 只在 `match == "no_action_id_ambiguous"` 时调用一致性检查（旧设计）——正是
    安全问题 A 要修复的缺陷，拒绝保留。
  - 让 `identity_match()` 自己内部调用 `has_target_evidence_conflict()` 并直接
    返回一个新的枚举值（如 `"action_id_match_conflicting"`）——会让 `identity_match()`
    从"纯粹的身份匹配判断"变成同时承担"安全判断"，职责混合，拒绝；保持
    `identity_match()` 单一职责（只判断身份），冲突检测与组合决策放在
    `RepeatGuard.check()` 编排层。

## 7. 危险目标漂移判定重写：AND 语义 + 风险级别路由（落实安全问题 B）

- **Decision**：`evaluate_target_consistency()` 重写为：

  ```text
  def evaluate_target_consistency(step_intent, previous_action, proposed_action) -> ConsistencyOutcome:
      if previous_action is None:
          return "legitimate_micro_action"
      purpose = proposed_action.micro_action_purpose
      risk = proposed_action.risk_level
      is_legit_purpose = purpose is not None  # 属于封闭枚举即视为声明了合法微动作类别
      passes_intent_check = _step_intent_consistency(step_intent, proposed_action)  # 见下方，不再用关键词，改用规范化目标与
                                                                                      # step_intent 的结构化重合判断（保留旧版本
                                                                                      # 已有的、不含业务词汇的重合度量算法本身）
      if is_legit_purpose and passes_intent_check:
          threshold = config.planning.micro_action_risk_thresholds[purpose]
          if not _risk_exceeds(risk, threshold):
              return "legitimate_micro_action"
      # 以上 AND 条件任一不满足：
      previous_interactive = _is_interactive(previous_action)
      proposed_interactive = _is_interactive(proposed_action)
      if previous_interactive and not proposed_interactive:
          return "dangerous_drift"
      if previous_interactive and proposed_interactive and not passes_intent_check:
          return "dangerous_drift"
      return "ambiguous"
  ```

  与旧版本的关键差异：**删除** `if previous_action.action_type !=
  proposed_action.action_type: return "dangerous_drift"` 这一无条件分支；
  `action_type` 差异现在只是促成"没有声明合法微动作目的"这一状态的自然结果（因为
  `action_type` 变了但没配合声明 `micro_action_purpose`，会走到 AND 条件不满足的
  分支），不再有任何代码路径**直接**因为 `action_type` 不同就返回
  `"dangerous_drift"`——是否判定为漂移最终由"是否声明了合法目的 AND 通过 intent
  一致性 AND 风险级别不超阈值"这一组合结果决定，与 2026-07-22 `/speckit-clarify`
  安全问题 B 的最终决议逐字对应。
  `_step_intent_consistency()`（原"关键词重合度量"逻辑）保留其"规范化目标文本与
  step_intent 的重合度比较"这一算法结构本身（不含固定业务词表，纯字符串处理），
  只是不再用它去判断"是否为合法微动作"（那已改由 `micro_action_purpose` 声明
  承担），只用它判断"新目标是否仍符合步骤 intent"这一独立问题。
- **Rationale**：直接落实 FR-012/013 与 2026-07-22 clarify 会话的 AND 语义决议；
  风险级别超阈值时不落入"legitimate_micro_action"，而是继续走后续的
  interactive/non-interactive 漂移判断或 `"ambiguous"`——`"ambiguous"` 结果会被
  §6 的 `RepeatGuard.check()` 路由到 FR-034 六字段恢复策略契约（例如触发
  `requires_human_confirmation=True` 的恢复策略），而不是本函数自己发明一个新的
  "风险裁决"分支，避免开辟脱离既有恢复契约的独立通道（FR-013 明确禁止）。
- **Alternatives considered**：
  - 把风险阈值判断做成硬编码常量而非可配置项——`ocr_sanity_check_ratio` 已经
    确立"这类阈值应可配置"的先例，且不同被测应用对"滚动/关闭弹窗"这类微动作的
    风险容忍度可能不同，拒绝硬编码。

## 8. GroundingCandidate 的 coordinate_space 数据模型与一次性转换架构（保留，仅示例去业务化）

- **Decision**：`domain/grounding.py::GroundingCandidate`（`coordinate_space`/
  `raw_bbox` 字段）、`models/coordinate_space.py::resolve_pixel_bbox()`（唯一换算
  点）、`models/mimo_grounder.py::MimoGrounderClient.ground()` 的现状实现**原样
  保留**——`checklists/domain-independence.md` 未在此模块发现任何业务字段泄漏，
  这正是 spec.md 要求"坐标空间和 RecoveryPolicy 中已经通用的设计应保留"的对象
  之一。唯一改动：`contracts/coordinate-space-contract.md` 中 wire 格式示例的
  `"label": "レジ袋"` 替换为业务无关的占位符（如 `"label": "toolbar_icon_3"`），
  避免核心契约文档的示例携带业务语言痕迹，纯编辑性修改，不改变任何字段定义或
  校验规则。
- **Rationale**：坐标空间协议是纯几何/协议层面的设计，与被测业务完全无关，
  `checklists/domain-independence.md` 也确认该模块通过检查（CHK008 类比）；本次
  唯一动作是清理契约文档里一个非规范性示例标签，避免读者误以为坐标空间协议本身
  与 POS 场景绑定。

## 9. RecoveryPolicy 六字段契约（保留，仅措辞去业务化）

- **Decision**：`config.py::RecoveryPolicy`（`max_retries`/`cooldown_ms`/
  `consumes_global_retry_budget`/`allows_action_path_change`/
  `requires_strong_model`/`requires_human_confirmation`）**原样保留**，这正是
  spec.md 明确要求保留的通用设计。唯一改动：
  `contracts/recovery-policy-contract.md` 中"任何策略不得构造自动清空购物车、
  删除商品或撤销已确认业务结果的动作"改写为"任何策略不得构造任何不在该测试步骤
  已声明动作范围内、会改变被测应用状态的操作"，与 spec.md FR-032 现有措辞对齐，
  移除"购物车"这一具体业务名词，不改变约束的实质范围。新增一条：风险级别驱动的
  `dangerous_drift`/`ambiguous` 结果（§7）MUST 通过本契约的
  `requires_human_confirmation`/`requires_strong_model` 字段路由，不得新增独立
  裁决逻辑（呼应 2026-07-22 clarify 会话对 FR-013 的决议）。
- **Rationale**：同 §8，本模块设计本身已经业务无关，只需清理措辞与补充一条
  跨引用说明。

## 10. 声明式动作 Tag 审计（替换固定四分类，落实 FR-027/028）

- **Decision**：
  1. 新增 `domain/reporting_tags.py::ActionMatcher`（结构化谓词，非文本关键词
     搜索）：

     ```python
     class ActionMatcher(BaseModel):
         action_type: ActionType | None = None
         target_role: str | None = None
         target_text_contains: str | None = None
         intent_contains: str | None = None
     ```

     四个字段均为可选，声明的字段之间为 AND 关系；`target_text_contains`/
     `intent_contains` 为大小写不敏感的子串匹配（由测试用例/场景 profile 提供
     具体业务子串，如 `"购物袋"`，核心代码本身不包含任何具体子串）。
  2. 新增 `ActionTagRule(BaseModel)`：`tag: str`、`matcher: ActionMatcher`。
  3. `config.py::ReportingConfig` 删除 `category_keywords` 字段与其校验器，替换为
     `action_tags: list[ActionTagRule] = Field(default_factory=list)`——**核心
     默认空列表，不含任何业务分类**；测试用例/场景 profile 可在 `expected`/顶层
     声明覆盖或追加规则（具体声明位置由 `domain/testcase.py` 的
     testcase-level schema 决定，见 data-model.md §8b）。
  4. `reporting/json_report.py::build_report_dict()` 对 `executed_action_log`
     中每条记录，依次匹配全部声明的 `ActionTagRule`（一个动作可同时匹配 0 个、
     1 个或多个 tag，不再是互斥的四选一分类），聚合为
     `declared_tag_counts: dict[str, int]`；未匹配任何规则的已发送动作仍保留在
     `executed_action_log` 中，但不计入任何 tag 计数（不再有"unclassified"
     兜底分类，因为 tag 匹配本身就是"零到多"的开放集合，不需要兜底桶）。
- **Rationale**：直接落实 FR-027/028 与用户要求 3"报告 action counters 必须由
  testcase/profile 声明，不得固定四分类"；`ActionMatcher` 是结构化字段谓词
  （非文本关键词表），核心模块本身不包含任何具体业务子串，全部业务子串由声明方
  （testcase/profile）提供，从架构上不可能出现"核心代码硬编码业务词汇"这一问题。
- **Alternatives considered**：
  - 保留 `category_keywords` 字段但去掉校验器的"必须恰好四类"约束，允许任意
    键——仍然是"文本关键词列表"这一设计，且默认工厂里如果不清空就仍然残留
    业务默认值；`ActionMatcher` 结构化谓词是更彻底的修复，拒绝只放松校验器。

## 11. 声明式运行前置条件（替换固定购物车字段，落实 FR-024/025/026 与 2026-07-22 clarify 决议）

- **Decision**：完全复用既有的 `domain/verification.py::VerificationSpec`/
  `VerificationCondition`/`VerificationResult` 与 `verification/engine.py::
  VerificationEngine.verify()`——这正是 2026-07-22 `/speckit-clarify` 会话对
  "facts/assertions 职责边界"问题的最终决议（"二者 MUST 是同一底层 fact/
  assertion 声明机制...仅触发时机不同"）在实现层面的具体落地：
  1. 新增 `domain/run.py::DeclaredFact(BaseModel)`：`key: str`、
     `spec: VerificationSpec`——**不新增任何断言语法**，直接复用步骤级业务
     断言已经在用的类型。
  2. 新增 `RunPrecondition(BaseModel)`：`facts: list[DeclaredFact] =
     Field(default_factory=list)`，由测试用例/场景 profile 在顶层可选声明
     （`domain/testcase.py` 新增 `TestCase.precondition: RunPrecondition |
     None = None`）。
  3. 新增 `FactEvaluation(BaseModel)`：`key: str`、`result: VerificationResult`
     （直接复用既有类型，不新增字段）。
  4. `TestRun` 新增 `precondition_evaluation: PreconditionEvaluation`，
     `PreconditionEvaluation(BaseModel)`：`status: Literal["not_required",
     "passed","failed"]`、`fact_evaluations: list[FactEvaluation]`、
     `checked_at: datetime | None`。
  5. Runtime：完成首次独立 Observe/Understand 后、任何 `PLANNING`/
     `RESOLVING_ACTION` 或 `ExecutableAction` 生成前，若
     `TestCase.precondition` 非 `None`，对每个 `DeclaredFact` 调用既有
     `VerificationEngine.verify(fact.spec, first_observed_screen)`；全部
     `VerificationResult.status == "passed"` 时整体 `status="passed"`，否则
     `status="failed"`（任一 `failed`/`uncertain` 即视为不满足，与既有
     `aggregate_conditions` 的"all"语义天然一致，不新增聚合规则）。`failed`
     时运行 MUST 停止，保存 `fact_evaluations` 证据，MUST NOT 生成任何
     `ExecutableAction`。未声明 `precondition` 的测试用例（含全部旧格式用例）
     `status="not_required"`，行为与 001/002 完全一致（向后兼容零改动）。
  6. **删除** `verification/business_resolver.py::extract_cart_state()` 与
     `evaluate_start_state_precondition()`——不再需要任何业务专用提取函数，
     因为"从截图中判断某个具名 fact 是否成立"这件事本身就是 `VerificationSpec`
     的既有职责（如 `text_appears`/`template_appears`），不需要为每个业务场景
     单独写一个 `extract_xxx_state()` 函数。
- **Rationale**：这是本次重新基线中**消除业务泄漏最彻底**的一步——旧设计为
  "购物车状态"单独建了 `ObservedStartState`/`extract_cart_state()`，本质上是
  把"业务状态提取"当成了框架需要内置的能力；而实际上 001/002 已经有一个完全
  通用的"从截图判断一组命名断言是否成立"的机制（`VerificationSpec`/
  `VerificationEngine`），前置条件只是把这个既有机制在"运行开始前"这个新的
  触发时机上再调用一次，不需要任何新概念、新校验器或新的业务提取逻辑。
- **Alternatives considered**：
  - 保留 `ObservedStartState` 式的"专用提取函数 + 专用比较函数"模式，只是把
    `cart_items`/`cart_amount` 泛化成 `dict[str, int | str]`——仍然需要一个
    "如何从截图提取任意命名字段"的通用提取器，而这正是 `VerificationSpec` 已经
    解决的问题，重新发明会造成两套并行的"从截图判断某事是否成立"机制，违反
    2026-07-22 clarify 决议"不新增第二套并行的断言语法"，拒绝。

## 12. CLI 与人工确认（替换固定业务参数）

- **Decision**：`api/cli.py::run` 命令删除 `--confirm-start-state`/
  `--confirmed-cart-items`/`--confirmed-cart-amount`/`--confirmed-screenshot`
  四个固定参数，替换为：
  - `--confirm-precondition key=value`（可重复，`typer.Option(...,
    "--confirm-precondition")`，类型 `list[str]`，运行时按 `=` 切分并聚合为
    `dict[str, str]`）——人工在真实/在线环境验收前，对**任意**声明的 fact
    key 提供人工独立确认值（不限定为购物车相关字段）。
  - `--confirm-screenshot <path>`（可选，配合上一参数使用；单独提供
    `--confirm-precondition` 而不提供本参数时使用默认前置截图策略，不强制
    二者绑定，除非 `TestCase.precondition` 非空且要求截图引用）。
  - CLI 校验：提供任一 `--confirm-precondition` 时，其 `key` MUST 能在
    `TestCase.precondition.facts` 中找到匹配的 `DeclaredFact.key`，否则在连接
    目标环境前以非零退出码失败（防止人工确认了一个测试用例根本没有声明的
    字段，产生虚假的"已确认"记录）。
  - 人工确认值本身 MUST NOT 参与自动前置条件判定的通过/失败决策（决策仍然
    完全基于 `VerificationEngine.verify()` 对声明 `spec` 的评估结果，见 §11）；
    人工确认值只作为独立的第二来源证据，与 `fact_evaluations` 一并写入报告，
    供人工复核"我确认的值"与"程序独立评估的结果"是否一致，不一致时报告中
    需要能看出差异（具体呈现方式见 data-model.md §8b、real-vnc-audit-contract.md）。
- **Rationale**：延续"人工独立确认 + 程序独立观察"这一双重来源的安全模式（旧
  设计已经确立，值得保留），但把字段从"购物车件数/金额"这两个固定字段泛化为
  任意声明 key/value，架构上不再对任何具体业务字段有依赖；`--confirm-precondition`
  是否提供与自动前置条件判定(§11) 是否通过完全解耦——即便不提供人工确认，
  `VerificationEngine.verify()` 的自动判定依然独立生效，人工确认是可选的**额外**
  交叉校验，不是自动判定的前提条件（这与 spec.md FR-025"系统…MUST 将声明的
  前置条件与独立观察到的证据自动比较"的措辞一致——比较的是"声明的前置条件"与
  "观察到的证据"，不要求人工确认值参与该比较本身）。

## 13. 三个通用离线场景 + POS 附加回归 fixture 的契约测试设计（落实 FR-040、用户要求 9）

- **Decision**：新增三个业务无关的离线契约测试场景，与既有 POS fixture 共同构成
  四个回归场景，任意两个通用场景即可证明每项通用能力：

  1. **表单填写并提交**（`tests/fixtures/test_scenario_form_submit.py`）：一个
     通用"设置表单"场景，`action_type="click"`、`action_id="submit-1"` 固定，
     Planner 在同一"提交"步骤重试中改写 `intent`/`target.description`（如"点击
     保存按钮"→"点击确认保存设置的按钮"），验证 `identity_match()` 判定为
     `"action_id_match"`、`has_target_evidence_conflict()` 为 `False`（角色/
     空间证据未变）、`RepeatGuard.check()` 拦截重复提交。
  2. **无文字图标打开菜单**（`tests/fixtures/test_scenario_icon_menu.py`）：
     一个仅有图标（`target.text=None`，`target.role="icon_button"`）的工具栏
     按钮场景，`GroundingCandidate` 声明 `coordinate_space="normalized_1000"`，
     画面分辨率为非正方形（复用原真实事故的 1024×1568 数值作为**示例分辨率**，
     不代表业务绑定，纯几何测试目的），验证坐标空间换算与视觉目标身份识别在
     缺乏文字锚点时仍然正确。
  3. **弹窗关闭或滚动后再操作目标**（`tests/fixtures/test_scenario_popup_scroll.py`）：
     构造 `proposed_action.micro_action_purpose="dismiss_overlay"`（关闭弹窗）
     与 `="scroll_reveal"`（滚动显现）两组场景，`risk_level="low"`，验证
     `evaluate_target_consistency()` 返回 `"legitimate_micro_action"`
     而非 `"dangerous_drift"`，且该微动作不被用于重新执行原非幂等动作。
  4. **POS 购物袋结算**（既有 `tests/e2e/test_scenario_15_pos_bag_business_
     acceptance.py`，复用 `testcases/pos-buy-bag-checkout.yaml`）：保留作为
     **第四个**回归 fixture，验证同样的通用机制（§2/§6/§7/§8/§11）在该具体
     业务场景下同样成立；测试断言与报告 MUST NOT 引用任何仅为该场景存在的
     核心代码分支（因为经过本次重新基线，已经没有这样的分支）。

  每一项声称通用的能力（`identity_match`/`has_target_evidence_conflict`/
  `evaluate_target_consistency`/`resolve_pixel_bbox`/前置条件评估/tag 审计），
  其契约测试套件 MUST 同时覆盖至少两个互不相关的场景（1/2/3 中的任意两个），
  POS 场景（4）作为附加验证，不单独满足 FR-040 的验收要求。
- **Rationale**：直接落实 spec.md FR-040/SC-012 与 Constitution Principle VI
  "任何声称为通用框架能力的变更，MUST 至少使用两个互不相关的 GUI 场景验证"；
  三个新场景分别覆盖动作身份/坐标空间/微动作判定三条主线，加上 POS 场景验证
  这三条主线在具体业务下同样成立，形成"通用性证明 + 具体场景回归"两层证据。
- **Alternatives considered**：
  - 只新增一个"通用"场景 + 保留 POS 场景——不满足"至少两个互不相关场景"的
    Constitution 硬性要求，拒绝。

## 14. 真实/在线环境验证边界（保留，无变化）

- **Decision**：延续 001/002/旧 003 已确立的约束——常规自动化测试
  （`pytest` 全量运行）MUST NOT 连接或操作真实/在线 VNC 目标；真实环境验证
  作为独立于自动化测试流水线之外、需最终人工批准后单次执行的环节。本次复核
  未发现任何新增测试违反该约束，`tests/unit/test_no_real_vnc_in_offline_tests.py`
  （静态扫描）继续覆盖新增的三个通用场景测试文件。
- **Rationale**：spec.md FR-039/041 与用户要求 10 完全对应现状约束，无需变更。
