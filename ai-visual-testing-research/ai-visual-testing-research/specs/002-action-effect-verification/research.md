# Phase 0 Research: 自适应动作效果检测与可信业务验证

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

本阶段的目标是在进入 Phase 1 设计前，把 Technical Context 与 spec.md 中隐含的实现层决策显式化。
本 feature 不引入任何新的第三方依赖或技术栈——001 已交付的 `vnc_agent` 包（Python 3.12、
opencv-python/numpy、RapidOCR、Pydantic v2、SQLAlchemy 2.x、pytest）完全够用；因此本文档聚焦
于"如何在既有模块基础上实现 spec.md 的新规则"，而不是技术选型。每条决策均以阅读既有源码
（`src/vnc_agent/...`）为依据，标注具体要修改或新增的文件。

## 1. 定位并解耦"全屏变化比例"与"局部区域证据"（复现 0.424% 事故的根因）

- **现状**：`perception/screen_diff.py::compute_diff()` 只有一个 `threshold: float = 0.02`
  全屏参数；`changed = ratio >= threshold`，且 `changed_regions`（轮廓检测结果）只在
  `if changed:` 分支内才计算——也就是说，当整屏变化比例低于阈值时，即便存在明确的局部
  变化区域，函数也会返回 `changed=False, regions=[]`，直接丢弃了局部证据。
  `verification/screen_change_verifier.py::verify_screen_change()` 与
  `recovery/classifier.py::classify_action_no_effect()` 都直接消费这个单一布尔值，这正是
  0.424% 全屏变化被误判为"无效果"、进而触发重复点击的根因所在。
- **Decision**：重构 `compute_diff()`，使轮廓检测（局部连通域）**始终执行**，不再受全屏
  `threshold` 门控；返回值扩展为 `(changed_since_last, changed_regions, diff_ratio, local_blobs)`
  ——其中 `local_blobs` 是不受全屏阈值影响、按独立的"单块最小像素数/面积占比"过滤后的局部
  变化区域列表（复用现有 `cv2.findContours` 逻辑，仅去掉外层 `if changed:` 门控）。全屏
  `pixel_diff_threshold`（`config.WaitConfig`）保留用于稳定性判定与 `changed_since_last`
  这一"弱证据"字段，不再是判断"局部是否发生变化"的唯一依据。
- **Rationale**：直接对应 spec FR-002/FR-003——不依赖固定 ROI、能发现整屏比例达不到阈值
  但局部确有变化的场景；改动范围小（去掉一个 `if` 门控 + 拆分返回值），不引入新的图像处理
  依赖，风险可控。
- **Alternatives considered**：
  - 为每个测试步骤单独配置"局部 ROI 阈值"——违反 spec FR-002"不依赖任何页面专用的预先
    配置固定 ROI"，拒绝。
  - 引入感知哈希（pHash）分块比较替代像素轮廓检测——对小面积但语义重要的变化（如购物车
    件数徽标）不够敏感，且改动面远大于"去掉一个门控"，本次不采用。

## 2. ActionEffect 四态判定的证据合并算法

- **Decision**：新增 `domain/action_effect.py`（`ActionEffectStatus` 四值枚举 + 证据模型）
  与 `perception/action_effect.py`（判定函数），输入为动作前后两个 `StructuredScreen`
  （含 OCR、模板匹配、`local_blobs`）及对应的动态噪声屏蔽区域。合并规则：
  1. 先对 §1 得到的 `local_blobs`、OCR 差集（新增/消失的 `OCRItem.normalized_text`）、
     模板差集（`TemplateMatch.template_id` 集合差异）三类信号分别排除已配置的动态噪声区域
     （复用 001 `perception/stability.py` 已有的动态区域屏蔽逻辑，不重新实现一套）。
  2. 若三类信号均为空 → `no_effect`。
  3. 若命中已知错误弹窗特征（见 §6）→ `unexpected_effect`，不再继续走 2/4 步判断。
  4. 若三类信号中至少一类给出**明确**信号（OCR/模板差集非空，或存在面积超过"确定性局部
     阈值"的 `local_blobs`）→ `expected_effect`。
  5. 若三类信号中存在信号但均低于"确定性局部阈值"（即只有轻微噪声级别的像素抖动）→
     `effect_uncertain`。
  该函数不产出 StepVerificationResult，只产出 ActionEffect（FR-001 的独立性要求）。
- **Rationale**：满足 FR-003/FR-004——综合四类证据（局部像素、OCR、模板、结构化页面状态；
  `vision_understanding` 差异并入"结构化页面状态"信号源）给出四态结果；步骤 3 优先判断
  错误弹窗，直接对应 FR-020（unexpected_effect 独立于变化幅度）。
- **Alternatives considered**：
  - 用单一加权分数（如"变化像素数 × OCR 差异数"综合打分再设一个总阈值）——退化成又一个
    需要调参的全局阈值，与本 feature"不依赖固定阈值/ROI"的精神相悖，拒绝。
  - 直接调用视觉模型判定 ActionEffect——违反宪法"资源约束"的"确定性手段优先"路由原则与
    spec FR-003 对确定性证据组合的要求，视觉模型仅在 StepVerificationResult 加强验证阶段
    （§8）作为补充，拒绝在 ActionEffect 层默认调用。

## 3. 非幂等动作分类的实现位置与默认识别规则

- **Decision**：在 `domain/action.py::SemanticAction` 新增可选字段
  `action_kind: Literal["idempotent", "non_idempotent"] | None = None`；新增
  `planning/action_classification.py::classify_action_kind()`，当 Planner 未显式给出
  `action_kind` 时，按 `intent` 关键词（可配置列表，默认含"加入/添加/加购/購入/レジ袋/
  add/append"、"删除/移除/取消/remove/delete/cancel"、"提交/确认/送出/submit/confirm"、
  "支付/结算/支払い/pay/checkout"等）做默认识别；两者都缺失时保守地视为
  `non_idempotent`（宁可误伤幂等动作触发一次多余的加强验证，也不放过应受保护的非幂等
  动作，呼应 Edge Cases 中的"避免既不误伤幂等动作、也不放过应受保护的非幂等动作"）。
- **Rationale**：直接落实 FR-013 与 Assumptions 中"分类以显式声明为主、辅以关键词默认
  识别"的既定默认；保守偏向"当不确定时按非幂等处理"，与 FR-014~016 的"默认禁止重复执行"
  精神一致，且比"默认按幂等处理"更安全。
- **Alternatives considered**：
  - 要求测试用例作者必须显式声明每个步骤的 `action_kind`，未声明时加载失败——对旧用例
    不友好，且与 FR-025 的向后兼容要求冲突，拒绝。

## 4. 重复执行防护（Repeat Guard）的实现位置

- **现状**：`runtime/agent_runtime.py::run()` 的步骤内 `while True` 循环里，每当一轮
  `ActionIteration` 验证结果为 `failed`/`uncertain` 且预算未耗尽，就直接 `continue` 到
  下一轮——下一轮会重新调用 `planner_orch.plan()` 产出新的语义动作，如果 Planner 对同一个
  未完成的意图（如"加入购物袋"）再次给出语义等价的点击动作，现有代码没有任何机制阻止其
  被执行，这正是重复加购的直接成因。
- **Decision**：新增 `execution/repeat_guard.py::RepeatGuard`，在 `AgentRuntime` 的步骤
  循环中、每轮 `ActionIteration` 开始 `RESOLVING_ACTION` 之前调用：若上一轮的
  `ActionEffect` 不是 `no_effect`、且上一轮 `StepVerificationResult` 未收敛为
  `passed`/`failed`、且本轮 Planner 提议的语义动作与上一轮"语义等价"（同一 `action_type`
  + 同一 `target` 归一化文本，或相同 `action_kind` 分类下相同 `intent` 归一化文本）且被
  分类为 `non_idempotent`，则 `RepeatGuard` 拒绝该轮直接执行，转而要求 Runtime 先执行
  "加强验证"（§5）而不消耗一次新的 `ActionIteration` 里的执行动作；只有当上一轮
  `ActionEffect` 被加强验证收敛判定为 `no_effect`、且步骤预算仍有剩余时，才放行。
  `RepeatGuard` 判断逻辑本身不发起新动作（职责仍属 Executor/调度层，不越权到 Verifier）。
- **Rationale**：直接落实 FR-014~016；放在 `AgentRuntime` 的迭代循环边界，是因为这是
  唯一同时持有"上一轮 ActionEffect""上一轮 StepVerificationResult""本轮拟执行动作"三者
  的调用点，符合 FR-028 对 Executor 层职责的要求。
- **Alternatives considered**：
  - 把重复防护逻辑塞进 `ActionPolicy.resolve()`——`ActionPolicy` 目前是无状态的纯函数式
    候选解析器，混入跨迭代状态会破坏其可测试性（现有 `tests/unit/test_action_policy_priority.py`
    大量依赖其无状态特性），拒绝。
  - 把重复防护逻辑塞进 `RecoveryEngine`——`RecoveryEngine` 处理的是"已识别失败类型 →
    恢复策略"，而 Repeat Guard 是在"是否应该执行"这一更早的决策点介入，语义不同，混合
    会让 `RecoveryEngine` 的职责边界模糊，拒绝。

## 5. StepVerificationResult 的加强验证升级路径

- **Decision**：新增 `verification/business_resolver.py`，封装 FR-017~019 的升级序列：
  (a) 重新观察（复用 `ObservationPipeline.observe()`）+ 用 `VerificationEngine` 重新评估
  已声明的确定性业务断言；(b) 若确定性断言仍为 `uncertain` 且该步骤存在
  `visual_question` 类型的业务断言，或调用者显式要求兜底，则调用
  `PlannerProvider.describe_screen(mode="answer_question")` 作为补充；(c) 若视觉模型
  仍不能给出确定结论，或其结论与已有的确定性断言冲突（§8），则最终 StepVerificationResult
  为 `uncertain`，且不触发任何新的动作执行。`RepeatGuard`（§4）在放行前必须调用本模块，
  不允许绕过直接重试原动作。
- **Rationale**：直接落实 FR-015/017/018/019；复用既有 `PlannerProvider.describe_screen`
  与 `VerificationEngine`，不新增模型客户端。
- **Alternatives considered**：
  - 把加强验证逻辑内联写在 `AgentRuntime.run_action_iteration()` 里——该方法已经承担
    观察/规划/定位/执行/等待/验证七个阶段的编排，继续内联会让单个方法过长、难以独立测试
    加强验证的分支覆盖，拒绝，改为独立可单测的模块。

## 6. 错误弹窗（unexpected_effect）识别机制

- **Decision**：`perception/action_effect.py` 内新增 `_classify_error_popup()`
  子函数，综合三个信号源：① OCR 命中可配置的错误关键词列表（默认含"错误/エラー/Error/
  失败/失敗/Failed"等，`config/agent.yaml` 新增 `perception.error_keywords`）；②
  可选的已知错误弹窗模板库匹配（复用现有 `perception/template/matcher.py`）；③ 当①②均
  不足以判断、且该步骤声明了 `visual_question` 业务断言时，允许 §5 的加强验证阶段将
  "是否出现了错误提示"作为兜底问题之一。命中①或②即可判定 `unexpected_effect`，不要求
  三者同时满足。
- **Rationale**：落实 FR-018/020；复用现有 OCR 与模板匹配管线，不引入新的检测技术；
  分类结果与画面变化幅度完全解耦，满足"不得仅因变化幅度大就判定为 expected_effect"。
- **Alternatives considered**：
  - 训练/接入专用的弹窗分类小模型——超出本 feature "不运行本地大型视觉模型、确定性手段
    优先"的资源约束，拒绝。

## 7. "正式业务模式"加载时校验与"旧用例"运行时兜底的分层策略

- **现状张力**：spec FR-008 要求"在加载与格式校验阶段拒绝新建的、仅含 screen_changed 且
  未声明 effect_only 的正式业务步骤"；FR-025 同时要求"MUST NOT 因该校验规则导致旧用例
  无法加载"。仅凭步骤内容本身（同样只有 `screen_changed` 条件）无法在加载时区分"新建"
  与"旧有"，两条 MUST 存在实现层面的张力，需要一个具体机制来同时满足两者。
- **Decision**：`domain/testcase.py::TestStep` 新增字段
  `verification_mode: Literal["business", "effect_only"] | None = None`（省略即为
  `None`）。加载器 `load_test_case()` 的行为分三支：
  - `verification_mode == "effect_only"`：允许 `expected` 仅含 `screen_changed`/
    `region_changed`，正常加载（FR-011/012）。
  - `verification_mode == "business"`（**显式**声明）：这是"新建正式业务步骤"的显式
    信号；加载器 MUST 校验 `expected.conditions` 至少含一个业务结果断言类型，否则在
    加载阶段拒绝并给出字段级错误（FR-008）。
  - `verification_mode` 省略（`None`）：视为默认正式业务模式，但由于无法确认是否为
    "新建"，加载器 MUST NOT 因缺少业务断言而拒绝加载（保证 FR-025）；该步骤在运行时
    经业务结果断言判定后若仅剩 `screen_changed` 类证据支撑，则 StepVerificationResult
    按 FR-026 封顶为 `uncertain` 并产生弱断言警告——即"运行时兜底"兜住了加载时无法拦截
    的旧步骤。
  测试用例编写指引：本 feature 之后新编写的正式业务步骤 SHOULD 显式写
  `verification_mode: business`，以便在加载阶段就获得快速反馈，而不必等到运行时才发现
  证据不足；这一约定通过更新 `contracts/test-case-schema.md` 与用例模板落实，不需要
  代码强制。
- **Rationale**：这是唯一能同时满足 FR-008（新建步骤加载即拒绝）与 FR-025（旧用例继续
  可加载）的机制——用"是否显式声明 `business`"作为可由代码判断的"新旧"代理信号，而不是
  试图从文件内容猜测作者意图。运行时兜底（FR-026/027）确保即便作者忘记显式声明
  `verification_mode: business`，也不会有业务步骤被静默当作可信通过。
- **Alternatives considered**：
  - 维护一份"已知旧用例 ID 白名单"文件，凡不在名单中的一律按加载时严格校验——需要额外
    维护一份随时可能过期的名单，且新增测试用例时容易忘记（或反过来误加入白名单），拒绝。
  - 只做运行时兜底，完全不做加载时拒绝（放弃 FR-008 的字面要求）——放弃了"新用例编写
    错误应尽早暴露"这一价值，且与 spec User Story 3 Acceptance Scenario 1 的明确描述
    （"系统在运行前拒绝该用例"）冲突，拒绝。

## 8. 确定性业务断言与视觉模型结论冲突时的裁决位置

- **Decision**：冲突裁决逻辑内聚在 §5 `verification/business_resolver.py` 的升级序列
  末端：当步骤 `expected` 同时包含至少一个确定性业务断言类型与一个 `visual_question`
  类型（或加强验证阶段临时发起的视觉问答）时，若二者结论不一致（例如确定性断言判定
  `failed`、视觉模型判定 `passed`），最终 StepVerificationResult MUST 采用确定性断言的
  结论；视觉模型的结论只在没有可比对的确定性断言、或确定性断言本身为 `uncertain` 时才
  参与决定最终结果。`aggregate_conditions()`（`domain/verification.py`）本身的 all/any
  语义保持不变，冲突裁决是在其之上的一层策略，只在"确定性给出明确结论、视觉给出相反明确
  结论"这一特定场景下介入覆盖。
- **Rationale**：落实 FR-010（Clarification 2026-07-21 决策 8）；不修改
  `aggregate_conditions()` 的既有 all/any 语义，避免影响 001 已交付且被
  `tests/unit/test_verification_compound.py` 覆盖的复合断言行为。
- **Alternatives considered**：
  - 在 `VerificationEngine._eval_one()` 层面就不允许视觉模型结论覆盖确定性条件——
    该层是逐条件独立求值，没有跨条件比较的上下文，冲突裁决必须在聚合之后的更高层进行，
    拒绝在该层实现。

## 9. 离线回归测试固定截图的构造方式

- **Decision**：延续 001 已建立的 fixture 模式——不提交任何二进制 PNG 资产，改为在
  `tests/fixtures/`（新增 `test_action_effect.py`、`test_repeat_guard.py`、
  `test_error_popup_classification.py` 等）内用 `numpy`/`cv2` 在测试运行时按精确像素
  比例程序化构造"整屏变化约 0.424%、局部购物车/件数区域变化"等场景（例如 1024×1568
  画布，仅在一个约 65×65px 的局部区域写入差异像素，使
  `65*65/(1024*1568) ≈ 0.263%`~`0.5%` 区间可调，精确复现"整屏低于 2%、局部明确变化"的
  事故条件），保持与 `tests/fixtures/test_screen_diff.py` 等既有测试完全一致的构造风格，
  不依赖真实 VNC 环境或外部图片资产（FR-030）。
- **Rationale**：与 001 既有测试基础设施保持一致，避免引入二进制资产的版本管理负担；
  程序化构造使"整屏变化比例"可以精确控制为任意目标值（如恰好 0.424%），比手工准备或
  截取真实截图更适合做回归断言的精确复现。
- **Alternatives considered**：
  - 从真实事故现场导出的实际截图作为固定资产提交仓库——更"真实"，但引入二进制资产、
    可能包含被测系统的界面细节（潜在信息泄露），且难以精确控制"整屏比例恰好 0.424%"
    这一边界条件，仅作为可选的人工复核材料，不作为自动化回归测试的默认输入。
