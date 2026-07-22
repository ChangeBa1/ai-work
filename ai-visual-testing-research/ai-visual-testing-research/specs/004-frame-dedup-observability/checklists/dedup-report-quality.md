# 需求质量检查清单：截图去重、缓存安全、性能度量与中文报告

**Purpose**: 评估 feature 004 的需求是否完整、明确、一致、可度量，并足以作为实现与 PR 评审门禁
**Created**: 2026-07-22
**Feature**: [spec.md](../spec.md)

**Note**: 本清单检查需求文本与设计契约的质量，不用于检查实现是否已经工作。

## Requirement Completeness

- [ ] CHK001 是否完整定义了每次成功逻辑采集必须保留的审计字段，以及失败采集尝试必须保留的错误与阶段证据？ [Completeness, Spec §FR-003–004, §FR-044]
- [ ] CHK002 是否明确要求观察、稳定等待、重试、恢复和验证期间的全部逻辑采样进入同一可排序轨迹，而不是只记录步骤前后图片？ [Completeness, Spec §FR-003–004]
- [ ] CHK003 是否为去重决定、缓存命中或未命中、实际分析、模型调用、跳过调用、物理写入和避免写入分别定义了可追溯记录？ [Completeness, Spec §FR-004, §FR-019, §FR-022–030]
- [ ] CHK004 是否完整列出所有不得仅因图片相同而跳过的上下文敏感输入，包括步骤意图、动作历史、验证问题、请求语义、重试策略和相关运行上下文？ [Completeness, Spec §FR-017–018]
- [ ] CHK005 是否完整规定了安全证据图片、私有模型图片和报告副本三种物理用途的引用与计数要求？ [Completeness, Spec §FR-013, §FR-024, §FR-028, §FR-037]
- [ ] CHK006 是否完整列出中文报告的主要可见区域、状态、错误、空值、警告和性能字段，足以发现资源字典遗漏？ [Completeness, Spec §FR-031–036, User Story 4]

## Requirement Clarity

- [ ] CHK007 “完全相同”是否以 run/session/相邻关系、full-screen/ROI、坐标、分辨率、像素格式、遮罩身份、规范化像素和逐像素比较无歧义定义？ [Clarity, Spec §FR-006–008]
- [ ] CHK008 是否明确区分 `content_hash` 候选匹配、逐像素最终裁决、稳定性阈值 diff 和 `changed_since_last` 四种不同语义？ [Clarity, Spec §FR-008, §FR-012, §FR-020]
- [ ] CHK009 是否为 OCR、模板、diff、视觉描述的缓存身份分别定义足以阻止跨 ROI、遮罩配置、分析配置和模型版本误命中的字段？ [Clarity, Spec §FR-015–018, Plan §Implementation Strategy 3]
- [ ] CHK010 是否明确说明每个重复逻辑帧必须拥有独立 frame id、时间戳和步骤关联，同时复用哪些物理路径及来源关系？ [Clarity, Spec §FR-003, §FR-011, §FR-020]
- [ ] CHK011 是否明确界定正常报告构建对 `report_frames` 的零副本要求，以及旧制品、缺失证据或非安全来源是否允许任何例外处理？ [Clarity, Spec §FR-009, §FR-037, Edge Cases]

## Requirement Consistency

- [ ] CHK012 物理去重要求是否与“每次运行保留完整采集轨迹”的审计要求一致，没有把减少文件数量误写成减少逻辑记录？ [Consistency, Spec §FR-003–004, §FR-009–014]
- [ ] CHK013 内容分析复用要求是否与 Observe → Act → Verify 独立性一致，没有允许缓存命中替代操作后观察或 Verifier 结论？ [Consistency, Spec §FR-002, §FR-017–022]
- [ ] CHK014 稳定性需求是否同时保持“重复帧计入采样数”和“严格像素变化不等于稳定性阈值变化”两项语义？ [Consistency, Spec §FR-010, §FR-014, §FR-020, SC-004]
- [ ] CHK015 ActionEffect/Verifier 的无效果、失败和不确定语义是否与缓存和去重需求一致，明确禁止画面未变时自动通过？ [Consistency, Spec §FR-002, §FR-021, SC-003]
- [ ] CHK016 JSON 中英文机器契约保持不变的要求，是否与 HTML 中文 display 值、CSS class 和 data marker 保持稳定的要求相互一致？ [Consistency, Spec §FR-031–036, SC-007–008]

## Acceptance Criteria Quality

- [ ] CHK017 10 张相同图片与第 11 张单像素变化的验收标准，是否同时量化逻辑帧、唯一帧、重复帧、物理文件、避免写入和实际分析次数？ [Measurability, Spec §SC-001–002, §SC-006]
- [ ] CHK018 不同 ROI、遮罩身份、配置、模型版本和验证问题的缓存隔离标准，是否规定了可客观判定的零错误命中目标？ [Measurability, Spec §SC-002–003]
- [ ] CHK019 性能汇总的守恒关系、三种输出一致性和异常完整性，是否都有明确的 100% 或零伪造判定标准？ [Acceptance Criteria, Spec §SC-005]
- [ ] CHK020 中文 HTML 的覆盖率标准是否区分“必须中文化的用户界面文本”和“允许保留的机器值、原始错误码及原始详情”？ [Acceptance Criteria, Spec §FR-032–034, SC-007]
- [ ] CHK021 JSON 兼容性标准是否明确旧键、类型、枚举、字段语义和允许新增字段的比较边界，而非仅使用“向后兼容”笼统措辞？ [Acceptance Criteria, Spec §FR-035, SC-008]

## Scenario Coverage

- [ ] CHK022 主要路径是否覆盖唯一帧首次保存、连续重复帧、单像素变化和报告证据复用四个阶段？ [Coverage, Spec §User Story 1]
- [ ] CHK023 交替路径是否覆盖相同像素但不同 ROI、不同遮罩配置、跨 run/session 和非相邻截图？ [Coverage, Spec §FR-007–013, Edge Cases]
- [ ] CHK024 异常与恢复路径是否覆盖 hash、像素比较、cache get、cache put、遮罩编码和物理持久化失败，并明确每类是否降级或中止？ [Coverage, Exception/Recovery, Spec §FR-029, §FR-044, Edge Cases]
- [ ] CHK025 上下文敏感路径是否覆盖相同画面配不同验证问题、不同动作历史和不同重试上下文，足以阻止错误答案复用？ [Coverage, Spec §FR-017–018, User Story 2]
- [ ] CHK026 是否为至少两个互不相关 GUI 场景定义了共同契约与不同交互路径，而不是只要求两个名称不同的同构 fixture？ [Coverage, Spec §FR-042, SC-009–010]

## Edge Case Coverage

- [ ] CHK027 是否定义 content hash 碰撞但像素不同、相同像素但 PNG 编码不同、像素格式不同三类边界的预期需求语义？ [Edge Case, Spec §FR-006–008, Edge Cases]
- [ ] CHK028 是否规定安全证据路径缺失、损坏、越界、用途错误或遮罩身份不匹配时的报告要求，并禁止静默选择私有路径？ [Edge Case, Security, Spec §FR-013, §FR-037, Edge Cases]
- [ ] CHK029 是否明确 `total_capture_count=0`、阶段从未开始、阶段部分失败和报告输出失败时的 null、状态与汇总语义？ [Edge Case, Spec §FR-027–030, Edge Cases]
- [ ] CHK030 是否明确未知 locale、未知错误码、原始错误详情含中文或 HTML 特殊字符时的需求边界？ [Edge Case, Spec §FR-031, §FR-034–036, Edge Cases]

## Non-Functional Requirements

- [ ] CHK031 性能需求是否定义了可重复的固定工作负载、独立调用计数事实来源和禁止依赖网络耗时的约束？ [Performance, Spec §FR-040, SC-006, Plan §Implementation Strategy 10]
- [ ] CHK032 每个阶段的计时边界、聚合方式、调用计数口径和 failed/cancelled/unavailable 状态是否足够明确以支持独立复算？ [Observability, Spec §FR-023–030]
- [ ] CHK033 `report_build` 是否有不包含自身最终写盘的明确测量边界，避免性能报告产生自引用或估算值？ [Clarity, Observability, Plan §Implementation Strategy 6]
- [ ] CHK034 UTF-8 要求是否覆盖 HTML、JSON、资源字典、测试名称和错误详情，并提供可客观识别乱码、替换字符或内容丢失的标准？ [Localization, Spec §FR-036, SC-007]
- [ ] CHK035 缓存内存约束是否明确为最近 3～5 个逻辑帧、定义淘汰与 session reset，并禁止缓存持有无界图片数据或完整上下文对象？ [Resource Constraint, Spec §Assumptions, Plan §Implementation Strategy 3]

## Dependencies & Assumptions

- [ ] CHK036 核心业务无关要求是否覆盖 domain、runtime、planning、grounding、execution、verification、reporting、recovery 和 config，并明确禁止场景专用字段、关键词与流程分支？ [Constitution VI, Spec §FR-005]
- [ ] CHK037 场景语义只允许存在于 testcase、fixture 或通用注册 profile 的边界是否写入需求，而不是仅作为实现者默认假设？ [Constitution VI, Dependency, Spec §FR-042]
- [ ] CHK038 “两个场景互不相关”的判定维度、共享契约和必须保留的独立验证证据是否有明确要求？ [Constitution VI, Assumption, Spec §FR-042, SC-009–010]

## Ambiguities & Conflicts

- [ ] CHK039 “实际模型调用”“分析调用”“缓存命中”“确定性跳过”的术语和计数关系是否在规格、计划和遥测契约中使用同一口径？ [Ambiguity/Consistency, Spec §FR-019, §FR-025, Contract §telemetry]
- [ ] CHK040 物理图片数量按实际文件计数的澄清，是否与无掩码共享文件、有掩码安全/私有双文件以及正常报告副本为零的要求完全一致？ [Conflict Check, Spec §FR-024, §FR-028, §FR-037]

## Notes

- Check items off as completed: `[x]`
- Add comments or findings inline
- Link findings back to the affected requirement, plan section, or contract
- Items are numbered sequentially for review traceability
