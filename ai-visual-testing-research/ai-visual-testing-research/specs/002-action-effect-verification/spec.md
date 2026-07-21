# Feature Specification: 自适应动作效果检测与可信业务验证

**Feature Branch**: `002-action-effect-verification`

**Created**: 2026-07-21

**Status**: Draft

**Input**: User description: "为现有 VNC 黑盒 GUI 自动化测试 Agent 增加"自适应动作效果检测与可信业务验证"能力，解决
pos-buy-bag-checkout.yaml 场景中因固定 2% 全屏变化阈值导致的 screen_changed 误判问题（真实点击已生效但整屏
变化仅约 0.424%，导致重复执行加入购物袋，随后恢复策略又将点击无依据地退化为 Tab、触发错误弹窗，错误弹窗因
画面大范围变化反而被误判为通过）：分离"动作是否产生效果"与"业务步骤是否成功"；不依赖固定 ROI 即可发现画面
任意位置的局部变化；综合局部变化、OCR、模板、页面状态判断动作效果状态（no_effect / expected_effect /
unexpected_effect / effect_uncertain）；screen_changed 仅能作为动作效果证据，不能单独证明正式业务步骤成功
（显式声明的 effect-only 测试除外）；正式业务步骤须至少包含一个业务结果断言；对添加、删除、提交、支付等
非幂等动作，效果已知但业务结果不确定时禁止盲目重复执行，应先加强验证、必要时调用视觉模型，仍不确定则返回
effect_uncertain；鼠标点击只有在存在可验证的焦点导航路径时才允许退化为键盘操作；错误弹窗不得因画面变化而
使业务步骤通过；保持 Planner / Grounder / Executor / Verifier 职责分离；旧用例须保持可加载，仅含
screen_changed 的旧业务用例须产生弱断言警告而非静默生成可信业务通过。范围不含 SQL Server Management
Studio、应用切换或人工误操作处理；常规自动化测试不得操作真实 VNC，真实 VNC 仅在最终人工批准后运行。"

## Clarifications

### Session 2026-07-21

- Q: ActionEffect（动作效果判定）与 StepVerificationResult（业务步骤验证结果）是否应作为两个完全独立的
  结果对象分别产生和记录，而不是合并为同一个通过/失败结论？ → A: 是，两者是两个独立结果：ActionEffect
  只回答"这次动作是否产生了效果"（`no_effect` / `expected_effect` / `unexpected_effect` /
  `effect_uncertain`）；StepVerificationResult 只回答"该业务步骤是否满足其 `expected` 定义"（`passed` /
  `failed` / `uncertain`）。两者 MUST 分别产生、分别记录，MUST NOT 合并为同一个判定。
- Q: screen_changed（含 region_changed）类证据在证据强度上应如何定性，能否单独支撑正式业务成功结论？ →
  A: screen_changed / region_changed 是"弱动作效果证据"——MAY 作为 ActionEffect 判定的输入之一（尤其是
  `expected_effect` / `effect_uncertain` 的支持证据），但 MUST NOT 单独构成 StepVerificationResult 判定
  为 `passed` 的充分条件（effect-only 步骤除外）。
- Q: "只关心画面变化"的步骤应通过什么规范化字段声明，该字段如何影响 screen_changed 的充分性？ → A:
  测试用例 MUST 通过显式字段 `verification_mode: effect_only` 声明该步骤为 effect-only 模式；只有当步骤
  显式声明 `verification_mode: effect_only` 时，screen_changed 才 MAY 作为该步骤 StepVerificationResult
  判定为 `passed` 的唯一充分条件。省略该字段或声明为其他值一律视为默认的正式业务模式，不适用该豁免。
- Q: 正式业务模式（即未声明 `verification_mode: effect_only`）下，业务断言的最低要求与允许类型有哪些？
  → A: 正式业务模式下步骤的 `expected` MUST 至少包含一个语义业务断言，类型限定为：文本出现/消失、数值
  达到预期、模板出现/消失、结构化页面状态达到预期、或 `visual_question`（视觉模型回答明确业务问题）
  之一；`screen_changed` / `region_changed` 不计入该最低要求。
- Q: 非幂等动作在 ActionEffect 为 `expected_effect` 但 StepVerificationResult 为 `uncertain` 时应如何
  处理？ → A: 系统 MUST NOT 重复执行该动作；MUST 先重新观察当前屏幕并执行加强验证（追加确定性验证条件、
  必要时调用视觉模型），在验证收敛为 `passed` 或 `failed` 之前不得重复执行该非幂等动作。
- Q: 非幂等动作在 ActionEffect 为 `effect_uncertain` 时是否可以重试？ → A: 同样 MUST NOT 盲目重试。只有
  当系统通过加强验证后可靠地将 ActionEffect 收敛判定为 `no_effect`（确认动作确未产生任何效果），且该
  步骤的重试预算（`max_retries` 等）仍允许时，系统才 MAY 再次执行该动作；`effect_uncertain` 状态本身
  MUST NOT 触发重复执行。
- Q: `unexpected_effect` 的判定范围与本 Feature 既有的排除范围（SSMS、应用切换、人工误操作）是什么
  关系？ → A: `unexpected_effect` 包括错误弹窗、或与该步骤操作意图明显冲突的页面状态；但本 Feature
  MUST NOT 处理由 SQL Server Management Studio 切换或人工误操作引起的应用切换类场景——这类场景的识别
  与处理超出本 Feature 边界，不计入 `unexpected_effect` 判定逻辑的设计目标。
- Q: 当确定性业务断言（文本/数值/模板/结构化状态）与视觉模型（`visual_question` 或补充判断）的结论
  冲突时，以哪个为准？ → A: 以确定性业务断言的判定结果为准；视觉模型结论仅在确定性方法本身不可用或
  不足以判断时才被采纳参与最终结果，一旦确定性断言给出明确的 `passed` 或 `failed`，MUST NOT 被视觉
  模型的相反结论推翻。
- Q: 鼠标点击切换为键盘路径时，"可验证的焦点导航路径"具体需要满足什么条件？ → A: MUST 同时具备
  （a）显式记录的焦点导航序列（从当前焦点到目标控件的具体 Tab/Shift+Tab 步骤），以及（b）验证该序列
  当前仍然有效的方法（而非仅凭一份未经复核的历史记录）；两者缺一即视为不存在可验证路径，系统 MUST
  停止当前恢复并转入重新定位或既有失败处理流程，MUST NOT 发送默认 Tab。
- Q: 旧用例（仅含 screen_changed，未声明 `verification_mode: effect_only`）在正式业务模式下，其最终
  StepVerificationResult 应该是什么？ → A: 系统 MUST 允许该用例正常加载执行（不因新规则拒绝加载）；
  但由于缺少业务断言，其 StepVerificationResult MUST 判定为 `uncertain`（而不是 `passed`），并 MUST
  同时产生明确的弱断言警告说明原因；只有显式设置 `verification_mode: effect_only` 时才允许仅凭
  screen_changed 判定为 `passed`。

## User Scenarios & Testing *(mandatory)*

<!--
  本 feature 建立在 001（VNC 黑盒 GUI 自动化测试核心执行闭环）已交付的观察-理解-执行-验证闭环之上，不重新
  定义该闭环的其他环节，只针对"动作效果判定"与"业务结果验证"这一具体薄弱环节做加固。下列用户故事均直接
  对应真实生产事故（pos-buy-bag-checkout.yaml 购物袋重复添加）中暴露出的具体缺陷：P1 组的 5 个故事共同
  构成"复现并修复该事故"所需的最小必要集合；P2 组是围绕该修复的必要配套能力（显式 effect-only 声明、旧
  用例兼容）；P3 是保障该修复本身可信、可回归验证的离线测试要求。
-->

### User Story 1 - 发现任意位置的局部画面变化以确认动作已产生效果 (Priority: P1)

作为测试工程师，我希望 Agent 在整屏像素变化比例很低（例如约 0.424%，低于固定全屏阈值）时，仍然能够通过
局部动态变化、OCR 状态差异、模板变化或页面结构化状态差异，发现画面任意位置已经发生的明确变化，而不是
因为整屏变化不达标就断定"动作没有效果"。

**Why this priority**: 这是本次生产事故的直接根因——固定 2% 全屏阈值把已经生效的点击（购物车件数从 0 变
为 1，但整屏变化仅约 0.424%）误判为无效果，进而触发了后续的重复点击。不修复这一判定，后续所有故事都
建立在错误的事实基础上。

**Independent Test**: 使用一组固定截图对（含本次事故的原始截图：整屏变化约 0.424%、购物车与件数区域已
发生变化），可独立验证动作效果判定逻辑能否输出 expected_effect，而无需连接真实 VNC 环境。

**Acceptance Scenarios**:

1. **Given** 一对操作前后截图，整屏像素变化比例约为 0.424%（低于配置的全屏变化阈值），但购物车图标和
   件数区域存在明确的局部变化，**When** 系统判定该动作是否产生效果，**Then** 系统判定为 expected_effect，
   而不是 no_effect。
2. **Given** 局部变化出现在画面中未被预先配置为 ROI 的任意位置（如页面右上角、左下角等此前未声明的
   区域），**When** 系统判定动作效果，**Then** 系统仍能发现该变化并据此判定为 expected_effect，不要求
   该位置被预先配置。
3. **Given** 一次操作前后截图对，OCR 识别到的文字状态、模板匹配结果或结构化页面状态三者之一发生了变化，
   但整屏与局部像素比较均未触发变化阈值，**When** 系统判定动作效果，**Then** 系统综合该证据仍判定为
   expected_effect 或 effect_uncertain，而不是仅依据像素比较得出 no_effect。
4. **Given** 一对操作前后截图，画面确实没有任何可观测变化，**When** 系统判定动作效果，**Then** 系统判定
   为 no_effect。

---

### User Story 2 - 效果已确认但业务结果未定时，先加强验证，不重复执行非幂等动作 (Priority: P1)

作为测试工程师，我希望当"加入购物袋"这类添加、删除、提交、支付等非幂等动作已经被判定为产生了某种效果、
但业务结果（如购物袋数量是否符合预期）尚不能确定时，Agent 先重新观察并加强验证，必要时调用视觉模型，
而不是盲目再点一次导致购物袋数量翻倍。

**Why this priority**: 这是本次事故的直接后果——系统在效果判定失败后重复执行了添加操作，造成多个购物袋。
即使 User Story 1 已经修复了效果判定本身，仍需要独立的重复执行防护规则，因为效果判定仍可能在其他场景下
返回 effect_uncertain，此时同样不能重复执行。

**Independent Test**: 使用"第一次点击后购物袋数量已从 0 变为 1"的固定截图序列和一次已记录的 effect_uncertain
判定结果，可独立验证重复执行防护逻辑能否阻止系统发出第二次点击指令，而无需真实执行任何键鼠动作。

**Acceptance Scenarios**:

1. **Given** 一次点击"レジ袋"（购物袋）按钮后，购物袋数量已经从 0 个变为 1 个（ActionEffect 为
   expected_effect），**When** 系统判断是否需要再次执行该添加动作，**Then** 系统不得再次点击该添加
   按钮。
2. **Given** 某个非幂等动作（添加、删除、提交或支付）已被判定为产生了 no_effect 以外的某种效果
   （expected_effect、unexpected_effect 或 effect_uncertain），但对应 StepVerificationResult 尚未
   确定为 passed 或 failed，**When** 系统决定下一步操作，**Then** 系统不重复发送该动作，而是先重新
   观察当前屏幕、执行加强验证。
3. **Given** 加强验证（重新观察、追加确定性验证条件）仍不能确认业务结果，**When** 系统评估是否需要
   进一步判断，**Then** 系统调用视觉模型对明确的业务问题进行判断，作为确定性方法之外的补充手段。
4. **Given** 视觉模型判断后业务结果依然无法确认，**When** 系统给出最终判定，**Then** 系统返回
   effect_uncertain，而不是武断判定通过、失败，也不再重复执行该非幂等动作。
5. **Given** 某个非幂等动作的 ActionEffect 经加强验证后被可靠地收敛判定为 no_effect，且该步骤的重试
   预算仍有剩余，**When** 系统决定下一步操作，**Then** 系统 MAY 再次执行该动作；`effect_uncertain`
   状态本身 MUST NOT 被当作触发重试的理由。

---

### User Story 3 - 正式业务步骤要求独立的业务结果断言，screen_changed 不能单独通过正式业务步骤 (Priority: P1)

作为测试工程师，我希望正式的业务测试步骤（如"加入一个购物袋"“计算合计金额”）除了确认动作产生了画面变化
之外，还必须验证一个明确的业务结果（如购物袋数量文字、合计金额数值、结构化状态），这样即便画面确实发生
了变化，也不会被误判为业务意义上的成功。

**Why this priority**: 这是分离"动作效果"与"业务成功"这一核心目标的落地规则，直接堵住了"画面变了就算
通过"的漏洞——这正是错误弹窗最终被误判为通过的根本原因。

**Independent Test**: 使用现有 pos-buy-bag-checkout.yaml 中"仅含 screen_changed 条件"的步骤定义作为反例
输入，可独立验证测试用例加载与校验逻辑能否正确拒绝这种定义（当未声明 `verification_mode: effect_only`
时），而无需实际执行测试。

**Acceptance Scenarios**:

1. **Given** 一个新编写的正式业务步骤（未声明 `verification_mode: effect_only`），其预期结果仅包含
   screen_changed 或 region_changed 条件，**When** 系统加载并校验该测试用例，**Then** 系统在运行前
   拒绝该用例并给出具体错误说明，而不是允许其运行到验证阶段才失败。
2. **Given** 一个正式业务步骤同时包含 screen_changed 条件与至少一个业务结果断言（文本、数值、模板、
   结构化状态或 visual_question），**When** 该步骤执行完毕，**Then** 只有当业务结果断言判定为 passed
   时，该步骤的 StepVerificationResult 才为 passed；单独的 screen_changed 通过不足以使 StepVerificationResult
   为 passed。
3. **Given** 一个测试步骤显式声明 `verification_mode: effect_only`，**When** 该步骤只包含 screen_changed
   条件，**Then** 系统允许该用例通过加载校验，且该步骤 MAY 仅依据动作效果证据判定 StepVerificationResult
   为 passed。

---

### User Story 4 - 错误弹窗不得因画面变化而使业务步骤通过 (Priority: P1)

作为测试工程师，我希望当操作意外触发错误弹窗时，即使弹窗造成了大范围的画面变化，Agent 也不会把这次
画面变化当作业务步骤成功的证据。

**Why this priority**: 这是本次事故中最危险的一环——恢复策略把点击退化成 Tab，触发了错误弹窗；错误
弹窗造成的大面积画面变化反而让 screen_changed 判定通过，让一个失败的操作被记录为"成功"，这比单纯的
误判无效果更具误导性。

**Independent Test**: 使用一组"点击后出现错误弹窗"的固定截图（弹窗造成远超阈值的整屏变化），可独立
验证系统能否将其判定为 unexpected_effect 且不使对应业务步骤通过，而无需真实触发任何弹窗。

**Acceptance Scenarios**:

1. **Given** 一次操作后出现了错误弹窗，整屏画面变化比例远高于配置的变化阈值，**When** 系统判定该动作
   的效果，**Then** 系统判定为 unexpected_effect，而不是 expected_effect。
2. **Given** 某个正式业务步骤的操作后截图中出现错误弹窗，**When** 系统判断该步骤的 StepVerificationResult，
   **Then** 系统不会仅因整屏或局部画面发生了大范围变化就判定该步骤为 passed；该步骤的最终判定 MUST
   反映 unexpected_effect 对应的 failed 或 uncertain 结果。
3. **Given** 一个测试用例的预期结果原本就是"应当出现错误提示"（即错误弹窗本身是该步骤的预期业务结果），
   **When** 系统执行该步骤对应的业务结果断言，**Then** 系统仍按该断言的定义正常判定 passed 或 failed，
   不因为本故事的规则而无差别拒绝所有弹窗场景。

---

### User Story 5 - 鼠标点击只有在存在可验证的焦点导航路径时才允许退化为键盘操作 (Priority: P1)

作为测试工程师，我希望 Agent 的恢复策略在把鼠标点击换成 Tab/Shift+Tab 等键盘序列之前，先证明当前控件
确实可以通过已知的焦点导航路径到达目标，而不是在缺乏依据的情况下无条件发送 Tab。

**Why this priority**: 这是本次事故中触发错误弹窗的直接操作——恢复策略在没有依据的情况下把点击降级为
Tab，导致焦点落到了错误的控件上并触发了错误弹窗。这条规则直接切断了事故的触发路径。

**Independent Test**: 给定一个不存在已知焦点导航路径证据的场景（如恢复上下文中没有记录当前焦点位置或
Tab 序列与目标控件的对应关系），可独立验证系统在该场景下拒绝把点击替换为 Tab，而无需真实执行任何键鼠
动作。

**Acceptance Scenarios**:

1. **Given** 一次鼠标点击动作失败或效果不确定，且系统既没有显式记录的焦点导航序列、也没有验证该序列
   当前仍然有效的方法，**When** 恢复策略选择下一步执行方式，**Then** 系统不得将该点击无条件替换为
   Tab 或其他键盘序列。
2. **Given** 系统已经同时具备（a）显式记录的焦点导航序列（当前焦点到目标控件的具体 Tab/Shift+Tab 步骤）
   与（b）验证该序列当前仍然有效的方法，**When** 恢复策略选择下一步执行方式，**Then** 系统 MAY 采用
   该键盘路径作为替代执行方式。
3. **Given** 既不存在满足上述双重条件的可验证焦点导航路径、鼠标路径也已失败，**When** 系统评估下一步，
   **Then** 系统停止当前动作并按已有的失败分类与恢复框架处理，而不是猜测性地发送键盘序列。

---

### User Story 6 - 显式声明 effect-only 测试步骤 (Priority: P2)

作为测试工程师，我希望能够为确实只关心"画面是否发生了变化"（而非具体业务结果）的测试步骤显式声明
`verification_mode: effect_only`，让这类步骤可以合法地仅依据动作效果证据通过。

**Why this priority**: 在 User Story 3 收紧"正式业务步骤必须有业务结果断言"这一规则之后，仍需要为
"只做探测性点击、验证界面有响应即可"这类合法场景保留一条不被误伤的路径。

**Independent Test**: 使用一个声明 `verification_mode: effect_only` 的测试步骤定义和对应的固定截图对，
可独立验证该步骤能否仅凭动作效果证据（含 screen_changed）判定 StepVerificationResult 为 passed，而
无需业务结果断言。

**Acceptance Scenarios**:

1. **Given** 一个测试步骤在定义中显式声明 `verification_mode: effect_only`，**When** 系统加载该用例，
   **Then** 系统允许该步骤的预期结果仅包含动作效果类条件（如 screen_changed），不要求业务结果断言。
2. **Given** 一个 `verification_mode: effect_only` 步骤执行完毕，动作效果被判定为 expected_effect，
   **When** 系统判断该步骤的 StepVerificationResult，**Then** 系统据此判定该步骤为 passed，且报告中
   明确标注该通过结论仅代表"动作产生了效果"，不代表已验证具体业务结果。
3. **Given** 一个测试步骤省略了 `verification_mode` 字段或声明为除 `effect_only` 以外的值，**When**
   系统加载并校验该步骤，**Then** 系统按默认的正式业务模式处理，不适用 effect-only 的豁免规则。

---

### User Story 7 - 旧用例保持可加载，仅 screen_changed 的旧业务用例产生弱断言警告且判定为 uncertain (Priority: P2)

作为测试工程师，我希望本次改动上线后，此前编写的现有测试用例（包括 pos-buy-bag-checkout.yaml 本身）
仍然可以被加载和执行，不会因为新规则而直接报错失败；但如果某个旧的正式业务步骤只声明了 screen_changed
条件、且未声明 `verification_mode: effect_only`，系统应在给出弱断言警告的同时，将其 StepVerificationResult
判定为 uncertain，而不是悄悄把它当作和有业务结果断言的步骤同等可信的 passed。

**Why this priority**: 这是保护现有测试资产、平滑升级到新规则的必要配套，避免新规则上线当天大批旧用例
无法运行；但同时不能让旧用例继续以"看起来通过、实际不可信"的方式蒙混过关——这正是本次事故中错误弹窗
被误判通过的同一类问题。

**Independent Test**: 使用改动前既有的 pos-buy-bag-checkout.yaml（仅含 screen_changed 条件、未声明
`verification_mode: effect_only`）作为输入，可独立验证系统既能正常加载执行该用例，又能在该步骤最终
判定为 uncertain 的同时输出弱断言警告，而无需先修改该用例文件本身。

**Acceptance Scenarios**:

1. **Given** 一份本 feature 之前编写、仅含 screen_changed / region_changed 条件、未声明
   `verification_mode: effect_only` 的正式业务步骤用例，**When** 系统加载该用例，**Then** 系统正常
   接受并可执行该用例，不因新增校验规则而拒绝加载。
2. **Given** 上述旧步骤在执行后其 screen_changed 条件判定为通过（即 ActionEffect 为 expected_effect），
   **When** 系统给出该步骤的最终 StepVerificationResult，**Then** 系统将该步骤判定为 uncertain（而
   不是 passed），并在结果与报告中附带明确的弱断言警告，说明业务结果未经验证、不能仅凭动作效果证据
   确认为业务通过。
3. **Given** 同一份旧用例，**When** 与一个新编写、包含业务结果断言且最终判定为 passed 的步骤的报告
   并列查看，**Then** 两者的 StepVerificationResult 状态（uncertain 与 passed）本身即清晰可区分，
   弱断言警告的步骤不会被误读为与有业务结果断言的 passed 步骤同等可信。

---

### User Story 8 - 针对购物袋重复添加问题的离线回归测试，不操作真实 VNC (Priority: P3)

作为测试工程师，我希望本次修复配有可重复运行的离线回归测试，完整复现"整屏变化约 0.424%、局部购物车
和件数区域已变化、随后错误弹窗因画面变化被误判通过"这一系列问题，并且这些回归测试和其余自动化测试一样
不需要连接真实 VNC 环境；真实 VNC 上的验证只在最终获得人工批准后单独运行一次。

**Why this priority**: 这是保证本次修复本身可信、可长期防止回归的收尾环节，依赖前述所有故事已经实现，
因此优先级最低，但对于"这个问题以后不会再犯"这一诉求是必要的。

**Independent Test**: 直接运行新增的离线回归测试集（基于固定截图与录制数据），可独立验证其在不连接
真实 VNC 的情况下产生与本次事故修复前后行为一致的判定结果，而无需人工连接测试环境复现。

**Acceptance Scenarios**:

1. **Given** 本次修复交付前既有的全部离线自动化测试，**When** 应用本 feature 的改动后重新运行，**Then**
   全部既有测试继续通过，不出现回归。
2. **Given** 新增的、基于本次事故原始截图构造的离线回归测试（覆盖整屏变化约 0.424%、局部变化、重复点击
   防护、错误弹窗误通过三个环节），**When** 运行该回归测试，**Then** 测试结果证明系统不再重复执行加入
   购物袋动作，也不再让错误弹窗因画面变化而通过。
3. **Given** 本 feature 新增的全部自动化测试，**When** 检查其执行方式，**Then** 这些测试均基于固定
   截图或录制数据离线运行，不发起或依赖真实 VNC 连接。
4. **Given** 需要在真实 VNC 环境上验证本次修复，**When** 团队安排该验证，**Then** 该验证作为独立于
   常规自动化测试运行之外的环节，仅在获得最终人工批准后执行一次，而不是被纳入常规测试流水线自动触发。

---

### Edge Cases

- 整屏变化比例已经达到原有阈值，但该变化实际来自与本步骤操作意图无关的动态噪声（如任务栏时钟跳动、
  加载动画），系统应如何避免把这类无关变化误判为 expected_effect？（应复用已有的动态区域屏蔽机制，
  局部变化证据同样需要排除已知动态噪声区域后再判定。）
- 局部像素变化、OCR 差异、模板变化、页面结构化状态差异这四类证据之间出现矛盾（如像素明显变化但 OCR
  文本完全不变）时，系统应如何给出综合判定，而不是简单地"任一为真即通过"？
- 非幂等动作的类型判定依据不明确（测试步骤既未显式标注也无法从操作意图关键词识别）时，系统应如何
  处理，以避免既不误伤幂等动作、也不放过应受保护的非幂等动作？
- 一个 `verification_mode: effect_only` 步骤在执行过程中意外产生了真实业务副作用（如探测性点击实际上
  也把商品加入了购物车），该情形是否需要额外提示，还是完全按 effect-only 规则处理而不做业务层面的额外
  检查？
- 视觉模型对业务结果的判断本身返回低置信度或矛盾结论、且不存在可比对的确定性业务断言时，系统应如何
  与"仍不确定则返回 effect_uncertain"的规则衔接，避免视觉模型的模糊回答被误当作确定性通过或失败？
  （若存在确定性业务断言，则按 Clarification 2026-07-21 的规则以确定性断言为准，本条边界只适用于
  纯 `visual_question` 断言、无确定性断言可比对的场景。）
- 旧用例中的 screen_changed 条件与其他非业务结果类条件（如 region_changed）组合出现、且仍未声明
  `verification_mode: effect_only` 时，弱断言警告与 uncertain 判定规则应如何适用（判定标准仍是"是否
  包含至少一个业务结果断言"，与条件数量和组合方式无关）？
- 错误弹窗与合法的大范围页面跳转（如提交后跳转到确认页）在画面变化幅度上可能相近，系统应依据什么区分
  二者，避免把合法跳转误判为错误弹窗、或把错误弹窗误判为合法跳转？
- 焦点导航路径证据的有效期问题：若该证据是在较早的观察中记录的，而当前页面结构已经因为中间的其他操作
  发生变化，系统应如何判断该证据是否仍然可信——根据 Clarification 2026-07-21，仅有历史记录不足以视为
  "可验证"，必须同时具备验证该序列当前仍然有效的方法，否则不得采用。

## Requirements *(mandatory)*

### Functional Requirements

**动作效果检测**

- **FR-001**: 系统 MUST 将动作效果判定（ActionEffect：动作是否产生效果）与业务步骤验证结果
  （StepVerificationResult：业务步骤是否满足其 `expected` 定义）作为两个独立的结果分别产生和记录，
  MUST NOT 将二者合并为同一个通过/失败结论。
- **FR-002**: 动作效果判定 MUST NOT 依赖任何页面专用的预先配置固定感兴趣区域（如购物车区域、合计区域）
  作为唯一依据；判定 MUST 能发现画面中任意位置出现的、未被预先配置的局部变化。
- **FR-003**: 动作效果判定 MUST 综合以下至少四类证据：动态定位的局部像素/区域变化、操作前后 OCR 文本
  状态差异、模板匹配状态差异、结构化页面状态差异。当整屏变化比例低于配置的全屏变化阈值，但上述任一
  证据显示明确的局部变化时，系统 MUST NOT 仅因整屏变化比例不达标就判定为 no_effect。
- **FR-004**: 动作效果判定结果（ActionEffect）MUST 是以下四种状态之一：`no_effect`（无可观测变化）、
  `expected_effect`（观测到与该动作意图相符的变化）、`unexpected_effect`（观测到变化但与该动作意图
  不符，例如错误弹窗）、`effect_uncertain`（观测到变化但现有证据不足以判定其性质）。
- **FR-005**: 动作效果判定 MUST 排除已知的动态噪声区域（如任务栏时钟、鼠标指针附近区域、加载动画）
  对局部变化证据的干扰，与 001 已定义的稳定性等待动态区域屏蔽机制保持一致的排除逻辑。
- **FR-006**: `screen_changed` 与 `region_changed` 的判定结果 MUST 被视为"弱动作效果证据"——MAY 作为
  ActionEffect 判定的输入之一，但 MUST NOT 单独作为 StepVerificationResult 判定为 `passed` 的充分
  证据（`verification_mode: effect_only` 步骤除外，见 FR-012）。

**业务结果断言**

- **FR-007**: 正式业务测试步骤（未声明 `verification_mode: effect_only`）MUST 至少包含一个业务结果
  断言，断言类型 MUST 属于以下之一：指定文本出现/消失、指定数值达到预期、指定模板出现/消失、结构化
  页面状态达到预期、或 `visual_question`（视觉模型对明确业务问题的回答）。
- **FR-008**: 系统 MUST 在测试用例加载与格式校验阶段拒绝新建的正式业务步骤——即预期结果仅包含
  `screen_changed` / `region_changed` 类条件、且未显式声明 `verification_mode: effect_only` 的步骤——
  并给出具体字段级错误说明，而不是允许其运行到验证阶段才失败。
- **FR-009**: 只有当业务结果断言判定为 `passed` 时，正式业务步骤的 StepVerificationResult 才 MUST 为
  `passed`；ActionEffect 判定结果（包括 `expected_effect`）MUST NOT 替代业务结果断言的判定。
- **FR-010**: 当确定性业务断言（文本、数值、模板、结构化状态）与视觉模型（`visual_question` 或补充
  判断）的结论出现冲突时，系统 MUST 以确定性业务断言的判定结果为准；视觉模型结论 MUST NOT 推翻已有
  明确结论的确定性断言。

**Effect-only 声明**

- **FR-011**: 系统 MUST 支持测试步骤通过显式字段 `verification_mode: effect_only` 声明为 effect-only
  模式，用于确实只关心画面是否发生变化、不需要业务结果断言的场景；省略该字段或声明为其他值 MUST 被
  视为默认的正式业务模式。
- **FR-012**: 仅当测试步骤显式声明 `verification_mode: effect_only` 时，纯粹的动作效果证据（含
  `screen_changed`）才 MUST 被允许单独作为该步骤 StepVerificationResult 判定为 `passed` 的充分依据；
  未声明该字段的正式业务步骤 MUST NOT 以此方式判定为 `passed`。
- **FR-013**: `verification_mode: effect_only` 步骤的执行结果与报告 MUST 明确标注该 `passed` 结论仅
  代表"动作产生了效果"，不代表已验证具体业务结果，避免与包含业务结果断言的步骤在报告中被同等看待。

**非幂等动作与重复执行防护**

- **FR-014**: 系统 MUST 能识别添加、删除、提交、支付等非幂等动作类型，并将其与可安全重复执行的幂等
  动作区分处理。
- **FR-015**: 当针对某个非幂等动作已经检测到 `no_effect` 以外的某种 ActionEffect（`expected_effect`、
  `unexpected_effect` 或 `effect_uncertain`），且对应 StepVerificationResult 尚未确定为 `passed` 或
  `failed` 时，系统 MUST NOT 再次执行该动作或语义等价的重复动作来尝试"重新达成"该效果。
- **FR-016**: 系统只有在同时满足以下两个条件时才 MAY 再次执行某个非幂等动作：(a) 经加强验证后 ActionEffect
  被可靠地收敛判定为 `no_effect`；(b) 该测试步骤的重试预算（`max_retries` 等）仍有剩余。`effect_uncertain`
  状态本身 MUST NOT 被当作触发重复执行的理由。
- **FR-017**: 当非幂等动作已检测到效果但业务结果不确定时，系统 MUST 先重新观察当前屏幕并执行加强
  验证（如更高分辨率局部复检、追加确定性验证条件），而不是立即重复执行该动作或武断判定通过/失败。
- **FR-018**: 当加强验证仍不能确认业务结果时，系统 MUST 调用视觉模型对明确的业务问题进行判断，作为
  确定性方法之外的补充手段。
- **FR-019**: 当视觉模型判断后业务结果依然无法确认时，系统 MUST 返回 `effect_uncertain`，MUST NOT
  因此重复执行该非幂等动作，也 MUST NOT 将其武断折叠为 `passed` 或 `failed`。

**错误弹窗与键盘降级**

- **FR-020**: 系统 MUST 能将导致大范围画面变化、但与当前步骤操作意图不符的弹窗类变化（含错误弹窗）
  识别为 `unexpected_effect`，而不是默认视为 `expected_effect`；此类画面变化的幅度 MUST NOT 单独作为
  对应 StepVerificationResult 判定为 `passed` 的依据。SQL Server Management Studio 切换或人工误操作
  引起的应用切换类场景不属于本 feature 的 `unexpected_effect` 判定范围（超出本 feature 边界）。
- **FR-021**: 当测试用例的业务结果断言本身就是"应当出现指定错误提示"时，系统 MUST 仍按该断言的定义
  正常判定 `passed` 或 `failed`，FR-020 的规则 MUST NOT 导致此类预期内的提示场景被无差别拒绝。
- **FR-022**: 系统 MUST NOT 在缺乏明确、可验证的焦点导航路径证据的情况下，将原定的鼠标点击动作无条件
  替换为 Tab、Shift+Tab 或其他键盘序列。
- **FR-023**: 只有当系统同时具备 (a) 显式记录的焦点导航序列（当前焦点到目标控件的具体 Tab/Shift+Tab
  步骤）与 (b) 验证该序列当前仍然有效的方法时，才 MAY 将该键盘路径采用为替代执行方式；仅存在历史记录
  而无法验证其当前有效性的情形 MUST 被视为不存在可验证路径。
- **FR-024**: 当既不存在满足 FR-023 双重条件的可验证焦点导航路径、鼠标路径也已失败时，系统 MUST 停止
  当前动作并按既有的失败分类与恢复框架处理，MUST NOT 猜测性地发送键盘序列。

**向后兼容与弱断言警告**

- **FR-025**: 系统 MUST 保持对本 feature 之前编写的既有测试用例的加载能力，MUST NOT 因本 feature
  新增的校验规则（FR-008）导致旧用例无法被加载。
- **FR-026**: 对于本 feature 之前编写、其正式业务步骤的预期结果仅包含 `screen_changed` /
  `region_changed` 类条件、且未声明 `verification_mode: effect_only` 的旧用例，系统 MUST 将该步骤的
  StepVerificationResult 判定为 `uncertain`（而不是 `passed`），并 MUST 同时产生明确的弱断言警告，
  说明该判定仅基于动作效果证据、业务结果未经验证。
- **FR-027**: 弱断言警告与其对应的 `uncertain` 判定 MUST NOT 被静默吞没、省略或在报告中呈现为与包含
  业务结果断言且判定为 `passed` 的步骤同等可信的"业务通过"。

**职责分离**

- **FR-028**: 本 feature 新增的动作效果判定、业务结果断言判定职责 MUST 归属于 Verifier；重复执行
  防护判断（是否可以重新执行某个非幂等动作）MUST 归属于 Executor 或调度该动作的组件，MUST NOT 归属
  于 Verifier 自身发起新的动作执行。
- **FR-029**: Planner 输出语义动作决策的职责与 Grounder 定位目标的职责 MUST 保持不变；本 feature
  MUST NOT 将效果判定、业务结果判定或重复执行防护逻辑合并进 Planner 或 Grounder。

**测试与验证方式**

- **FR-030**: 本 feature 新增的自动化测试 MUST 基于固定截图、录制帧序列或其他可离线重放的证据数据
  运行，MUST NOT 在常规自动化测试执行过程中连接或操作真实 VNC 环境。
- **FR-031**: 系统 MUST 提供覆盖本次购物袋重复添加问题原始场景的离线回归测试，至少包含：整屏变化约
  0.424% 但局部购物车与件数区域已变化的判定场景、第一次点击后购物袋数量从 0 变为 1 后不得重复点击的
  防护场景、错误弹窗因画面大范围变化仍不得通过的场景；该回归测试 MUST 在本 feature 交付前处于通过
  状态。
- **FR-032**: 涉及真实 VNC 环境的验证 MUST 作为独立于常规自动化测试运行的环节，仅在获得最终人工批准
  后执行，MUST NOT 被纳入常规自动化测试流水线中自动触发。

### Key Entities

- **动作效果判定结果（ActionEffect）**：针对一次动作前后观察结果的综合判定输出，取值为
  `no_effect` / `expected_effect` / `unexpected_effect` / `effect_uncertain` 之一，回答"这次动作是否
  产生了效果"，与 StepVerificationResult 相互独立。
- **动作效果证据（Action Effect Evidence）**：ActionEffect 判定的输入，包含动态定位的局部像素/区域
  变化、OCR 状态差异、模板匹配状态差异、结构化页面状态差异，以及各证据是否已排除已知动态噪声区域的
  干扰；`screen_changed` / `region_changed` 属于其中的弱证据。
- **业务步骤验证结果（StepVerificationResult）**：针对某个测试步骤 `expected` 定义的独立判定，取值为
  `passed` / `failed` / `uncertain`，回答"该业务步骤是否满足预期"，只能由业务结果断言（正式业务模式）
  或动作效果证据（仅 effect-only 模式）驱动，MUST NOT 与 ActionEffect 混同。
- **业务结果断言（Business Result Assertion）**：正式业务步骤 MUST 至少包含一个的验证条件，类型限定
  为文本出现/消失、数值达到预期、模板出现/消失、结构化页面状态达到预期、`visual_question` 之一；
  `screen_changed` / `region_changed` 不属于此类型。
- **Effect-only 测试步骤**：测试用例中通过 `verification_mode: effect_only` 显式声明只关心动作效果、
  不需要业务结果断言的步骤，其 `passed` 结论 MUST 在报告中与业务结果断言区分标注。
- **非幂等动作分类（Non-idempotent Action Classification）**：标记某个语义动作是否属于添加、删除、
  提交、支付等重复执行会改变业务状态的动作类别，用于触发重复执行防护规则。
- **重复执行防护决策（Repeat Guard Decision）**：针对某个非幂等动作是否允许再次执行的判定；默认禁止，
  仅当 ActionEffect 被可靠收敛为 `no_effect` 且步骤重试预算允许时才转为允许。
- **弱断言警告（Weak Assertion Warning）**：附加在仅依据动作效果证据（且未声明 effect-only）而被
  判定为 `uncertain` 的旧业务步骤上的明确标注，说明该判定未经业务结果验证；不附加在 `passed` 结论上。
- **焦点导航路径证据（Verified Focus Navigation Path）**：同时包含（a）当前焦点到目标控件的具体
  Tab/Shift+Tab 序列记录与（b）验证该序列当前仍然有效的方法两部分的证据；只有两部分均具备时才允许
  把鼠标点击替换为键盘序列。
- **错误弹窗判定（Error Popup Classification）**：将某次操作后出现的、与操作意图不符的弹窗类变化
  归类为 `unexpected_effect` 的判定结果，独立于该变化的画面幅度大小；不涵盖 SSMS 切换或人工误操作
  引起的应用切换场景。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 在整屏像素变化约 0.424%、但局部购物车与件数区域存在真实变化的固定截图回归测试场景中，
  系统 100% 判定该动作效果为 `expected_effect`，而不是旧行为下的 `no_effect`。
- **SC-002**: 在购物袋重复添加离线回归测试中，第一次点击成功使购物袋数量从 0 变为 1 后，系统在人工
  抽查的全部回归运行中，发出第二次添加点击指令的比例为零。
- **SC-003**: 在"动作已产生效果但业务结果暂时无法确定"的固定截图场景中，系统在给出 `effect_uncertain`
  最终判定之前，均先完成至少一轮加强验证（含必要时的视觉模型判断），且不重复执行该非幂等动作；人工
  抽查中此规则的违反比例为零。
- **SC-004**: 在错误弹窗固定截图回归测试中，无论画面变化幅度多大，对应业务步骤的 StepVerificationResult
  被判定为 `passed` 的比例为零。
- **SC-005**: 在局部变化分别出现于画面九个不同区域（预先构造、位置各异、均未被声明为 ROI）的固定
  截图回归测试集中，系统识别出 `expected_effect` 的比例为 100%。
- **SC-006**: 在覆盖列表更新、表单更新、弹窗出现、页面跳转四类场景的固定截图回归测试集中，系统输出
  的动作效果状态与人工标注的预期结果一致的比例为 100%。
- **SC-007**: 在离线回归测试中，全部仅声明 `screen_changed` / `region_changed` 条件、未声明
  `verification_mode: effect_only` 的正式业务步骤，其 StepVerificationResult 均被判定为 `uncertain`
  并附带弱断言警告；被误判为与业务结果断言步骤同等可信的 `passed` 的比例为零。
- **SC-008**: 本 feature 交付前既有的全部离线自动化测试，在应用本 feature 改动后重新运行时全部继续
  通过，不出现回归。
- **SC-009**: 本 feature 新增的全部自动化测试均基于固定截图或录制数据离线运行，运行过程中发起真实
  VNC 连接的次数为零；真实 VNC 上的验证作为独立环节，仅在获得最终人工批准后运行。
- **SC-010**: 在确定性业务断言与视觉模型判断结论相冲突的固定截图回归场景中，系统最终 StepVerificationResult
  与确定性业务断言的判定结果一致的比例为 100%。

## Assumptions

- 本 feature 建立在 001（VNC 黑盒 GUI 自动化测试核心执行闭环）已定义的实体与流程之上，复用其
  `TestStep`、`StructuredScreen`、`VerificationCondition`、`ActionIteration`、Planner/Grounder/
  Executor/Verifier 职责划分等既有设计；本 feature 不重新定义闭环中观察、定位、执行、等待等环节的
  既有行为，只针对动作效果判定与业务结果验证环节做加固与规则收紧。
- 非幂等动作的分类以显式声明为主（如测试步骤或已知语义动作库中标注该动作类别），辅以对"添加、删除、
  提交、支付"等常见操作意图关键词的默认识别；具体分类规则的实现细节由实现阶段给出，不影响本规格对
  行为本身的要求。
- 错误弹窗的识别综合运用 OCR 关键词、已知弹窗模板库与视觉模型判断，具体判定算法由实现阶段选择，只要
  满足"不得仅因画面变化幅度大就判定为 expected_effect 或使业务步骤通过"这一行为要求即可。
- 视觉模型的调用成本与延迟预算遵循既有宪法"资源约束"条款中"语义验证仅作为最后手段"的路由原则，不
  在本 feature 中单独放宽或收紧。
- 旧业务步骤在缺少业务断言且未声明 `verification_mode: effect_only` 时，其 StepVerificationResult
  判定为 `uncertain` 而非 `passed`（Clarification 2026-07-21）；这意味着此类旧用例在正式模式下默认
  不再能被当作"业务通过"的回归基线，团队 SHOULD 逐步为其补充业务结果断言，或在确实只关心画面变化时
  显式声明 `verification_mode: effect_only`，以恢复 `passed` 判定能力。
- `verification_mode: effect_only` 声明与"非幂等动作"分类是两个独立维度：一个声明
  `verification_mode: effect_only` 的步骤仍然 MAY 对应一个非幂等动作，此时重复执行防护规则
  （FR-014～FR-019）依然适用；effect-only 只影响该步骤是否需要业务结果断言才能判定 `passed`，不豁免
  重复执行防护。
- 本 feature 范围不包含：SQL Server Management Studio 相关场景、应用切换场景、人工误操作的自动
  识别与处理；这些场景的处理留待未来功能规划。
- 本 feature 范围不包含对 001 中 Grounding、键鼠执行、页面稳定等待等环节本身算法的重新设计，仅在
  User Story 5 涉及的"键盘降级前置条件"这一具体决策点上收紧规则。
- 用于验收标准（SC-005、SC-006 等）的固定截图回归测试集由实现阶段基于本次事故的真实截图与人工构造
  的补充场景准备，具体截图数量与来源不在本规格中固化。
