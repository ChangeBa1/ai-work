# Spec Kit 开发流程与提示词：画面元素坐标索引 + 版本管理

> 配套文档：`需求分析报告-画面元素坐标索引.md`
> 目标读者：负责推进本功能的开发者 / AI 协作者
> 用途：把需求分析报告落成可执行的 Spec-Driven Development 流水线，每一步给出**可直接粘贴的提示词**

---

## 零、总览：为什么不是一个 feature

需求分析报告里的路线分四期。**不要把它们塞进同一个 speckit feature**——理由有三：

1. 第 0 期（修主键）和第 2 期（建库）之间隔着一个**假设验证**：如果修完主键后元素记忆命中率仍然是 0，说明根因不止 prose key，第 2 期的设计前提就要推翻。
2. 第 2 期依赖第 1 期摸底数据（dynamic 元素占比）才能定 IoU 阈值和覆盖率目标，而摸底本身不产出生产代码，不该走 spec→plan→tasks 全套。
3. 单个 feature 的 tasks.md 超过 ~80 条时，`/speckit-implement` 的执行质量会明显下降，中途上下文丢失导致返工。

所以拆成 **3 个 feature + 1 个调研 spike + 1 次宪法修订**：

| 编号 | 类型 | 内容 | 对应报告 | 预估 | 前置 |
|---|---|---|---|---|---|
| **S0** | 宪法修订 | 在执行优先级阶梯中插入"索引直连点击"层，并明确版本变更的人工审批约束 | 全局约束 | 0.5 人日 | — |
| **025** | speckit feature | 元素身份主键修复（prose label → 结构化身份） | 第 0 期 | 3~5 人日 | S0 |
| **SPIKE-1** | 调研（不走 speckit） | 静态/动态元素占比、WinForms 布局来源摸底 | 第 1 期 | 2~3 人日 | 可与 025 并行 |
| **026** | speckit feature | 画面元素坐标索引 + 画面版本管理 + Grounder 旁路 | 第 2 期 | 2~3 人周 | 025 + SPIKE-1 |
| **027** | speckit feature | Planner / Verification 旁路 | 第 3 期 | 3~4 人周 | 026 |

**中途叫停点**：025 + SPIKE-1 合计 ≤10 人日就能验证两个最关键假设。如果 025 的命中率没上去、或 SPIKE-1 发现 dynamic 元素占比过高，**在这里停下重新评估**，不要往 026 投入。

---

## 一、Spec Kit 在本仓库的实际形态

本仓库的 speckit 以 **skill** 形式安装（不是 upstream 的 `/speckit.xxx` 点号命令）：

```
.claude/skills/speckit-{specify,clarify,plan,tasks,analyze,checklist,implement,converge,constitution,taskstoissues}/
.specify/
├── feature.json          # 当前活动 feature 目录指针
├── memory/constitution.md
├── templates/{spec,plan,tasks,checklist,constitution}-template.md
├── scripts/powershell/{create-new-feature,setup-plan,setup-tasks,check-prerequisites}.ps1
└── workflows/speckit/workflow.yml
```

调用方式：在 Claude Code 里输入 `/speckit-specify <描述>`（连字符，不是点号）。

**每次开新 feature 前先确认 `.specify/feature.json` 指向的目录**——它决定后续 `/speckit-plan`、`/speckit-tasks` 写到哪里。`/speckit-specify` 会自动创建新目录并更新它；如果你是接着做一个已存在的 feature，手动确认这个文件指对了。

标准流水线与人工门禁：

```
/speckit-constitution   ← 仅在需要改变基本原则时
        ↓
/speckit-specify        → spec.md            【门禁 A：人读一遍，删掉臆造的需求】
        ↓
/speckit-clarify        → spec.md (更新)     【最多 5 问，可跑多轮】
        ↓
/speckit-plan           → plan.md + research.md + data-model.md + contracts/ + quickstart.md
        ↓                                     【门禁 B：Constitution Check 必须全绿】
/speckit-tasks          → tasks.md
        ↓
/speckit-checklist      → checklists/*.md    【可选但本功能强烈建议】
        ↓
/speckit-analyze        → 一致性报告（只读） 【门禁 C：CRITICAL 清零才能实施】
        ↓
/speckit-implement      → 代码
        ↓
/speckit-converge       → 补漏的 tasks       【实施后自查，可反复】
```

---

## 二、S0：宪法修订（必做，且必须最先做）

### 为什么必须先改宪法

本功能直接触碰三条 Core Principle，不先改宪法的话，`/speckit-plan` 的 Constitution Check 会在门禁 B 上判定违规，导致返工：

| 原则 | 冲突点 | 处理 |
|---|---|---|
| **III. 键盘优先，视觉点击兜底** | 现文把优先级阶梯**逐项枚举**为"已验证回放动作 → 快捷键 → 焦点导航 → Win+R → OCR 文本定位 → 模板/视觉锚点 → MiMo Grounding → 强模型分析"。"索引直连点击"不在其中，插入它属于修改规范性条款。 | 在 OCR 文本定位**之前**插入新层级 |
| **V. 受控自进化** | 明确禁止"无条件自动接受所有 UI 变化"。画面新版本的自动建立正撞在这一条上。 | 明确：新版本索引 MUST 以 `pending` 落库，approved 前不得用于直连点击 |
| **VI. 业务无关核心** | 索引必须不含 NodeMaster / POS / 画面名等业务语义；且新能力 MUST 用两个互不相关的 GUI 场景验证。 | 无需改宪法，但要在 spec 的 Success Criteria 里显式承接 |

### 提示词（直接粘贴）

```
/speckit-constitution 为即将开展的"画面元素坐标索引 + 画面版本管理"能力做一次 MINOR 版本修订，只改必要条款，不要重写整部宪法。

需要的修改：

1. 【原则 III 键盘优先，视觉点击兜底】在现有优先级阶梯中插入一个新层级。修订后的阶梯为：
   已验证回放动作 → 快捷键 → Tab/Shift+Tab 焦点导航 → Win+R + PowerShell 配方 →
   【新增】已审批的画面版本坐标索引直连定位 → OCR 文本定位 → 模板或视觉锚点 →
   MiMo Grounding → 强模型异常分析
   新层级的准入条件 MUST 同时写进原则正文，缺一不可：
   (a) 当前帧已匹配到某个已知画面的某个 approved 版本；
   (b) 目标元素在该版本索引中存在唯一确定的坐标记录；
   (c) 点击前必须通过元素级模板校验（在记录坐标的邻域内重新确认该元素仍然存在）；
   (d) 任一条件不满足时 MUST 直接降级到下一层，MUST NOT 猜测坐标、MUST NOT 放宽阈值重试。
   理由段要说明：索引直连的确定性和成本优于 OCR 与视觉定位，但它建立在"画面未变更"这一
   外部假设上，因此必须由 (c) 提供运行时的独立证伪手段，否则不得进入阶梯。

2. 【原则 V 受控自进化】在现有"MUST NOT 无条件自动接受所有 UI 变化"之后补充一句具体化约束：
   当系统检测到画面变更并自动生成新版本的元素坐标索引时，该新版本 MUST 以 `pending` 状态落库，
   MUST NOT 在 approved 之前被用于直连定位；`pending` 期间系统 MUST 回退到视觉定位路径。
   版本的审批入口 MUST 是显式的人工动作，MUST NOT 由运行时的连续成功次数自动转正。

3. 【工程与安全约束】补充一条可观测性要求：任何一次索引直连定位 MUST 在审计记录中留下
   画面 ID、版本 ID、元素 ID、模板校验得分、以及被跳过的模型调用类型，使"省了哪几次模型调用"
   可被离线核对。

不要修改原则 I、II、IV、VI 的正文。修订后请按模板输出 Sync Impact Report，并检查
.specify/templates/ 下四个模板是否需要同步（预期不需要，但要逐个确认并在报告里写明结论）。
```

### 门禁

- [ ] `constitution.md` 版本号从 1.2.0 → 1.3.0（MINOR）
- [ ] Sync Impact Report 里逐个列出四个模板的检查结论
- [ ] 原则 III 的新层级**四个准入条件一个不少**（尤其 (c) 模板校验和 (d) 禁止放宽阈值）

---

## 三、Feature 025：元素身份主键修复（第 0 期）

### 这一步在解决什么

实测事实（写进提示词，避免模型臆造）：

- `memory/service.py` 的 `normalize_target_label()` 只做 `strip().lower()`，直接把 **planner 生成的自然语言** 当主键。
- 数据库里真实存着 `'小計'`、`'金券'`、`'預/現計'`、`'確定'`，也存着 `'标题以 scanner 开头的窗口缩略图内部的浅色预览区域，位于标题文字下方约30像素处'`。
- 后果：4 次真实运行的 `memory_hits.element_memory` **全部为 0**。feature 015 建的表，一次没命中过。

这是整条链路的**地基**——026 的索引查询同样要用元素身份做键，主键不修好，026 建的库照样查不中。

### 3.1 /speckit-specify

```
/speckit-specify 元素记忆的身份主键从"自然语言描述"改为结构化元素身份，使 feature 015 建立的元素记忆真正可命中。

## 背景与实测证据

feature 015（page-element-memory）已经建好了 page_memories / element_memories 两张表和完整的
写入-查询链路，但在 4 次真实运行（run 7392616a / 867660a6 / e261f92c 及另一次）中，
report 的 memory_hits.element_memory **全部为 0**——即这套记忆从上线至今一次都没命中过。

根因已定位在 vnc_agent/src/vnc_agent/memory/service.py：

    def normalize_target_label(label: str) -> str:
        return (label or "").strip().lower()

以及 _lookup() 中的 `element = await self.repo.find_element(page.page_id, label)`。

也就是说，**Planner 每轮现场生成的自然语言目标描述被直接当成了元素的主键**。
数据库 element_memories.target_label 的真实取值同时包含两类：
- 短标签类：'小計'、'金券'、'預/現計'、'確定'
- 长描述类：'标题以 scanner 开头的窗口缩略图内部的浅色预览区域，位于标题文字下方约30像素处'

自然语言描述是**每轮重新生成、措辞不稳定**的，用它做精确匹配主键，命中率注定趋近于 0。
同一个按钮这次叫"小計"，下次可能叫"屏幕右下角的小計按钮"，两者 strip().lower() 之后不相等。

## 本 feature 的范围

引入一个稳定的**元素身份（element identity）**概念作为记忆的主键，并保证：
1. 同一个物理控件在不同轮次、不同措辞的 Planner 描述下，解析到同一个身份；
2. 不同的物理控件不会被误并到同一个身份（宁可不命中，不可错命中）；
3. 自然语言描述降级为身份解析的**输入线索之一**，不再是主键本身；
4. 存量 element_memories 数据有明确的迁移或作废策略，不能出现新旧混用导致的错命中。

身份的构成要素（具体方案交给 plan 阶段研究，spec 只约束性质）至少要能承载：
可归一化的可见文本、控件在画面中的几何位置、以及所属画面身份。身份 MUST NOT 依赖
Planner 的措辞，MUST NOT 依赖任何被测应用专有的字段名或业务词汇。

## 明确不在范围内

- 不建立跨画面的元素多对多索引（那是后续 feature 026）
- 不引入画面版本管理（feature 026）
- 不改变 Planner / Grounder 的调用协议本身
- 不新增任何模型调用

## 必须可度量的成功标准

- 在同一批回归用例上，element_memory 命中次数从 0 变为大于 0，且给出具体的命中率数字
- 误命中（命中了记忆但点击后验证失败）次数必须可被单独统计，且要设定上限
- 命中路径的单次开销要有实测数字（预期在毫秒级）
- 关闭开关后行为与现状逐字节一致（回归安全）

## 约束

遵守 Constitution VI：身份的定义与解析逻辑属于核心代码，MUST NOT 包含 POS / 收银 /
商品 等业务词汇；被测应用相关的一切只能出现在测试用例 YAML 与 fixture 中。
```

### 3.2 /speckit-clarify

```
/speckit-clarify 重点澄清以下方向，优先问那些"答案不同会导致设计完全不同"的问题：
(1) 元素身份的构成要素与相等判定——文本归一化到什么程度（全半角、日文假名、空白、大小写）；
    几何位置用绝对坐标还是容器相对坐标；位置参与相等判定时的容差如何定义。
(2) 一个身份在同一画面上出现多个候选（例如表格里多行同名按钮）时的消歧规则。
(3) 存量 element_memories 数据的处理：整表作废重建、惰性迁移、还是双写并行一段时间。
(4) 命中后是否仍然强制走元素模板校验，还是允许在高置信下跳过。
(5) 误命中的判定口径与可接受上限。
```

### 3.3 /speckit-plan

```
/speckit-plan 规划时请遵守以下约束：

- 复用而非新建：memory/fingerprint.py（画面指纹）、memory/retrieval.py（match_element_template）
  已经存在且经实测有效，本 feature MUST 复用它们，MUST NOT 另起一套。
- 改动集中在 memory/service.py 与 memory/repository.py 及其数据模型，尽量不扩散到
  runtime/agent_runtime.py 的主循环。若必须改主循环，在 plan 里单列一节说明改动点与回滚方式。
- 数据库变更必须给出可回滚的迁移路径，并说明存量 8 行 element_memories / 5 行 page_memories
  的处理结论。
- research.md 里必须包含：日文 UI 文本归一化的具体规则表（含全半角、濁点、長音符号的处理），
  以及至少一组来自 artifacts/runs/ 真实 OCR 输出的正反例验证。
- Constitution Check 一节要逐条对照 I / III / IV / V / VI，特别说明本 feature 如何满足
  原则 III 新增层级的准入条件 (c)（元素级模板校验）。
- quickstart.md 要给出一条离线可复现的验证命令：用既有 artifacts/runs/ 下的截图 fixture
  跑通"写入身份 → 换一种措辞查询 → 命中"的完整链路，不依赖真实 VNC 环境。
```

### 3.4 /speckit-tasks

```
/speckit-tasks 生成任务时的约束：

- 第一批任务必须是"度量基线"：在改任何代码之前，先写一个离线脚本统计当前
  element_memory 的命中率（预期 0）并存档，作为后续对比的基准。没有基线就没有验收。
- 每个 User Story 的任务组必须能独立验证，且都要有一条对应的离线回归测试任务。
- 数据迁移任务与代码任务分开，迁移任务要包含"迁移前备份 data/vnc_agent.db"这一步。
- 标记出可并行 [P] 的任务，但数据模型变更与依赖它的服务层改动 MUST NOT 并行。
- 任务总数控制在 40 条以内；超过就说明拆分粒度太细，合并同一文件内的连续改动。
```

### 3.5 /speckit-checklist

```
/speckit-checklist 生成一份"记忆命中正确性"专项检查清单，覆盖：
身份解析的边界情况（空文本、纯符号、超长描述、日文全半角混排）、
同画面多候选消歧、跨画面同名元素、
存量数据迁移的正确性与可回滚性、
误命中的检测与上报、
开关关闭时的行为一致性。
每条要写成可判定的断言，不要写成"应该考虑 XX"这种无法验收的句子。
```

### 3.6 /speckit-analyze → /speckit-implement

```
/speckit-analyze 重点检查：spec 里承诺的可度量成功标准是否在 tasks.md 里都有对应的度量任务；
Constitution Check 的结论是否与 tasks 的实际内容一致；有没有任务在做 spec 明确排除的范围
（跨画面索引、画面版本管理）。
```

```
/speckit-implement 严格按 tasks.md 顺序执行。每完成一个 User Story 的任务组就停下来，
运行该组对应的离线回归测试并报告结果，测试不通过不要继续下一组。
不要顺手重构无关代码。不要修改 config/agent.yaml 中与本 feature 无关的阈值。
```

### 门禁：这一期做完必须回答的问题

> **命中率上去了吗？** 如果修完主键，element_memory 命中率仍然接近 0，
> **不要进入 026**。说明根因不止 prose key（可能是画面指纹匹配层就没通过，
> 或者 action_policy 在第 3 步 ocr_template 就已经解决了目标、根本没走到记忆查询）。
> 先把新的根因查清楚。

---

## 四、SPIKE-1：定量摸底（不走 speckit）

调研不产出生产代码，走 speckit 全套是浪费。用普通对话提示词即可，产出一份 Markdown 摸底报告。

### 提示词

```
做一次只读的定量摸底，不要修改任何代码和配置，所有中间产物写到 scratchpad。
产出一份 Markdown 报告，放在 ai-visual-testing-research/ 根目录，命名为
摸底报告-元素静态动态占比.md。

需要用实测数据回答五个问题：

Q1. /mnt/d/POJ/NodeMaster 的 WinForms 部分（574 个元素）中，有多少控件的位置尺寸是
    硬编码在 *.Designer.cs 里的，有多少是运行时从配置表/主数据动态生成的？
    给出文件级别的证据清单，不要只给结论。

Q2. 在 artifacts/runs/ 已有的 608 张真实截图中，按画面聚类后，每个画面上的元素分为
    "每次运行位置完全一致"（static）、"位置抖动 1~5px"（jitter）、
    "内容或位置随数据变化"（dynamic）三类，各占多少比例？
    这个比例直接决定 IoU 阈值该取多少、索引覆盖率上限是多少。

Q3. 布局是否受 NodeMaster/Database 下的配置表驱动？如果是，哪些画面受影响、
    影响面有多大？这一条决定"代码侧自动失效检测"这一层的价值。

Q4. feature 016 record-replay 目前只有 1 条脚本、6 个步骤，为什么没有被更多使用？
    是能力不足、还是接入成本高、还是没人知道？查代码和运行记录给结论。

Q5. 测试环境里是否同时存在新旧两个版本的被测应用？如果存在，画面版本管理必须支持
    "同一画面同时有多个 approved 版本"，这会显著改变 026 的数据模型。

约束：NodeMaster 的 .git 是空目录，不能用 git 做差异分析，只能做文件内容哈希。
所有统计要给出样本量和方法，不要给没有样本量的百分比。
```

### 门禁

- [ ] Q2 的 dynamic 占比 —— 如果 > 40%，索引的收益面大幅缩水，需要重新评估 026 的投产比
- [ ] Q3 若"布局主要来自配置表" —— 026 的 L2 层（代码侧自动失效）价值大跌，手动入口权重要上调
- [ ] Q5 若"新旧版本共存" —— 026 的数据模型必须从一开始就支持同画面多 approved 版本

---

## 五、Feature 026：坐标索引 + 版本管理 + Grounder 旁路（第 2 期）

这是本功能的主体。提示词要足够长——**把实测数字全部写进去**，否则模型会自行脑补出"从代码解析坐标"这类做不到的方案。

### 5.1 /speckit-specify

```
/speckit-specify 建立画面元素坐标索引与画面版本管理，让已确认画面上的元素点击不再依赖视觉模型定位。

## 需求来源

见 ai-visual-testing-research/需求分析报告-画面元素坐标索引.md。本 spec 是该报告
第 2 期的落地。以下实测结论是**设计前提，不得推翻，也不要重新论证**：

### 前提 1：坐标不可能来自代码

已有的静态分析产物 /mnt/d/POJ/NodeMaster/ui-analysis-output/ui-analysis-bundle-v1/
包含 189 个画面、5788 个元素，覆盖 wpf / winforms / razor / html 四种框架。
实测：**5788 个元素中有 normalized_bounds 的是 0 个**，全部元素的 confidence 都是
`statically_inferred`。这不是分析器没做完，而是架构性限制——WPF 的 Grid/StackPanel
布局、Razor 的 CSS 流式布局，其最终像素位置只有在运行时才确定。

因此本 feature 的分工是：**代码侧提供元素身份与画面归属（189/189 画面有 source_path，
5788/5788 元素有 file:line 级 source_evidence），截图侧提供坐标**。任何"从源码解析出
坐标"的方案都不要写进设计。

### 前提 2：元素归并不能用"位置尺寸完全相同"

实测跨画面身份判定：取 12 个最大画面聚类，103 个文本出现在多个画面上，
**bbox 完全一致的是 0 个**。举例：
  チャージ            [942,613,1007,646] / [942,611,1008,642] / [942,610,1008,643]
  ScannerSimulator    [15,9,110,23]      / [14,7,110,25]      / [27,39,126,61]
  NonPLU              [164,223,209,240]  / [164,223,209,239]  / [256,307,304,326]
反向验证：跨画面 bbox 完全相同的有 115 组，其中 30 组**文本不同**——包括位于
(860,4,1020,24) 的时钟，一处读作 '2026/07728 14:20'，另一处读作 '2026/0772315:55'。

结论：精确相等规则会让多对多表**永久为空**，同时**仍然允许误并**。
本 feature MUST 采用三条组合规则：语义一致（归一化文本 / 控件角色）+ IoU 容差（初值 0.8，
具体阈值由 SPIKE-1 的 jitter 分布确定）+ 容器相对坐标（在画面内的父容器坐标系下比较）。

### 前提 3：画面指纹检测不出元素级变更，因此必须有版本管理

实测画面指纹（memory/fingerprint.py，pHash 0.375 + OCR 关键词 0.375 + 8x8 布局网格 0.25）
的敏感度：
  完全相同的两帧                 1.0000  → high
  同一画面不同运行               1.0000  → high
  **抹掉一个按钮                 0.9695~0.9762 → 仍然判 high**
  **移动一个元素 20px            0.9941 → 仍然判 high**
  底部面板整体上移 20px          0.8762 → medium
  抹掉 4 个按钮                  0.8690 → medium
（配置阈值：high 0.88 / medium 0.72 / low 0.55）

也就是说：**UI 改掉一个按钮，系统会认为画面没变，然后自信地点到旧坐标上。**
这是本 feature 最大的风险，也是版本管理存在的唯一理由。

### 前提 4：元素级模板校验是有效的安全网

实测 memory/retrieval.py 的 match_element_template：
  原图命中          1.000
  跨运行命中        1.000（说明对正常运行抖动零误报）
  元素被删除        miss
  元素移动 20px     miss
  元素移动 120px    miss
指纹漏掉的三种情况，模板校验全部拦下，开销约 1~2ms。因此模板校验 MUST 是直连点击的
强制前置条件，MUST NOT 因为"索引里有坐标"就跳过。

### 前提 5：收益目标必须修正

实测 4 次运行的耗时分解（全部以失败告终）：
  run 7392616a  总 224s：planner 48.7s/5 次、capture 40.0s/29 次、verification 35.7s/6 次、
                        OCR 22.5s/14 次、grounder 8.2s/1 次
  run 867660a6  总 156s：grounder 58.4s/4 次、planner 55.4s/6 次、capture 19.9s/20 次
  run e261f92c  总 41s ：planner 11.5s/2 次、grounder 6.3s/1 次
Grounder 只占总耗时的 3.7%~37%。只旁路 Grounder 的预期改善仅 5%~20%。
本 feature 只做 Grounder 旁路（Planner / Verification 旁路是后续 feature），
因此**成功标准里的耗时目标要按这个量级设定，不要承诺"提速一倍"**。

## 本 feature 的范围

1. **离线建库**：从已有截图（artifacts/runs/ 下 608 张真实截图，以及后续新增运行）
   批量提取画面元素坐标，与代码侧 bundle 的元素身份对齐，建立
   "画面 → 元素" 与 "元素 → 画面" 的多对多索引。
2. **画面版本管理**：同一画面的索引按版本存储。版本状态至少包含 pending / approved /
   deprecated。只有 approved 版本可用于直连定位（Constitution V）。
3. **三层变更感知**：
   - L1 人工入口：显式告诉系统"某画面改了"，触发该画面重新分析并建立新版本
   - L2 代码侧自动失效：NodeMaster 的 .git 是空目录（实测 git rev-parse 失败），
     不能用 git diff；但 manifest 已有 tree 内容哈希、189/189 画面有 source_path，
     所以用 **per-file 内容哈希**做自动失效，命中变更的画面版本自动转 pending
   - L3 运行时强制模板校验：见前提 4，直连点击前必须过
4. **Grounder 旁路**：命中 approved 版本 + 模板校验通过时，直接产出坐标，跳过 Grounder
   调用；审计记录必须写明画面 ID、版本 ID、元素 ID、模板得分、被跳过的模型调用类型。

## 明确不在范围内

- Planner 旁路、Verification 旁路（后续 feature 027）
- 自动审批：pending → approved MUST 是人工动作，MUST NOT 由连续成功次数自动转正
- 修改 Grounder / Planner 的模型或提示词
- 在线实时建库（本期只做离线批量建库 + 运行时查询）

## 成功标准（都要可度量）

- 在回归用例集上，Grounder 调用次数下降的比例（给绝对值和百分比）
- 索引直连点击的准确率，以及"直连点击后独立验证失败"的次数上限
- 模板校验对合成变更（删除元素 / 移动 20px / 移动 120px）的拦截率必须 100%
- 索引覆盖率：多少比例的点击目标能在索引中找到 approved 记录
- 端到端耗时变化（按前提 5，预期改善 5%~20%，不要承诺更多）
- 关闭开关后行为与现状一致

## 约束

- Constitution III：直连定位插在 Win+R 之后、OCR 文本定位之前，四条准入条件全部满足
- Constitution IV：直连点击**不豁免**操作后的独立验证闭环
- Constitution V：新版本以 pending 落库，approved 前不得用于直连
- Constitution VI：核心代码不得出现被测应用名、画面名、控件词汇；
  bundle 路径、画面注册表必须走配置或插件接口；
  本能力 MUST 用两个互不相关的 GUI 场景验证（不能只用 POS 一个应用证明它通用）
```

### 5.2 /speckit-clarify（这一期建议跑两轮）

**第一轮 —— 数据模型与身份**

```
/speckit-clarify 第一轮只澄清数据模型层面的问题，不要问实现细节：
(1) 画面版本的粒度——整个画面一个版本，还是画面内的区域可以独立版本化？
(2) 同一画面是否允许同时存在多个 approved 版本（对应测试环境新旧版本共存的可能性）？
(3) 元素在多对多关系中的身份是全局唯一还是画面内唯一？跨画面"同一个元素"的判定
    在数据模型上如何表达？
(4) 容器相对坐标的"容器"如何定义与识别——来自代码侧 bundle 的父子关系，
    还是从截图上推断？两者冲突时以谁为准？
(5) 索引与 feature 015 的 element_memories 是同一张表、两张表、还是一张表两种来源？
```

**第二轮 —— 版本生命周期与失效**

```
/speckit-clarify 第二轮只澄清版本生命周期：
(1) L1 人工入口的具体形态——CLI 子命令、配置文件、还是 API？触发后是立即重新分析
    还是标记为待分析？
(2) L2 内容哈希失效的粒度——某个源文件变更时，只让直接引用它的画面转 pending，
    还是连带它引用的组件所在的画面一起转？
(3) 一个画面转入 pending 后，运行时的行为是什么——直接降级到视觉定位，
    还是允许用旧版本但降低信任度？
(4) 重新分析新版本需要多少张截图才算样本充足？样本不足时如何处理？
(5) deprecated 版本保留多久、是否参与历史审计追溯？
```

### 5.3 /speckit-plan

```
/speckit-plan 规划约束：

必须复用的既有资产（MUST NOT 重造）：
- memory/fingerprint.py：画面指纹与匹配分级
- memory/retrieval.py：match_element_template（元素模板校验，实测零误报）
- ui_index/：bundle 读取、校验、runtime_adapter；注意 runtime_adapter._element_to_candidate
  目前在 normalized_bounds 为 None 时返回 None，即它今天永远吐不出坐标——
  本 feature 要接管的正是这个缺口，但接管方式是**从截图侧补齐坐标**，不是改静态分析器
- planning/action_policy.py：ActionPolicy.resolve() 的分层 fallthrough 结构，
  新的直连层要插进这个既有结构，MUST NOT 另起一条并行路径
- memory/service.py 的元素身份（feature 025 的产出）

research.md 必须包含：
- 三条归并规则（语义一致 + IoU 容差 + 容器相对坐标）的具体判定算法与伪码，
  以及用 SPIKE-1 的 jitter 分布反推出的 IoU 阈值取值依据
- L2 内容哈希方案的具体设计：哪些文件参与哈希、哈希粒度、如何从 source_path
  反查受影响画面、误报与漏报的权衡
- 离线建库的处理流程与吞吐估算（608 张截图的处理耗时）
- 至少一组对照实验设计：证明"直连坐标"与"Grounder 定位"在同一批目标上的准确率差异

data-model.md 必须给出：
- 画面版本表、元素索引表、元素-画面关联表的完整字段与约束
- 版本状态机（pending / approved / deprecated）的合法转移与触发者
- 与既有 page_memories / element_memories 的关系与迁移路径

contracts/ 必须给出：
- L1 人工入口的接口契约
- 直连定位的输入输出契约（含拒绝时的原因码枚举——参考 feature 024 spec 里
  not_declared / declared_off / roi_not_subwindow 那种粒度的原因码设计）
- 审计记录的字段契约

Constitution Check 逐条对照 I / III / IV / V / VI。原则 VI 的"两个互不相关 GUI 场景"
要求必须在 plan 里落到具体的第二个验证场景上，不能写"后续补充"。

plan 里要明确本 feature 的**开关粒度**：全局开关、按画面开关、按用例开关，
以及三者的优先级。回滚必须是改配置就能完成的，不需要回滚代码。
```

### 5.4 /speckit-tasks

```
/speckit-tasks 约束：

- 按 User Story 分组，每组独立可验证、可独立回滚。
- 第一批任务是"离线建库工具 + 建库结果的人工抽检报告"，在任何运行时改动之前完成。
  没有一份人工抽检过的索引，运行时改动就是在拿错数据做实验。
- 运行时改动（直连层接入 action_policy）必须排在建库、版本管理、模板校验之后，
  且必须默认关闭，通过配置显式开启。
- 必须有一组"负向测试"任务：合成变更（删除元素 / 移动 20px / 移动 120px）
  必须被模板校验 100% 拦截，这是本 feature 的安全底线，不通过不允许合入。
- 必须有一组"第二场景验证"任务，满足 Constitution VI。
- 任务总数如果超过 80 条，就把 L1/L2/L3 中的一层拆成独立 feature，
  在 tasks.md 顶部写明拆分建议，不要硬塞。
- 标注 [P] 并行任务，但版本状态机与依赖它的运行时查询 MUST NOT 并行。
```

### 5.5 /speckit-checklist（这一期建议生成三份）

```
/speckit-checklist 生成"坐标索引正确性"清单：归并规则的正反例、IoU 边界值、
容器相对坐标的换算、跨画面同名元素、动态内容元素的排除、索引为空/多值时的行为。
```

```
/speckit-checklist 生成"画面版本安全性"清单：版本状态机的非法转移、
pending 期间的运行时行为、L1/L2 同时触发时的冲突、
新旧版本共存时的选择规则、审批人工入口的防误操作、
以及"画面变了但系统没发现"这一失效模式的每一层防线是否都有对应断言。
```

```
/speckit-checklist 生成"回归安全"清单：开关关闭后与现状的一致性、
索引未命中时的降级路径、直连点击失败后的恢复流程、
审计记录的完整性、以及本 feature 是否引入了任何新的最终态或 FailureType（预期为否）。
```

### 5.6 /speckit-analyze

```
/speckit-analyze 重点检查：
(1) spec 的五条实测前提是否在 plan 和 tasks 里都被尊重——特别是有没有任务在试图
    "从源码解析坐标"（前提 1 已判定不可行）或使用"位置尺寸精确相等"归并（前提 2 已判定失效）。
(2) 成功标准里的耗时目标是否与前提 5 的量级一致，有没有出现过度承诺。
(3) Constitution V 的 pending/approved 约束是否在 tasks 里真的有对应实现任务，
    还是只写在 spec 里没落地。
(4) 三份 checklist 的每一条是否都能追溯到至少一个任务。
```

### 5.7 /speckit-implement

```
/speckit-implement 按 tasks.md 顺序执行，但遵守以下纪律：

- 完成"离线建库"任务组后**停下来**，输出建库结果的统计摘要（覆盖了多少画面、
  多少元素、平均每画面多少元素、有多少元素因归并冲突被丢弃），等人工确认后再继续。
- 完成"负向测试"任务组后**停下来**，报告三种合成变更的拦截率，
  不是 100% 就不要继续往下做运行时接入。
- 运行时接入的所有改动默认关闭，实施完成后不要顺手把配置开关打开。
- 不要修改 config/agent.yaml 中与本 feature 无关的既有阈值
  （page_match_high 0.88 / medium 0.72 / low 0.55 / template_match_threshold 0.85
   都是实测有效的，除非 tasks 明确要求，否则不动）。
```

### 5.8 /speckit-converge

```
/speckit-converge 对照 spec 的四项范围（离线建库 / 版本管理 / 三层变更感知 / Grounder 旁路）
和全部成功标准，评估当前代码库的实际完成度，把未完成的部分作为新任务追加到 tasks.md。
特别核对：审计记录字段是否齐全、第二场景验证是否真的做了、
三份 checklist 里未勾选的条目是否都有对应的补漏任务。
```

---

## 六、Feature 027：Planner / Verification 旁路（第 3 期）

只在 026 验收通过、且索引覆盖率达标后启动。提示词骨架如下（细节等 026 的实测数据出来后再补）：

```
/speckit-specify 在画面版本已确定的前提下，用确定性状态机替代部分 Planner 调用，
用索引断言替代部分 visual_question 视觉验证。

## 为什么做这一期

实测耗时分解（见需求分析报告第二章）显示 Planner 与 Verification 才是耗时主体：
  run 7392616a：planner 48.7s/5 次 + verification 35.7s/6 次 = 84.4s，占总 224s 的 38%
  run 867660a6：planner 55.4s/6 次，占总 156s 的 36%
feature 026 只旁路了 Grounder（占比 3.7%~37%）。要把端到端耗时压到 60 秒以内，
必须处理 Planner 和 Verification。

## 范围

1. **Planner 旁路**：当前帧匹配到 approved 画面版本、且当前步骤在该画面上的后续动作
   已被历史成功轨迹确定时，用确定性状态机产出下一步动作，跳过 Planner 模型调用。
2. **Verification 旁路**：当预期的操作后画面可由索引断言唯一确定时
   （例如"点击后应跳转到画面 X 的 approved 版本 V"），用画面指纹 + 索引断言完成验证，
   跳过 visual_question 模型调用。

## 红线（Constitution I / IV）

- Planner 旁路 MUST NOT 让模型自主决定跳过——跳过与否由代码状态机判定，且判定依据必须
  是已审批的确定性数据，不是模型的置信度自述。
- Verification 旁路 MUST NOT 削弱"验证基于操作后重新采集的独立证据"这一原则：
  索引断言本身就是对新截图的独立判定，但 `uncertain` 时 MUST 升级到模型验证，
  MUST NOT 直接判过。
- 任何一次跳过 MUST 留下可离线核对的审计记录。
```

后续步骤（clarify / plan / tasks / checklist / analyze / implement）与 026 同构，此处不重复。

---

## 七、通用纪律：这套流程里最容易踩的坑

### 7.1 提示词要写实测数字，不要写形容词

对比：

- ❌ "画面指纹对小改动不敏感，需要版本管理"
- ✅ "抹掉一个按钮相似度 0.9695~0.9762，阈值 high 是 0.88，所以仍然判 high"

第一种写法，模型会自己发明一套敏感度假设；第二种写法，模型只能在给定事实上做设计。本文档所有 specify 提示词都遵循这个原则，改写时不要把数字删掉换成概括。

### 7.2 明确写"不在范围内"

speckit 的 spec 阶段最常见的失控是范围膨胀——你要一个索引，它给你连带做了自动审批、在线学习、跨应用泛化。每份 specify 提示词都要有 "## 明确不在范围内" 段落。

### 7.3 门禁 A（spec 人读）不能跳

`/speckit-specify` 生成的 spec.md 一定要人读一遍，重点删两类东西：

1. **模型臆造的需求**——你没说过、但它觉得"应该有"的功能
2. **不可验收的成功标准**——"提升准确率"、"改善用户体验"这类没有数字的句子

这一步花 20 分钟，能省掉后面 plan/tasks 两轮的返工。

### 7.4 Constitution Check 绿灯要看内容不看结论

`/speckit-plan` 会自己写一段 Constitution Check 并宣布通过。**它宣布通过不等于真的通过**。逐条读它给的理由，尤其是原则 V（受控自进化）和原则 VI（业务无关核心）——这两条最容易被一句"本 feature 不涉及"糊弄过去，而本功能其实两条都实打实涉及。

### 7.5 tasks.md 超过 80 条就该拆 feature

不是形式主义。`/speckit-implement` 在长任务列表上跑到后半段时，前面的设计决策已经滑出上下文，产出质量会掉。026 如果 tasks 超过 80 条，把 L2（代码侧自动失效）单独拆成 feature 027，把 Planner 旁路顺延到 028。

### 7.6 每期结束必须回答"要不要继续"

三个叫停点：

| 时点 | 判据 | 不通过怎么办 |
|---|---|---|
| 025 完成后 | element_memory 命中率是否 > 0 | 停。重新定位根因，可能在指纹匹配层或 action_policy 的 ocr_template 层 |
| SPIKE-1 完成后 | dynamic 元素占比是否 < 40% | 停。索引收益面不足，考虑改做"只索引高频关键按钮"的窄范围方案 |
| 026 完成后 | 索引覆盖率与端到端耗时改善是否达标 | 停。027 的收益建立在 026 的覆盖率上，覆盖率不够则 Planner 旁路也无从谈起 |

---

## 八、一页速查

```
# 第 0 步（必做，最先）
/speckit-constitution   <见 §2 提示词>            → constitution 1.2.0 → 1.3.0

# 第 025 号 feature：修主键（3~5 人日）
/speckit-specify        <见 §3.1>                 → specs/025-*/spec.md    【人读】
/speckit-clarify        <见 §3.2>                 → spec.md 更新
/speckit-plan           <见 §3.3>                 → plan.md + research + data-model + contracts + quickstart
/speckit-tasks          <见 §3.4>                 → tasks.md（≤40 条）
/speckit-checklist      <见 §3.5>                 → checklists/
/speckit-analyze        <见 §3.6>                 → 一致性报告【CRITICAL 清零】
/speckit-implement      <见 §3.6>                 → 代码
                        ▲ 叫停点：命中率仍为 0 则不要继续

# SPIKE-1：摸底（2~3 人日，可与 025 并行，不走 speckit）
<见 §4 提示词>                                     → 摸底报告-元素静态动态占比.md
                        ▲ 叫停点：dynamic 占比 > 40% 则重估

# 第 026 号 feature：索引 + 版本 + Grounder 旁路（2~3 人周）
/speckit-specify        <见 §5.1，最长的一份>
/speckit-clarify        <见 §5.2，跑两轮>
/speckit-plan           <见 §5.3>
/speckit-tasks          <见 §5.4>（>80 条则拆 feature）
/speckit-checklist      <见 §5.5，生成三份>
/speckit-analyze        <见 §5.6>
/speckit-implement      <见 §5.7，两处强制停顿>
/speckit-converge       <见 §5.8>
                        ▲ 叫停点：覆盖率与耗时改善不达标则不做 027

# 第 027 号 feature：Planner / Verification 旁路（3~4 人周）
<见 §6 骨架，细节待 026 数据>
```
