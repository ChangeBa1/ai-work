# 记忆命中正确性 Checklist: 结构化元素身份主键（element-identity-key）

**Purpose**: 作为需求质量的「单元测试」——判定 spec/plan/research/contracts 是否把记忆命中相关行为写到可验收、无歧义、可度量；**不**用于验证代码是否已实现。
**Created**: 2026-08-06
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [research.md](../research.md) · [contracts/element-identity.md](../contracts/element-identity.md) · [tasks.md](../tasks.md)
**Depth**: Standard（发布前需求门禁 / PR 评审）
**Audience**: 规格作者与评审者（实现前与实现中对照需求完整性）
**How to use**: 每条只问「书面需求是否满足」——答案为 **是 / 否 / 部分（附缺口）**；否或部分即需求未就绪，须改文档而非改代码凑合。

---

## 身份解析边界 — 空文本 / 纯符号 / 超长描述

- [x] CHK001 规格是否用 MUST 写明：可见文本归一化结果为空串时，身份文本分量为空且**不得**回退到 Planner 原文作主键？[Clarity, Spec §FR-005a, Edge Cases]
- [x] CHK002 规格是否写明：无线索（无可见文本、无可用几何、画面身份未知）时，写入侧「跳过可检索写入或标记不可检索」与查询侧「未命中」的**具体二选一规则**（不得仅写「可」）？[Completeness, Spec §US3-AS3, Edge Cases]
- [x] CHK003 规格或 research 是否定义：纯符号串（如仅 `×`、`/`、`-`、标点）经归一化后，是作为合法文本分量参与相等，还是视为空/不可检索？[Gap 或 Clarity, research R4]
- [x] CHK004 规格是否写明：`is_dynamic_token` 过滤的数字形态 token **不得**单独成为写入路径的可见文本分量？[Consistency, research R3, fingerprint 复用]
- [x] CHK005 规格/research 是否用可判定规则描述「超长 Planner 描述」如何抽取可见文本（精确相等 OCR / 唯一最长整词 OCR），并写明抽取失败时 MUST 未命中？[Clarity, research R3, Spec §FR-005]
- [x] CHK006 规格是否禁止将「描述包含某短标签」单独作为身份文本分量相等条件（例如 `…小計…` 不得等于 `小計`）？[Consistency, Spec §FR-005a, Clarifications Q2]
- [x] CHK007 Edge Cases 是否覆盖：Planner 描述与 OCR 可见文本冲突时 MUST 倾向未命中、不得仅因描述相似命中？[Coverage, Spec §Edge Cases]

## 身份解析边界 — 日文全半角与假名

- [x] CHK008 需求是否规定归一化流水线步骤顺序固定为 NFKC →（浊点预合成）→ 长音统一 → casefold → 空白折叠，且比较为归一化后 `==`？[Clarity, Spec §FR-005a, research R4]
- [x] CHK009 需求是否给出至少一组**可复现**全半角正例（如半角片假名 `ﾚｼﾞ袋` → `レジ袋`）并标明出处（单测金样或 research 表）？[Measurability, research R4 表]
- [x] CHK010 需求是否明确**禁止**清音≡浊音合并（`は` 不得等于 `ば`）与平假名≡片假名互转？[Clarity, research R4 明确不做]
- [x] CHK011 需求是否规定长音符号 `ー`/`ｰ` 的统一规则，且 ASCII `-` **不得**被改写成日文长音（以免破坏 `預/現計`）？[Clarity, research R4]
- [x] CHK012 需求是否写明：`小計` 与 `小計解除`、`金券` 与 `1金券` 归一化后 MUST 仍不相等？[Consistency, research R5 反例 N1/N2]
- [x] CHK013 假名折叠规则是否约束为通用脚本处理、MUST NOT 含被测应用业务同义词表？[Consistency, Spec §FR-004, Constitution VI]

## 几何与相等判定

- [x] CHK014 需求是否将几何相等定义为「画面归一化中心落入同一固定网格单元」，并写明绝对像素 bbox 仅用于点击/模板、不作为身份相等键？[Clarity, Spec §FR-001, Clarifications Q1]
- [x] CHK015 需求是否写明 MUST NOT 使用应用容器相对坐标？[Completeness, Spec §FR-001]
- [x] CHK016 需求是否将网格粒度标为可配置但语义固定，且默认值（如 G=16）出现在 plan/research 中可供验收引用？[Measurability, plan, research R2]
- [x] CHK017 需求是否写明分辨率不一致时 MUST NOT 元素直点（即使归一化网格可计算）？[Consistency, Spec §Edge Cases, 015 门槛]

## 同画面多候选消歧

- [x] CHK018 需求是否用 MUST 写明：同画面身份下可检索候选集合大小 ≥2 时 MUST 未命中并降级？[Completeness, Spec §FR-003a]
- [x] CHK019 需求是否规定禁止的消歧手段清单至少包含：最后成功时间、随机选取、未编码进身份键的序数/方位猜测？[Clarity, Spec §FR-003a, Clarifications Q3]
- [x] CHK020 需求是否要求多候选事件可审计（如原因码 `identity_ambiguous`）且与「身份未解析」可区分？[Completeness, Spec §FR-003a, US1-AS3]
- [x] CHK021 需求是否写明：仅当候选被唯一收窄为 1 条时才允许进入模板校验与直点？[Consistency, Spec §FR-007]
- [x] CHK022 验收场景是否包含「同文案、不同网格单元的两控件」写入后互不命中对方的 Given/When/Then？[Coverage, Spec §US2]

## 跨画面同名元素

- [x] CHK023 需求是否写明元素身份检索作用域为**所属画面身份（page）内**，不同 page_id 下相同归一化文本+几何 cell 不得跨页命中？[Clarity, Spec §FR-001/007, Key Entities]
- [x] CHK024 需求是否明确本 feature **不实现**跨画面元素多对多索引（026），且当前命中路径不得引入跨页合并？[Consistency, Spec §FR-012]
- [x] CHK025 需求是否说明页面未达 high 相似档时 MUST NOT 进入元素身份直点（跨「看起来像」的页）？[Coverage, Spec §FR-008, Edge Cases]
- [x] CHK026 若两页 OCR 均含相同短标签，需求是否足以判定「仅页面指纹匹配决定是否进入该页的元素集」而无第二种跨页键？[Ambiguity 检查, Spec §FR-007 + 015 页面门槛]

## 强制模板与命中授权

- [x] CHK027 需求是否写明：身份候选唯一后直点前 MUST 执行邻域模板校验，且 MUST NOT 因高置信/连续成功跳过？[Completeness, Spec §FR-007a, Clarifications Q5]
- [x] CHK028 需求是否区分「身份命中但模板未通过」与「身份未命中」两种审计语义？[Clarity, Spec §US1-AS3]
- [x] CHK029 需求是否写明模板未达标/缺失时 MUST NOT 直点，仅可降级（medium 提示或 Grounder）？[Consistency, Spec §FR-007, contracts]
- [x] CHK030 直点授权条件是否可客观判定为：`level==high` 且 `matched_bbox` 非空（或等价书面条件）？[Measurability, contracts §3]

## 存量数据迁移正确性与可回滚性

- [x] CHK031 需求是否规定启用新身份路径时旧自然语言主键 `element_memories` MUST 整表作废或隔离且 MUST NOT 参与直点？[Completeness, Spec §FR-009, Clarifications Q4]
- [x] CHK032 需求是否禁止对旧记录做猜测式惰性迁移与旧/新键双写并行命中？[Consistency, Spec §FR-009]
- [x] CHK033 plan/tasks 是否写明迁移前 MUST 备份 `data/vnc_agent.db`（或等价路径）且备份可定位？[Completeness, tasks T012, plan §6]
- [x] CHK034 需求/plan 是否给出可回滚步骤：从备份/JSONL 恢复 element 行，且回滚后可回到 015 标签路径或 `identity_enabled=false`？[Coverage, Recovery, plan §6, tasks T040]
- [x] CHK035 需求是否写明 `page_memories` 在元素作废后是否保留，以及「保留页面记忆不得放行旧元素主键」？[Clarity, Spec §FR-009, plan 存量表]
- [x] CHK036 需求是否规定代码侧双保险：`identity_key` 为空或 schema 不匹配的行 MUST 永不进入命中候选？[Completeness, data-model, tasks T024]
- [x] CHK037 是否用可核对数字记录迁移对象规模（如 8 行 element / 5 行 page）作为验收对照而非模糊「存量」？[Measurability, plan, research R5]

## 误命中的定义、检测与上报

- [x] CHK038 需求是否将**误命中**精确定义为：已执行元素记忆直点，且该次独立验证为 `failed` **或** `uncertain`？[Clarity, Spec §FR-008a, SC-002]
- [x] CHK039 需求是否写明「仅身份命中但强制模板未通过、未直点」MUST NOT 计入误命中？[Consistency, Spec §SC-002]
- [x] CHK040 需求是否要求误命中次数可**单独统计**（不得只埋在总失败里）？[Completeness, Spec §FR-013, US6]
- [x] CHK041 验收是否给出可计算上限：误命中次数 ÷ 元素记忆命中次数 ≤ 10%（同分母定义可在报告核对）？[Measurability, Spec §SC-002]
- [x] CHK042 需求是否要求误命中触发 015 既有失败计数与本步抑制语义？[Consistency, Spec §FR-008a]
- [x] CHK043 需求是否要求成功命中审计至少包含：元素身份、画面身份、模板校验得分、被跳过的模型调用类型？[Completeness, Spec §FR-013, Constitution 可观测性]

## 开关关闭时的行为一致性

- [x] CHK044 需求是否规定存在专用能力开关（如 `identity_enabled`），关闭后本 feature 引入的身份主键行为不生效？[Completeness, Spec §FR-010, plan 配置表]
- [x] CHK045 需求是否规定 `memory.enabled: false` 时全链路不读不写记忆，与合入前基线一致？[Consistency, Spec §US5, 015]
- [x] CHK046 需求是否将「关闭开关后的一致性」写成可验收表述（模型调用序列、记忆副作用边界、关键断言），而非仅「尽量一致」？[Measurability, Spec §SC-004]
- [x] CHK047 需求是否写明开关关闭路径不得调用新身份解析作为隐式副作用？[Clarity, Spec §US5-AS1]
- [x] CHK048 contracts/plan 是否写明 `identity_enabled=false` 时回退到 `target_label` 精确路径（及旧行已 purge 时命中可为 0 的预期）？[Completeness, contracts §3, tasks T027]

## 度量基线与成功标准可判定性

- [x] CHK049 需求/tasks 是否要求在改代码前产出基线文件，且基线中 element_memory 命中次数/率可读取并预期为 0？[Completeness, tasks Phase 1, Spec §SC-001]
- [x] CHK050 SC-001 是否定义命中率分子分母（命中次数 ÷ 进入记忆查找次数）且要求报告可核对？[Measurability, Spec §SC-001]
- [x] CHK051 SC-003 是否给出命中路径 p95 数值上限（≤50ms）且要求报告含实测分位？[Measurability, Spec §SC-003]
- [x] CHK052 是否要求至少两个互不相关 GUI 场景 fixture 上命中 >0（SC-006），而非单一场景？[Coverage, Spec §SC-006, FR-014]
- [x] CHK064 是否规定误命中率（SC-002）的最小有效样本量，样本不足时 MUST 标注「结论不成立」而非直接判定通过？（现状：分母是命中次数，命中 3 次错 1 次 = 33% 判不合格，命中 100 次错 9 次 = 9% 合格，同一份实现两种结论）[Measurability, Spec §SC-002, tasks T034]
- [x] CHK065 是否要求「解析/查询异常」与「正常未命中」在审计中可区分且单独计数？（现状：contracts 第3节 fail-open 是「任意异常 → None + 日志」，FR-013 的计数项里没有异常次数，异常被吞掉后与正常未命中不可区分，持续性 bug 可以静默活过整个验收期）[Completeness, Spec §FR-013, contracts §3]
- [x] CHK066 是否要求 SC-001 的分母（进入记忆查找的次数）在基线采集与验收采集中口径同源可比，且报告需给出分母绝对值而非仅百分比？[Measurability, Spec §SC-001, tasks T001/T003/T034]

## 一致性、冲突与范围

- [x] CHK053 「宁可不命中、不可错命中」是否与所有放宽匹配（子串、最近成功、跳过模板）的禁止条款无冲突？[Consistency, Spec §FR-003/003a/005a/007a]
- [x] CHK054 本 feature「不改 Planner/Grounder 协议、不新增模型调用」是否与可观测性「记录被跳过的模型调用类型」兼容且无要求新协议字段？[Consistency, Spec §FR-011, SC-005]
- [x] CHK055 原则 III 索引直连层级（026）是否被明确排除，且本 feature 仅对 015 记忆直点强制模板 (c) 同构语义？[Consistency, plan Constitution Check, Spec §FR-012]
- [x] CHK056 公开 API `lookup(screen, target_label)` 签名保持是否在 contracts 中写明，以避免实现擅自改协议？[Traceability, contracts §3]

## 几何锚点同源与写入侧保守规则

- [x] CHK057 需求/plan 是否用 MUST 写明：写入侧与查询侧计算 geom_cell 所用的中心点 MUST 来自同一锚点定义，并给出当两者可得时的唯一取舍规则？[Clarity, Spec §FR-002, plan §2, research R3, contracts §1]
- [x] CHK058 需求是否写明写入侧 MUST 使用「被选中作为文本分量的那一条 OCR 项」的 bbox 中心，而非 target_region 中心？[Completeness, Spec §FR-001, research R3, contracts resolve_identity_for_write]
- [x] CHK059 验收是否要求一组「同一控件先写后查」的金样断言两侧 geom_cell 逐字符相等（而不仅断言最终命中）？[Measurability, Spec §FR-002, tasks T018a]
- [x] CHK060 需求是否已消除 FR-005a 与 research R3 查询规则关于纯图标身份的矛盾（写入侧承诺可建立、查询侧不可达）？[Consistency, Spec §FR-005a, Edge Cases, research R3/R5]
- [x] CHK061 需求是否用 MUST 约束网格粒度变更后旧记录 MUST NOT 被命中（G 编码进键，或 G 变更强制 schema 递增并 purge）？[Completeness, Spec §FR-001a, plan §1, contracts §4–5]
- [x] CHK062 需求是否写明写入侧文本分量选取规则唯一确定（最近非动态 token；距离并列时的确定性 tie-break）？[Clarity, research R3]
- [x] CHK063 需求是否写明写入侧 find_elements_by_identity 返回 ≥2 时 MUST 跳过可检索写入并审计，MUST NOT 合并或任选？[Completeness, plan §2 步骤4]

## 缺口汇总（评审时填写）

**评审日期**: 2026-08-06（CHK062/064/065 修复后复评）｜ **结果**: 66 条中 **66 是 / 0 部分 / 0 否**（未列入下表者判定为「是」）

| ID | 结论 (是/否/部分) | 缺口说明 | 建议改文档位置 |
|----|-------------------|----------|----------------|
| CHK002 | 已修复（2026-08-06 修订轮） | 原：FR-006 / US3-AS3 写「跳过**或**标记」。现：MUST 跳过可检索写入。 | — |
| CHK003 | 已修复（2026-08-06 修订轮） | 原：纯符号未定义。现：Edge Cases + R4 金样。 | — |
| CHK008 | 已修复（2026-08-06 修订轮） | 原：FR-005a 与 R4 顺序相反。现：FR-005a 对齐 R4 (0)–(7)。 | — |
| CHK062 | 已修复（2026-08-06 修订轮） | 原：等距无 tie-break。现：`research.md` R3 写入步骤1 MUST 按 `(normalize_visible_text(text), (x1,y1,x2,y2))` 字典序；contracts `resolve_identity_for_write` 同步；tasks T016/T006。 | — |
| CHK064 | 已修复（2026-08-06 修订轮） | 原：hits>0 即判 ≤10%。现：`spec.md` SC-002 规定 `SC002_MIN_HITS=20`、三态（`<20` → `sc002_inconclusive` 非通过非失败）；tasks T003/T034。 | — |
| CHK065 | 已修复（2026-08-06 修订轮） | 原：异常静默 None。现：FR-013 MUST 计 `identity_lookup_error` 且与 insufficient/ambiguous 可区分；contracts §3 fail-open MUST 记账 + `resolution_status=error`；§6 信号表；tasks T029/T031。 | — |

**CHK057–CHK066 判定（当前）**: 全部为 **是**（出处见上表与各 FR/R3/contracts/tasks）。

---

## Notes

- 勾选 `[x]` 表示：**书面需求已满足该条可判定标准**（不是「代码已测过」）。
- 覆盖域映射：身份边界（空/符号/超长/日文）→ CHK001–013；多候选 → CHK018–022；跨画面同名 → CHK023–026；迁移回滚 → CHK031–037；误命中 → CHK038–043；开关 → CHK044–048；度量基线/SC → CHK049–052 + **CHK064–066**；一致性/范围 → CHK053–056；**几何锚点同源与写入保守** → **CHK057–063**。
- 判定须引用具体文件与章节；缺口表保留历史行（含「已修复」）以便评审追溯。
- 关联实现任务见 [tasks.md](../tasks.md)；本清单不替代 pytest。
