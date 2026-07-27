# Feature Specification: 目标未找到的局部放大重定位恢复（zoom_reground）

**Feature Branch**: `014-target-not-found-zoom-recovery`

**Created**: 2026-07-26

**Status**: Draft

**Input**: User description: "真实运行 25980277 中，步骤反复以 `action policy stop:
FailureType.TARGET_NOT_FOUND` 失败。recovery 对 target_not_found 目前只有 recapture
（重截图再试一次），对『目标真实存在但太小 / OCR 读不出 / grounder 全屏看不清』的场景无力。
总体设计 §9.2 深度路径与 §9.3 Active Observer 规定了『局部裁剪 + 局部放大 + 重新
OCR/Grounding』的观察动作，但代码里没有实现。需要为 target_not_found 与
grounding_low_confidence 增加一档升级恢复策略 zoom_reground。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 小目标经局部放大后被成功定位 (Priority: P1)

测试工程师的用例点击一个在全屏截图上只占十几个像素的小按钮。全屏 Grounding 找不到它
（或置信度过低），第一次恢复重截图后仍然找不到。工程师期望系统自动把可疑区域裁剪出来、
放大一倍分辨率、对放大图重新 OCR 与 Grounding，并用还原到原图坐标的结果重新走动作
决策，最终点击落在原始屏幕上的正确像素位置。

**Why this priority**: 这是本 feature 的直接动因（真实运行 25980277 的反复
`TARGET_NOT_FOUND` 假失败）；不解决则小字号/低对比 GUI 上的用例持续失败。

**Independent Test**: 离线 e2e——脚本化 Grounder 对全屏请求一律 `found=false`，对放大
请求返回放大图坐标系内的高置信候选；断言最终点击坐标等于按 `bbox/scale + crop_offset`
还原后的原图坐标，且 recovery_attempts 中出现 `zoom_reground` 记录（含 ROI、缩放因子）。

**Acceptance Scenarios**:

1. **Given** 全屏 Grounding 失败一次并已执行 recapture 恢复，**When** 同一步骤内再次发生
   `target_not_found` / `grounding_low_confidence`，**Then** 系统执行一次 zoom_reground：
   确定 ROI → ROI 截图/裁剪 → 按配置倍率（默认 2x）放大 → 对放大图重新 OCR →
   重新 Grounding → 重新走既有 action policy。
2. **Given** 放大图上的 Grounding 候选 bbox（像素坐标系或 normalized_1000），**When** 还原
   到原图坐标，**Then** 结果精确等于 `round(bbox/scale) + crop_offset`，且越界/退化结果被
   严格拒绝（不 clamp、不猜）。
3. **Given** zoom_reground 成功产出可执行动作，**When** 执行并验证通过，**Then** 步骤按既有
   路径判 passed，不引入任何新的最终态语义。

---

### User Story 2 - 升级失败后按既有恢复路径终结 (Priority: P1)

zoom_reground 也没能定位目标时（放大图 Grounding 仍失败、或 ROI 无法确定），系统必须
沿既有恢复路径继续（re_ground/第二候选/键盘路径/step 失败），在既有 Tier-1/Tier-2 预算
内终结，不得引入新的无限重试。

**Why this priority**: 恢复升级绝不能变成新的重试黑洞——预算与终结性是 Constitution I
的红线。

**Independent Test**: 离线 e2e——Grounder 全程 `found=false`（含放大请求）；断言 run 以
failed 终结、zoom_reground 每步至多出现配置的次数（默认 1 次）、其后的恢复策略回到
既有序列。

**Acceptance Scenarios**:

1. **Given** zoom_reground 已在本步骤消耗完每步上限（默认 1 次），**When** 同类失败再次
   发生，**Then** 恢复选择既有的后续策略（re_ground），不再产生新的放大观察。
2. **Given** ROI 无法确定（无历史候选、锚点文本未命中），**When** 恢复升级轮到
   zoom_reground，**Then** 直接跳过升级、采用既有序列中的下一策略，不做盲目网格扫描。
3. **Given** 步骤 Tier-1 预算耗尽，**When** 任何失败再发生，**Then** 步骤按既有语义失败，
   run 终结，无新增循环。

---

### User Story 3 - 恢复过程完全可审计 (Priority: P2)

测试工程师在报告中要能看到：每次 zoom_reground 的策略名、选用的 ROI、ROI 来源
（历史候选 / 锚点文本）、缩放因子、策略是否执行成功；放大截图按既有 artifact 惯例落盘
可供报告引用；模型调用审计记录包含放大请求的坐标变换标识。

**Why this priority**: 观察动作改变了送模型的图像与坐标系，没有审计就无法排查坐标
还原错误——而坐标正确性是本 feature 红线。

**Independent Test**: 单测/e2e 断言 `RecoveryAttempt` 含 `strategy="zoom_reground"`、
`roi`、`scale_factor`、`roi_source`、`resolved` 字段；放大图物理文件存在于 run 的
artifact 目录。

**Acceptance Scenarios**:

1. **Given** 一次 zoom_reground 恢复，**When** 查看该 iteration 的 recovery_attempts，
   **Then** 记录含策略名、ROI 四元组、缩放因子、ROI 来源与 resolved 标志。
2. **Given** 放大观察已执行，**When** 查看 run artifact 目录，**Then** 放大截图（安全
   遮罩版本）已落盘；配置了遮罩且允许私有持久化时另存未遮罩模型版本。

---

### Edge Cases

- ROI 候选 bbox 部分越界（这正是 target_not_found 的常见成因）：ROI 作为观察窗口
  允许被平移/收缩到屏幕范围内（这不是点击坐标，不违反严格拒绝语义）；收缩后小于
  最小尺寸时按最小尺寸在屏幕内重排。
- 放大图 Grounding 候选还原后越界原图：候选被拒绝（不 clamp），结果按
  `target_not_found` 继续既有恢复路径。
- 还原后 bbox 退化（x1>=x2 或 y1>=y2）：拒绝该候选。
- `nearby_texts` 在 OCR 结果中命中多条：取置信度最高的一条作为锚点（确定性规则）。
- 驱动不支持 ROI 抓屏（返回全屏）：观察层在内存中裁剪同一 ROI，语义不变。
- ROI 抓屏/编码/落盘失败：本次放大观察放弃，Grounding 按原全屏路径继续（fail-open
  到既有行为，绝不让升级路径引入新的致命失败）。
- 遮罩区域与 ROI 相交：安全落盘版本必须应用遮罩（遮罩矩形按裁剪偏移平移并按缩放
  因子放大）；送模型版本遵循既有 FR-049（未遮罩），仅在私有持久化被禁止时退回遮罩版。
- 同类失败发生在 RepeatGuard 阻断分支（无本轮 grounding 上下文）：ROI 无法确定 →
  跳过升级（Edge 同 US2-2）。
- zoom_reground 请求已设置但下一迭代未走 Grounding 路径（如 OCR 唯一命中直接解析）：
  请求在步骤结束时丢弃，不跨步骤泄漏。

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001（策略引入）**: 系统 MUST 为 `target_not_found` 与 `grounding_low_confidence`
  增加升级恢复策略 `zoom_reground`，插入既有策略序列中首选策略之后：
  `target_not_found: [recapture, zoom_reground, re_ground]`；
  `grounding_low_confidence: [second_candidate, zoom_reground, re_ground]`。
  首次恢复行为（recapture / second_candidate）MUST 保持不变。
- **FR-002（ROI 确定顺序）**: zoom_reground 的 ROI MUST 按以下确定性顺序选取：
  1. 上次 Grounding 失败时置信度最高的候选 bbox，按配置外扩因子（默认 2.0，即
     宽高各放大到 2 倍）居中外扩；
  2. 无候选时，`target.nearby_texts` 在当前屏幕 OCR 结果中命中的锚点文本 bbox
     （多条命中取置信度最高者）按外扩因子的 2 倍外扩为邻域；
  3. 两者都不可用时 MUST 放弃升级，直接采用既有序列中的下一策略——**不做网格扫描**
     （决策见 Clarifications 决策 2）。
  ROI MUST 收缩/平移到屏幕范围内且不小于配置的最小尺寸（默认 64px）。
- **FR-003（放大观察）**: 系统 MUST 执行 ROI 截图（驱动支持时）或对当前帧内存裁剪，
  按配置缩放因子（默认 2.0）放大，对放大图重新 OCR（OCR 结果 bbox MUST 还原为原图
  坐标），并以放大图为输入重新调用 Grounding。
- **FR-004（坐标还原红线）**: 放大图上得到的任何 bbox MUST 精确还原为原图像素坐标：
  先在放大图坐标系完成 coordinate_space 解析（pixel / normalized_1000，分辨率为放大图
  尺寸），再按 `round(v / scale_factor) + crop_offset` 还原。还原结果越界原图或退化时
  MUST 拒绝该候选（不 clamp、不猜）；`resolve_pixel_bbox` 的既有严格拒绝语义 MUST
  原样保留。Grounding 请求侧 MUST 新增 `scale_factor`（默认 1.0，兼容既有调用）与
  `original_resolution`（还原后校验边界）字段。
- **FR-005（重新走 action policy）**: 还原后的 Grounding 结果 MUST 通过既有
  `ActionPolicy.resolve` 接口重新决策（含在界过滤、置信度分类、OCR 一致性校验），
  MUST NOT 绕过或修改 action policy。
- **FR-006（预算）**: zoom_reground 每 TestStep 至多执行可配置次数（默认 1）；每次执行
  MUST 消耗既有全局恢复预算（Tier-1 shared budget）并计入对应 FailureType 的 Tier-2
  预算。预算耗尽或 ROI 不可确定时 MUST 回落到既有序列的下一策略。系统 MUST NOT
  引入任何新的无限重试路径。
- **FR-007（配置）**: zoom_reground 参数 MUST 配置在 `config/agent.yaml` 的 `recovery`
  段（`recovery.zoom_reground`），含 `max_per_step`（默认 1）、`scale_factor`（默认
  2.0）、`roi_expand_factor`（默认 2.0）、`min_roi_size_px`（默认 64），并有配置模型
  校验；缺省时全部取默认值（不破坏既有配置文件）。
- **FR-008（可观测性）**: `RecoveryAttempt` MUST 新增可选字段 `roi`（四元组）、
  `scale_factor`、`roi_source`（`grounding_candidate` | `anchor_text`），
  zoom_reground 尝试 MUST 填充这些字段并沿既有 recovery_attempts 链路进入 JSON/HTML
  报告。放大截图 MUST 按既有 artifact 惯例落盘（安全遮罩版本始终落盘；未遮罩模型
  版本遵循既有私有持久化开关）。放大请求的模型调用审计 MUST 包含缩放因子与裁剪
  偏移的坐标变换标识。
- **FR-009（既有语义不回退）**: 本 feature MUST NOT 修改：`planning/action_policy.py`、
  `verification/`、OCR 引擎选择逻辑（feature 010）、planner-skip（feature 009）与
  缓存接线（feature 008）。既有恢复策略（recapture / second_candidate /
  switch_to_keyboard / restart_step 等）语义不变；`allows_action_path_change=false`
  的部署 MUST 同样禁止 zoom_reground（它是 path-changing 策略）。
- **FR-010（业务无关性）**: ROI 确定、放大、坐标还原逻辑 MUST 完全基于通用几何与
  通用感知结构（bbox、OCR 文本、置信度），MUST NOT 引入任何被测应用专用词汇
  （Constitution VI）。

### Key Entities

- **ZoomRegroundPlan**: 一次放大重定位计划——ROI 四元组（原图坐标）、缩放因子、
  ROI 来源；由恢复引擎产出、运行时在下一迭代消费（一次性）。
- **ZoomObservation**: 一次放大观察的产物——放大图 artifact 路径、`crop_offset`、
  `scale_factor`、放大图分辨率、已还原到原图坐标的 OCR 结果。
- **RecoveryAttempt（扩展）**: 新增 `roi` / `scale_factor` / `roi_source` 可选字段。
- **ZoomRegroundConfig（配置）**: `recovery.zoom_reground` 段的
  `max_per_step` / `scale_factor` / `roi_expand_factor` / `min_roi_size_px`。
- **GroundingRequest（扩展）**: 新增 `scale_factor`（默认 1.0）与
  `original_resolution`（默认 None）字段。

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 复现 25980277 形态的离线场景（全屏 Grounding 失败 → recapture 后仍失败）
  中，zoom_reground 使用放大图候选完成定位，最终点击坐标与手工计算的
  `round(bbox/scale)+offset` 还原值逐像素一致。
- **SC-002**: 坐标还原单测覆盖：缩放+偏移组合、normalized_1000 在放大图分辨率下的
  解析、越界拒绝、退化拒绝、scale=1/offset=0 恒等——100% 通过。
- **SC-003**: zoom_reground 在任一 TestStep 内出现次数 ≤ 配置上限（默认 1）；升级失败
  后 run 在既有预算内以 failed 终结，无新增重试循环。
- **SC-004**: 每次 zoom_reground 的 recovery_attempts 记录 100% 含策略名、ROI、缩放
  因子、ROI 来源、resolved；放大截图物理文件 100% 落盘。
- **SC-005**: 既有测试套件（unit / fixtures / e2e）全部保持通过（HTML golden 快照因
  RecoveryAttempt 新增字段按其自带流程重新生成属预期内变更）。

## Clarifications（全自动流程，代替 /speckit-clarify）

### 决策 1：zoom_reground 以『恢复旗标 + 下一迭代消费』方式接线

与既有 `second_candidate` / `prefer_keyboard` 升级旗标同构：恢复引擎在失败迭代末尾
产出 `ZoomRegroundPlan`，下一 ActionIteration 的 Grounding 分支一次性消费它，用放大
观察替换本次 Grounding 的输入图像。这样 zoom 路径天然复用『重新观察 → 重新
policy.resolve → 执行 → 独立验证』的完整闭环（Constitution IV），不在恢复处理器内
另造一条执行链。代价是多一次迭代（消耗 Tier-1 预算），与既有升级策略一致。

### 决策 2：ROI 不可确定时放弃升级，不做网格扫描

粗网格（2x2/3x3）逐块 Grounding 每块都是一次真实模型调用：3x3 最坏 9 次调用、约
9×(截图+OCR+Grounding) 的时延，且无先验时块内命中率低、还原错误面扩大。收益/成本
比明显劣于『放弃升级、走既有 re_ground/键盘/失败路径』。故 FR-002 规定顺序 a/b 均
不可用时直接跳过升级（记录在案），网格扫描不进入本 feature（如未来需要，可作为带
独立硬上限的新策略提案）。

### 决策 3：坐标还原顺序为『先空间解析、后缩放偏移还原』

normalized_1000 坐标只能相对模型实际看到的图像（即放大图）解析；因此
`GroundingRequest.resolution` 语义定为『送模型图像的分辨率』，先由既有
`resolve_pixel_bbox` 在该分辨率下严格解析/拒绝，再做 `round(v/scale)+offset` 还原，
最后按 `original_resolution` 校验拒绝越界。既有全屏调用 `scale=1, offset=(0,0),
resolution=全屏` 下行为逐字节不变。这同时修正了旧链路中『先加 offset 再做空间解析』
在 crop+normalized 组合下的潜在双重变换错误（旧组合在生产中从未出现，offset 恒为 0）。

### 决策 4：每步上限默认 1 次、消耗全局预算

放大观察包含 1 次截图 + 1 次 OCR + 1 次 Grounding 调用，成本≈一次常规迭代；每步 1 次
已覆盖『小目标看不清』的主场景，重复放大同一 ROI 无新信息。上限可配置
（`max_per_step`，设 0 即完全停用），且每次执行消耗既有共享预算，保证终结性由既有
StepController 单点裁决。

### 决策 5：锚点邻域取外扩因子的 2 倍

锚点文本（nearby_texts）在目标附近而非目标之上，邻域必须比『候选 bbox 外扩』更宽；
取 `roi_expand_factor * 2`（默认即 4 倍锚点 bbox 尺寸）并受最小尺寸/屏幕边界约束，
是无额外配置项的确定性规则。

### 决策 6：HTML golden 快照允许再生成

RecoveryAttempt 新增字段会改变 golden 报告中恢复尝试的渲染文本；按该快照测试自带的
再生成流程（删除后重跑生成）更新，属预期内、可审计的变更（SC-005）。

## Assumptions

- 真实 VNC 驱动的 `capture_region` 可用；不可用/返回全屏时内存裁剪路径语义等价
  （Edge Cases 已覆盖）。
- 2x 放大对『小目标 OCR/Grounding 读不出』场景有实质改善（overall_design §9.3 的
  zoom 观察动作即为此设计）；倍率可配置以便部署侧调优。
- `GroundingRequest.crop_offset` 与 `ScreenFrame.crop_offset` 既有字段语义
  （裁剪原点，原图坐标）保持不变；缩放因子为本 feature 新增（既有链路无
  `scale_factor` 字段）。
- 恢复引擎的 Tier-2 预算与 step 级策略推进机制（`_step_strategy_index`）保持既有
  语义，zoom_reground 只是策略表中的新条目。
