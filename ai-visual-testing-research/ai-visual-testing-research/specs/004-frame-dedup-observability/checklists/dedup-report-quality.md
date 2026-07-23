# 需求质量检查清单：截图去重、缓存安全、性能度量与中文报告

**Purpose**: 评估 feature 004 的需求是否完整、明确、一致、可度量，并足以作为实现与 PR 评审门禁
**Created**: 2026-07-22
**Feature**: [spec.md](../spec.md)

**Note**: 本清单检查需求文本与设计契约的质量，不用于检查实现是否已经工作。

## Requirement Completeness

- [x] CHK001 是否完整定义了每次成功逻辑采集必须保留的审计字段，以及失败采集尝试必须保留的错误与阶段证据？ [Completeness, Spec §FR-003–004, §FR-044] — 证据：`spec.md` §FR-003–004、Key Entities/Logical Frame；`data-model.md` §4、§13；`contracts/frame-capture-contract.md` §Capture response。
- [x] CHK002 是否明确要求观察、稳定等待、重试、恢复和验证期间的全部逻辑采样进入同一可排序轨迹，而不是只记录步骤前后图片？ [Completeness, Spec §FR-003–004] — 证据：`spec.md` §FR-003、§FR-039；`contracts/report-contract.md` §frames[]；`tasks.md` T025、T057、T061。
- [x] CHK003 是否为去重决定、缓存命中或未命中、实际分析、模型调用、跳过调用、物理写入和避免写入分别定义了可追溯记录？ [Completeness, Spec §FR-004, §FR-019, §FR-022–030] — 证据：`spec.md` §FR-004、§FR-019、§FR-022–030；`data-model.md` §9–11；`contracts/telemetry-contract.md` §Stable structured-log events、§Counter definitions。
- [x] CHK004 是否完整列出所有不得仅因图片相同而跳过的上下文敏感输入，包括步骤意图、动作历史、验证问题、请求语义、重试策略和相关运行上下文？ [Completeness, Spec §FR-017–018] — 证据：`spec.md` §FR-017–019 的三角色身份矩阵；`data-model.md` §6A；`contracts/perception-cache-contract.md` §Explicit exclusions、§Role-specific request/context identity。
- [x] CHK005 是否完整规定了安全证据图片、私有模型图片和报告副本三种物理用途的引用与计数要求？ [Completeness, Spec §FR-013, §FR-024, §FR-028, §FR-037] — 证据：`spec.md` §FR-013、§FR-024、§FR-028、§FR-037；`data-model.md` §3、§11；`contracts/frame-capture-contract.md` §Artifact safety。
- [x] CHK006 是否完整列出中文报告的主要可见区域、状态、错误、空值、警告和性能字段，足以发现资源字典遗漏？ [Completeness, Spec §FR-031–036, User Story 4] — 证据：`spec.md` §FR-031–036；`contracts/report-contract.md` §Resource registry contract、§Error localization；`tasks.md` T050–T051。

## Requirement Clarity

- [x] CHK007 “完全相同”是否以 run/session/相邻关系、full-screen/ROI、坐标、分辨率、像素格式、遮罩身份、规范化像素和逐像素比较无歧义定义？ [Clarity, Spec §FR-006–008] — 证据：`spec.md` §FR-006–008；`contracts/frame-capture-contract.md` §Exact duplicate decision；`research.md` R2。
- [x] CHK008 是否明确区分 `content_hash` 候选匹配、逐像素最终裁决、稳定性阈值 diff 和 `changed_since_last` 四种不同语义？ [Clarity, Spec §FR-008, §FR-012, §FR-020] — 证据：`spec.md` §FR-008、§FR-012、§FR-020；`plan.md` §Implementation Strategy 1、4；`research.md` R2、R8。
- [x] CHK009 是否为 OCR、模板、diff、视觉描述的缓存身份分别定义足以阻止跨 ROI、遮罩配置、分析配置和模型版本误命中的字段？ [Clarity, Spec §FR-015–018, Plan §Implementation Strategy 3] — 证据：`data-model.md` §5；`contracts/perception-cache-contract.md` §Cacheable components、§Configuration/model invalidation；`plan.md` §Implementation Strategy 3。
- [x] CHK010 是否明确说明每个重复逻辑帧必须拥有独立 frame id、时间戳和步骤关联，同时复用哪些物理路径及来源关系？ [Clarity, Spec §FR-003, §FR-011, §FR-020] — 证据：`spec.md` §FR-003、§FR-011、§FR-020；`data-model.md` §4；`contracts/frame-capture-contract.md` §Logical/physical invariants。
- [x] CHK011 是否明确界定正常报告构建对 `report_frames` 的零副本要求，以及旧制品、缺失证据或非安全来源是否允许任何例外处理？ [Clarity, Spec §FR-009, §FR-037, Edge Cases] — 证据：`spec.md` §FR-037、Edge Cases；`contracts/report-contract.md` §Safe evidence contract；`plan.md` §Implementation Strategy 6。

## Requirement Consistency

- [x] CHK012 物理去重要求是否与“每次运行保留完整采集轨迹”的审计要求一致，没有把减少文件数量误写成减少逻辑记录？ [Consistency, Spec §FR-003–004, §FR-009–014] — 证据：Constitution §资源约束、§制品与可观测性；`spec.md` Clarification 6、§FR-003–004、§FR-009–014；`data-model.md` §3–4。
- [x] CHK013 内容分析复用要求是否与 Observe → Act → Verify 独立性一致，没有允许缓存命中替代操作后观察或 Verifier 结论？ [Consistency, Spec §FR-002, §FR-017–022] — 证据：Constitution Principle IV；`spec.md` §FR-002、§FR-017–022；`contracts/perception-cache-contract.md` §Explicit exclusions。
- [x] CHK014 稳定性需求是否同时保持“重复帧计入采样数”和“严格像素变化不等于稳定性阈值变化”两项语义？ [Consistency, Spec §FR-010, §FR-014, §FR-020, SC-004] — 证据：`spec.md` §FR-010、§FR-014、§FR-020、§SC-004；`plan.md` §Implementation Strategy 4；`research.md` R8。
- [x] CHK015 ActionEffect/Verifier 的无效果、失败和不确定语义是否与缓存和去重需求一致，明确禁止画面未变时自动通过？ [Consistency, Spec §FR-002, §FR-021, SC-003] — 证据：`spec.md` User Story 2 scenario 4、§FR-002、§FR-021、§SC-003；`tasks.md` T031、T039。
- [x] CHK016 JSON 中英文机器契约保持不变的要求，是否与 HTML 中文 display 值、CSS class 和 data marker 保持稳定的要求相互一致？ [Consistency, Spec §FR-031–036, SC-007–008] — 证据：`spec.md` §FR-031–036、§SC-007–008；`contracts/report-contract.md` §Display fields、§Resource registry contract、§Backward compatibility rule。

## Acceptance Criteria Quality

- [x] CHK017 10 张相同图片与第 11 张单像素变化的验收标准，是否同时量化逻辑帧、唯一帧、重复帧、物理文件、避免写入和实际分析次数？ [Measurability, Spec §SC-001–002, §SC-006] — 证据：`spec.md` User Story 1 scenarios 1–2、§SC-001–002、§SC-006；`plan.md` §Performance Goals；`tasks.md` T025、T029。
- [x] CHK018 不同 ROI、遮罩身份、配置、模型版本和验证问题的缓存隔离标准，是否规定了可客观判定的零错误命中目标？ [Measurability, Spec §SC-002–003] — 证据：`spec.md` §SC-002 明确错误内容命中为 0、§SC-003 明确上下文错误复用/skip 为 0；`tasks.md` T026、T030。
- [x] CHK019 性能汇总的守恒关系、三种输出一致性和异常完整性，是否都有明确的 100% 或零伪造判定标准？ [Acceptance Criteria, Spec §SC-005] — 证据：`spec.md` §FR-026、§FR-029–030、§SC-005；`contracts/telemetry-contract.md` §Conservation checks、§Test oracle。
- [x] CHK020 中文 HTML 的覆盖率标准是否区分“必须中文化的用户界面文本”和“允许保留的机器值、原始错误码及原始详情”？ [Acceptance Criteria, Spec §FR-032–034, SC-007] — 证据：`spec.md` §FR-032–034、§SC-007；`contracts/report-contract.md` §Resource registry contract；`tasks.md` T051。
- [x] CHK021 JSON 兼容性标准是否明确旧键、类型、枚举、字段语义和允许新增字段的比较边界，而非仅使用“向后兼容”笼统措辞？ [Acceptance Criteria, Spec §FR-035, SC-008] — 证据：`spec.md` §FR-035、§SC-008；`contracts/report-contract.md` §Backward compatibility rule、§Compatibility tests；`tasks.md` T052、T057。

## Scenario Coverage

- [x] CHK022 主要路径是否覆盖唯一帧首次保存、连续重复帧、单像素变化和报告证据复用四个阶段？ [Coverage, Spec §User Story 1] — 证据：`spec.md` User Story 1 scenarios 1–4、User Story 4 scenario 6；`tasks.md` T014–T015、T025、T054。
- [x] CHK023 交替路径是否覆盖相同像素但不同 ROI、不同遮罩配置、跨 run/session 和非相邻截图？ [Coverage, Spec §FR-007–013, Edge Cases] — 证据：`spec.md` User Story 1 scenario 3、User Story 2 scenario 6、§FR-007–013、Edge Cases；`tasks.md` T015、T026。
- [x] CHK024 异常与恢复路径是否覆盖 hash、像素比较、cache get、cache put、遮罩编码和物理持久化失败，并明确每类是否降级或中止？ [Coverage, Exception/Recovery, Spec §FR-029, §FR-044, Edge Cases] — 证据：`spec.md` §FR-003、§FR-044、Edge Cases；`contracts/frame-capture-contract.md` §Failure matrix 覆盖第二文件/sync/rename、逻辑提交失败和启动恢复；`contracts/perception-cache-contract.md` §Error behavior；`tasks.md` T017、T019、T032。
- [x] CHK025 上下文敏感路径是否覆盖相同画面配不同验证问题、不同动作历史和不同重试上下文，足以阻止错误答案复用？ [Coverage, Spec §FR-017–018, User Story 2] — 证据：`spec.md` User Story 2 scenarios 3、5、7，§FR-017–019；`contracts/perception-cache-contract.md` §Role-specific request/context identity；`tasks.md` T030、T039。
- [x] CHK026 是否为至少两个互不相关 GUI 场景定义了共同契约与不同交互路径，而不是只要求两个名称不同的同构 fixture？ [Coverage, Spec §FR-042, SC-009–010] — 证据：`spec.md` §FR-042–043、§SC-009–010；`plan.md` §Implementation Strategy 10；`tasks.md` T062。

## Edge Case Coverage

- [x] CHK027 是否定义 content hash 碰撞但像素不同、相同像素但 PNG 编码不同、像素格式不同三类边界的预期需求语义？ [Edge Case, Spec §FR-006–008, Edge Cases] — 证据：`spec.md` §FR-006–008、Edge Cases 前两项；`research.md` R1–R2；`tasks.md` T002、T013。
- [x] CHK028 是否规定安全证据路径缺失、损坏、越界、用途错误或遮罩身份不匹配时的报告要求，并禁止静默选择私有路径？ [Edge Case, Security, Spec §FR-013, §FR-037, Edge Cases] — 证据：`spec.md` §FR-013、§FR-037、Edge Cases 明确缺失/截断/损坏/身份不一致不得链接；`data-model.md` §PhysicalImageRef/FrameArtifactBundle 区分 `artifact_sha256` 与 `content_hash`；`contracts/report-contract.md` §Safe evidence contract 要求 byte size、文件 SHA-256、可解码性与 referenced bundle 校验；`tasks.md` T054、T056 覆盖全部负例。
- [x] CHK029 是否明确 `total_capture_count=0`、阶段从未开始、阶段部分失败和报告输出失败时的 null、状态与汇总语义？ [Edge Case, Spec §FR-027–030, Edge Cases] — 证据：`spec.md` §FR-027、§FR-029、Edge Cases；`data-model.md` §9、§11；`contracts/telemetry-contract.md` §Measurement semantics；`tasks.md` T042、T048。
- [x] CHK030 是否明确未知 locale、未知错误码、原始错误详情含中文或 HTML 特殊字符时的需求边界？ [Edge Case, Spec §FR-031, §FR-034–036, Edge Cases] — 证据：`spec.md` §FR-031、§FR-034–036、Edge Cases；`contracts/report-contract.md` §Locale configuration、§Error localization、§Encoding and rendering；`tasks.md` T053。

## Non-Functional Requirements

- [x] CHK031 性能需求是否定义了可重复的固定工作负载、独立调用计数事实来源和禁止依赖网络耗时的约束？ [Performance, Spec §FR-040, SC-006, Plan §Implementation Strategy 10] — 证据：`spec.md` §FR-040、§SC-006；`plan.md` §Implementation Strategy 10；`contracts/telemetry-contract.md` §Test oracle；`tasks.md` T001、T049。
- [x] CHK032 每个阶段的计时边界、聚合方式、调用计数口径和 failed/cancelled/unavailable 状态是否足够明确以支持独立复算？ [Observability, Spec §FR-023–030] — 证据：`spec.md` §FR-023–030；`data-model.md` §9–11；`contracts/telemetry-contract.md` §Measurement semantics、§Counter definitions、§Conservation checks。
- [x] CHK033 `report_build` 是否有不包含自身最终写盘的明确测量边界，避免性能报告产生自引用或估算值？ [Clarity, Observability, Plan §Implementation Strategy 6] — 证据：`plan.md` §Implementation Strategy 6；`research.md` R11；`contracts/telemetry-contract.md` §Report build boundary；`tasks.md` T048。
- [x] CHK034 UTF-8 要求是否覆盖 HTML、JSON、资源字典、测试名称和错误详情，并提供可客观识别乱码、替换字符或内容丢失的标准？ [Localization, Spec §FR-036, SC-007] — 证据：`spec.md` §FR-036、§FR-041、§SC-007；`contracts/report-contract.md` §Encoding and rendering；`tasks.md` T053。
- [x] CHK035 缓存内存约束是否明确为最近 3～5 个逻辑帧、定义淘汰与 session reset，并禁止缓存持有无界图片数据或完整上下文对象？ [Resource Constraint, Spec §Assumptions, Plan §Implementation Strategy 3] — 证据：Constitution §资源约束；`plan.md` §Implementation Strategy 3；`data-model.md` §2、§6；`contracts/perception-cache-contract.md` §Capacity and lifecycle。

## Dependencies & Assumptions

- [x] CHK036 核心业务无关要求是否覆盖 domain、runtime、planning、grounding、execution、verification、reporting、recovery 和 config，并明确禁止场景专用字段、关键词与流程分支？ [Constitution VI, Spec §FR-005] — 证据：Constitution Principle VI；`spec.md` §FR-005；`plan.md` §Constitution Check；`tasks.md` T063。
- [x] CHK037 场景语义只允许存在于 testcase、fixture 或通用注册 profile 的边界是否写入需求，而不是仅作为实现者默认假设？ [Constitution VI, Dependency, Spec §FR-042] — 证据：Constitution Principle VI；`spec.md` §FR-042、Assumptions；`plan.md` §Constitution Check。
- [x] CHK038 “两个场景互不相关”的判定维度、共享契约和必须保留的独立验证证据是否有明确要求？ [Constitution VI, Assumption, Spec §FR-042, SC-009–010] — 证据：`spec.md` §FR-042–043、§SC-009–010；`plan.md` §Implementation Strategy 10；`research.md` R14；`tasks.md` T062。

## Ambiguities & Conflicts

- [x] CHK039 “实际模型调用”“分析调用”“缓存命中”“确定性跳过”的术语和计数关系是否在规格、计划和遥测契约中使用同一口径？ [Ambiguity/Consistency, Spec §FR-019, §FR-025, Contract §telemetry] — 证据：`spec.md` §FR-019、§FR-025；`plan.md` §Implementation Strategy 5；`data-model.md` §10–11；`contracts/telemetry-contract.md` §Counter definitions。
- [x] CHK040 物理图片数量按实际文件计数的澄清，是否与无掩码共享文件、有掩码安全/私有双文件以及正常报告副本为零的要求完全一致？ [Conflict Check, Spec §FR-024, §FR-028, §FR-037] — 证据：`spec.md` User Story 1 scenario 1、§FR-024、§FR-028、§FR-037、§SC-001；`contracts/frame-capture-contract.md` §Artifact safety；`data-model.md` §11 Conservation。

## Incremental Release-Gate Review (2026-07-23)

- [x] CHK041 成功逻辑帧的“立即持久化”要求是否明确了唯一图片物理提交、逻辑记录提交和返回调用方三者的顺序，并与持久化失败时不得产生成功 `ScreenFrame` 的要求一致？ [Clarity/Consistency, Spec §FR-003, §FR-044, Contract §frame-capture] — 证据：`spec.md` §FR-003、§FR-024、§FR-044；`plan.md` §Implementation Strategy 2 定义 staging bundle 单次目录 rename、逻辑帧/physical event 同一 TestRun 更新、隔离与恢复；`data-model.md` §FrameArtifactBundle、§Capture state transitions；`contracts/frame-capture-contract.md` §Capture response、§Artifact safety、§Failure matrix；`tasks.md` T014、T017、T019–T020、T041、T044。
- [x] CHK042 完整轨迹要求是否足以按全局采集顺序重建观察、稳定等待、重试和操作后验证的每次成功采集，同时为未产生成功帧的失败尝试定义可关联的错误证据？ [Completeness/Traceability, Spec §FR-003–004, §FR-022, §FR-044] — 证据：`spec.md` §FR-003–004、§FR-022、§FR-039、§FR-044；`data-model.md` §4、§10、§13；`contracts/frame-capture-contract.md` §Capture response。
- [x] CHK043 上下文敏感调用的要求是否定义了可规范化的 request/context identity、必须纳入的完整字段以及缺少任一字段时的 miss/实际调用规则，使 Planner skip 的充要条件可客观审查？ [Clarity/Measurability, Spec §FR-017–019, §FR-022] — 证据：`spec.md` §FR-017–019、§FR-022；`data-model.md` §6A；`contracts/perception-cache-contract.md` §Role-specific request/context identity；`tasks.md` T030、T039。
- [x] CHK044 每个操作后的验证要求是否同时明确“独立新采集证据”和“实际执行 Verifier 判断”，且不会把 Planner skip、纯内容缓存命中或无画面变化误解为可以省略验证？ [Consistency/Coverage, Spec §FR-002, §FR-017, §FR-021–022, §SC-003] — 证据：Constitution Principle IV；`spec.md` §FR-002、§FR-017–022、§SC-003；`contracts/perception-cache-contract.md` §Explicit exclusions；`tasks.md` T030–T031、T039。
- [x] CHK045 稳定性与 ActionEffect 的要求是否明确区分“重复逻辑帧累计一次稳定采样”和“操作前后无变化不得自动通过”，禁止从 stable 状态推导动作生效？ [Consistency, Spec §FR-014, §FR-020–021, §SC-003–004] — 证据：`spec.md` §FR-014、§FR-020–021、§SC-003–004；`research.md` R8；`tasks.md` T016、T031。
- [x] CHK046 敏感图片要求是否覆盖掩码身份或 private 持久化权限变更后的路径复用，并明确禁止链接、恢复或故障回退到先前已存在的未遮罩制品？ [Security/Coverage, Spec §FR-013, §FR-037, §FR-044] — 证据：Constitution §凭据与隐私；`spec.md` §FR-013、§FR-037、§FR-044、Edge Cases；`contracts/frame-capture-contract.md` §Artifact safety、§Failure matrix；`contracts/report-contract.md` §Safe evidence contract。
- [x] CHK047 “报告零副本”是否明确适用于正常执行报告、离线重建、部分失败报告及兼容入口，并将 `report_frames` 和任何其他报告目录中的证据副本统一列为禁止范围？ [Coverage/Gap, Spec §FR-009, §FR-037, Contract §report] — 证据：`spec.md` §FR-037；`plan.md` §Implementation Strategy 6；`contracts/report-contract.md` §Safe evidence contract、§Compatibility tests；`tasks.md` T054、T059。
- [x] CHK048 JSON 向后兼容要求是否为旧顶层、step 和 iteration 字段逐层定义了键名、类型、枚举、null/缺省语义与聚合规则的不变性，并说明旧消费者忽略新字段的客观判定方式？ [Clarity/Measurability, Spec §FR-035, §SC-008, Contract §report] — 证据：`spec.md` §FR-035、§SC-008；`contracts/report-contract.md` §Backward compatibility rule、§Compatibility tests；`tasks.md` T052、T057。
- [x] CHK049 HTML “用户可见文本 100% 中文化”是否定义了允许保留英文的明确白名单（如机器值、原始错误码/详情或模型名），以及不得遗留英文 UI 标签的可度量边界？ [Ambiguity/Acceptance Criteria, Spec §FR-032–034, §SC-007] — 证据：`spec.md` §FR-032–034、§SC-007；`contracts/report-contract.md` §Resource registry contract；`tasks.md` T051。
- [x] CHK050 UTF-8 要求是否同时定义 HTML、JSON、资源字典与原始错误详情的字节编码、序列化及往返验收标准，并将 U+FFFD、字符丢失和错误转义区分为可独立判定的失败？ [Completeness/Measurability, Spec §FR-036, §FR-041, §SC-007] — 证据：`spec.md` §FR-036、§FR-041、§SC-007；`contracts/report-contract.md` §Encoding and rendering、§Compatibility tests；`tasks.md` T053。
- [x] CHK051 性能度量要求是否明确同一 run 的结构化日志、JSON 和 HTML 必须由同一事件集派生，并定义固定工作负载、Spy 事实源、时钟/聚合口径及失败阶段的可重复交叉核对标准？ [Performance/Measurability, Spec §FR-023–030, §FR-040, §SC-005–006] — 证据：`spec.md` §FR-023–030、§FR-040、§SC-005–006；`plan.md` §Implementation Strategy 5、10；`contracts/telemetry-contract.md` §Measurement semantics、§Test oracle；`tasks.md` T043、T049、T068。
- [x] CHK052 “两个互不相关 GUI 场景”是否具有可客观评审的独立性判据（不同交互路径、不同可见结构但共享同一通用契约），而不是仅要求两个名称或图片不同的同构 fixture？ [Coverage/Clarity, Spec §FR-042–043, §SC-009–010, Plan §Implementation Strategy 10] — 证据：`spec.md` §FR-042–043、§SC-009–010；`plan.md` §Implementation Strategy 10；`research.md` R14；`tasks.md` T062。

## Notes

### Release-gate audit record (2026-07-23)

- 审核范围：Constitution、`spec.md`、`plan.md`、`research.md`、`data-model.md`、`contracts/` 全部契约、`tasks.md`；另复核 `quickstart.md` 与 feature 001 基础 report schema 的引用一致性。
- 审核结果：CHK001–CHK052 共 52 项，全部逐项获得文档与章节证据；未使用 N/A，未保留无证据勾选项。
- 已修正规格缺口：成功/失败采集轨迹边界、恢复采集来源、角色专属上下文身份、不同 PNG 编码同像素、`report_output` 失败、HTML 英文白名单、UTF-8 往返、JSON null/缺省与旧消费者、全部报告入口零副本、跨场景独立性判据。
- 已修正计划/契约缺口：bundle 单次发布→逻辑提交→返回与孤儿恢复顺序；Planner/Grounder/Verifier 身份矩阵；同一事件源；safe resolver 覆盖正常/离线/部分失败/兼容入口及 artifact 完整性；代表性旧消费者与 HTML DOM/编码验收；跨场景独立性只使用 VNC 可见像素和声明式 fixture 元数据。
- 已修正任务遗漏：T020/T025/T030/T039/T042/T043/T048/T051–T054/T057/T059/T061/T062/T067/T068 已包含对应 RED/GREEN、依赖和独立验收要求。
- 工作流结论：用户目标未改变，澄清答案仍完整，因此无需重新运行 `speckit-clarify`；`plan.md` 与 `tasks.md` 已在本次门禁中同步修正，无需重新生成 `speckit-plan` 或 `speckit-tasks`。本记录只放行后续实现入口，本次未运行 `speckit-implement`、未修改应用代码。

### Post-analyze HIGH remediation (2026-07-23)

- 重新打开并复核 CHK011、CHK014、CHK021、CHK024、CHK041、CHK045、CHK047、CHK048；修正后仍全部有证据通过。
- JSON 路径兼容：明确旧 `before_frame_path`/`after_frame_path` 只承诺对应可读取安全证据，不承诺 `report_frames` 目录或独立副本；非路径字段精确投影，路径以 safe purpose、前后关联和 physical identity/content hash 等价验收。
- 稳定性隔离：只有活动 StabilityEngine 等待自身发起的采样影响该等待的 `stable_frame_count`/`early_exit`；其他来源只进入全局轨迹与总采集数。
- 失败边界：decode/规范化失败中止成功采集且不进入分析/验证；只有可信像素已获得后的 hash/compare/cache 故障才降级为 unique/full analysis。
- 任务独立性：T029 先建立三个 ndarray 入口隔离 RED 用例；T034–T036 各自只运行对应隔离测试，完整缓存/StructuredScreen 集成分别留给 T037–T038。
